"""
Import de polygones hydrologiques (aléas) vers HydroZone pour le calcul PostGIS d’inondation.

Attend un GeoJSON FeatureCollection avec géométries Polygon ou MultiPolygon.

Usage :
  python manage.py geo_import_hydro_zones --path data/hydro.geojson
  python manage.py geo_import_hydro_zones --dry-run
"""

from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...import_audit import record_import_run
from ...models import HydroZone


def _iter_features(data: dict):
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features") or []:
            if feature.get("type") == "Feature":
                yield feature
    elif data.get("type") == "Feature":
        yield data


def _to_multipolygon(geom_dict: dict | None) -> MultiPolygon | None:
    if not geom_dict:
        return None
    try:
        g = GEOSGeometry(json.dumps(geom_dict))
    except Exception:
        return None
    g.srid = 4326
    if g.geom_type == "Polygon":
        return MultiPolygon(g)
    if g.geom_type == "MultiPolygon":
        return g
    return None


class Command(BaseCommand):
    help = "Importe des polygones hydro vers HydroZone (intersection commune en PostGIS)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="data/hydro.geojson",
            help="Chemin relatif au BASE_DIR.",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--source",
            type=str,
            default="geojson_import",
            help="Valeur du champ source sur HydroZone.",
        )

    def handle(self, *args, **options):
        rel = options["path"]
        dry = options["dry_run"]
        src = (options["source"] or "import")[:64]
        path = (Path(settings.BASE_DIR) / rel).resolve()
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide : {e}") from e

        created = 0
        skipped = 0

        for feature in _iter_features(data):
            mp = _to_multipolygon(feature.get("geometry"))
            if mp is None:
                skipped += 1
                continue
            props = feature.get("properties") or {}
            name = ""
            for k in ("name:fr", "name", "label"):
                v = props.get(k)
                if v and str(v).strip():
                    name = str(v).strip()[:255]
                    break
            if dry:
                self.stdout.write(f"[dry-run] hydro {name or '(sans nom)'}")
                continue
            with transaction.atomic():
                HydroZone.objects.create(name=name, geom=mp, source=src)
            created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"HydroZone : créés={created}, ignorés={skipped}"
                + (" (dry-run)" if dry else "")
            )
        )

        if not dry:
            record_import_run(
                command_name="geo_import_hydro_zones",
                file_name=str(path.name),
                success_count=created,
                error_lines=[],
            )
