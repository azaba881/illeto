"""Communes factices (développement)."""

from django.core.management.base import BaseCommand

from apps.geo_data.importers.internal.seed_dummy import run_seed_dummy_communes


class Command(BaseCommand):
    help = "Crée des communes is_placeholder (ou purge avec --purge-placeholders)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge-placeholders",
            action="store_true",
            dest="purge_placeholders",
        )

    def handle(self, *args, **options):
        if options["purge_placeholders"]:
            self.stdout.write(
                self.style.WARNING(
                    "ATTENTION : données de test — ne pas utiliser sur une base officielle."
                )
            )
        n, msg = run_seed_dummy_communes(options["purge_placeholders"])
        if msg and msg.startswith("purge"):
            self.stdout.write(self.style.WARNING("Supprimé : %s enregistrement(s)." % n))
            return
        if msg == "no_departements":
            self.stdout.write(self.style.ERROR("Aucun département en base."))
            return
        self.stdout.write(self.style.SUCCESS("%s commune(s) factice(s) créée(s)." % n))
