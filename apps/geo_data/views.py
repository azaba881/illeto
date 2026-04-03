import csv
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.utils.text import slugify
from django.views.decorators.http import require_GET

from apps.accounts.models import ExportLog, ShapefileLibraryEntry

from .models import Commune, Departement, PointInteret, Quartier, Zone

User = get_user_model()

OVERPASS_INTERPRETER_URL = "https://overpass-api.de/api/interpreter"
# Bénin approximatif (sud, ouest, nord, est) — Overpass (south,west,north,east)
BENIN_BBOX_DEFAULT = (6.2, 0.2, 12.7, 3.9)
OVERPASS_CACHE_TIMEOUT = 86400  # 24 h
MAX_BBOX_SPAN_DEG = 5.0

# PRJ WGS 84 si GDAL n’écrit pas le fichier (certification cabinets)
SHP_WGS84_PRJ = (
    b'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137,298.257223563]],'
    b'PRIMEM["Greenwich",0],UNIT["Degree",0.017453292519943295]]\n'
)


def _commune_queryset_for_departement(dept_pk: int):
    qs = Commune.objects.filter(departement_id=dept_pk)
    if not settings.ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES:
        qs = qs.filter(is_placeholder=False)
    return qs.order_by("name")


def _parse_bbox(request) -> tuple[float, float, float, float] | None:
    raw = request.GET.get("bbox")
    if raw is None or str(raw).strip() == "":
        return None
    parts = [p.strip() for p in str(raw).split(",")]
    if len(parts) != 4:
        return None
    try:
        south, west, north, east = (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError:
        return None
    if south >= north or west >= east:
        return None
    if (north - south) > MAX_BBOX_SPAN_DEG or (east - west) > MAX_BBOX_SPAN_DEG:
        return None
    return (south, west, north, east)


def _overpass_query_hydro(south: float, west: float, north: float, east: float) -> str:
    return (
        f'[out:json][timeout:90];('
        f'way["waterway"="river"]({south},{west},{north},{east});'
        f'way["waterway"="stream"]({south},{west},{north},{east});'
        f");out geom;"
    )


def _overpass_query_landuse(south: float, west: float, north: float, east: float) -> str:
    return (
        f'[out:json][timeout:60];('
        f'way["landuse"="forest"]({south},{west},{north},{east});'
        f'way["landuse"="residential"]({south},{west},{north},{east});'
        f");out geom;"
    )


@require_GET
def departement_geojson(request):
    """FeatureCollection GeoJSON : chaque Feature a un id (= pk) pour la synchro carte / filtres."""
    features = []
    for d in Departement.objects.all().order_by("name"):
        geom = json.loads(d.geom.geojson) if d.geom else None
        features.append(
            {
                "type": "Feature",
                "id": d.pk,
                "properties": {"name": d.name},
                "geometry": geom,
            }
        )
    return JsonResponse({"type": "FeatureCollection", "features": features})


@require_GET
def communes_json(request):
    """Liste JSON des communes pour un département : ?departement_id=<pk>."""
    raw = request.GET.get("departement_id")
    if raw is None or str(raw).strip() == "":
        return JsonResponse(
            {"detail": "Paramètre departement_id requis."},
            status=400,
        )
    try:
        dept_pk = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "departement_id invalide."}, status=400)

    if not Departement.objects.filter(pk=dept_pk).exists():
        return JsonResponse({"detail": "Département introuvable."}, status=404)

    rows = [
        {"id": c.id, "name": c.name}
        for c in _commune_queryset_for_departement(dept_pk)
    ]
    return JsonResponse(rows, safe=False)


@require_GET
def communes_geojson(request):
    """GeoJSON des communes d'un département : ?departement_id=<pk>."""
    raw = request.GET.get("departement_id")
    if raw is None or str(raw).strip() == "":
        return JsonResponse(
            {"detail": "Paramètre departement_id requis."},
            status=400,
        )
    try:
        dept_pk = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "departement_id invalide."}, status=400)

    if not Departement.objects.filter(pk=dept_pk).exists():
        return JsonResponse({"detail": "Département introuvable."}, status=404)

    features = []
    for c in _commune_queryset_for_departement(dept_pk):
        geom = json.loads(c.geom.geojson) if c.geom else None
        features.append(
            {
                "type": "Feature",
                "id": c.pk,
                "properties": {"name": c.name},
                "geometry": geom,
            }
        )
    return JsonResponse({"type": "FeatureCollection", "features": features})


@require_GET
def zones_geojson_by_commune(request):
    """
    Zones (admin_level 8) et quartiers (admin_level 10) pour une commune.
    GET: commune_id=<pk>
    """
    raw = request.GET.get("commune_id")
    if raw is None or str(raw).strip() == "":
        return JsonResponse(
            {"detail": "Paramètre commune_id requis."},
            status=400,
        )
    try:
        commune_pk = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "commune_id invalide."}, status=400)

    if not Commune.objects.filter(pk=commune_pk).exists():
        return JsonResponse({"detail": "Commune introuvable."}, status=404)

    commune = Commune.objects.get(pk=commune_pk)
    features = []

    for z in Zone.objects.filter(commune=commune).order_by("name"):
        geom = json.loads(z.geom.geojson) if z.geom else None
        features.append(
            {
                "type": "Feature",
                "id": z.pk,
                "properties": {
                    "name": z.name,
                    "kind": "zone",
                    "admin_level": 8,
                    "type_zone": z.type_zone or "",
                },
                "geometry": geom,
            }
        )

    for q in Quartier.objects.filter(commune=commune).order_by("name"):
        geom = json.loads(q.geom.geojson) if q.geom else None
        features.append(
            {
                "type": "Feature",
                "id": q.pk,
                "properties": {
                    "name": q.name,
                    "kind": "quartier",
                    "admin_level": 10,
                },
                "geometry": geom,
            }
        )

    return JsonResponse({"type": "FeatureCollection", "features": features})


@require_GET
def poi_geojson(request):
    """
    POI pour une commune.
    GET: commune_id=<pk> (requis)
    Optionnel : category=market&category=health ou category=market,transport
    Optionnel : layer=existing|discovery|offer (filtrage par champ source).
    """
    raw = request.GET.get("commune_id")
    if raw is None or str(raw).strip() == "":
        return JsonResponse(
            {"detail": "Paramètre commune_id requis."},
            status=400,
        )
    try:
        commune_pk = int(raw)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "commune_id invalide."}, status=400)

    if not Commune.objects.filter(pk=commune_pk).exists():
        return JsonResponse({"detail": "Commune introuvable."}, status=404)

    qs = PointInteret.objects.filter(commune_id=commune_pk).select_related(
        "commune", "quartier"
    )

    cats = [c.strip() for c in request.GET.getlist("category") if c.strip()]
    if not cats:
        raw_cat = (request.GET.get("category") or "").strip()
        if raw_cat:
            cats = [p.strip() for p in raw_cat.split(",") if p.strip()]
    allowed_cat = {c.value for c in PointInteret.Category}
    if cats:
        cats = [c for c in cats if c in allowed_cat]
        if cats:
            qs = qs.filter(category__in=cats)

    layer = (request.GET.get("layer") or request.GET.get("dataset") or "existing").strip().lower()
    crowd_q = (
        Q(source__icontains="crowd")
        | Q(source__icontains="contribution")
        | Q(source__icontains="utilisateur")
    )
    offer_q = Q(source__icontains="offre") | Q(source__icontains="opportun") | Q(
        source__icontains="projet"
    )
    if layer == "discovery":
        qs = qs.filter(crowd_q)
    elif layer == "offer":
        qs = qs.filter(offer_q)
    else:
        qs = qs.exclude(crowd_q).exclude(offer_q)

    features = []
    for p in qs.order_by("name"):
        geom = json.loads(p.geom.geojson) if p.geom else None
        features.append(
            {
                "type": "Feature",
                "id": p.pk,
                "properties": {
                    "name": p.name,
                    "category": p.category,
                    "quartier_id": p.quartier_id,
                    "quartier_name": p.quartier.name if p.quartier else "",
                },
                "geometry": geom,
            }
        )

    return JsonResponse({"type": "FeatureCollection", "features": features})


def _territory_attrs_for_shapefile(territory_type: str, territory_id: int) -> dict:
    """
    Retourne geom (GeoDjango) + attributs DBF (noms ≤ 10 caractères).
    Colonnes : NAME, KIND, DEPT, CODE_INSAE, SOURCE
    """
    t = (territory_type or "").strip().lower()
    if t == "commune":
        obj = Commune.objects.select_related("departement").get(pk=territory_id)
        dept_name = obj.departement.name if obj.departement else ""
        return {
            "label": obj.name,
            "geom": obj.geom,
            "NAME": (obj.name or "")[:254],
            "KIND": "commune",
            "DEPT": (dept_name or "")[:254],
            "CODE_INSAE": "",
            "SOURCE": "Illeto",
        }
    if t == "zone":
        obj = Zone.objects.select_related("commune", "commune__departement").get(pk=territory_id)
        dept_name = ""
        if obj.commune and obj.commune.departement:
            dept_name = obj.commune.departement.name
        return {
            "label": obj.name,
            "geom": obj.geom,
            "NAME": (obj.name or "")[:254],
            "KIND": "zone",
            "DEPT": (dept_name or "")[:254],
            "CODE_INSAE": "",
            "SOURCE": "Illeto",
        }
    if t == "quartier":
        obj = Quartier.objects.select_related("commune", "commune__departement").get(pk=territory_id)
        dept_name = ""
        if obj.commune and obj.commune.departement:
            dept_name = obj.commune.departement.name
        return {
            "label": obj.name,
            "geom": obj.geom,
            "NAME": (obj.name or "")[:254],
            "KIND": "quartier",
            "DEPT": (dept_name or "")[:254],
            "CODE_INSAE": "",
            "SOURCE": "Illeto",
        }
    raise Http404("Type de territoire inconnu.")


def _norm_export_territory_type(s: str) -> str:
    t = (s or "").strip().lower()
    if t == "department":
        return "departement"
    return t


def _resolve_territory_for_export(territory_type: str, territory_id: int) -> tuple[str, str, object]:
    t = _norm_export_territory_type(territory_type)
    if t == "departement":
        o = Departement.objects.get(pk=territory_id)
        return o.name, "departement", o.geom
    if t == "commune":
        o = Commune.objects.get(pk=territory_id)
        return o.name, "commune", o.geom
    if t == "zone":
        o = Zone.objects.get(pk=territory_id)
        return o.name, "zone", o.geom
    if t == "quartier":
        o = Quartier.objects.get(pk=territory_id)
        return o.name, "quartier", o.geom
    raise Http404("Type de territoire inconnu.")


def _geom_to_kml_fragment(geom) -> str:
    if geom is None:
        return ""
    if geom.geom_type == "Polygon":
        polys = [geom]
    elif geom.geom_type == "MultiPolygon":
        polys = list(geom)
    else:
        c = geom.centroid
        return f"<Point><coordinates>{c.x},{c.y},0</coordinates></Point>"
    parts = []
    for poly in polys:
        shell = poly.exterior_ring
        coords = " ".join(f"{x},{y},0" for x, y, *_ in shell.coords)
        parts.append(
            "<Polygon><outerBoundaryIs><LinearRing><coordinates>"
            f"{coords}</coordinates></LinearRing></outerBoundaryIs></Polygon>"
        )
    if len(parts) == 1:
        return parts[0]
    return "<MultiGeometry>" + "".join(parts) + "</MultiGeometry>"


@require_GET
def export_territory_geo_data(request):
    """
    Export CSV ou KML pour un territoire (département, commune, zone, quartier).
    GET: format=csv|kml, territory_type=…, territory_id=<pk>
    """
    fmt = (request.GET.get("format") or "").strip().lower()
    tt = request.GET.get("territory_type") or request.GET.get("type")
    tid_raw = request.GET.get("territory_id") or request.GET.get("id")
    if not fmt or not tt or tid_raw is None or str(tid_raw).strip() == "":
        return JsonResponse(
            {"detail": "Paramètres requis : format, territory_type, territory_id."},
            status=400,
        )
    try:
        tid = int(tid_raw)
    except (TypeError, ValueError):
        return JsonResponse({"detail": "territory_id invalide."}, status=400)
    try:
        name, kind, geom = _resolve_territory_for_export(tt, tid)
    except Departement.DoesNotExist:
        return JsonResponse({"detail": "Territoire introuvable."}, status=404)
    except Commune.DoesNotExist:
        return JsonResponse({"detail": "Territoire introuvable."}, status=404)
    except Zone.DoesNotExist:
        return JsonResponse({"detail": "Territoire introuvable."}, status=404)
    except Quartier.DoesNotExist:
        return JsonResponse({"detail": "Territoire introuvable."}, status=404)
    except Http404:
        return JsonResponse({"detail": "Type de territoire inconnu."}, status=400)
    if geom is None:
        return JsonResponse({"detail": "Géométrie absente."}, status=400)

    slug = slugify(name)[:50] or "territoire"
    cen = geom.centroid

    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["name", "kind", "lon", "lat", "wkt"])
        w.writerow([name, kind, f"{cen.x:.6f}", f"{cen.y:.6f}", geom.wkt])
        resp = HttpResponse(
            "\ufeff" + buf.getvalue(),
            content_type="text/csv; charset=utf-8",
        )
        resp["Content-Disposition"] = f'attachment; filename="illeto_{slug}.csv"'
        return resp

    if fmt == "kml":
        inner = _geom_to_kml_fragment(geom)
        title = xml_escape(str(name))
        desc = xml_escape(f"{kind} — {name}")
        kml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<kml xmlns="http://www.opengis.net/kml/2.2">'
            "<Document><Placemark>"
            f"<name>{title}</name><description>{desc}</description>"
            f"{inner}"
            "</Placemark></Document></kml>"
        )
        resp = HttpResponse(
            kml,
            content_type="application/vnd.google-earth.kml+xml; charset=utf-8",
        )
        resp["Content-Disposition"] = f'attachment; filename="illeto_{slug}.kml"'
        return resp

    return JsonResponse(
        {"detail": "Format non pris en charge (csv, kml)."},
        status=400,
    )


@require_GET
def export_shapefile_view(request, territory_type, territory_id):
    """
    Export ESRI Shapefile natif (ZIP : .shp, .shx, .dbf, .prj) via GeoPandas/GDAL.
    Réservé aux comptes PROFESSIONAL et INSTITUTION.
    """
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentification requise."}, status=401)

    ut = getattr(request.user, "user_type", None)
    if ut not in (User.UserType.PROFESSIONAL, User.UserType.INSTITUTION):
        return JsonResponse(
            {"detail": "Export Shapefile réservé aux comptes professionnels."},
            status=403,
        )

    try:
        attrs = _territory_attrs_for_shapefile(territory_type, territory_id)
    except (Commune.DoesNotExist, Zone.DoesNotExist, Quartier.DoesNotExist):
        return JsonResponse({"detail": "Territoire introuvable."}, status=404)
    except Http404 as e:
        return JsonResponse({"detail": str(e) or "Requête invalide."}, status=404)

    try:
        import geopandas as gpd
    except ImportError:
        return JsonResponse(
            {"detail": "Moteur GeoPandas indisponible sur ce serveur."},
            status=503,
        )

    geom = attrs["geom"]
    if geom is None:
        return JsonResponse({"detail": "Géométrie absente."}, status=400)

    gdf = gpd.GeoDataFrame(
        {
            "NAME": [attrs["NAME"]],
            "KIND": [attrs["KIND"]],
            "DEPT": [attrs["DEPT"]],
            "CODE_INSAE": [attrs["CODE_INSAE"]],
            "SOURCE": [attrs["SOURCE"]],
        },
        geometry=gpd.GeoSeries.from_wkt([geom.wkt], crs="EPSG:4326"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        shp_base = Path(tmpdir) / "territoire.shp"
        try:
            gdf.to_file(shp_base, driver="ESRI Shapefile")
        except Exception as exc:
            return JsonResponse(
                {"detail": "Échec d’écriture Shapefile.", "error": str(exc)},
                status=500,
            )

        shp_sidecars = list(Path(tmpdir).glob("territoire.*"))
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for p in shp_sidecars:
                zf.write(p, arcname=p.name)
            if "territoire.prj" not in {p.name for p in shp_sidecars}:
                zf.writestr("territoire.prj", SHP_WGS84_PRJ)
        buf.seek(0)

    try:
        ShapefileLibraryEntry.objects.create(
            user=request.user,
            territory_type=(territory_type or "").strip().lower()[:16],
            territory_id=int(territory_id),
            label=(attrs.get("label") or "")[:255],
        )
        ExportLog.objects.create(user=request.user, kind="shapefile")
    except Exception:
        pass

    slug = slugify(attrs.get("label") or "export")[:40] or "export"
    date_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"IleTo_Export_{slug}_{date_str}.zip"

    resp = FileResponse(buf, as_attachment=True, filename=filename, content_type="application/zip")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@require_GET
def overpass_proxy(request):
    """
    Proxy Overpass avec cache 24 h. GET: type=hydro|landuse, bbox optionnel south,west,north,east.
    Sans bbox : emprise Bénin par défaut.
    """
    kind = (request.GET.get("type") or "").strip().lower()
    if kind not in ("hydro", "landuse"):
        return JsonResponse(
            {"detail": "Paramètre type requis : hydro ou landuse."},
            status=400,
        )

    bbox = _parse_bbox(request)
    if bbox is None:
        bbox = BENIN_BBOX_DEFAULT
    south, west, north, east = bbox

    if kind == "hydro":
        query = _overpass_query_hydro(south, west, north, east)
    else:
        query = _overpass_query_landuse(south, west, north, east)

    cache_key = "overpass:v1:" + hashlib.sha256(
        f"{kind}:{south:.5f},{west:.5f},{north:.5f},{east:.5f}".encode()
    ).hexdigest()
    payload = cache.get(cache_key)
    if payload is not None:
        return JsonResponse(payload)

    try:
        resp = requests.get(
            OVERPASS_INTERPRETER_URL,
            params={"data": query},
            timeout=90,
            headers={"User-Agent": "Illeto-Atlas/1.0 (Django overpass proxy)"},
        )
    except requests.Timeout:
        return JsonResponse({"detail": "Délai dépassé côté Overpass."}, status=504)
    except requests.RequestException as exc:
        return JsonResponse(
            {"detail": "Erreur réseau vers Overpass.", "error": str(exc)},
            status=502,
        )

    if resp.status_code != 200:
        return JsonResponse(
            {
                "detail": "Réponse Overpass invalide.",
                "status": resp.status_code,
            },
            status=502,
        )

    try:
        payload = resp.json()
    except json.JSONDecodeError:
        return JsonResponse({"detail": "JSON Overpass illisible."}, status=502)

    cache.set(cache_key, payload, OVERPASS_CACHE_TIMEOUT)
    return JsonResponse(payload)


@require_GET
def commune_flood_metrics(request, commune_id: int):
    """Métrique d’aléa inondation (PostGIS + HydroZone) — source unique Atlas / rapports."""
    from .utils import flood_metrics_for_commune

    data = flood_metrics_for_commune(int(commune_id))
    if not data.get("ok"):
        return JsonResponse(
            {"detail": data.get("detail", "erreur")},
            status=404,
        )
    return JsonResponse(
        {
            "flood_percent": data["flood_percent"],
            "flood_area_ha": data.get("flood_area_ha"),
            "territory_area_ha": data.get("territory_area_ha"),
            "source": data["source"],
            "commune_id": data["commune_id"],
            "commune_name": data["commune_name"],
        }
    )
