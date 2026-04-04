"""Conversions géométriques communes (GeoJSON dict → MultiPolygon)."""

from __future__ import annotations

import json
import logging

from django.contrib.gis.geos import GEOSGeometry, MultiPolygon

logger = logging.getLogger(__name__)


def geometry_dict_to_multipolygon(geom_dict: dict | None) -> MultiPolygon | None:
    if not geom_dict:
        return None
    try:
        g = GEOSGeometry(json.dumps(geom_dict))
    except Exception as e:
        logger.warning("Géométrie invalide : %s", e)
        return None
    if g.srid in (None, 0):
        g.srid = 4326
    if g.geom_type == "Polygon":
        return MultiPolygon(g)
    if g.geom_type == "MultiPolygon":
        return g
    logger.warning("Type géométrique non pris en charge : %s", g.geom_type)
    return None
