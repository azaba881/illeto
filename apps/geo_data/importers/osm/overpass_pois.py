"""POI santé / marché via Overpass (Bénin)."""

from __future__ import annotations

import json
import logging
from typing import Any

import requests
from django.contrib.gis.geos import Point
from django.db import transaction

from apps.geo_data.importers.env_paths import overpass_api_url
from apps.geo_data.importers.spatial import commune_and_quartier_for_point
from apps.geo_data.models import PointInteret
from apps.geo_data.text_normalize import normalize_boundary_label

logger = logging.getLogger(__name__)

BENIN_SOUTH, BENIN_WEST, BENIN_NORTH, BENIN_EAST = 6.2, 0.2, 12.7, 3.9
HEALTH_AMENITIES = frozenset(
    {"hospital", "clinic", "doctors", "pharmacy", "dentist"}
)


def _build_query(south: float, west: float, north: float, east: float) -> str:
    parts = []
    for a in sorted(HEALTH_AMENITIES):
        parts.append('node["amenity"="%s"](%s,%s,%s,%s);' % (a, south, west, north, east))
        parts.append('way["amenity"="%s"](%s,%s,%s,%s);' % (a, south, west, north, east))
    parts.append('node["amenity"="marketplace"](%s,%s,%s,%s);' % (south, west, north, east))
    parts.append('way["amenity"="marketplace"](%s,%s,%s,%s);' % (south, west, north, east))
    parts.append('node["shop"="marketplace"](%s,%s,%s,%s);' % (south, west, north, east))
    parts.append('way["shop"="marketplace"](%s,%s,%s,%s);' % (south, west, north, east))
    inner = "\n  ".join(parts)
    return "[out:json][timeout:300];\n(\n  %s\n);\nout center tags;" % inner


def _category_from_tags(tags: dict) -> str:
    amenity = (tags.get("amenity") or "").strip().lower()
    shop = (tags.get("shop") or "").strip().lower()
    if amenity in HEALTH_AMENITIES:
        return PointInteret.Category.HEALTH
    if amenity == "marketplace" or shop == "marketplace":
        return PointInteret.Category.MARKET
    return PointInteret.Category.OTHER


def _name_from_tags(tags: dict) -> str:
    for key in ("name:fr", "name"):
        v = tags.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()[:255]
    return "Sans nom"


def _element_to_point(el: dict) -> Point | None:
    if el.get("type") == "node":
        lat, lon = el.get("lat"), el.get("lon")
    else:
        c = el.get("center") or {}
        lat, lon = c.get("lat"), c.get("lon")
    if lat is None or lon is None:
        return None
    try:
        return Point(float(lon), float(lat), srid=4326)
    except (TypeError, ValueError):
        return None


def _external_id(el: dict) -> str:
    return ("osm/%s/%s" % (el.get("type", "?"), el.get("id")))[:128]


def run_overpass_pois_import(
    url: str | None, timeout: int, dry_run: bool
) -> tuple[int, int, int]:
    base_url = (url or overpass_api_url()).strip()
    q = _build_query(BENIN_SOUTH, BENIN_WEST, BENIN_NORTH, BENIN_EAST)
    resp = requests.post(
        base_url,
        data={"data": q},
        headers={
            "User-Agent": "Illeto-Django/overpass_pois",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        timeout=max(30, timeout),
    )
    resp.raise_for_status()
    payload = resp.json()
    elements = payload.get("elements") or []
    created = updated = skipped = 0
    with transaction.atomic():
        for el in elements:
            tags = el.get("tags") or {}
            if not tags:
                skipped += 1
                continue
            cat = _category_from_tags(tags)
            if cat == PointInteret.Category.OTHER:
                skipped += 1
                continue
            pt = _element_to_point(el)
            if pt is None:
                skipped += 1
                continue
            commune, quartier = commune_and_quartier_for_point(pt)
            if not commune:
                skipped += 1
                continue
            name = normalize_boundary_label(_name_from_tags(tags))[:255]
            ext = _external_id(el)
            defaults = {
                "name": name,
                "category": cat,
                "geom": pt,
                "commune": commune,
                "quartier": quartier,
                "source": "OSM",
            }
            if dry_run:
                continue
            _, was_c = PointInteret.objects.update_or_create(
                external_id=ext, defaults=defaults
            )
            if was_c:
                created += 1
            else:
                updated += 1
        if dry_run:
            transaction.set_rollback(True)
    return created, updated, skipped
