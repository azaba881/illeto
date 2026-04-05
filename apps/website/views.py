import json
import logging
from io import BytesIO

from django.conf import settings
from django.http import FileResponse, JsonResponse
from django.views import View
from django.views.generic import TemplateView

from apps.accounts.models import User

logger = logging.getLogger(__name__)


def _validate_atlas_export_payload(body: dict) -> str | None:
    fmt = (body.get("format") or "png").lower()
    if fmt not in ("png", "pdf"):
        return "Format inconnu (png ou pdf attendu)."
    if not body.get("fit_geometry"):
        c = body.get("center") or {}
        try:
            float(c.get("lat"))
            float(c.get("lng"))
            float(body.get("zoom"))
        except (TypeError, ValueError):
            return "Champs center (lat, lng) et zoom requis si pas de fit_geometry."
    clip = body.get("clip") or {}
    try:
        w = float(clip.get("width", 0))
        h = float(clip.get("height", 0))
        if w < 16 or h < 16:
            return "Zone de capture (clip) trop petite."
        max_c = int(getattr(settings, "ILLETO_ATLAS_EXPORT_MAX_CLIP", 2400))
        if w > max_c or h > max_c:
            return f"Zone de capture trop grande (max {max_c}px)."
        float(clip.get("x", 0))
        float(clip.get("y", 0))
    except (TypeError, ValueError):
        return "clip (x, y, width, height) invalide."
    vp = body.get("viewport") or {}
    if vp:
        try:
            vww = float(vp.get("width", 0))
            vhh = float(vp.get("height", 0))
            if vww < 320 or vhh < 320:
                return "viewport (width, height) trop petit."
        except (TypeError, ValueError):
            return "viewport invalide."
    return None


def _merge_atlas_export_nom_departement(body: dict) -> None:
    if (body.get("nom_departement") or "").strip():
        return
    ms = body.get("map_state")
    if not isinstance(ms, dict):
        return
    dn = ms.get("departmentName")
    if dn:
        body["nom_departement"] = str(dn).strip()


def _merge_atlas_export_user_label(request, body: dict) -> None:
    """Renseigne l’utilisateur pour le PDF et la clé de cache (évite collisions entre comptes)."""
    if (body.get("export_user_label") or "").strip():
        return
    u = getattr(request, "user", None)
    if u and u.is_authenticated:
        fn = (u.get_full_name() or "").strip()
        body["export_user_label"] = fn or (getattr(u, "email", None) or "") or str(
            u.pk
        )


def _merge_atlas_export_hide_selection_style(body: dict) -> None:
    """
    Carte « pure » côté Playwright si aucun territoire dans map_state :
    pas de surbrillance export même si le client omet la clé.
    """
    ms = body.get("map_state")
    if not isinstance(ms, dict):
        return
    has_territory = bool(
        ms.get("departmentId")
        or ms.get("communeId")
        or (ms.get("neighborhood") not in (None, ""))
    )
    if not has_territory:
        body["hideSelectionStyle"] = True


class AtlasExportView(View):
    """POST JSON → PNG ou PDF (capture Playwright côté serveur)."""

    http_method_names = ["post"]

    def post(self, request):
        if not getattr(settings, "ILLETO_PLAYWRIGHT_EXPORT_ENABLED", False):
            return JsonResponse(
                {
                    "detail": "Export haute définition désactivé sur ce serveur "
                    "(ILLETO_PLAYWRIGHT_EXPORT_ENABLED)."
                },
                status=503,
            )
        try:
            body = json.loads(request.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"detail": "Corps JSON invalide."}, status=400)
        if not isinstance(body, dict):
            return JsonResponse({"detail": "JSON objet attendu."}, status=400)

        err = _validate_atlas_export_payload(body)
        if err:
            return JsonResponse({"detail": err}, status=400)

        _merge_atlas_export_hide_selection_style(body)
        _merge_atlas_export_nom_departement(body)
        _merge_atlas_export_user_label(request, body)

        try:
            from apps.website.utils.export_service import capture_atlas_export

            data, mime, fname = capture_atlas_export(request, body)
        except ValueError as e:
            return JsonResponse({"detail": str(e)}, status=400)
        except RuntimeError as e:
            logger.warning("Atlas export Playwright: %s", e)
            return JsonResponse({"detail": str(e)}, status=503)
        except Exception:
            logger.exception("Atlas export capture")
            return JsonResponse(
                {"detail": "Erreur serveur lors de la capture."},
                status=500,
            )

        resp = FileResponse(BytesIO(data), as_attachment=True, filename=fname)
        resp["Content-Type"] = mime
        return resp


class IndexView(TemplateView):
    template_name = "website/index.html"


class CartesView(TemplateView):
    template_name = "website/cartes.html"


class AtlasView(TemplateView):
    template_name = "website/atlas.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        u = self.request.user
        if u.is_authenticated:
            ctx["atlas_user_type"] = getattr(
                u, "user_type", User.UserType.STUDENT
            )
        else:
            ctx["atlas_user_type"] = "PUBLIC"
        ctx["mapbox_access_token"] = getattr(
            settings, "ILLETO_MAPBOX_ACCESS_TOKEN", ""
        ) or ""
        return ctx


class AProposView(TemplateView):
    template_name = "website/a_propos.html"


class ContactView(TemplateView):
    template_name = "website/contact.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        commune = (self.request.GET.get("commune") or "").strip()
        sujet = (self.request.GET.get("sujet") or "").strip().lower()
        lines = []
        if commune:
            lines.append(f"Commune concernée : {commune}")
        if sujet == "crowd":
            lines.append(
                "Contribution crowdsourcing : merci d’indiquer les sources ou fichiers utiles "
                "pour vectoriser les quartiers / zones manquants pour cette commune."
            )
        ctx["contact_prefill"] = "\n\n".join(lines) if lines else ""
        if sujet == "crowd":
            ctx["contact_subject_value"] = "crowd"
        return ctx


class FaqView(TemplateView):
    template_name = "website/faq.html"


class PartenaireView(TemplateView):
    template_name = "website/partenaire.html"
