"""Import arrondissements / quartiers OSM (admin_level 8 / 10)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from django.db import transaction

from apps.geo_data.importers.geometry_utils import geometry_dict_to_multipolygon
from apps.geo_data.importers.spatial import commune_for_centroid
from apps.geo_data.models import Commune, Quartier, Zone
from apps.geo_data.text_normalize import normalize_boundary_label

logger = logging.getLogger(__name__)


def _iter_features(data: dict):
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features") or []:
            if feature.get("type") == "Feature":
                yield feature
    elif data.get("type") == "Feature":
        yield data


def _admin_level(properties: dict | None) -> int | None:
    if not properties:
        return None
    al = properties.get("admin_level")
    if al is None:
        return None
    try:
        return int(str(al).strip())
    except ValueError:
        return None


def _feature_name(properties: dict | None) -> str | None:
    if not properties:
        return None
    for key in ("name:fr", "name", "official_name"):
        if key not in properties:
            continue
        value = properties[key]
        if value is None or str(value).strip() == "":
            continue
        name = str(value).strip()
        return name[:255] if len(name) > 255 else name
    return None


def _osm_id(properties: dict | None) -> str | None:
    if not properties:
        return None
    oid = properties.get("@id") or properties.get("id")
    if oid is None or str(oid).strip() == "":
        return None
    s = str(oid).strip()
    return s[:128] if len(s) > 128 else s


def run_osm_districts_import(path: Path, dry_run: bool, stdout: Any, style: Any) -> dict:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    stats = {
        "zones_created": 0,
        "zones_updated": 0,
        "quartiers_created": 0,
        "quartiers_updated": 0,
        "skipped_geom": 0,
        "skipped_name": 0,
        "skipped_no_parent": 0,
        "dry_run_ok": 0,
    }
    for feature in _iter_features(data):
        props = feature.get("properties") or {}
        al = _admin_level(props)
        if al not in (8, 10):
            continue
        name = _feature_name(props)
        if not name:
            stats["skipped_name"] += 1
            continue
        name = normalize_boundary_label(name)
        if not name.strip():
            stats["skipped_name"] += 1
            continue
        name = name[:255]
        mp = geometry_dict_to_multipolygon(feature.get("geometry"))
        if mp is None:
            stats["skipped_geom"] += 1
            continue
        parent = commune_for_centroid(mp.centroid)
        if parent is None:
            stats["skipped_no_parent"] += 1
            continue
        oid = _osm_id(props)
        if dry_run:
            stats["dry_run_ok"] += 1
            stdout.write("[dry-run] %s %r" % ("Zone" if al == 8 else "Quartier", name))
            continue
        with transaction.atomic():
            if al == 8:
                if oid:
                    _o, c = Zone.objects.update_or_create(
                        osm_id=oid,
                        defaults={"commune": parent, "name": name, "geom": mp},
                    )
                else:
                    _o, c = Zone.objects.update_or_create(
                        commune=parent,
                        name=name,
                        defaults={"geom": mp},
                    )
                if c:
                    stats["zones_created"] += 1
                else:
                    stats["zones_updated"] += 1
            else:
                if oid:
                    _o, c = Quartier.objects.update_or_create(
                        osm_id=oid,
                        defaults={"commune": parent, "name": name, "geom": mp},
                    )
                else:
                    _o, c = Quartier.objects.update_or_create(
                        commune=parent,
                        name=name,
                        defaults={"geom": mp},
                    )
                if c:
                    stats["quartiers_created"] += 1
                else:
                    stats["quartiers_updated"] += 1
    return stats
