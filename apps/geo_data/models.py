from django.conf import settings
from django.contrib.gis.db import models


class Departement(models.Model):
    name = models.CharField("nom", max_length=255)
    code_officiel = models.CharField(
        "code administratif officiel (pcode HDX / COD)",
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Ex. pcode ADM1 OCHA (ex. BJ-XX). Idempotence import HDX.",
    )
    geom = models.MultiPolygonField(srid=4326)

    class Meta:
        ordering = ["name"]
        verbose_name = "département"
        verbose_name_plural = "départements"

    def __str__(self):
        return self.name


class Commune(models.Model):
    name = models.CharField("nom", max_length=255)
    code_officiel = models.CharField(
        "code administratif officiel (pcode HDX / COD)",
        max_length=64,
        blank=True,
        null=True,
        unique=True,
        db_index=True,
        help_text="Ex. pcode ADM2 OCHA (ex. BJ-XX-XXX). Clé d’import HDX.",
    )
    geom = models.MultiPolygonField(srid=4326)
    departement = models.ForeignKey(
        Departement,
        on_delete=models.CASCADE,
        related_name="communes",
        verbose_name="département",
    )
    is_placeholder = models.BooleanField(
        "donnée factice",
        default=False,
        help_text="True = seed dev uniquement ; import officiel → False. "
        "API liste/GeoJSON masque les True si ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES est False.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "commune"
        verbose_name_plural = "communes"

    def __str__(self):
        return self.name


class Zone(models.Model):
    """
    Arrondissement municipal (OSM admin_level=8).
    Rattaché spatialement à une Commune via import (centroïde dans la commune).
    """

    class LandUseType(models.TextChoices):
        RESIDENTIAL = "residential", "Résidentiel"
        COMMERCIAL = "commercial", "Commercial"
        GREEN = "green", "Espace vert"

    commune = models.ForeignKey(
        Commune,
        on_delete=models.CASCADE,
        related_name="zones",
        verbose_name="commune",
    )
    name = models.CharField("nom", max_length=255)
    geom = models.MultiPolygonField(srid=4326)
    osm_id = models.CharField(
        "identifiant OSM",
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        help_text="Ex. relation/123456 — pour réimport idempotent.",
    )
    type_zone = models.CharField(
        "type d’usage (land use)",
        max_length=32,
        choices=LandUseType.choices,
        blank=True,
        null=True,
        db_index=True,
        help_text="Usage du sol pour filtres Atlas (Résidentiel / Commercial / Espace vert).",
    )

    class Meta:
        ordering = ["name"]
        unique_together = [["commune", "name"]]
        verbose_name = "zone (arrondissement)"
        verbose_name_plural = "zones (arrondissements)"

    def __str__(self):
        return self.name


class Quartier(models.Model):
    """
    Quartier (OSM admin_level=10).
    """

    commune = models.ForeignKey(
        Commune,
        on_delete=models.CASCADE,
        related_name="quartiers",
        verbose_name="commune",
    )
    name = models.CharField("nom", max_length=255)
    geom = models.MultiPolygonField(srid=4326)
    osm_id = models.CharField(
        "identifiant OSM",
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        help_text="Ex. relation/123456 — pour réimport idempotent.",
    )

    class Meta:
        ordering = ["name"]
        unique_together = [["commune", "name"]]
        verbose_name = "quartier"
        verbose_name_plural = "quartiers"

    def __str__(self):
        return self.name


class PointInteret(models.Model):
    """
    Point d'intérêt (POI) : rattachement spatial aux quartiers / communes
    via import (geom__covers).
    """

    class Category(models.TextChoices):
        HEALTH = "health", "Santé"
        MARKET = "market", "Marché"
        TRANSPORT = "transport", "Transport"
        EDUCATION = "education", "Éducation"
        CULTURE = "culture", "Culture"
        ADMIN = "admin", "Administration"
        OTHER = "other", "Autre"

    name = models.CharField("nom", max_length=255)
    category = models.CharField(
        "catégorie",
        max_length=32,
        choices=Category.choices,
        default=Category.OTHER,
    )
    geom = models.PointField(srid=4326)
    commune = models.ForeignKey(
        Commune,
        on_delete=models.CASCADE,
        related_name="points_interet",
        verbose_name="commune",
        null=True,
        blank=True,
    )
    quartier = models.ForeignKey(
        Quartier,
        on_delete=models.SET_NULL,
        related_name="points_interet",
        verbose_name="quartier",
        null=True,
        blank=True,
    )
    external_id = models.CharField(
        "identifiant externe",
        max_length=128,
        blank=True,
        null=True,
        unique=True,
        help_text="Clé idempotente (ex. OSM node id) pour réimport.",
    )
    source = models.CharField(
        "source",
        max_length=64,
        default="OSM",
        help_text="Origine métadonnée (ex. OSM, import manuel).",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "point d'intérêt"
        verbose_name_plural = "points d'intérêt"
        indexes = [
            models.Index(fields=["commune", "category"], name="geo_poi_commune_cat_idx"),
        ]

    def __str__(self):
        return self.name


class HydroZone(models.Model):
    """
    Surfaces hydrologiques / aléas (polygones) pour calcul serveur d’intersection avec les communes.
    """

    name = models.CharField("nom", max_length=255, blank=True)
    geom = models.MultiPolygonField(srid=4326)
    source = models.CharField(max_length=64, default="import")

    class Meta:
        ordering = ["name"]
        verbose_name = "zone hydrologique"
        verbose_name_plural = "zones hydrologiques"

    def __str__(self):
        return self.name or f"Hydro #{self.pk}"


class ImportLog(models.Model):
    """Trace d’exécution des commandes import_* (observabilité Super-Admin)."""

    created_at = models.DateTimeField(auto_now_add=True)
    command_name = models.CharField(max_length=128)
    file_name = models.CharField(max_length=512, blank=True)
    success_count = models.PositiveIntegerField(default=0)
    error_log = models.TextField(blank=True)
    admin_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="geo_import_logs",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "journal d’import"
        verbose_name_plural = "journaux d’import"

    def __str__(self):
        return f"{self.command_name} @ {self.created_at:%Y-%m-%d %H:%M}"
