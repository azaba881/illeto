"""
Sérialisation GeoJSON pour l’API géographique : précision décimale élevée (PostGIS ST_AsGeoJSON),
sans simplification côté serveur. Utilisé par les vues JSON de ``apps.geo_data.views``.
"""

from __future__ import annotations

import json

from django.db import connection


def is_valid_polygonal_geojson(g: dict | None) -> bool:
    """True si la geometry GeoJSON est un polygone / multi exploitable côté carte (coords non vides)."""
    if not g or not isinstance(g, dict):
        return False
    t = g.get("type")
    if t == "Polygon":
        coords = g.get("coordinates")
        if not coords or not isinstance(coords, list) or not len(coords):
            return False
        ring = coords[0]
        return isinstance(ring, list) and len(ring) >= 4
    if t == "MultiPolygon":
        coords = g.get("coordinates")
        if not coords or not isinstance(coords, list):
            return False
        for poly in coords:
            if not poly or not isinstance(poly, list) or not len(poly):
                continue
            ring = poly[0]
            if isinstance(ring, list) and len(ring) >= 4:
                return True
        return False
    return False


def geometry_to_geojson_dict(geom, max_decimal_digits: int = 15, *, polygonal_only: bool = False):
    """
    Retourne un objet geometry GeoJSON (dict) ou None.

    ``max_decimal_digits`` : précision ST_AsGeoJSON (15 : limite les écarts / liserés côté
    navigateur vs géométrie serveur ; évite l’arrondi visible vs ``geom.geojson`` GEOS).
    ``polygonal_only`` : si True, n’accepte que Polygon / MultiPolygon valides (zones / quartiers).
    Retombe sur ``geom.geojson`` si la requête SQL échoue (ex. hors PostGIS).
    """
    if geom is None:
        return None
    try:
        if getattr(geom, "empty", False):
            return None
    except Exception:
        pass
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ST_AsGeoJSON(%s::geometry, %s, 0)::text",
                [geom, max_decimal_digits],
            )
            row = cursor.fetchone()
        if not row or not row[0]:
            return None
        parsed = json.loads(row[0])
        if polygonal_only and not is_valid_polygonal_geojson(parsed):
            return None
        return parsed
    except Exception:
        pass
    try:
        parsed = json.loads(geom.geojson)
        if polygonal_only and not is_valid_polygonal_geojson(parsed):
            return None
        return parsed
    except Exception:
        return None
