from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    # Django exige le chemin Python complet du package ; le label d’app reste « accounts ».
    name = "apps.accounts"
