"""
Import des limites administratives HDX (OCHA / COD) pour le Bénin.

Filtre pays : adm0_en ou adm0_name ∈ {Benin, Bénin} (insensible à la casse).

Niveaux :
  --level adm1 : adm1_name → Departement, adm1_pcode → code_officiel
  --level adm2 : adm2_name → Commune, adm2_pcode → code_officiel
                 rattachement au département via adm1_pcode (prioritaire) ou adm1_name

Géométries : conversion systématique en MultiPolygon (EPSG:4326).

Idempotence : update_or_create sur code_officiel (pcode) ; mise à jour de la géométrie HDX.

Si les départements ADM1 n’existent pas encore, l’import ADM2 peut
``--bootstrap-missing-departments`` pour créer un département minimal
(géométrie = commune, à remplacer par un import ADM1 officiel).

Usage :
  python manage.py geo_import_hdx_boundaries --path data/benin_adm1.geojson --level adm1
  python manage.py geo_import_hdx_boundaries --path data/benin_adm2.geojson --level adm2
  python manage.py geo_import_hdx_boundaries --path data/benin_adm2.geojson --level adm2 --dry-run
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from django.conf import settings
from django.contrib.gis.geos import GEOSGeometry, MultiPolygon
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...import_audit import record_import_run
from ...models import Commune, Departement

logger = logging.getLogger(__name__)


def _norm_props(props: dict | None) -> dict[str, object]:
    """Clés de propriétés en minuscules pour tolérer les variantes HDX."""
    if not props:
        return {}
    return {str(k).lower(): v for k, v in props.items()}


def _as_str(v: object | None) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    return s


def _is_benin(props_norm: dict[str, object]) -> bool:
    adm0 = _as_str(
        props_norm.get("adm0_en")
        or props_norm.get("adm0_name")
        or props_norm.get("admin0name")
    )
    if not adm0:
        return False
    low = adm0.lower()
    return low in ("benin", "bénin")


def geometry_to_multipolygon(geom_dict: dict | None) -> MultiPolygon | None:
    """Convertit Polygon / MultiPolygon en MultiPolygon (équivalent ST_Multi côté géométrie)."""
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


class Command(BaseCommand):
    help = "Import HDX (limites administratives Bénin) — ADM1 départements ou ADM2 communes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            type=str,
            required=True,
            help="Chemin GeoJSON (relatif au BASE_DIR ou absolu).",
        )
        parser.add_argument(
            "--level",
            type=str,
            choices=("adm1", "adm2"),
            required=True,
            help="Niveau administratif du fichier (ADM1 ou ADM2).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse sans écrire en base.",
        )
        parser.add_argument(
            "--bootstrap-missing-departments",
            action="store_true",
            dest="bootstrap_departments",
            help=(
                "ADM2 uniquement : si le département parent est introuvable, "
                "le créer avec la géométrie de la commune (provisoire)."
            ),
        )

    def handle(self, *args, **options):
        rel_path = options["path"]
        level = options["level"]
        dry = options["dry_run"]
        bootstrap_dept = options["bootstrap_departments"]

        base = Path(settings.BASE_DIR)
        path = Path(rel_path)
        if not path.is_file():
            path = (base / rel_path).resolve()
        if not path.is_file():
            raise CommandError(f"Fichier introuvable : {rel_path}")

        raw = path.read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide : {e}") from e

        features = []
        if data.get("type") == "FeatureCollection":
            features = [f for f in (data.get("features") or []) if f.get("type") == "Feature"]
        elif data.get("type") == "Feature":
            features = [data]

        stats = {
            "processed": 0,
            "skipped_country": 0,
            "skipped_geom": 0,
            "skipped_no_code": 0,
            "skipped_no_dept": 0,
            "created": 0,
            "updated": 0,
        }

        for feature in features:
            props = _norm_props(feature.get("properties") or {})
            if not _is_benin(props):
                stats["skipped_country"] += 1
                continue

            mp = geometry_to_multipolygon(feature.get("geometry"))
            if mp is None:
                stats["skipped_geom"] += 1
                continue

            stats["processed"] += 1

            if level == "adm1":
                self._import_adm1(
                    props,
                    mp,
                    dry,
                    stats,
                )
            else:
                self._import_adm2(
                    props,
                    mp,
                    dry,
                    stats,
                    bootstrap_dept,
                )

        msg = (
            f"HDX {level.upper()} — traités={stats['processed']}, "
            f"créés={stats['created']}, mis à jour={stats['updated']}, "
            f"hors Bénin={stats['skipped_country']}, sans géom={stats['skipped_geom']}, "
            f"sans pcode={stats['skipped_no_code']}, sans département={stats['skipped_no_dept']}"
        )
        self.stdout.write(self.style.SUCCESS(msg))

        if not dry:
            record_import_run(
                command_name=f"geo_import_hdx_boundaries_{level}",
                file_name=str(path.name),
                success_count=stats["created"] + stats["updated"],
                error_lines=[],
            )

    def _import_adm1(
        self,
        props: dict[str, object],
        mp: MultiPolygon,
        dry: bool,
        stats: dict,
    ) -> None:
        name = _as_str(props.get("adm1_name") or props.get("name"))
        pcode = _as_str(props.get("adm1_pcode") or props.get("pcode"))
        if not name:
            stats["skipped_no_code"] += 1
            logger.warning("ADM1 sans adm1_name")
            return

        if dry:
            self.stdout.write(f"[dry-run] ADM1 {name!r} pcode={pcode or '—'}")
            return

        with transaction.atomic():
            if pcode:
                obj, created = Departement.objects.update_or_create(
                    code_officiel=pcode[:64],
                    defaults={
                        "name": name[:255],
                        "geom": mp,
                    },
                )
            else:
                obj, created = Departement.objects.update_or_create(
                    name=name[:255],
                    defaults={"geom": mp},
                )
        stats["created" if created else "updated"] += 1

    def _import_adm2(
        self,
        props: dict[str, object],
        mp: MultiPolygon,
        dry: bool,
        stats: dict,
        bootstrap_dept: bool,
    ) -> None:
        name = _as_str(props.get("adm2_name") or props.get("name"))
        pcode = _as_str(props.get("adm2_pcode") or props.get("pcode"))
        adm1_name = _as_str(props.get("adm1_name"))
        adm1_pcode = _as_str(props.get("adm1_pcode"))

        if not name:
            stats["skipped_no_code"] += 1
            logger.warning("ADM2 sans adm2_name")
            return
        if not pcode:
            stats["skipped_no_code"] += 1
            logger.warning("ADM2 sans adm2_pcode — ignoré (pcode requis pour l’idempotence)")
            return

        dept = None
        if adm1_pcode:
            dept = Departement.objects.filter(code_officiel=adm1_pcode[:64]).first()
        if dept is None and adm1_name:
            dept = Departement.objects.filter(name__iexact=adm1_name).first()

        if dept is None and bootstrap_dept and adm1_name:
            if dry:
                self.stdout.write(
                    self.style.WARNING(
                        f"[dry-run] bootstrap département pour {adm1_name!r}"
                    )
                )
            else:
                with transaction.atomic():
                    dept = Departement.objects.create(
                        name=adm1_name[:255],
                        code_officiel=adm1_pcode[:64] if adm1_pcode else None,
                        geom=mp,
                    )
                self.stdout.write(
                    self.style.WARNING(
                        f"Département créé (bootstrap) : {dept.name} — "
                        "préférez un import ADM1 HDX pour la géométrie officielle."
                    )
                )

        if dept is None:
            stats["skipped_no_dept"] += 1
            logger.warning(
                "ADM2 %s : département introuvable (adm1_pcode=%s adm1_name=%s)",
                name,
                adm1_pcode,
                adm1_name,
            )
            return

        if dry:
            self.stdout.write(f"[dry-run] ADM2 {name!r} pcode={pcode} dept={dept.name}")
            return

        with transaction.atomic():
            obj, created = Commune.objects.update_or_create(
                code_officiel=pcode[:64],
                defaults={
                    "name": name[:255],
                    "geom": mp,
                    "departement": dept,
                    "is_placeholder": False,
                },
            )
        stats["created" if created else "updated"] += 1
