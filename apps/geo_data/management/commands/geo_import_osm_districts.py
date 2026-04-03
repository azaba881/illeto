"""
Import des arrondissements (admin_level=8 → Zone) et quartiers (admin_level=10 → Quartier)
depuis un GeoJSON OSM (ex. data/export.geojson).

Rattachement à la commune : centroïde de la géométrie doit être couvert par Commune.geom
(Commune.objects.filter(geom__covers=centroid).first()).

Usage :
  python manage.py geo_import_osm_districts
  python manage.py geo_import_osm_districts --path data/export.geojson
  python manage.py geo_import_osm_districts --dry-run
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...import_audit import record_import_run
from ...models import Commune, Quartier, Zone

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
        if len(name) > 255:
            name = name[:255]
        return name
    return None


def _osm_id(properties: dict | None) -> str | None:
    if not properties:
        return None
    oid = properties.get("@id") or properties.get("id")
    if oid is None or str(oid).strip() == "":
        return None
    s = str(oid).strip()
    if len(s) > 128:
        s = s[:128]
    return s


def _geometry_to_multipolygon(geom_dict: dict | None) -> MultiPolygon | None:
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
    help = (
        "Importe les arrondissements (admin_level 8) et quartiers (admin_level 10) "
        "depuis un GeoJSON vers Zone et Quartier."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="data/export.geojson",
            help="Chemin relatif au répertoire du projet (défaut: data/export.geojson).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse et journaux sans écrire en base.",
        )

    def handle(self, *args, **options):
        rel_path = options["path"]
        dry_run = options["dry_run"]
        base = Path(settings.BASE_DIR)
        path = (base / rel_path).resolve()
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide : {e}") from e

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
                logger.warning(
                    "geo_import_osm_districts: entité admin_level=%s sans nom exploitable, propriétés=%s",
                    al,
                    list(props.keys()),
                )
                continue

            mp = _geometry_to_multipolygon(feature.get("geometry"))
            if mp is None:
                stats["skipped_geom"] += 1
                logger.warning(
                    "geo_import_osm_districts: géométrie non polygonale ignorée (admin_level=%s, nom=%s)",
                    al,
                    name,
                )
                continue

            centroid = mp.centroid
            parent = Commune.objects.filter(geom__covers=centroid).first()

            if parent is None:
                stats["skipped_no_parent"] += 1
                logger.warning(
                    "geo_import_osm_districts: aucune commune parente pour %r (admin_level=%s, "
                    "centroïde lon=%.6f lat=%.6f) — cas possible : zone frontalière ou données OSM hors limites communales.",
                    name,
                    al,
                    centroid.x,
                    centroid.y,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"[sans commune] {name} (admin_level={al}) — "
                        f"centroïde ({centroid.x:.6f}, {centroid.y:.6f})"
                    )
                )
                continue

            oid = _osm_id(props)

            if dry_run:
                stats["dry_run_ok"] += 1
                self.stdout.write(
                    f"[dry-run] {'Zone' if al == 8 else 'Quartier'} {name!r} → commune {parent.name!r} (pk={parent.pk})"
                )
                continue

            if al == 8:
                with transaction.atomic():
                    if oid:
                        obj, created = Zone.objects.update_or_create(
                            osm_id=oid,
                            defaults={
                                "commune": parent,
                                "name": name,
                                "geom": mp,
                            },
                        )
                    else:
                        obj, created = Zone.objects.update_or_create(
                            commune=parent,
                            name=name,
                            defaults={"geom": mp},
                        )
                    if created:
                        stats["zones_created"] += 1
                    else:
                        stats["zones_updated"] += 1
            else:
                with transaction.atomic():
                    if oid:
                        obj, created = Quartier.objects.update_or_create(
                            osm_id=oid,
                            defaults={
                                "commune": parent,
                                "name": name,
                                "geom": mp,
                            },
                        )
                    else:
                        obj, created = Quartier.objects.update_or_create(
                            commune=parent,
                            name=name,
                            defaults={"geom": mp},
                        )
                    if created:
                        stats["quartiers_created"] += 1
                    else:
                        stats["quartiers_updated"] += 1

        msg = (
            "Terminé — "
            f"zones créées={stats['zones_created']} mises à jour={stats['zones_updated']}, "
            f"quartiers créés={stats['quartiers_created']} mis à jour={stats['quartiers_updated']}, "
            f"sans nom={stats['skipped_name']}, "
            f"mauvaise géom={stats['skipped_geom']}, sans commune parente={stats['skipped_no_parent']}"
        )
        if dry_run:
            msg += f", dry-run importables={stats['dry_run_ok']}"
        self.stdout.write(self.style.SUCCESS(msg))

        if not dry_run:
            total_written = (
                stats["zones_created"]
                + stats["zones_updated"]
                + stats["quartiers_created"]
                + stats["quartiers_updated"]
            )
            record_import_run(
                command_name="geo_import_osm_districts",
                file_name=str(path.name),
                success_count=total_written,
                error_lines=[
                    (
                        f"Résumé : zones créées={stats['zones_created']} "
                        f"mises à jour={stats['zones_updated']}, "
                        f"quartiers créés={stats['quartiers_created']} "
                        f"mis à jour={stats['quartiers_updated']}, "
                        f"ignorés sans nom={stats['skipped_name']}, "
                        f"géométrie invalide={stats['skipped_geom']}, "
                        f"sans commune parente={stats['skipped_no_parent']}."
                    )
                ],
            )
