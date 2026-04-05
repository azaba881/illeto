from django.urls import path

from . import views

app_name = "website"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("cartes/", views.CartesView.as_view(), name="cartes"),
    path("atlas/", views.AtlasView.as_view(), name="atlas"),
    path(
        "atlas/export/capture/",
        views.AtlasExportView.as_view(),
        name="atlas_export_capture",
    ),
    path("a-propos/", views.AProposView.as_view(), name="a_propos"),
    path("contact/", views.ContactView.as_view(), name="contact"),
    path("faq/", views.FaqView.as_view(), name="faq"),
    path("partenaire/", views.PartenaireView.as_view(), name="partenaire"),
]
