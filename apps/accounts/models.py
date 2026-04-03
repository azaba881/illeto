from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class UserType(models.TextChoices):
        STUDENT = "STUDENT", _("Étudiant / grand public")
        PROFESSIONAL = "PROFESSIONAL", _("Professionnel")
        INSTITUTION = "INSTITUTION", _("Institution")

    email = models.EmailField(_("email address"), unique=True)
    is_enterprise = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=32, blank=True)
    user_type = models.CharField(
        max_length=32,
        choices=UserType.choices,
        default=UserType.STUDENT,
        db_index=True,
    )
    favorite_commune = models.ForeignKey(
        "geo_data.Commune",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="favorited_by_users",
        verbose_name=_("commune favorite (décideur)"),
    )
    last_commune = models.ForeignKey(
        "geo_data.Commune",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="last_consulted_by_users",
        verbose_name=_("dernière commune consultée (Atlas)"),
    )
    subscription_valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("fin de validité de l’abonnement"),
        help_text=_("Laisser vide pour calculer une date par défaut selon le type de compte."),
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    def __str__(self):
        return self.email


class ExportLog(models.Model):
    """Un enregistrement par téléchargement / export (Atlas, API, etc.)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="export_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    kind = models.CharField(max_length=32, default="unknown")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("journal d’export")
        verbose_name_plural = _("journaux d’export")


class CommuneSearchLog(models.Model):
    """Historique des communes consultées (Atlas, filtres)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="commune_searches",
    )
    commune = models.ForeignKey(
        "geo_data.Commune",
        on_delete=models.CASCADE,
        related_name="search_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
        ]


class ShapefileLibraryEntry(models.Model):
    """Exports Shapefile natifs stockés côté historique (référence métier)."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="shapefile_entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    territory_type = models.CharField(max_length=16)
    territory_id = models.PositiveIntegerField()
    label = models.CharField(max_length=255)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("export Shapefile")
        verbose_name_plural = _("exports Shapefile")


class AnnualTerritoryReport(models.Model):
    """
    Rapport territorial généré (synthèse : population estimée, quartiers, zone inondable).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="annual_reports",
    )
    commune = models.ForeignKey(
        "geo_data.Commune",
        on_delete=models.CASCADE,
        related_name="annual_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    population_est = models.PositiveIntegerField(
        verbose_name=_("population estimée"),
    )
    quartiers_count = models.PositiveIntegerField(
        verbose_name=_("nombre de quartiers"),
    )
    flood_zone_percent = models.FloatField(
        verbose_name=_("part zone inondable (%)"),
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("rapport territorial")
        verbose_name_plural = _("rapports territoriaux")
