"""
Découpe les géométries Zone et Quartier par la commune parente :
ST_Multi + polygones uniquement après intersection, buffer(0) topologique,
ST_Snap sur la commune, option ST_SnapToGrid.

Usage :
  python manage.py clean_geometries
  python manage.py clean_geometries --dry-run
  python manage.py clean_geometries --only zones
  python manage.py clean_geometries --grid 0
"""

from django.core.management.base import BaseCommand
from django.db import connection, transaction

SNAP_TOLERANCE = 0.00001


def _clipped_geom_core(geom_alias: str, grid: float) -> str:
    """
    Chaîne SQL : Buffer(0) sur l'intersection, puis snap des sommets sur la commune.
    geom_alias : 'z.geom' ou 'q.geom' ; jointure sur geo_data_commune c.
    """
    inter_buf = f"""ST_Buffer(
              ST_Intersection(
                ST_MakeValid({geom_alias}::geometry),
                ST_MakeValid(c.geom::geometry)
              ),
              0
            )"""
    snapped = f"""ST_Snap(
            ST_MakeValid({inter_buf}),
            ST_MakeValid(c.geom::geometry),
            {SNAP_TOLERANCE!r}::double precision
          )"""
    core = f"ST_MakeValid({snapped})"
    if grid and grid > 0:
        core = f"ST_SnapToGrid({core}, {grid!r}::double precision)"
    return core


def _build_clip_sql(table: str, alias: str, geom_column: str, grid: float) -> str:
    inner = _clipped_geom_core(f"{alias}.{geom_column}", grid)
    poly_only = f"""ST_CollectionExtract(
          ST_MakeValid(
            ST_CollectionExtract(
              ST_MakeValid(
                {inner}
              ),
              3
            )
          ),
          3
        )"""
    return f"""
WITH clipped AS (
  SELECT {alias}.id,
    ST_SetSRID(
      ST_Multi(
        {poly_only}
      ),
      4326
    ) AS g
  FROM {table} {alias}
  INNER JOIN geo_data_commune c ON c.id = {alias}.commune_id
  WHERE {alias}.geom IS NOT NULL
    AND NOT ST_IsEmpty({alias}.geom::geometry)
    AND c.geom IS NOT NULL
    AND NOT ST_IsEmpty(c.geom::geometry)
    AND ST_Intersects({alias}.geom::geometry, c.geom::geometry)
)
UPDATE {table} {alias}
SET geom = clipped.g
FROM clipped
WHERE {alias}.id = clipped.id
  AND clipped.g IS NOT NULL
  AND NOT ST_IsEmpty(clipped.g)
  AND GeometryType(clipped.g) IN ('MULTIPOLYGON', 'POLYGON')
"""


class Command(BaseCommand):
    help = (
        "Clips Zone and Quartier to parent Commune: "
        "ST_Multi(ST_CollectionExtract*(ST_Snap(ST_Buffer(ST_Intersection(...),0), commune, tol)))."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compte les enregistrements éligibles sans mettre à jour la base.",
        )
        parser.add_argument(
            "--only",
            choices=("zones", "quartiers", "all"),
            default="all",
            help="Limiter le traitement aux zones, aux quartiers, ou tout.",
        )
        parser.add_argument(
            "--grid",
            type=float,
            default=1e-8,
            help=(
                "Pas ST_SnapToGrid en degrés WGS84 après snap (défaut: 1e-8, ~1 m). "
                "0 = désactive."
            ),
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        only = options["only"]
        grid = float(options["grid"])

        if grid < 0:
            self.stderr.write(self.style.ERROR("--grid doit être >= 0."))
            return

        use_snap_grid = grid > 0
        g = grid if use_snap_grid else 0.0

        sql_z = _build_clip_sql("geo_data_zone", "z", "geom", g)
        sql_q = _build_clip_sql("geo_data_quartier", "q", "geom", g)

        if dry:
            self._dry_counts(only)
            self.stdout.write(
                f"ST_Snap tolérance : {SNAP_TOLERANCE} ° · "
                f"ST_SnapToGrid : {'activé (' + str(grid) + ' °)' if use_snap_grid else 'désactivé'}."
            )
            self.stdout.write(
                self.style.WARNING("Dry-run : aucune écriture. Relancez sans --dry-run.")
            )
            return

        with transaction.atomic():
            with connection.cursor() as cursor:
                if only in ("all", "zones"):
                    cursor.execute(sql_z)
                    self.stdout.write(
                        self.style.SUCCESS(f"Zones mises à jour : {cursor.rowcount}.")
                    )
                if only in ("all", "quartiers"):
                    cursor.execute(sql_q)
                    self.stdout.write(
                        self.style.SUCCESS(f"Quartiers mis à jour : {cursor.rowcount}.")
                    )

        self.stdout.write(
            self.style.SUCCESS("Géométries en EPSG:4326 (MultiPolygonField).")
        )

    def _dry_counts(self, only: str) -> None:
        from apps.geo_data.models import Quartier, Zone

        if only in ("all", "zones"):
            nz = (
                Zone.objects.exclude(geom__isnull=True)
                .filter(commune__geom__isnull=False)
                .count()
            )
            self.stdout.write(f"Zones avec commune géométrique : {nz}.")
        if only in ("all", "quartiers"):
            nq = (
                Quartier.objects.exclude(geom__isnull=True)
                .filter(commune__geom__isnull=False)
                .count()
            )
            self.stdout.write(f"Quartiers avec commune géométrique : {nq}.")
