"""
Import HDX / geoBoundaries : schéma OCHA (adm1/adm2) ou geoBoundaries (shapeName, shapeID).
Idempotence : code officiel prioritaire, sinon correspondance par nom (insensible à la casse).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.contrib.gis.geos import MultiPolygon
from django.db import transaction

from apps.geo_data.importers.geometry_utils import geometry_dict_to_multipolygon
from apps.geo_data.importers.spatial import commune_for_centroid
from apps.geo_data.models import Commune, Departement, Zone
from apps.geo_data.text_normalize import normalize_boundary_label

if TYPE_CHECKING:
    from django.core.management.base import OutputWrapper

logger = logging.getLogger(__name__)


def _norm_props(props: dict | None) -> dict[str, object]:
    if not props:
        return {}
    return {str(k).lower(): v for k, v in props.items()}


def _as_str(v: object | None) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _is_benin_ocha(props_norm: dict[str, object]) -> bool:
    adm0 = _as_str(
        props_norm.get("adm0_en")
        or props_norm.get("adm0_name")
        or props_norm.get("admin0name")
    )
    if not adm0:
        return False
    return adm0.lower() in ("benin", "bénin")


def geometry_to_multipolygon(geom_dict: dict | None) -> MultiPolygon | None:
    return geometry_dict_to_multipolygon(geom_dict)


def _geoboundaries_country_ok(
    props_norm: dict[str, object], country_hint: str
) -> bool:
    if not country_hint:
        return True
    hint = country_hint.strip().upper()
    iso = _as_str(props_norm.get("shapeiso") or props_norm.get("shape_iso")).upper()
    if iso and hint in ("BEN", "BJ"):
        return "BJ" in iso or "BEN" in iso
    if iso:
        return hint in iso or iso.startswith(hint)
    return True


def _iter_features(data: dict) -> list[dict]:
    if data.get("type") == "FeatureCollection":
        return [f for f in (data.get("features") or []) if f.get("type") == "Feature"]
    if data.get("type") == "Feature":
        return [data]
    return []


def run_hdx_import(
    *,
    path: Path,
    schema: str,
    level: str,
    dry_run: bool,
    bootstrap_departments: bool,
    update_geometry: bool,
    country_iso: str,
    stdout: OutputWrapper | None,
    style: Any | None,
) -> dict[str, int]:
    raw = path.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    features = _iter_features(data)

    stats = {
        "processed": 0,
        "skipped_country": 0,
        "skipped_geom": 0,
        "skipped_no_code": 0,
        "skipped_no_dept": 0,
        "created": 0,
        "updated": 0,
    }

    for feature in features:
        props_raw = feature.get("properties") or {}
        props = _norm_props(props_raw)
        mp = geometry_to_multipolygon(feature.get("geometry"))
        if mp is None:
            stats["skipped_geom"] += 1
            continue

        if schema == "ocha":
            if not _is_benin_ocha(props):
                stats["skipped_country"] += 1
                continue
            stats["processed"] += 1
            if level == "adm1":
                _ocha_adm1(props, mp, dry_run, update_geometry, stats, stdout, style)
            elif level == "adm2":
                _ocha_adm2(
                    props,
                    mp,
                    dry_run,
                    bootstrap_departments,
                    update_geometry,
                    stats,
                    stdout,
                    style,
                )
        elif schema == "geoboundaries":
            if not _geoboundaries_country_ok(props, country_iso):
                stats["skipped_country"] += 1
                continue
            stats["processed"] += 1
            if level == "adm2":
                _gb_adm2(props, mp, dry_run, update_geometry, stats, stdout, style)
            elif level == "adm3":
                _gb_adm3(props, mp, dry_run, update_geometry, stats, stdout, style)
            else:
                stats["skipped_no_code"] += 1

    return stats


def _write(
    stdout: OutputWrapper | None, style: Any | None, msg: str, kind: str = "success"
) -> None:
    if not stdout:
        return
    if style and kind == "warning":
        stdout.write(style.WARNING(msg))
    elif style and kind == "error":
        stdout.write(style.ERROR(msg))
    else:
        stdout.write(msg)


def _upsert_departement(
    name: str,
    pcode: str,
    mp: MultiPolygon,
    update_geometry: bool,
    stats: dict,
) -> None:
    if not name:
        stats["skipped_no_code"] += 1
        return

    with transaction.atomic():
        if pcode:
            _obj, created = Departement.objects.update_or_create(
                code_officiel=pcode[:64],
                defaults={"name": name[:255], "geom": mp},
            )
            stats["created" if created else "updated"] += 1
            return
        obj = Departement.objects.filter(name__iexact=name).first()
        if obj:
            obj.name = name[:255]
            if update_geometry:
                obj.geom = mp
            obj.save()
            stats["updated"] += 1
            return
        Departement.objects.create(
            name=name[:255],
            code_officiel=None,
            geom=mp,
        )
        stats["created"] += 1


def _ocha_adm1(
    props: dict,
    mp: MultiPolygon,
    dry_run: bool,
    update_geometry: bool,
    stats: dict,
    stdout: Any,
    style: Any,
) -> None:
    name = normalize_boundary_label(_as_str(props.get("adm1_name") or props.get("name")))
    pcode = _as_str(props.get("adm1_pcode") or props.get("pcode"))
    if dry_run:
        _write(stdout, style, f"[dry-run] ADM1 {name!r} pcode={pcode or '—'}")
        return
    _upsert_departement(name, pcode, mp, update_geometry, stats)


def _ocha_adm2(
    props: dict,
    mp: MultiPolygon,
    dry_run: bool,
    bootstrap_departments: bool,
    update_geometry: bool,
    stats: dict,
    stdout: Any,
    style: Any,
) -> None:
    name = normalize_boundary_label(_as_str(props.get("adm2_name") or props.get("name")))
    pcode = _as_str(props.get("adm2_pcode") or props.get("pcode"))
    adm1_name = normalize_boundary_label(_as_str(props.get("adm1_name")))
    adm1_pcode = _as_str(props.get("adm1_pcode"))

    if not name:
        stats["skipped_no_code"] += 1
        logger.warning("ADM2 sans nom")
        return

    dept = None
    if adm1_pcode:
        dept = Departement.objects.filter(code_officiel=adm1_pcode[:64]).first()
    if dept is None and adm1_name:
        dept = Departement.objects.filter(name__iexact=adm1_name).first()

    if dept is None and bootstrap_departments and adm1_name:
        if dry_run:
            _write(
                stdout,
                style,
                f"[dry-run] bootstrap département pour {adm1_name!r}",
                "warning",
            )
        else:
            with transaction.atomic():
                dept = Departement.objects.create(
                    name=adm1_name[:255],
                    code_officiel=adm1_pcode[:64] if adm1_pcode else None,
                    geom=mp,
                )
            _write(
                stdout,
                style,
                f"Département créé (bootstrap) : {dept.name}",
                "warning",
            )

    if dept is None:
        stats["skipped_no_dept"] += 1
        logger.warning("ADM2 %s : département introuvable", name)
        return

    if dry_run:
        _write(
            stdout,
            style,
            f"[dry-run] ADM2 {name!r} pcode={pcode or '—'} dept={dept.name}",
        )
        return

    with transaction.atomic():
        if pcode:
            _obj, created = Commune.objects.update_or_create(
                code_officiel=pcode[:64],
                defaults={
                    "name": name[:255],
                    "geom": mp,
                    "departement": dept,
                    "is_placeholder": False,
                },
            )
            stats["created" if created else "updated"] += 1
            return
        obj = Commune.objects.filter(departement=dept, name__iexact=name).first()
        if obj:
            if update_geometry:
                obj.geom = mp
            obj.is_placeholder = False
            obj.save()
            stats["updated"] += 1
            return
        Commune.objects.create(
            name=name[:255],
            code_officiel=None,
            geom=mp,
            departement=dept,
            is_placeholder=False,
        )
        stats["created"] += 1


def _gb_adm2(
    props: dict,
    mp: MultiPolygon,
    dry_run: bool,
    update_geometry: bool,
    stats: dict,
    stdout: Any,
    style: Any,
) -> None:
    name = normalize_boundary_label(_as_str(props.get("shapename") or props.get("shape_name")))
    sid = _as_str(props.get("shapeid") or props.get("shape_id"))
    parent = _as_str(props.get("shapegroup") or props.get("shape_group"))

    if not name:
        stats["skipped_no_code"] += 1
        return

    dept = None
    if parent:
        dept = Departement.objects.filter(
            name__iexact=normalize_boundary_label(parent)
        ).first()
    if dept is None:
        stats["skipped_no_dept"] += 1
        logger.warning("geoBoundaries ADM2 %s : département introuvable (%s)", name, parent)
        return

    if dry_run:
        _write(
            stdout,
            style,
            f"[dry-run] GB ADM2 {name!r} id={sid or '—'} dept={dept.name}",
        )
        return

    code = sid[:64] if sid else None
    with transaction.atomic():
        if code:
            _obj, created = Commune.objects.update_or_create(
                code_officiel=code,
                defaults={
                    "name": name[:255],
                    "geom": mp,
                    "departement": dept,
                    "is_placeholder": False,
                },
            )
            stats["created" if created else "updated"] += 1
            return
        obj = Commune.objects.filter(departement=dept, name__iexact=name).first()
        if obj:
            if update_geometry:
                obj.geom = mp
            obj.is_placeholder = False
            obj.save()
            stats["updated"] += 1
            return
        Commune.objects.create(
            name=name[:255],
            code_officiel=None,
            geom=mp,
            departement=dept,
            is_placeholder=False,
        )
        stats["created"] += 1


def _gb_adm3(
    props: dict,
    mp: MultiPolygon,
    dry_run: bool,
    update_geometry: bool,
    stats: dict,
    stdout: Any,
    style: Any,
) -> None:
    name = normalize_boundary_label(_as_str(props.get("shapename") or props.get("shape_name")))
    sid = _as_str(props.get("shapeid") or props.get("shape_id"))
    if not name:
        stats["skipped_no_code"] += 1
        return

    centroid = mp.centroid
    parent = commune_for_centroid(centroid)
    if parent is None:
        stats["skipped_no_dept"] += 1
        logger.warning("ADM3 %s : aucune commune ne couvre le centroïde", name)
        return

    ext_id = ("geoboundaries:%s" % sid)[:128] if sid else None

    if dry_run:
        _write(
            stdout,
            style,
            f"[dry-run] GB ADM3 Zone {name!r} → commune {parent.name!r}",
        )
        return

    with transaction.atomic():
        defaults = {"commune": parent, "name": name[:255], "geom": mp}
        if ext_id:
            obj, created = Zone.objects.update_or_create(
                osm_id=ext_id,
                defaults=defaults,
            )
        else:
            obj, created = Zone.objects.update_or_create(
                commune=parent,
                name=name,
                defaults={"geom": mp},
            )
        stats["created" if created else "updated"] += 1
