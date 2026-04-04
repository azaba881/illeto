"""Import polygones vers HydroZone."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.geo_data.import_audit import record_import_run
from apps.geo_data.importers.env_paths import hydro_geojson_path, resolve_path
from apps.geo_data.importers.osm.hydro_geojson import run_hydro_geojson_import


class Command(BaseCommand):
    help = "Importe des HydroZone depuis GeoJSON (défaut : ILLETO_HYDRO_GEOJSON_PATH)."

    def add_arguments(self, parser):
        parser.add_argument("--path", type=str, default="")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--source", type=str, default="geojson_import")

    def handle(self, *args, **options):
        rel = (options["path"] or "").strip()
        path = resolve_path(rel, hydro_geojson_path) if rel else hydro_geojson_path()
        if path is None:
            path = (Path(settings.BASE_DIR) / "data" / "hydro.geojson").resolve()
        if not path.is_file():
            raise CommandError("Fichier introuvable : %s" % path)

        created, skipped = run_hydro_geojson_import(
            path, options["dry_run"], options["source"]
        )
        self.stdout.write(
            self.style.SUCCESS(
                "HydroZone : créés=%s ignorés=%s%s"
                % (created, skipped, " (dry-run)" if options["dry_run"] else "")
            )
        )
        if not options["dry_run"]:
            record_import_run(
                command_name="geo_import_hydro_zones",
                file_name=path.name,
                success_count=created,
                error_lines=[],
            )
