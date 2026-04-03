import django.contrib.gis.db.models.fields
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geo_data", "0004_point_interet"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="HydroZone",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(blank=True, max_length=255, verbose_name="nom")),
                (
                    "geom",
                    django.contrib.gis.db.models.fields.MultiPolygonField(srid=4326),
                ),
                ("source", models.CharField(default="import", max_length=64)),
            ],
            options={
                "verbose_name": "zone hydrologique",
                "verbose_name_plural": "zones hydrologiques",
                "ordering": ["name"],
            },
        ),
        migrations.CreateModel(
            name="ImportLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("command_name", models.CharField(max_length=128)),
                ("file_name", models.CharField(blank=True, max_length=512)),
                ("success_count", models.PositiveIntegerField(default=0)),
                ("error_log", models.TextField(blank=True)),
                (
                    "admin_user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="geo_import_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "journal d’import",
                "verbose_name_plural": "journaux d’import",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="pointinteret",
            name="source",
            field=models.CharField(
                default="OSM",
                help_text="Origine métadonnée (ex. OSM, import manuel).",
                max_length=64,
                verbose_name="source",
            ),
        ),
        migrations.AddIndex(
            model_name="pointinteret",
            index=models.Index(
                fields=["commune", "category"],
                name="geo_poi_commune_cat_idx",
            ),
        ),
    ]
