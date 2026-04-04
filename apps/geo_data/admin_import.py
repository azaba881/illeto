"""Vue Admin superuser : upload GeoJSON / KML et import synchrone."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from django import forms
from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse

from apps.geo_data.import_audit import record_import_run
from apps.geo_data.importers.osm.hydro_geojson import run_hydro_geojson_import
from apps.geo_data.importers.osm.poi_geojson import run_poi_geojson_import
from apps.geo_data.importers.universal.vector_runner import run_universal_import


class GeoImportForm(forms.Form):
    MODEL_CHOICES = [
        ("Departement", "Département (ADM1, polygones)"),
        ("Commune", "Commune (ADM2, polygones + département parent)"),
        ("Zone", "Zone / arrondissement (ADM3, polygones + commune parente)"),
        ("HydroZone", "Zone hydrologique (polygones)"),
        ("PointInteret", "Points d’intérêt (GeoJSON Point uniquement)"),
    ]

    upload = forms.FileField(
        label="Fichier",
        help_text="GeoJSON (.geojson, .json) ou KML / Shapefile via import universel (.kml, .shp).",
    )
    target_model = forms.ChoiceField(label="Modèle cible", choices=MODEL_CHOICES)
    name_field = forms.CharField(
        initial="name",
        max_length=128,
        help_text="Clé des propriétés GeoJSON ou nom du champ OGR.",
    )
    code_field = forms.CharField(
        required=False,
        max_length=128,
        help_text="Code officiel (Département/Commune) ou identifiant stable (ex. shapeID → osm_id pour Zone).",
    )
    departement = forms.ModelChoiceField(
        label="Département parent (Commune)",
        queryset=None,  # set in __init__
        required=False,
    )
    commune_parent = forms.ModelChoiceField(
        label="Commune parente (Zone / ADM3)",
        queryset=None,  # set in __init__
        required=False,
    )
    source_label = forms.CharField(
        required=False,
        initial="admin_upload",
        max_length=64,
        help_text="Valeur HydroZone.source (si applicable).",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.geo_data.models import Commune, Departement

        self.fields["departement"].queryset = Departement.objects.order_by("name")
        self.fields["commune_parent"].queryset = Commune.objects.select_related(
            "departement"
        ).order_by("departement__name", "name")


def _suffix_for_upload(fobj) -> str:
    name = (fobj.name or "").lower()
    for ext in (".geojson", ".json", ".kml", ".shp"):
        if name.endswith(ext):
            return ext
    return ".geojson"


def import_geo_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Réservé aux superutilisateurs.")
        return HttpResponseRedirect(reverse("admin:geo_data_importlog_changelist"))

    if request.method == "POST":
        form = GeoImportForm(request.POST, request.FILES)
        if form.is_valid():
            f = form.cleaned_data["upload"]
            model_key = form.cleaned_data["target_model"]
            name_f = form.cleaned_data["name_field"].strip() or "name"
            code_f = (form.cleaned_data["code_field"] or "").strip()
            dept = form.cleaned_data.get("departement")
            commune_parent = form.cleaned_data.get("commune_parent")
            src = (form.cleaned_data.get("source_label") or "admin_upload").strip()
            suf = _suffix_for_upload(f)

            err_lines: list[str] = []
            success = 0
            ran = False
            should_redirect = False

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suf)
            try:
                for chunk in f.chunks():
                    tmp.write(chunk)
                tmp.flush()
                tmp_path = Path(tmp.name)

                if model_key == "PointInteret":
                    if suf not in (".geojson", ".json"):
                        messages.error(
                            request,
                            "PointInteret : utilisez un GeoJSON de points (.geojson / .json).",
                        )
                    else:
                        ran = True
                elif model_key == "HydroZone":
                    if suf not in (".geojson", ".json"):
                        messages.error(
                            request,
                            "HydroZone : GeoJSON polygone (.geojson / .json).",
                        )
                    else:
                        ran = True
                elif model_key == "Commune":
                    if not dept:
                        messages.error(
                            request,
                            "Pour Commune, sélectionnez le département parent.",
                        )
                    else:
                        ran = True
                elif model_key == "Zone":
                    if not commune_parent:
                        messages.error(
                            request,
                            "Pour Zone (ADM3), sélectionnez la commune parente.",
                        )
                    elif suf not in (".geojson", ".json", ".kml", ".shp"):
                        messages.error(
                            request,
                            "Zone : GeoJSON, KML ou Shapefile (.geojson, .json, .kml, .shp).",
                        )
                    else:
                        ran = True
                elif model_key == "Departement":
                    if suf not in (".geojson", ".json", ".kml", ".shp"):
                        messages.error(
                            request,
                            "Département : GeoJSON, KML ou Shapefile.",
                        )
                    else:
                        ran = True
                else:
                    messages.error(
                        request,
                        "Modèle cible non géré : %s." % model_key,
                    )

                if ran:
                    try:
                        if model_key == "PointInteret":
                            c, u, sk = run_poi_geojson_import(
                                tmp_path,
                                dry_run=False,
                                name_field=name_f,
                            )
                            success = c + u
                            err_lines.append("Ignorés : %s" % sk)
                        elif model_key == "HydroZone":
                            cr, sk = run_hydro_geojson_import(
                                tmp_path, dry_run=False, source=src
                            )
                            success = cr
                            err_lines.append("Ignorés (géométrie) : %s" % sk)
                        elif model_key in ("Departement", "Commune", "Zone"):
                            total, errors = run_universal_import(
                                paths=[tmp_path],
                                model_name=model_key,
                                name_field=name_f,
                                code_field=code_f,
                                departement_pk=dept.pk if dept else None,
                                commune_pk=commune_parent.pk
                                if commune_parent
                                else None,
                                source_label=src,
                                dry_run=False,
                                encoding="utf-8",
                                layer_index=0,
                                stdout=None,
                                style=None,
                            )
                            success = total
                            err_lines.extend(errors[:100])
                        else:
                            raise AssertionError(
                                "Branche import manquante pour %r" % model_key
                            )

                        record_import_run(
                            command_name="admin_geo_import",
                            file_name=f.name[:512],
                            success_count=success,
                            error_lines=err_lines,
                            admin_user_id=request.user.pk,
                        )
                        if success:
                            messages.success(
                                request,
                                "Import terminé : %s enregistrement(s) écrit(s)."
                                % success,
                            )
                        elif not err_lines:
                            messages.warning(
                                request,
                                "Aucun enregistrement créé ou mis à jour.",
                            )
                        else:
                            messages.warning(
                                request,
                                "Import terminé avec des avertissements (voir le journal).",
                            )
                        should_redirect = True
                    except Exception as exc:
                        record_import_run(
                            command_name="admin_geo_import",
                            file_name=f.name[:512],
                            success_count=0,
                            error_lines=[str(exc)],
                            admin_user_id=request.user.pk,
                        )
                        messages.error(request, "Erreur : %s" % exc)
                        should_redirect = True
            finally:
                tmp.close()
                try:
                    os.unlink(tmp.name)
                except OSError:
                    pass

            if should_redirect:
                return HttpResponseRedirect(
                    reverse("admin:geo_data_importlog_changelist")
                )
    else:
        form = GeoImportForm()

    ctx = {
        **admin.site.each_context(request),
        "title": "Import géographique",
        "form": form,
    }
    return render(request, "admin/geo_data/importlog/import_geo.html", ctx)
