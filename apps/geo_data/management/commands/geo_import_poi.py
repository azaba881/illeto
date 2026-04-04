"""Import POI depuis GeoJSON (points) — rattachement geom__covers."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.geo_data.import_audit import record_import_run
from apps.geo_data.importers.env_paths import poi_geojson_path, resolve_path
from apps.geo_data.importers.osm.poi_geojson import run_poi_geojson_import


class Command(BaseCommand):
    help = "Importe des PointInteret depuis GeoJSON (défaut : ILLETO_POI_GEOJSON_PATH)."

    def add_arguments(self, parser):
        parser.add_argument("--path", type=str, default="")
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        rel = (options["path"] or "").strip()
        path = resolve_path(rel, poi_geojson_path) if rel else poi_geojson_path()
        if path is None:
            path = (Path(settings.BASE_DIR) / "data" / "poi.geojson").resolve()
        if not path.is_file():
            raise CommandError("Fichier introuvable : %s" % path)

        c, u, s = run_poi_geojson_import(path, options["dry_run"])
        self.stdout.write(
            self.style.SUCCESS(
                "POI : créés=%s mis à jour=%s ignorés=%s%s"
                % (c, u, s, " (dry-run)" if options["dry_run"] else "")
            )
        )
        if not options["dry_run"]:
            record_import_run(
                command_name="geo_import_poi",
                file_name=path.name,
                success_count=c + u,
                error_lines=[],
            )
