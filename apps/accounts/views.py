import csv
import json
from datetime import timedelta
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import CreateView, TemplateView

from .forms import (
    IlletoAuthenticationForm,
    IlletoPasswordChangeForm,
    ProfileForm,
    RegisterForm,
)
from .models import (
    AnnualTerritoryReport,
    CommuneSearchLog,
    ExportLog,
    ShapefileLibraryEntry,
    User,
)


def _is_pro_user(user) -> bool:
    return getattr(user, "user_type", None) in (
        User.UserType.PROFESSIONAL,
        User.UserType.INSTITUTION,
    )


def _sidebar_include_path(user) -> str:
    return (
        "entreprise/includes/sidebar.html"
        if _is_pro_user(user)
        else "dashboard/includes/sidebar.html"
    )


def _user_plan_label(user) -> str:
    mapping = {
        User.UserType.STUDENT: "Étudiant / Exploration",
        User.UserType.PROFESSIONAL: "Professionnel",
        User.UserType.INSTITUTION: "Institution",
    }
    return mapping.get(getattr(user, "user_type", None), "Exploration")


def _base_dashboard_context(request, extra=None):
    ctx = {
        "dashboard_sidebar_include": _sidebar_include_path(request.user),
        "user_display_name": request.user.get_full_name() or request.user.email,
        "user_plan_label": _user_plan_label(request.user),
        "dashboard_topbar_role": (
            "Décideur" if _is_pro_user(request.user) else "Client"
        ),
    }
    if extra:
        ctx.update(extra)
    return ctx


def _active_commune_for_user(user):
    """
    Commune « active » : dernière consultée (Atlas), sinon favorite, sinon dernière entrée d’historique.
    """
    from apps.geo_data.models import Commune

    if getattr(user, "last_commune_id", None):
        c = (
            Commune.objects.select_related("departement")
            .filter(pk=user.last_commune_id)
            .first()
        )
        if c:
            return c
    if getattr(user, "favorite_commune_id", None):
        c = (
            Commune.objects.select_related("departement")
            .filter(pk=user.favorite_commune_id)
            .first()
        )
        if c:
            return c
    row = (
        CommuneSearchLog.objects.filter(user=user)
        .order_by("-created_at")
        .select_related("commune__departement")
        .first()
    )
    return row.commune if row else None


def _commune_context_note(user, commune):
    if not commune:
        return ""
    if getattr(user, "last_commune_id", None) == commune.pk:
        return "Dernière commune consultée depuis l’Atlas."
    if getattr(user, "favorite_commune_id", None) == commune.pk:
        return "Commune favorite (paramètres)."
    return "Dérivée de votre historique de recherche."


def _metrics_for_territory_report(commune):
    """Indicateurs rapport annuel — aléa inondation via PostGIS (utils.flood_percent_for_report)."""
    from apps.geo_data.models import Quartier
    from apps.geo_data.utils import flood_percent_for_report

    q_count = Quartier.objects.filter(commune=commune).count()
    population_est = 8000 + (commune.pk % 97) * 250
    flood_zone_percent = flood_percent_for_report(commune.pk)
    return {
        "population_est": population_est,
        "quartiers_count": q_count,
        "flood_zone_percent": flood_zone_percent,
    }


def _subscription_valid_until_display(user):
    if user.subscription_valid_until:
        return user.subscription_valid_until.strftime("%d/%m/%Y")
    if user.user_type == User.UserType.STUDENT:
        return "Sans limite (exploration)"
    if user.date_joined:
        end = user.date_joined.date() + timedelta(days=365)
        return end.strftime("%d/%m/%Y")
    return "—"


def _student_home_context(user):
    total_exports = ExportLog.objects.filter(user=user).count()
    maps_viewed_count = CommuneSearchLog.objects.filter(user=user).count()
    recent_qs = (
        CommuneSearchLog.objects.filter(user=user)
        .select_related("commune")
        .order_by("-created_at")[:5]
    )
    recent_searches = [
        {
            "id": row.commune_id,
            "name": row.commune.name,
            "at": row.created_at,
        }
        for row in recent_qs
    ]
    return {
        "total_exports": total_exports,
        "maps_viewed_count": maps_viewed_count,
        "recent_searches": recent_searches,
        "is_limited": user.user_type == User.UserType.STUDENT,
    }


def _enterprise_home_context(user):
    from apps.geo_data.models import PointInteret
    from apps.geo_data.utils import flood_metrics_for_commune

    commune = _active_commune_for_user(user)
    commune_stats = None
    if commune:
        agg = PointInteret.objects.filter(commune=commune).aggregate(
            health=Count("id", filter=Q(category=PointInteret.Category.HEALTH)),
            market=Count("id", filter=Q(category=PointInteret.Category.MARKET)),
            total=Count("id"),
        )
        h = agg["health"] or 0
        m = agg["market"] or 0
        t = agg["total"] or 0
        fm = flood_metrics_for_commune(commune.pk)
        flood_pct = float(fm.get("flood_percent") or 0) if fm.get("ok") else 0.0
        risk_score = min(100, int(flood_pct + min(40, h * 2 + m)))
        commune_stats = {
            "commune_name": commune.name,
            "poi_health": h,
            "poi_market": m,
            "poi_total": t,
            "risk_score": risk_score,
            "flood_percent": flood_pct,
            "flood_source": fm.get("source", "") if fm.get("ok") else "",
            "commune_note": _commune_context_note(user, commune),
        }
    inventory_count = ShapefileLibraryEntry.objects.filter(user=user).count()
    billing_status = {
        "tier": user.user_type,
        "label": (
            "Institution"
            if user.user_type == User.UserType.INSTITUTION
            else "Professionnel (Décideur)"
        ),
        "is_institution": user.user_type == User.UserType.INSTITUTION,
        "subtitle": (
            "Offre institutionnelle"
            if user.user_type == User.UserType.INSTITUTION
            else "Atlas certifié · exports natifs"
        ),
    }
    account_badge = (
        "Institution — Certifiée"
        if user.user_type == User.UserType.INSTITUTION
        else "Compte Professionnel — Certifié"
    )
    return {
        "commune_stats": commune_stats,
        "inventory_count": inventory_count,
        "billing_status": billing_status,
        "account_badge": account_badge,
    }


@login_required
def dashboard_home(request):
    """
    Tableau de bord : STUDENT → templates/dashboard/ ; PRO / INSTITUTION → templates/entreprise/.
    Superuser → admin Django.
    """
    user = request.user
    if user.is_superuser:
        return redirect("admin:index")
    if _is_pro_user(user):
        ctx = _enterprise_home_context(user)
        ctx.update(_base_dashboard_context(request))
        return render(request, "entreprise/client-home.html", ctx)
    ctx = _student_home_context(user)
    ctx.update(_base_dashboard_context(request))
    return render(request, "dashboard/client-home.html", ctx)


def dashboard_root_redirect(request):
    """Alias /dashboard/ → /dashboard/client/"""
    return redirect("accounts:dashboard_client")


@login_required
def dashboard_library(request):
    if request.user.is_superuser:
        return redirect("admin:index")
    ctx = _base_dashboard_context(request)
    if _is_pro_user(request.user):
        ctx["library_entries"] = list(
            ShapefileLibraryEntry.objects.filter(user=request.user).order_by("-created_at")[
                :200
            ]
        )
        return render(request, "entreprise/client-library.html", ctx)
    ctx["export_logs"] = list(
        ExportLog.objects.filter(user=request.user).order_by("-created_at")[:100]
    )
    return render(request, "dashboard/client-library.html", ctx)


@login_required
def dashboard_settings(request):
    if request.user.is_superuser:
        return redirect("admin:index")
    from apps.geo_data.models import Commune

    if request.method == "POST":
        if (
            request.POST.get("form_action") == "favorite_commune"
            and _is_pro_user(request.user)
        ):
            raw = (request.POST.get("favorite_commune_id") or "").strip()
            if raw.isdigit() and Commune.objects.filter(pk=int(raw)).exists():
                request.user.favorite_commune_id = int(raw)
            else:
                request.user.favorite_commune_id = None
            request.user.save(update_fields=["favorite_commune_id"])
            messages.success(request, "Commune de travail enregistrée.")
            return redirect("accounts:dashboard_settings")

        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            if _is_pro_user(request.user) and "favorite_commune_id" in request.POST:
                raw = (request.POST.get("favorite_commune_id") or "").strip()
                if raw.isdigit() and Commune.objects.filter(pk=int(raw)).exists():
                    request.user.favorite_commune_id = int(raw)
                else:
                    request.user.favorite_commune_id = None
                request.user.save(update_fields=["favorite_commune_id"])
            messages.success(request, "Profil enregistré.")
            return redirect("accounts:dashboard_settings")
    else:
        form = ProfileForm(instance=request.user)

    ctx = _base_dashboard_context(request)
    ctx["profile_form"] = form
    ctx["commune_choices"] = Commune.objects.select_related("departement").order_by(
        "departement__name", "name"
    )[:500]
    tpl = (
        "entreprise/client-settings.html"
        if _is_pro_user(request.user)
        else "dashboard/client-settings.html"
    )
    return render(request, tpl, ctx)


@login_required
def dashboard_billing(request):
    if request.user.is_superuser:
        return redirect("admin:index")
    ctx = _base_dashboard_context(request)
    ut = request.user.user_type
    ctx["billing_status"] = {
        "tier": ut,
        "label": _user_plan_label(request.user),
        "is_institution": ut == User.UserType.INSTITUTION,
        "subtitle": (
            "Offre institutionnelle — exports certifiés et suivi dédié"
            if ut == User.UserType.INSTITUTION
            else (
                "Exploration — téléchargements et crédits selon conditions"
                if ut == User.UserType.STUDENT
                else "Atlas certifié · exports Shapefile natifs"
            )
        ),
    }
    limits = getattr(settings, "ILLETO_PLAN_EXPORT_LIMITS", {})
    ctx["plan_export_limit_label"] = limits.get(ut, "")
    ctx["subscription_valid_until_display"] = _subscription_valid_until_display(
        request.user
    )
    tpl = (
        "entreprise/client-billing.html"
        if _is_pro_user(request.user)
        else "dashboard/client-billing.html"
    )
    return render(request, tpl, ctx)


@login_required
def dashboard_reports(request):
    if not _is_pro_user(request.user):
        raise PermissionDenied(
            "Espace réservé aux comptes Professionnel ou Institution."
        )
    from apps.geo_data.models import Commune

    if request.method == "POST":
        raw = (request.POST.get("commune_id") or "").strip()
        if not raw.isdigit():
            messages.error(request, "Sélectionnez une commune valide.")
            return redirect("accounts:dashboard_reports")
        commune = get_object_or_404(
            Commune.objects.select_related("departement"), pk=int(raw)
        )
        m = _metrics_for_territory_report(commune)
        AnnualTerritoryReport.objects.create(
            user=request.user,
            commune=commune,
            population_est=m["population_est"],
            quartiers_count=m["quartiers_count"],
            flood_zone_percent=m["flood_zone_percent"],
        )
        messages.success(
            request,
            f"Rapport enregistré pour {commune.departement.name} — {commune.name}.",
        )
        return redirect("accounts:dashboard_reports")

    generated_reports = list(
        AnnualTerritoryReport.objects.filter(user=request.user)
        .select_related("commune__departement")
        .order_by("-created_at")[:100]
    )
    commune_opts = Commune.objects.select_related("departement").order_by(
        "departement__name", "name"
    )[:500]
    active_c = _active_commune_for_user(request.user)
    ctx = _base_dashboard_context(
        request,
        {
            "shapefile_api_pattern": "/geo/api/export/shapefile/<territory_type>/<territory_id>/",
            "atlas_url": reverse("website:atlas"),
            "generated_reports": generated_reports,
            "report_commune_choices": commune_opts,
            "default_report_commune_id": active_c.pk if active_c else None,
        },
    )
    return render(request, "entreprise/reports.html", ctx)


@login_required
def dashboard_inventory(request):
    if not _is_pro_user(request.user):
        raise PermissionDenied(
            "Espace réservé aux comptes Professionnel ou Institution."
        )
    from apps.geo_data.models import Commune, PointInteret

    raw_cid = (request.GET.get("commune_id") or "").strip()
    commune = None
    if raw_cid.isdigit():
        commune = Commune.objects.filter(pk=int(raw_cid)).select_related("departement").first()
    if commune is None:
        commune = _active_commune_for_user(request.user)
    pois = []
    if commune:
        pois = list(
            PointInteret.objects.filter(commune=commune)
            .select_related("quartier")
            .order_by("category", "name")[:500]
        )
    ctx = _base_dashboard_context(
        request,
        {
            "selected_commune": commune,
            "poi_list": pois,
            "commune_choices": Commune.objects.select_related("departement").order_by(
                "departement__name", "name"
            )[:400],
            "commune_note": _commune_context_note(request.user, commune) if commune else "",
        },
    )
    return render(request, "entreprise/inventory.html", ctx)


@login_required
@require_GET
def dashboard_inventory_export(request):
    if not _is_pro_user(request.user):
        raise PermissionDenied(
            "Espace réservé aux comptes Professionnel ou Institution."
        )
    from apps.geo_data.models import Commune, PointInteret

    raw_cid = (request.GET.get("commune_id") or "").strip()
    commune = None
    if raw_cid.isdigit():
        commune = Commune.objects.filter(pk=int(raw_cid)).select_related("departement").first()
    if commune is None:
        commune = _active_commune_for_user(request.user)
    if commune is None:
        messages.error(request, "Aucune commune active : sélectionnez une commune dans l’inventaire.")
        return redirect("accounts:dashboard_inventory")

    pois = (
        PointInteret.objects.filter(commune=commune)
        .select_related("quartier")
        .order_by("category", "name")
    )
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    slug = f"{commune.pk}_{commune.name}"[:60]
    response["Content-Disposition"] = (
        f'attachment; filename="inventaire_poi_{slug}.csv"'
    )
    w = csv.writer(response)
    w.writerow(
        ["nom", "categorie", "lon", "lat", "source", "quartier", "commune", "departement"]
    )
    for poi in pois:
        w.writerow(
            [
                poi.name,
                poi.get_category_display(),
                f"{poi.geom.x:.6f}" if poi.geom else "",
                f"{poi.geom.y:.6f}" if poi.geom else "",
                getattr(poi, "source", "") or "",
                poi.quartier.name if poi.quartier else "",
                commune.name,
                commune.departement.name if commune.departement else "",
            ]
        )
    return response


class DashboardPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = IlletoPasswordChangeForm
    template_name = "accounts/dashboard_change_password.html"
    success_url = reverse_lazy("accounts:dashboard_settings")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_dashboard_context(self.request))
        return ctx

    def form_valid(self, form):
        messages.success(self.request, "Mot de passe mis à jour.")
        return super().form_valid(form)


class RegisterView(CreateView):
    form_class = RegisterForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("website:index")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(
            self.request,
            self.object,
            backend=settings.AUTHENTICATION_BACKENDS[0],
        )
        return response


class AccountsLoginView(LoginView):
    form_class = IlletoAuthenticationForm
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        user = self.request.user
        if user.is_superuser:
            return "/admin/"
        return reverse("accounts:dashboard_client")


class AccountsLogoutView(LogoutView):
    next_page = reverse_lazy("website:index")


class EnterpriseRequiredMixin(UserPassesTestMixin):
    """Boutique : entreprise déclarée ou profil décideur / institution."""

    def test_func(self):
        u = self.request.user
        return bool(
            getattr(u, "is_enterprise", False)
            or _is_pro_user(u)
        )

    def handle_no_permission(self):
        return redirect("accounts:dashboard_client")


class DashboardStoreView(LoginRequiredMixin, EnterpriseRequiredMixin, TemplateView):
    def get_template_names(self):
        if _is_pro_user(self.request.user):
            return ["entreprise/client-store.html"]
        return ["dashboard/client-store.html"]

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_base_dashboard_context(self.request))
        u = self.request.user
        ut = u.user_type
        ctx["current_plan_key"] = ut
        ctx["plan_tiers"] = [
            {
                "key": User.UserType.STUDENT,
                "title": "Étudiant / Exploration",
                "price": "Gratuit",
                "features": "Atlas, consultation des cartes, exports basiques.",
                "is_current": ut == User.UserType.STUDENT,
            },
            {
                "key": User.UserType.PROFESSIONAL,
                "title": "Professionnel",
                "price": "Sur devis",
                "features": "Shapefile serveur, rapports territoriaux, inventaire POI complet.",
                "is_current": ut == User.UserType.PROFESSIONAL,
            },
            {
                "key": User.UserType.INSTITUTION,
                "title": "Institution",
                "price": "Contrat annuel",
                "features": "Multi-utilisateurs, support dédié, données certifiées.",
                "is_current": ut == User.UserType.INSTITUTION,
            },
        ]
        items = list(getattr(settings, "ILLETO_STORE_ITEMS", []))
        ctx["store_items"] = items
        ctx["store_departments"] = sorted({i["department"] for i in items})
        ctx["store_layer_types"] = sorted({i["layer_type"] for i in items})
        limits = getattr(settings, "ILLETO_PLAN_EXPORT_LIMITS", {})
        ctx["plan_export_limit_label"] = limits.get(ut, "")
        return ctx


@require_POST
@login_required
def log_commune_view(request):
    try:
        data = json.loads(request.body.decode())
        cid = int(data.get("commune_id"))
    except (ValueError, TypeError, json.JSONDecodeError, AttributeError):
        return JsonResponse({"ok": False, "detail": "commune_id invalide."}, status=400)
    from apps.geo_data.models import Commune

    if not Commune.objects.filter(pk=cid).exists():
        return JsonResponse({"ok": False, "detail": "Commune introuvable."}, status=404)
    CommuneSearchLog.objects.create(user=request.user, commune_id=cid)
    User.objects.filter(pk=request.user.pk).update(last_commune_id=cid)
    return JsonResponse({"ok": True})


@require_POST
@login_required
def log_export_view(request):
    try:
        data = json.loads(request.body.decode())
        kind = str(data.get("kind") or "unknown")[:32]
    except json.JSONDecodeError:
        return JsonResponse({"ok": False}, status=400)
    ExportLog.objects.create(user=request.user, kind=kind)
    return JsonResponse({"ok": True})


@require_POST
@login_required
def simulate_atlas_professional(request):
    """
    Simulation de paiement Atlas : passage en mode Professionnel (démo).
    """
    user = request.user
    user.user_type = User.UserType.PROFESSIONAL
    user.save(update_fields=["user_type"])
    return JsonResponse(
        {
            "ok": True,
            "user_type": user.user_type,
            "message": "Profil mis à jour — Mode Décideur activé.",
        }
    )
