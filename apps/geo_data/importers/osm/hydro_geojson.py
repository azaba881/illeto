"""Import HydroZone depuis GeoJSON Polygon/MultiPolygon."""

from __future__ import annotations

import json
from pathlib import Path

from django.db import transaction

from apps.geo_data.importers.geometry_utils import geometry_dict_to_multipolygon
from apps.geo_data.models import HydroZone
from apps.geo_data.text_normalize import normalize_boundary_label


def _iter_features(data: dict):
    if data.get("type") == "FeatureCollection":
        for f in data.get("features") or []:
            if f.get("type") == "Feature":
                yield f
    elif data.get("type") == "Feature":
        yield data


def run_hydro_geojson_import(
    path: Path, dry_run: bool, source: str
) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    created = skipped = 0
    src = (source or "import")[:64]
    with transaction.atomic():
        for feature in _iter_features(data):
            mp = geometry_dict_to_multipolygon(feature.get("geometry"))
            if mp is None:
                skipped += 1
                continue
            props = feature.get("properties") or {}
            if not isinstance(props, dict):
                props = {}
            name = ""
            for k in ("name:fr", "name", "label"):
                v = props.get(k)
                if v and str(v).strip():
                    name = normalize_boundary_label(str(v).strip())[:255]
                    break
            if dry_run:
                created += 1
                continue
            HydroZone.objects.create(name=name, geom=mp, source=src)
            created += 1
        if dry_run:
            transaction.set_rollback(True)
    return created, skipped
