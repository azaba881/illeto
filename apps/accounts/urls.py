from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "api/atlas/simulate-professional/",
        views.simulate_atlas_professional,
        name="simulate_atlas_professional",
    ),
    path("api/commune-log/", views.log_commune_view, name="api_commune_log"),
    path("api/export-log/", views.log_export_view, name="api_export_log"),
    path("login/", views.AccountsLoginView.as_view(), name="login"),
    path("logout/", views.AccountsLogoutView.as_view(), name="logout"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("dashboard/", views.dashboard_root_redirect, name="dashboard_root"),
    path("dashboard/client/", views.dashboard_home, name="dashboard_client"),
    path("dashboard/cartotheque/", views.dashboard_library, name="dashboard_library"),
    path("dashboard/boutique/", views.DashboardStoreView.as_view(), name="dashboard_store"),
    path("dashboard/facturation/", views.dashboard_billing, name="dashboard_billing"),
    path("dashboard/parametres/", views.dashboard_settings, name="dashboard_settings"),
    path(
        "dashboard/mot-de-passe/",
        views.DashboardPasswordChangeView.as_view(),
        name="dashboard_password_change",
    ),
    path("dashboard/rapports/", views.dashboard_reports, name="dashboard_reports"),
    path("dashboard/inventaire/", views.dashboard_inventory, name="dashboard_inventory"),
    path(
        "dashboard/inventaire/export.csv",
        views.dashboard_inventory_export,
        name="dashboard_inventory_export",
    ),
]
