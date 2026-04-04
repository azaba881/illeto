"""POI Overpass (santé + marchés) — Bénin."""

from django.core.management.base import BaseCommand, CommandError

from apps.geo_data.import_audit import record_import_run
from apps.geo_data.importers.env_paths import overpass_api_url
from apps.geo_data.importers.osm.overpass_pois import run_overpass_pois_import


class Command(BaseCommand):
    help = "Interroge Overpass et importe les POI santé / marché (PointInteret)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--url",
            type=str,
            default="",
            help="URL Overpass (défaut : ILLETO_OVERPASS_API_URL ou serveur public).",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--timeout", type=int, default=600)

    def handle(self, *args, **options):
        url = options["url"].strip() or None
        dry = options["dry_run"]
        try:
            c, u, s = run_overpass_pois_import(
                url, options["timeout"], dry
            )
        except Exception as e:
            raise CommandError(str(e)) from e
        self.stdout.write(
            self.style.SUCCESS(
                "POI Overpass : créés=%s maj=%s ignorés=%s%s"
                % (c, u, s, " (dry-run)" if dry else "")
            )
        )
        if not dry:
            record_import_run(
                command_name="import_osm_pois",
                file_name="overpass",
                success_count=c + u,
                error_lines=[],
            )
