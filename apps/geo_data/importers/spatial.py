"""
Rattachements spatiaux : ``geom__covers`` pour points et centroïdes.
"""

from __future__ import annotations

from django.contrib.gis.geos import Point

from apps.geo_data.models import Commune, Quartier


def commune_and_quartier_for_point(pt: Point) -> tuple[Commune | None, Quartier | None]:
    """Quartier couvrant le point en priorité, sinon commune couvrant le point."""
    q = Quartier.objects.filter(geom__covers=pt).select_related("commune").first()
    if q:
        return q.commune, q
    c = Commune.objects.filter(geom__covers=pt).first()
    return c, None


def commune_for_centroid(centroid) -> Commune | None:
    """Commune dont le polygone contient le centroïde (ADM3 geoBoundaries, OSM).

    On essaie d’abord ``covers`` puis ``intersects`` : un point exactement sur une limite
    communale peut échouer avec ``covers`` seul.
    """
    qs = Commune.objects.all()
    c = qs.filter(geom__covers=centroid).first()
    if c is not None:
        return c
    return qs.filter(geom__intersects=centroid).first()
