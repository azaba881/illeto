from django.conf import settings
from django.views.generic import TemplateView

from apps.accounts.models import User


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
