"""
Génère 77 communes factices réparties sur les départements existants
(ex. « Commune 1 de [NomDept] ») avec une petite géométrie (buffer) pour l’UI.

À remplacer par un import réel des 77 communes quand le fichier est disponible.

Usage :
  python manage.py geo_seed_dummy_communes
  python manage.py geo_seed_dummy_communes --purge-placeholders   # supprime d’abord les placeholders
"""

from django.contrib.gis.geos import MultiPolygon
from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import Commune, Departement

# 77 communes au total pour 12 départements (répartition type Bénin)
_COUNTS_12 = (7, 7, 7, 7, 7, 6, 6, 6, 6, 6, 6, 6)


def _counts_for_n_departements(n: int) -> list[int]:
    if n <= 0:
        return []
    if n <= len(_COUNTS_12):
        return list(_COUNTS_12[:n])
    base, rem = divmod(77, n)
    return [base + (1 if i < rem else 0) for i in range(n)]


class Command(BaseCommand):
    help = (
        "Crée des communes factices (is_placeholder=True) pour chaque département, "
        "total 77 si 12 départements, sinon répartition équilibrée de 77. "
        "En production (DEBUG=False), l’API communes GeoJSON/JSON les exclut par défaut "
        "(settings ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES, défaut=DEBUG)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge-placeholders",
            action="store_true",
            help="Supprime toutes les communes marquées is_placeholder avant insertion.",
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "ATTENTION : Ce script crée des données de test. Ne pas utiliser en production "
                "sur la base officielle du Bénin."
            )
        )
        purge = options["purge_placeholders"]
        if purge:
            n_del, _ = Commune.objects.filter(is_placeholder=True).delete()
            self.stdout.write(self.style.WARNING(f"Supprimé {n_del} commune(s) factice(s)."))

        depts = list(Departement.objects.order_by("name"))
        if not depts:
            self.stdout.write(self.style.ERROR("Aucun département en base. Importez les départements d’abord."))
            return

        counts = _counts_for_n_departements(len(depts))
        created = 0

        with transaction.atomic():
            for idx, dept in enumerate(depts):
                n_here = counts[idx] if idx < len(counts) else max(1, 77 // len(depts))
                Commune.objects.filter(departement=dept, is_placeholder=True).delete()
                if not dept.geom:
                    self.stdout.write(
                        self.style.WARNING(f"Département « {dept.name} » sans géométrie — ignoré.")
                    )
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
                    self.stdout.write(
                        self.style.ERROR(f"« {dept.name} » : buffer inattendu ({buf.geom_type}).")
                    )
                    continue

                for k in range(1, n_here + 1):
                    name = f"Commune {k} de {dept.name}"
                    Commune.objects.create(
                        name=name,
                        departement=dept,
                        geom=mp,
                        is_placeholder=True,
                    )
                    created += 1

        self.stdout.write(self.style.SUCCESS(f"{created} commune(s) factice(s) créée(s) ({len(depts)} département(s))."))
