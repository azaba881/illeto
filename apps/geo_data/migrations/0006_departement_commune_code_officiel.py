from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geo_data", "0005_hydro_importlog_poi_source_index"),
    ]

    operations = [
        migrations.AddField(
            model_name="departement",
            name="code_officiel",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Ex. pcode ADM1 OCHA (ex. BJ-XX). Idempotence import HDX.",
                max_length=64,
                null=True,
                unique=True,
                verbose_name="code administratif officiel (pcode HDX / COD)",
            ),
        ),
        migrations.AddField(
            model_name="commune",
            name="code_officiel",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Ex. pcode ADM2 OCHA (ex. BJ-XX-XXX). Clé d’import HDX.",
                max_length=64,
                null=True,
                unique=True,
                verbose_name="code administratif officiel (pcode HDX / COD)",
            ),
        ),
    ]
