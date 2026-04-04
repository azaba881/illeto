"""
Import vectoriel générique vers Departement, Commune, Zone ou HydroZone.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from django.contrib.gis.gdal import CoordTransform, DataSource, SpatialReference
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.db import transaction

from apps.geo_data.importers.geometry_utils import geometry_dict_to_multipolygon
from apps.geo_data.models import Commune, Departement, HydroZone, Zone
from apps.geo_data.text_normalize import normalize_boundary_label

logger = logging.getLogger(__name__)

MODEL_BY_NAME = {
    "departement": Departement,
    "commune": Commune,
    "zone": Zone,
    "hydrozone": HydroZone,
}


def _to_multipolygon_geos(g: GEOSGeometry) -> MultiPolygon | None:
    if g.geom_type == "Polygon":
        return MultiPolygon(g)
    if g.geom_type == "MultiPolygon":
        return g
    return None


def _reproject_to_wgs84(geos_geom: GEOSGeometry, layer) -> None:
    dest = SpatialReference(4326)
    src = layer.srs
    if src and src.srid not in (None, 0):
        geos_geom.srid = src.srid
        if src.srid != 4326:
            geos_geom.transform(CoordTransform(src, dest))
        return
    if geos_geom.srid in (None, 0, -1):
        geos_geom.srid = 4326
        return
    if geos_geom.srid != 4326:
        geos_geom.transform(CoordTransform(SpatialReference(geos_geom.srid), dest))


def _feat_val(feat, field_name: str) -> str:
    if not field_name:
        return ""
    try:
        v = feat[field_name]
    except Exception:
        return ""
    if v is None:
        return ""
    return str(v).strip()


def _iter_geojson_features(path: Path, encoding: str):
    data = json.loads(path.read_text(encoding=encoding))
    if data.get("type") == "FeatureCollection":
        for f in data.get("features") or []:
            if f.get("type") == "Feature":
                yield f
    elif data.get("type") == "Feature":
        yield data


def run_universal_import(
    *,
    paths: list[Path],
    model_name: str,
    name_field: str,
    code_field: str,
    departement_pk: int | None,
    commune_pk: int | None,
    source_label: str,
    dry_run: bool,
    encoding: str,
    layer_index: int,
    stdout: Any,
    style: Any,
) -> tuple[int, list[str]]:
    key = model_name.strip().lower()
    if key not in MODEL_BY_NAME:
        raise ValueError(
            "Modèle inconnu : %r (attendu : Departement, Commune, Zone, HydroZone)."
            % model_name
        )
    model = MODEL_BY_NAME[key]
    errors: list[str] = []
    total_ok = 0

    dept_obj = None
    commune_obj = None
    if model is Commune:
        if not departement_pk:
            raise ValueError("Import Commune : fournir departement_pk.")
        dept_obj = Departement.objects.filter(pk=departement_pk).first()
        if not dept_obj:
            raise ValueError("Département pk=%s introuvable." % departement_pk)
    elif model is Zone:
        if not commune_pk:
            raise ValueError("Import Zone : fournir commune_pk (commune parente).")
        commune_obj = Commune.objects.filter(pk=commune_pk).first()
        if not commune_obj:
            raise ValueError("Commune pk=%s introuvable." % commune_pk)

    for path in paths:
        ext = path.suffix.lower()
        if ext in (".geojson", ".json"):
            total_ok += _import_geojson_file(
                path,
                model,
                name_field,
                code_field,
                dept_obj,
                commune_obj,
                source_label,
                dry_run,
                encoding,
                stdout,
                style,
                errors,
            )
            continue
        if ext in (".shp", ".kml"):
            total_ok += _import_ogr_file(
                path,
                model,
                name_field,
                code_field,
                dept_obj,
                commune_obj,
                source_label,
                dry_run,
                encoding,
                layer_index,
                stdout,
                style,
                errors,
            )
            continue
        errors.append("Extension non prise en charge : %s (%s)" % (ext, path.name))

    return total_ok, errors


def _import_geojson_file(
    path,
    model,
    name_field: str,
    code_field: str,
    dept_obj,
    commune_obj,
    source_label: str,
    dry_run: bool,
    encoding: str,
    stdout,
    style,
    errors: list[str],
) -> int:
    n = 0
    try:
        for feature in _iter_geojson_features(path, encoding):
            props = feature.get("properties") or {}
            name = normalize_boundary_label(str(props.get(name_field) or "").strip())
            if not name:
                errors.append("%s : feature sans champ %r" % (path.name, name_field))
                continue
            name = name[:255]
            code = (
                str(props.get(code_field) or "").strip()[:64]
                if code_field
                else ""
            )
            mp = geometry_dict_to_multipolygon(feature.get("geometry"))
            if mp is None:
                errors.append("%s : géométrie invalide pour %r" % (path.name, name))
                continue
            if dry_run:
                if stdout is not None:
                    stdout.write("[dry-run] %s %r" % (model.__name__, name))
                n += 1
                continue
            _write_instance(
                model, name, code, mp, dept_obj, commune_obj, source_label, errors
            )
            n += 1
    except json.JSONDecodeError as e:
        errors.append("%s : JSON invalide (%s)" % (path.name, e))
    return n


def _write_instance(
    model, name, code, mp, dept_obj, commune_obj, source_label, errors
):
    try:
        with transaction.atomic():
            if model is Departement:
                if code:
                    Departement.objects.update_or_create(
                        code_officiel=code,
                        defaults={"name": name, "geom": mp},
                    )
                else:
                    o = Departement.objects.filter(name__iexact=name).first()
                    if o:
                        o.geom = mp
                        o.save()
                    else:
                        Departement.objects.create(
                            name=name, code_officiel=None, geom=mp
                        )
            elif model is Commune:
                assert dept_obj is not None
                if code:
                    Commune.objects.update_or_create(
                        code_officiel=code,
                        defaults={
                            "name": name,
                            "geom": mp,
                            "departement": dept_obj,
                            "is_placeholder": False,
                        },
                    )
                else:
                    o = Commune.objects.filter(
                        departement=dept_obj, name__iexact=name
                    ).first()
                    if o:
                        o.geom = mp
                        o.is_placeholder = False
                        o.save()
                    else:
                        Commune.objects.create(
                            name=name,
                            code_officiel=None,
                            geom=mp,
                            departement=dept_obj,
                            is_placeholder=False,
                        )
            elif model is Zone:
                assert commune_obj is not None
                cid = code[:128] if code else ""
                if cid:
                    Zone.objects.update_or_create(
                        osm_id=cid,
                        defaults={
                            "commune": commune_obj,
                            "name": name,
                            "geom": mp,
                        },
                    )
                else:
                    Zone.objects.update_or_create(
                        commune=commune_obj,
                        name=name,
                        defaults={"geom": mp},
                    )
            elif model is HydroZone:
                HydroZone.objects.create(
                    name=name, geom=mp, source=source_label[:64]
                )
    except Exception as e:
        errors.append("%s : %s" % (name, e))
        logger.exception("Import %s", name)


def _import_ogr_file(
    path,
    model,
    name_field: str,
    code_field: str,
    dept_obj,
    commune_obj,
    source_label: str,
    dry_run: bool,
    encoding: str,
    layer_index: int,
    stdout,
    style,
    errors: list[str],
) -> int:
    try:
        ds = DataSource(str(path), encoding=encoding)
    except Exception as e:
        errors.append("OGR %s : %s" % (path.name, e))
        return 0
    if layer_index < 0 or layer_index >= len(ds):
        errors.append("Index de couche invalide pour %s" % path.name)
        return 0
    layer = ds[layer_index]
    n = 0
    for feat in layer:
        name = normalize_boundary_label(_feat_val(feat, name_field))
        if not name:
            errors.append("%s FID %s : nom vide (%r)" % (path.name, feat.fid, name_field))
            continue
        name = name[:255]
        code = _feat_val(feat, code_field)[:64] if code_field else ""
        try:
            geos_geom = feat.geom.geos
        except Exception as e:
            errors.append("%s FID %s : pas de géom (%s)" % (path.name, feat.fid, e))
            continue
        try:
            _reproject_to_wgs84(geos_geom, layer)
        except Exception as e:
            errors.append("%s FID %s : reprojection (%s)" % (path.name, feat.fid, e))
            continue
        mp = _to_multipolygon_geos(geos_geom)
        if mp is None:
            errors.append(
                "%s FID %s : type %s (attendu polygone)"
                % (path.name, feat.fid, geos_geom.geom_type)
            )
            continue
        if dry_run:
            if stdout is not None:
                stdout.write("[dry-run] %s %r" % (model.__name__, name))
            n += 1
            continue
        _write_instance(
            model, name, code, mp, dept_obj, commune_obj, source_label, errors
        )
        n += 1
    return n
