import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geo_data", "0004_point_interet"),
        ("accounts", "0004_user_favorite_and_activity_logs"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_commune",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="last_consulted_by_users",
                to="geo_data.commune",
                verbose_name="dernière commune consultée (Atlas)",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="subscription_valid_until",
            field=models.DateField(
                blank=True,
                help_text="Laisser vide pour calculer une date par défaut selon le type de compte.",
                null=True,
                verbose_name="fin de validité de l’abonnement",
            ),
        ),
        migrations.CreateModel(
            name="AnnualTerritoryReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("population_est", models.PositiveIntegerField(verbose_name="population estimée")),
                ("quartiers_count", models.PositiveIntegerField(verbose_name="nombre de quartiers")),
                ("flood_zone_percent", models.FloatField(verbose_name="part zone inondable (%)")),
                (
                    "commune",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="annual_reports",
                        to="geo_data.commune",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="annual_reports",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "rapport territorial",
                "verbose_name_plural": "rapports territoriaux",
                "ordering": ["-created_at"],
            },
        ),
    ]
