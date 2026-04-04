"""Import arrondissements / quartiers OSM (admin_level 8 / 10)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.geo_data.import_audit import record_import_run
from apps.geo_data.importers.env_paths import osm_districts_path, resolve_path
from apps.geo_data.importers.osm.districts import run_osm_districts_import


class Command(BaseCommand):
    help = "Zone (8) et Quartier (10) depuis GeoJSON — commune parente via geom__covers."

    def add_arguments(self, parser):
        parser.add_argument("--path", type=str, default="")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rel = (options["path"] or "").strip()
        if rel:
            path = resolve_path(rel, osm_districts_path)
        else:
            path = osm_districts_path()
        if path is None:
            path = (Path(settings.BASE_DIR) / "data" / "export.geojson").resolve()
        if not path.is_file():
            raise CommandError("Fichier introuvable : %s" % path)
        stats = run_osm_districts_import(
            path, options["dry_run"], self.stdout, self.style
        )
        msg = (
            "zones c=%(zones_created)s u=%(zones_updated)s "
            "quartiers c=%(quartiers_created)s u=%(quartiers_updated)s"
        ) % stats
        self.stdout.write(self.style.SUCCESS(msg))
        if not options["dry_run"]:
            t = (
                stats["zones_created"]
                + stats["zones_updated"]
                + stats["quartiers_created"]
                + stats["quartiers_updated"]
            )
            record_import_run(
                command_name="geo_import_osm_districts",
                file_name=path.name,
                success_count=t,
                error_lines=[],
            )
