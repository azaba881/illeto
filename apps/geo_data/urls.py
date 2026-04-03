from django.urls import path

from . import views

app_name = "geo_data"

urlpatterns = [
    path(
        "api/departements/",
        views.departement_geojson,
        name="api_departements",
    ),
    path(
        "api/communes/",
        views.communes_json,
        name="api_communes",
    ),
    path(
        "api/communes/geojson/",
        views.communes_geojson,
        name="api_communes_geojson",
    ),
    path(
        "api/communes/<int:commune_id>/flood-metrics/",
        views.commune_flood_metrics,
        name="api_commune_flood_metrics",
    ),
    path(
        "api/overpass/",
        views.overpass_proxy,
        name="api_overpass_proxy",
    ),
    path(
        "api/zones/geojson/",
        views.zones_geojson_by_commune,
        name="api_zones_geojson",
    ),
    path(
        "api/poi/geojson/",
        views.poi_geojson,
        name="api_poi_geojson",
    ),
    path(
        "api/poi/",
        views.poi_geojson,
        name="api_poi",
    ),
    path(
        "api/export/territory/",
        views.export_territory_geo_data,
        name="api_export_territory",
    ),
    path(
        "api/export/shapefile/<str:territory_type>/<int:territory_id>/",
        views.export_shapefile_view,
        name="api_export_shapefile",
    ),
]
