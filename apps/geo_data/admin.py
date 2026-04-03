from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import Commune, Departement, HydroZone, ImportLog, PointInteret, Zone

User = get_user_model()


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "command_name", "file_name", "success_count", "admin_user")
    list_filter = ("command_name",)
    search_fields = ("file_name", "error_log")
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(HydroZone)
class HydroZoneAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "source")
    search_fields = ("name",)


@admin.register(PointInteret)
class PointInteretAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "commune", "source")
    list_filter = ("category", "source")
    search_fields = ("name", "external_id")


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ("name", "code_officiel")
    search_fields = ("name", "code_officiel")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "commune", "type_zone")
    list_filter = ("type_zone", "commune__departement")
    search_fields = ("name", "commune__name")


@admin.register(Commune)
class CommuneAdmin(admin.ModelAdmin):
    list_display = ("name", "code_officiel", "departement", "is_placeholder")
    list_filter = ("is_placeholder", "departement")
    search_fields = ("name", "code_officiel")
