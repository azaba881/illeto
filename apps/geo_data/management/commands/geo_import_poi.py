"""
Import de points d'intérêt (GeoJSON Points) vers PointInteret.

Rattachement : pour chaque point, Quartier.objects.filter(geom__covers=point).first(),
sinon Commune.objects.filter(geom__covers=point).first().

Usage :
  python manage.py geo_import_poi --path data/poi_sample.geojson
  python manage.py geo_import_poi --path data/poi.geojson --dry-run
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.contrib.gis.geos import GEOSGeometry, Point
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...import_audit import record_import_run
from ...models import Commune, PointInteret, Quartier

logger = logging.getLogger(__name__)

_CATEGORY_VALUES = {c.value for c in PointInteret.Category}


def _iter_features(data: dict):
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features") or []:
            if feature.get("type") == "Feature":
                yield feature
    elif data.get("type") == "Feature":
        yield data


def _infer_category(props: dict | None) -> str:
    if not props:
        return PointInteret.Category.OTHER
    raw = props.get("category") or props.get("Category")
    if raw is not None and str(raw).strip():
        s = str(raw).strip().lower()
        aliases = {
            "santé": PointInteret.Category.HEALTH,
            "sante": PointInteret.Category.HEALTH,
            "health": PointInteret.Category.HEALTH,
            "hospital": PointInteret.Category.HEALTH,
            "clinic": PointInteret.Category.HEALTH,
            "marché": PointInteret.Category.MARKET,
            "marche": PointInteret.Category.MARKET,
            "market": PointInteret.Category.MARKET,
            "transport": PointInteret.Category.TRANSPORT,
            "bus": PointInteret.Category.TRANSPORT,
            "éducation": PointInteret.Category.EDUCATION,
            "education": PointInteret.Category.EDUCATION,
            "school": PointInteret.Category.EDUCATION,
            "culture": PointInteret.Category.CULTURE,
            "theatre": PointInteret.Category.CULTURE,
            "admin": PointInteret.Category.ADMIN,
            "administration": PointInteret.Category.ADMIN,
            "government": PointInteret.Category.ADMIN,
            "other": PointInteret.Category.OTHER,
            "autre": PointInteret.Category.OTHER,
        }
        if s in _CATEGORY_VALUES:
            return s
        if s in aliases:
            return aliases[s]
    amenity = (props.get("amenity") or "").strip().lower()
    if amenity in ("hospital", "clinic", "doctors", "pharmacy"):
        return PointInteret.Category.HEALTH
    if amenity in ("school", "university", "kindergarten"):
        return PointInteret.Category.EDUCATION
    if amenity in ("bus_station",):
        return PointInteret.Category.TRANSPORT
    shop = (props.get("shop") or "").strip().lower()
    if shop in ("marketplace", "supermarket", "convenience"):
        return PointInteret.Category.MARKET
    return PointInteret.Category.OTHER


def _feature_name(props: dict | None) -> str | None:
    if not props:
        return None
    for key in ("name:fr", "name", "title"):
        v = props.get(key)
        if v is None or str(v).strip() == "":
            continue
        name = str(v).strip()
        if len(name) > 255:
            name = name[:255]
        return name
    return None


def _external_id(props: dict | None, feature: dict) -> str | None:
    if props:
        for key in ("external_id", "@id", "id", "osm_id"):
            v = props.get(key)
            if v is None or str(v).strip() == "":
                continue
            s = str(v).strip()
            if len(s) > 128:
                s = s[:128]
            return s
    fid = feature.get("id")
    if fid is not None and str(fid).strip():
        s = str(fid).strip()
        if len(s) > 128:
            s = s[:128]
        return s
    return None


def _point_from_feature(geom_dict: dict | None) -> Point | None:
    if not geom_dict or geom_dict.get("type") != "Point":
        return None
    try:
        g = GEOSGeometry(json.dumps(geom_dict))
        g.srid = 4326
        if g.geom_type != "Point":
            return None
        return g
    except Exception:
        return None


def _link_spatial(pt: Point) -> tuple[Commune | None, Quartier | None]:
    q = Quartier.objects.filter(geom__covers=pt).select_related("commune").first()
    if q:
        return q.commune, q
    c = Commune.objects.filter(geom__covers=pt).first()
    return c, None


class Command(BaseCommand):
    help = "Importe des POI (GeoJSON Point) avec rattachement geom__covers."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="data/poi.geojson",
            help="Fichier GeoJSON (FeatureCollection de Points).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse sans écrire en base.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        dry = options["dry_run"]
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {path}")

        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide : {e}") from e

        created = 0
        updated = 0
        skipped = 0

        with transaction.atomic():
            for feature in _iter_features(data):
                geom_dict = feature.get("geometry")
                pt = _point_from_feature(geom_dict)
                if not pt:
                    skipped += 1
                    continue
                props = feature.get("properties") or {}
                name = _feature_name(props)
                if not name:
                    skipped += 1
                    logger.warning("Feature sans nom ignorée : %s", feature.get("id"))
                    continue
                commune, quartier = _link_spatial(pt)
                if not commune:
                    skipped += 1
                    logger.warning(
                        "Point hors commune (ignoré) : %s",
                        name,
                    )
                    continue
                cat = _infer_category(props)
                ext = _external_id(props, feature)
                src_raw = props.get("source") if props else None
                src = (str(src_raw).strip()[:64] if src_raw else "") or "OSM"

                if dry:
                    self.stdout.write(
                        f"[dry-run] {name} → {commune.name} / "
                        f"Q={quartier.name if quartier else '—'} / {cat}"
                    )
                    continue

                defaults = {
                    "name": name,
                    "category": cat,
                    "geom": pt,
                    "commune": commune,
                    "quartier": quartier,
                    "source": src,
                }
                if ext:
                    _, was_created = PointInteret.objects.update_or_create(
                        external_id=ext,
                        defaults=defaults,
                    )
                else:
                    existing = PointInteret.objects.filter(
                        name=name, commune=commune
                    ).first()
                    if existing:
                        for key, val in defaults.items():
                            setattr(existing, key, val)
                        existing.save()
                        was_created = False
                    else:
                        PointInteret.objects.create(**defaults)
                        was_created = True
                if was_created:
                    created += 1
                else:
                    updated += 1

            if dry:
                transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"POI : créés={created}, mis à jour={updated}, ignorés={skipped}"
                + (" (dry-run)" if dry else "")
            )
        )

        if not dry:
            record_import_run(
                command_name="geo_import_poi",
                file_name=str(path),
                success_count=created + updated,
                error_lines=[],
            )
