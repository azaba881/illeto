# Generated manually for Atlas land-use filters

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geo_data", "0006_departement_commune_code_officiel"),
    ]

    operations = [
        migrations.AddField(
            model_name="zone",
            name="type_zone",
            field=models.CharField(
                blank=True,
                choices=[
                    ("residential", "Résidentiel"),
                    ("commercial", "Commercial"),
                    ("green", "Espace vert"),
                ],
                db_index=True,
                help_text="Usage du sol (filtre Atlas). Vide = non classé.",
                max_length=32,
                null=True,
                verbose_name="type d’usage (land use)",
            ),
        ),
    ]
