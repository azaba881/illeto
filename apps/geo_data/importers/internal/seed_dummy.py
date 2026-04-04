"""Génération de communes factices (is_placeholder)."""

from __future__ import annotations

from django.contrib.gis.geos import MultiPolygon
from django.db import transaction

from apps.geo_data.models import Commune, Departement

_COUNTS_12 = (7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6)


def _counts_for_n_departements(n: int) -> list[int]:
    if n <= 0:
        return []
    if n <= len(_COUNTS_12):
        return list(_COUNTS_12[:n])
    base, rem = divmod(77, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


def run_seed_dummy_communes(purge: bool) -> tuple[int, str | None]:
    if purge:
        n_del, _ = Commune.objects.filter(is_placeholder=True).delete()
        return n_del, "purge:%s" % n_del
    depts = list(Departement.objects.order_by("name"))
    if not depts:
        return 0, "no_departements"
    counts = _counts_for_n_departements(len(depts))
    created = 0
    with transaction.atomic():
        for idx, dept in enumerate(depts):
            n_here = counts[idx] if idx < len(counts) else max(1, 77 // len(depts))
            Commune.objects.filter(departement=dept, is_placeholder=True).delete()
            if not dept.geom:
                continue
            try:
                pt = dept.geom.point_on_surface
            except Exception:
                pt = dept.geom.centroid
            buf = pt.buffer(0.035)
            if buf.geom_type == "Polygon":
                mp = MultiPolygon(buf)
            elif buf.geom_type == "MultiPolygon":
                mp = buf
            else:
                continue
            for k in range(1, n_here + 1):
                name = "Commune %s de %s" % (k, dept.name)
                Commune.objects.create(
                    name=name,
                    departement=dept,
                    geom=mp,
                    is_placeholder=True,
                )
                created += 1
    return created, None
