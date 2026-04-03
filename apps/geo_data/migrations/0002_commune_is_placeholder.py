# Generated manually for placeholder communes seeding

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("geo_data", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="commune",
            name="is_placeholder",
            field=models.BooleanField(
                default=False,
                help_text="True pour les communes générées (seed) en attendant l'import officiel.",
                verbose_name="donnée factice",
            ),
        ),
    ]
