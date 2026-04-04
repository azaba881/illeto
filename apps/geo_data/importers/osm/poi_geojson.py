"""Import PointInteret depuis GeoJSON (points) — rattachement geom__covers."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, Point
from django.db import transaction

from apps.geo_data.importers.spatial import commune_and_quartier_for_point
from apps.geo_data.models import PointInteret
from apps.geo_data.text_normalize import normalize_boundary_label

logger = logging.getLogger(__name__)

_CATEGORY_VALUES = {c.value for c in PointInteret.Category}


def _iter_features(data: dict):
    if data.get("type") == "FeatureCollection":
        for f in data.get("features") or []:
            if f.get("type") == "Feature":
                yield f
    elif data.get("type") == "Feature":
        yield data


def _infer_category(props: dict | None) -> str:
    if not props:
        return PointInteret.Category.OTHER
    raw = props.get("category") or props.get("Category")
    if raw is not None and str(raw).strip():
        s = str(raw).strip().lower()
        if s in _CATEGORY_VALUES:
            return s
    amenity = (props.get("amenity") or "").strip().lower()
    if amenity in ("hospital", "clinic", "doctors", "pharmacy"):
        return PointInteret.Category.HEALTH
    shop = (props.get("shop") or "").strip().lower()
    if shop in ("marketplace", "supermarket", "convenience"):
        return PointInteret.Category.MARKET
    return PointInteret.Category.OTHER


def _feature_name(props: dict | None, name_field: str | None = None) -> str | None:
    if not props:
        return None
    keys: list[str] = []
    if name_field and str(name_field).strip():
        keys.append(str(name_field).strip())
    keys.extend(["name:fr", "name", "title"])
    seen: set[str] = set()
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        if key not in props:
            continue
        v = props.get(key)
        if v is None or str(v).strip() == "":
            continue
        return str(v).strip()[:255]
    return None


def _external_id(props: dict | None, feature: dict) -> str | None:
    if props:
        for key in ("external_id", "@id", "id", "osm_id"):
            v = props.get(key)
            if v is not None and str(v).strip():
                return str(v).strip()[:128]
    fid = feature.get("id")
    if fid is not None and str(fid).strip():
        return str(fid).strip()[:128]
    return None


def _coerce_single_point(g: GEOSGeometry) -> Point | None:
    if g.geom_type == "Point":
        return None if g.empty else g
    if g.geom_type == "MultiPoint":
        for i in range(len(g)):
            p = g[i]
            if p.geom_type == "Point" and not p.empty:
                return p
        return None
    if g.geom_type == "GeometryCollection":
        for i in range(len(g)):
            p = _coerce_single_point(g[i])
            if p is not None:
                return p
        return None
    return None


def _point_from_feature(geom_dict: dict | None) -> Point | None:
    if not geom_dict:
        return None
    try:
        g = GEOSGeometry(json.dumps(geom_dict))
        g.srid = 4326
    except Exception:
        logger.warning(
            "POI GeoJSON: impossible de lire la géométrie (GeoJSON invalide), entité ignorée."
        )
        return None

    pt = _coerce_single_point(g)
    if pt is not None and pt.valid:
        return pt

    if pt is not None and not pt.valid:
        g = pt

    if not g.valid and hasattr(g, "make_valid"):
        try:
            fixed = g.make_valid()
            pt = _coerce_single_point(fixed)
            if pt is not None and pt.valid:
                return pt
        except Exception:
            pass

    pt = _coerce_single_point(g)
    if pt is None:
        logger.warning(
            "POI GeoJSON: pas de Point exploitable (type=%s), entité ignorée.",
            g.geom_type,
        )
        return None
    if not pt.valid:
        logger.warning(
            "POI GeoJSON: géométrie point invalide et non corrigeable, entité ignorée."
        )
        return None
    return pt


def run_poi_geojson_import(
    path: Path,
    dry_run: bool,
    *,
    name_field: str | None = None,
) -> tuple[int, int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    created = updated = skipped = 0
    with transaction.atomic():
        for feature in _iter_features(data):
            pt = _point_from_feature(feature.get("geometry"))
            if not pt:
                skipped += 1
                continue
            props = feature.get("properties") or {}
            name = _feature_name(props, name_field=name_field)
            if not name:
                skipped += 1
                continue
            name = normalize_boundary_label(name)[:255]
            if not name.strip():
                skipped += 1
                continue
            commune, quartier = commune_and_quartier_for_point(pt)
            if not commune:
                skipped += 1
                continue
            cat = _infer_category(props)
            ext = _external_id(props, feature)
            src = str(props.get("source") or "").strip()[:64] or "OSM"
            defaults = {
                "name": name,
                "category": cat,
                "geom": pt,
                "commune": commune,
                "quartier": quartier,
                "source": src,
            }
            if dry_run:
                created += 1
                continue
            if ext:
                _, was_c = PointInteret.objects.update_or_create(
                    external_id=ext, defaults=defaults
                )
            else:
                ex = PointInteret.objects.filter(name=name, commune=commune).first()
                if ex:
                    for k, v in defaults.items():
                        setattr(ex, k, v)
                    ex.save()
                    was_c = False
                else:
                    PointInteret.objects.create(**defaults)
                    was_c = True
            if was_c:
                created += 1
            else:
                updated += 1
        if dry_run:
            transaction.set_rollback(True)
    return created, updated, skipped
