"""Commande Django partagée : import_hdx_boundaries / geo_import_hdx_boundaries."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.geo_data.import_audit import record_import_run
from apps.geo_data.importers.env_paths import (
    hdx_adm1_path,
    hdx_adm2_path,
    hdx_adm3_path,
    resolve_path,
)
from apps.geo_data.importers.hdx.pipeline import run_hdx_import


class Command(BaseCommand):
    help = (
        "Import limites HDX / geoBoundaries (OCHA adm1/adm2 ou shapeName/shapeID adm2/adm3)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            default="",
            help="GeoJSON (relatif à BASE_DIR ou absolu). Sinon variables ILLETO_HDX_ADM*_PATH.",
        )
        parser.add_argument(
            "--schema",
            type=str,
            choices=("ocha", "geoboundaries"),
            default="ocha",
            help=(
                "Format des attributs : ocha (adm1/adm2 HDX) ou geoboundaries (shapeName/shapeID). "
                "Obligatoire geoboundaries pour les fichiers type geoBoundaries-*.geojson (ADM2/ADM3)."
            ),
        )
        parser.add_argument(
            "--level",
            type=str,
            choices=("adm1", "adm2", "adm3"),
            required=True,
            help="Niveau : adm1/adm2 (OCHA ou geoBoundaries), adm3 → Zone (geoBoundaries).",
        )
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--bootstrap-missing-departments",
            action="store_true",
            dest="bootstrap_departments",
            help="OCHA ADM2 : créer le département parent si absent.",
        )
        parser.add_argument(
            "--update-geometry",
            action="store_true",
            dest="update_geometry",
            help="Correspondance par nom sans code : mettre à jour la géométrie.",
        )
        parser.add_argument(
            "--country",
            type=str,
            default="BJ",
            help="Filtre geoBoundaries (shapeISO), ex. BJ.",
        )

    def handle(self, *args, **options):
        rel = (options["path"] or "").strip()
        schema = options["schema"]
        level = options["level"]
        dry = options["dry_run"]
        bootstrap = options["bootstrap_departments"]
        upd_geom = options["update_geometry"]
        country = (options["country"] or "").strip()

        path: Path | None = None
        if rel:
            path = resolve_path(rel, lambda: None)
        if path is None:
            if schema == "geoboundaries":
                path = hdx_adm3_path() if level == "adm3" else hdx_adm2_path()
            elif level == "adm1":
                path = hdx_adm1_path()
            elif level == "adm2":
                path = hdx_adm2_path()

        if path is None or not path.is_file():
            raise CommandError(
                "Fichier introuvable. Utilisez --path ou définissez ILLETO_HDX_ADM1_PATH / "
                "ILLETO_HDX_ADM2_PATH / ILLETO_HDX_ADM3_PATH dans .env (selon niveau et schéma)."
            )

        if level == "adm3" and schema != "geoboundaries":
            raise CommandError(
                "ADM3 (zones geoBoundaries) exige --schema geoboundaries. "
                "Exemple : python manage.py import_hdx_boundaries "
                "--schema geoboundaries --level adm3 --path data/geoBoundaries-BEN-ADM3.geojson"
            )

        stats = run_hdx_import(
            path=path,
            schema=schema,
            level=level,
            dry_run=dry,
            bootstrap_departments=bootstrap,
            update_geometry=upd_geom,
            country_iso=country,
            stdout=self.stdout,
            style=self.style,
        )
        self.stdout.write(
            self.style.SUCCESS(
                "HDX — traités=%(processed)s créés=%(created)s maj=%(updated)s "
                "hors_pays=%(skipped_country)s sans_géom=%(skipped_geom)s "
                "sans_code=%(skipped_no_code)s sans_dept=%(skipped_no_dept)s"
                % stats
            )
        )
        if not dry:
            record_import_run(
                command_name="import_hdx_boundaries_%s_%s" % (schema, level),
                file_name=path.name,
                success_count=stats["created"] + stats["updated"],
                error_lines=[],
            )
