"""
Import des départements : OSM JSON, GeoJSON (dict), ou données OGR (Shapefile, GeoJSON, KML…)
via LayerMapping pour la reprojection et le typage des champs IGN.
"""

import json
from pathlib import Path

from django.contrib.gis.gdal import CoordTransform, DataSource, SpatialReference
from django.contrib.gis.geos import GEOSGeometry, LinearRing, MultiPolygon, Polygon
from django.contrib.gis.utils import LayerMapError, LayerMapping
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ...import_audit import record_import_run
from ...models import Commune, Departement

# Modèle Departement : champs Django -> noms d’attributs OGR courants (IGN, cadastre, OSM dérivés)
NAME_OGR_CANDIDATES = (
    "nom",
    "NOM",
    "name",
    "NAME",
    "NAME_1",
    "NOM_1",
    "LIBELLE",
    "Libelle",
    "libelle",
    "admin1Name_fr",
    "ID",
    "id",
    "CODE",
    "code",
)

def _is_osm_json(data: dict) -> bool:
    return isinstance(data.get("elements"), list)


def _iter_geojson_features(data: dict):
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features") or []:
            if feature.get("type") == "Feature":
                yield feature
    elif data.get("type") == "Feature":
        yield data


def _resolve_name(properties: dict | None) -> str | None:
    if not properties:
        return None
    for key in ("name", "NAME_1", "admin1Name_fr", "id"):
        if key not in properties:
            continue
        value = properties[key]
        if value is None or value == "":
            continue
        return str(value).strip()
    return None


def _commune_name_from_properties(properties: dict | None) -> str | None:
    """Nom affiché pour une commune OSM / export (admin_level 6)."""
    if not properties:
        return None
    for key in ("name:fr", "name", "official_name"):
        if key not in properties:
            continue
        value = properties[key]
        if value is None or str(value).strip() == "":
            continue
        name = str(value).strip()
        if len(name) > 255:
            name = name[:255]
        return name
    return None


def _is_admin_level_6(properties: dict | None) -> bool:
    if not properties:
        return False
    al = properties.get("admin_level")
    if al is None:
        return False
    return str(al).strip() == "6"


def _resolve_osm_relation_name(tags: dict | None) -> str | None:
    if not tags:
        return None
    name = tags.get("name")
    if name is not None and str(name).strip():
        return str(name).strip()
    return _resolve_name(tags)


def _coords_equal(a, b, tol: float = 1e-7) -> bool:
    return abs(a[0] - b[0]) < tol and abs(a[1] - b[1]) < tol


def _collect_outer_segments(members: list) -> list[list[tuple[float, float]]]:
    segments = []
    for m in members or []:
        if m.get("type") != "way":
            continue
        role = (m.get("role") or "").lower()
        if role == "inner":
            continue
        if role not in ("outer", "outer_", ""):
            continue
        geom = m.get("geometry")
        if not geom:
            continue
        coords = [(float(p["lon"]), float(p["lat"])) for p in geom]
        if len(coords) >= 2:
            segments.append(coords)
    return segments


def _merge_segments_to_rings(segments: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    if not segments:
        return []
    remaining = [list(s) for s in segments]
    rings_out = []

    while remaining:
        ring = remaining.pop(0)
        if len(ring) < 2:
            continue
        growing = True
        while growing:
            growing = False
            i = 0
            while i < len(remaining):
                seg = remaining[i]
                if len(seg) < 2:
                    remaining.pop(i)
                    continue
                if _coords_equal(ring[-1], seg[0]):
                    ring.extend(seg[1:])
                    remaining.pop(i)
                    growing = True
                    continue
                if _coords_equal(ring[-1], seg[-1]):
                    ring.extend(seg[-2::-1])
                    remaining.pop(i)
                    growing = True
                    continue
                if _coords_equal(ring[0], seg[-1]):
                    ring = seg[:-1] + ring
                    remaining.pop(i)
                    growing = True
                    continue
                if _coords_equal(ring[0], seg[0]):
                    ring = list(reversed(seg[1:])) + ring
                    remaining.pop(i)
                    growing = True
                    continue
                i += 1
        rings_out.append(ring)

    closed = []
    for ring in rings_out:
        if len(ring) < 3:
            continue
        if not _coords_equal(ring[0], ring[-1]):
            ring = ring + [ring[0]]
        closed.append(ring)
    return closed


def _rings_to_multipolygon(rings: list[list[tuple[float, float]]]) -> MultiPolygon | None:
    if not rings:
        return None
    polys = []
    for ring in rings:
        if len(ring) < 4:
            continue
        try:
            lr = LinearRing(ring, srid=4326)
            polys.append(Polygon(lr, srid=4326))
        except Exception:
            continue
    if not polys:
        return None
    if len(polys) == 1:
        return MultiPolygon(polys[0])
    return MultiPolygon(*polys)


def _relation_geom_from_members(members: list) -> MultiPolygon | None:
    segments = _collect_outer_segments(members)
    if not segments:
        return None
    rings = _merge_segments_to_rings(segments)
    return _rings_to_multipolygon(rings)


def _relation_geom_from_osm(relation: dict) -> MultiPolygon | None:
    raw_geom = relation.get("geometry") or relation.get("geom")
    if raw_geom:
        try:
            if isinstance(raw_geom, dict):
                g = GEOSGeometry(json.dumps(raw_geom))
            elif isinstance(raw_geom, str):
                g = GEOSGeometry(raw_geom)
            else:
                return None
            if g.srid in (None, 0):
                g.srid = 4326
            return _to_multipolygon(g)
        except Exception:
            pass
    return _relation_geom_from_members(relation.get("members") or [])


def _to_multipolygon(geom: GEOSGeometry) -> MultiPolygon | None:
    if geom.geom_type == "Polygon":
        return MultiPolygon(geom)
    if geom.geom_type == "MultiPolygon":
        return geom
    return None


def _remove_benin_country_outline(stdout, style) -> None:
    labels = (
        "Benin",
        "Bénin",
        "Republic of Benin",
        "République du Bénin",
        "Le Bénin",
    )
    total = 0
    for label in labels:
        n, _ = Departement.objects.filter(name__iexact=label).delete()
        total += n
    if total:
        stdout.write(style.WARNING(f"Nettoyage : {total} enregistrement(s) « pays » retiré(s) (Benin / Bénin…)."))


def _pick_name_ogr_field(layer) -> str | None:
    """Choisit l’attribut OGR pour le nom du département (casse ignorée)."""
    fields = list(layer.fields)
    if not fields:
        return None
    lower_to_actual = {f.lower(): f for f in fields}
    for cand in NAME_OGR_CANDIDATES:
        key = cand.lower()
        if key in lower_to_actual:
            return lower_to_actual[key]
    return None


def _ogr_geom_mapping_keyword(layer) -> str:
    """
    Valeur du mapping LayerMapping pour le champ géométrique du modèle :
    'POLYGON' ou 'MULTIPOLYGON' (voir doc Django LayerMapping).
    """
    gname = layer.geom_type.name
    if gname.startswith("MultiPolygon"):
        return "MULTIPOLYGON"
    if gname.startswith("Polygon"):
        return "POLYGON"
    raise LayerMapError(
        f"Géométrie OGR non prise en charge pour les départements : {gname} "
        f"(attendu Polygon / MultiPolygon)."
    )


def _reproject_geos_to_wgs84(geos_geom: GEOSGeometry, layer) -> None:
    """
    Passe la géométrie en SRID 4326. Utilise la SRS de la couche OGR (fichier .prj, GeoJSON CRS, etc.)
    et PROJ via GDAL — sans lecture de spatial_ref_sys PostGIS.
    """
    dest = SpatialReference(4326)
    src = layer.srs
    if src and src.srid not in (None, 0):
        geos_geom.srid = src.srid
        if src.srid != 4326:
            geos_geom.transform(CoordTransform(src, dest))
        return
    if geos_geom.srid in (None, 0, -1):
        geos_geom.srid = 4326
        return
    if geos_geom.srid != 4326:
        geos_geom.transform(CoordTransform(SpatialReference(geos_geom.srid), dest))


def _build_layermapping_dict(layer) -> dict:
    name_field = _pick_name_ogr_field(layer)
    if not name_field:
        raise LayerMapError(
            "Aucun champ nom reconnu dans la couche. Champs présents : %s. "
            "Attendu un des alias : %s."
            % (", ".join(layer.fields), ", ".join(NAME_OGR_CANDIDATES[:8]) + ", …")
        )
    geom_kw = _ogr_geom_mapping_keyword(layer)
    return {"name": name_field, "geom": geom_kw}


class Command(BaseCommand):
    help = (
        "Importe les départements depuis OSM JSON, GeoJSON (fichier JSON) "
        "ou OGR (Shapefile .shp, GeoJSON, KML…). Reprojection automatique vers SRID 4326. "
        "Option --import-communes : lit data/export.geojson (admin_level 6) et rattache "
        "chaque commune au département dont la géométrie couvre le centroïde."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "paths",
            nargs="*",
            type=str,
            help="Chemins : .shp (dbf/shx automatiques), .geojson, .json, .kml",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Analyse sans écrire en base.",
        )
        parser.add_argument(
            "--encoding",
            default="utf-8",
            help="Encodage OGR (ex. latin1 pour certains shapefiles IGN).",
        )
        parser.add_argument(
            "--layer",
            type=int,
            default=0,
            help="Index de la couche OGR (sources multi-couches).",
        )
        parser.add_argument(
            "--import-communes",
            action="store_true",
            dest="import_communes",
            help="Importe les communes depuis data/export.geojson (features admin_level=6).",
        )
        parser.add_argument(
            "--clear-placeholders",
            action="store_true",
            dest="clear_placeholders",
            help="Supprime les communes is_placeholder=True (souvent avant --import-communes).",
        )

    def handle(self, *args, **options):
        paths = options["paths"]
        dry_run = options["dry_run"]
        encoding = options["encoding"]
        layer_index = options["layer"]
        import_communes = options["import_communes"]
        clear_placeholders = options["clear_placeholders"]

        if clear_placeholders:
            n_del, _ = Commune.objects.filter(is_placeholder=True).delete()
            self.stdout.write(
                self.style.WARNING(f"Communes factices supprimées : {n_del}.")
            )

        if import_communes:
            export_path = Path(settings.BASE_DIR) / "data" / "export.geojson"
            if not export_path.is_file():
                raise CommandError(f"Fichier introuvable : {export_path}")
            self.stdout.write(f"Import communes : {export_path}")
            n_communes = self._import_communes_export_geojson(export_path, dry_run)
            if not dry_run:
                self._log_vector_import(export_path.name, n_communes)

        if not paths and not import_communes:
            if clear_placeholders:
                return
            self.stdout.write(
                self.style.WARNING(
                    "Aucune action. Exemples :\n"
                    "  ./venv/bin/python manage.py geo_import_vector_benin data/departements.shp\n"
                    "  ./venv/bin/python manage.py geo_import_vector_benin --import-communes\n"
                    "  ./venv/bin/python manage.py geo_import_vector_benin --clear-placeholders --import-communes\n"
                    "  ./venv/bin/python manage.py geo_import_vector_benin data/ign.geojson"
                )
            )
            return

        benin_cleanup_done = False

        for raw in paths:
            path = Path(raw).expanduser().resolve()
            if not path.is_file():
                raise CommandError(f"Fichier introuvable : {path}")

            ext = path.suffix.lower()
            self.stdout.write(f"Fichier : {path.name} ({ext or 'sans extension'})")

            if ext == ".shp" or ext == ".kml" or ext == ".geojson":
                n = self._import_ogr_vector(path, dry_run, encoding, layer_index)
                if not dry_run:
                    self._log_vector_import(path.name, n)
                continue

            if ext == ".json":
                try:
                    text = path.read_text(encoding=encoding)
                    data = json.loads(text)
                except json.JSONDecodeError as e:
                    raise CommandError(f"JSON invalide ({path}) : {e}") from e

                if _is_osm_json(data):
                    if not dry_run and not benin_cleanup_done:
                        _remove_benin_country_outline(self.stdout, self.style)
                        benin_cleanup_done = True
                    n = self._import_osm(data, dry_run)
                    if not dry_run:
                        self._log_vector_import(path.name, n)
                    continue

                if data.get("type") in ("FeatureCollection", "Feature"):
                    n = self._import_geojson(data, dry_run)
                    if not dry_run:
                        self._log_vector_import(path.name, n)
                    continue

                try:
                    n = self._import_ogr_vector(path, dry_run, encoding, layer_index)
                    if not dry_run:
                        self._log_vector_import(path.name, n)
                except Exception as e:
                    raise CommandError(
                        f"Fichier .json non reconnu comme OSM ni GeoJSON, "
                        f"et échec OGR : {e}"
                    ) from e
                continue

            raise CommandError(
                f"Extension non prise en charge : {ext}. "
                f"Utilisez .shp, .geojson, .json ou .kml."
            )

    def _log_vector_import(self, source_label: str, count: int) -> None:
        if count:
            detail = (
                f"{count} entité(s) vectorielle(s) importée(s) via la source « {source_label} »."
            )
        else:
            detail = (
                f"Source « {source_label} » traitée : aucune entité écrite (0 succès)."
            )
        record_import_run(
            command_name="geo_import_vector_benin",
            file_name=source_label[:512],
            success_count=count,
            error_lines=[detail],
        )

    def _import_ogr_vector(
        self,
        path: Path,
        dry_run: bool,
        encoding: str,
        layer_index: int,
    ) -> int:
        try:
            ds = DataSource(str(path), encoding=encoding)
        except Exception as e:
            raise CommandError(f"Impossible d’ouvrir la source OGR ({path}) : {e}") from e

        if layer_index < 0 or layer_index >= len(ds):
            raise CommandError(
                f"Index de couche invalide : {layer_index} (0–{len(ds) - 1}, {len(ds)} couche(s))."
            )

        layer = ds[layer_index]
        try:
            mapping = _build_layermapping_dict(layer)
        except LayerMapError as e:
            raise CommandError(str(e)) from e

        srs_hint = f"EPSG:{layer.srs.srid}" if layer.srs and layer.srs.srid else "non défini (→ 4326)"
        self.stdout.write(
            f"LayerMapping : name ← « {mapping['name']} », geom ← {mapping['geom']} "
            f"({layer.num_feat} entité(s), SRS : {srs_hint})"
        )

        # transform=False : LayerMapping avec transform=True interroge spatial_ref_sys (PostGIS).
        # Reprojection WGS84 via GDAL CoordTransform ci‑dessous (fichiers IGN en TM local, etc.).
        lm = LayerMapping(
            Departement,
            ds,
            mapping,
            layer=layer_index,
            transform=False,
            encoding=encoding,
            transaction_mode="autocommit",
        )

        total = max(layer.num_feat, 1)
        report_every = max(1, total // 50)
        num_ok = 0
        num_err = 0

        for i, feat in enumerate(layer, start=1):
            if i == 1 or i == total or i % report_every == 0:
                pct = min(100, int(100 * i / total))
                self.stdout.write(f"  Progression : {pct}% ({i}/{total})")

            try:
                kwargs = lm.feature_kwargs(feat)
            except LayerMapError as err:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(f"  FID {feat.fid} ignoré : {err}")
                )
                continue
            except Exception as err:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(f"  FID {feat.fid} erreur : {err}")
                )
                continue

            name = (kwargs.get("name") or "").strip()
            if not name:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(f"  FID {feat.fid} : nom vide après mapping.")
                )
                continue
            if len(name) > 255:
                name = name[:255]

            geom_wkt = kwargs.get("geom")
            if not geom_wkt:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(f"  FID {feat.fid} (« {name} ») : pas de géométrie.")
                )
                continue

            try:
                geos_geom = GEOSGeometry(geom_wkt)
            except Exception as err:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  FID {feat.fid} (« {name} ») : WKT invalide — {err}"
                    )
                )
                continue

            try:
                _reproject_geos_to_wgs84(geos_geom, layer)
            except Exception as err:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  FID {feat.fid} (« {name} ») : reprojection vers 4326 impossible — {err}"
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [dry-run] « {name} » — {geos_geom.geom_type} (SRID 4326)"
                    )
                )
                num_ok += 1
                continue

            try:
                with transaction.atomic():
                    _obj, created = Departement.objects.update_or_create(
                        name=name,
                        defaults={"geom": geos_geom},
                    )
            except Exception as err:
                num_err += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  « {name} » : échec en base (transaction annulée pour cette entité) — {err}"
                    )
                )
                continue

            num_ok += 1
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Importé : {name}"))
            else:
                self.stdout.write(self.style.WARNING(f"  Mis à jour : {name}"))

        self.stdout.write(
            f"Couche terminée : {num_ok} réussite(s), {num_err} ignorée(s) ou en erreur."
        )
        return num_ok

    def _import_osm(self, data: dict, dry_run: bool) -> int:
        num_ok = 0
        for el in data.get("elements") or []:
            if el.get("type") != "relation":
                continue
            tags = el.get("tags") or {}
            name = _resolve_osm_relation_name(tags)
            if not name:
                self.stdout.write(
                    self.style.ERROR(
                        "Relation ignorée : pas de tags['name'] ni clé de repli."
                    )
                )
                continue

            if len(name) > 255:
                name = name[:255]
                self.stdout.write(
                    self.style.WARNING("Nom tronqué à 255 caractères pour la relation suivante.")
                )

            mp = _relation_geom_from_osm(el)
            if mp is None:
                self.stdout.write(
                    self.style.ERROR(
                        f"Relation « {name} » : impossible de reconstruire la géométrie."
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[dry-run] {name} — OSM, {mp.geom_type} ({mp.num_geom} polygone(s))"
                    )
                )
                num_ok += 1
                continue

            with transaction.atomic():
                _obj, created = Departement.objects.update_or_create(
                    name=name,
                    defaults={"geom": mp},
                )
            num_ok += 1
            if created:
                self.stdout.write(self.style.SUCCESS(f"Importé: {name}"))
            else:
                self.stdout.write(self.style.WARNING(f"Mis à jour: {name}"))
        return num_ok

    def _import_geojson(self, data: dict, dry_run: bool) -> int:
        features = list(_iter_geojson_features(data))
        num_ok = 0
        total = max(len(features), 1)
        report_every = max(1, total // 50)

        for i, feature in enumerate(features, start=1):
            if i == 1 or i == total or i % report_every == 0:
                pct = min(100, int(100 * i / total))
                self.stdout.write(f"  Progression : {pct}% ({i}/{total})")

            props = feature.get("properties") or {}
            name = _resolve_name(props)
            if not name:
                self.stdout.write(
                    self.style.ERROR(
                        "Entité ignorée : aucun nom (name, NAME_1, admin1Name_fr, id)."
                    )
                )
                continue

            if len(name) > 255:
                name = name[:255]
                self.stdout.write(
                    self.style.WARNING(
                        "Nom tronqué à 255 caractères pour l’entité suivante."
                    )
                )

            raw_geom = feature.get("geometry")
            if not raw_geom:
                self.stdout.write(
                    self.style.ERROR(f"Entité « {name} » ignorée : géométrie absente.")
                )
                continue

            try:
                geom = GEOSGeometry(json.dumps(raw_geom))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Entité « {name} » : géométrie invalide ({e}).")
                )
                continue

            if geom.srid in (None, 0):
                geom.srid = 4326

            mp = _to_multipolygon(geom)
            if mp is None:
                self.stdout.write(
                    self.style.ERROR(
                        f"Entité « {name} » ignorée : type {geom.geom_type!r}."
                    )
                )
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(f"  [dry-run] {name} — {mp.geom_type}")
                )
                num_ok += 1
                continue

            try:
                with transaction.atomic():
                    _obj, created = Departement.objects.update_or_create(
                        name=name,
                        defaults={"geom": mp},
                    )
            except Exception as err:
                self.stdout.write(
                    self.style.ERROR(
                        f"  « {name} » : échec en base — {err}"
                    )
                )
                continue

            num_ok += 1
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Importé : {name}"))
            else:
                self.stdout.write(self.style.WARNING(f"  Mis à jour : {name}"))
        return num_ok

    def _import_communes_export_geojson(self, path: Path, dry_run: bool) -> int:
        """Importe les communes depuis data/export.geojson (Overpass / OSM, admin_level 6)."""
        try:
            text = path.read_text(encoding="utf-8")
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise CommandError(f"JSON invalide ({path}) : {e}") from e

        features = [
            f for f in _iter_geojson_features(data) if _is_admin_level_6(f.get("properties"))
        ]
        total = len(features)
        if not total:
            self.stdout.write(self.style.WARNING("Aucune entité admin_level=6 dans ce fichier."))
            return 0

        self.stdout.write(f"  {total} commune(s) candidate(s) (admin_level=6).")
        num_ok = 0
        num_skip = 0
        num_err = 0
        report_every = max(1, total // 20)

        for i, feature in enumerate(features, start=1):
            if i == 1 or i == total or i % report_every == 0:
                pct = min(100, int(100 * i / total))
                self.stdout.write(f"  Progression : {pct}% ({i}/{total})")

            props = feature.get("properties") or {}
            name = _commune_name_from_properties(props)
            if not name:
                self.stdout.write(self.style.ERROR("  Entité ignorée : pas de nom utilisable."))
                num_err += 1
                continue

            raw_geom = feature.get("geometry")
            if not raw_geom:
                self.stdout.write(
                    self.style.ERROR(f"  « {name} » ignorée : géométrie absente.")
                )
                num_err += 1
                continue

            try:
                geom = GEOSGeometry(json.dumps(raw_geom))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"  « {name} » : géométrie invalide ({e}).")
                )
                num_err += 1
                continue

            if geom.srid in (None, 0):
                geom.srid = 4326

            mp = _to_multipolygon(geom)
            if mp is None:
                self.stdout.write(
                    self.style.ERROR(
                        f"  « {name} » ignorée : type {geom.geom_type!r} (attendu Polygon/MultiPolygon)."
                    )
                )
                num_err += 1
                continue

            centroid = mp.centroid
            if centroid.srid in (None, 0):
                centroid.srid = 4326

            parent = Departement.objects.filter(geom__covers=centroid).first()
            if parent is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"  « {name} » : aucun département ne couvre le centroïde — ignorée."
                    )
                )
                num_skip += 1
                continue

            if dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [dry-run] « {name} » → département « {parent.name} »"
                    )
                )
                num_ok += 1
                continue

            try:
                with transaction.atomic():
                    _obj, created = Commune.objects.update_or_create(
                        departement=parent,
                        name=name,
                        defaults={
                            "geom": mp,
                            "is_placeholder": False,
                        },
                    )
            except Exception as err:
                self.stdout.write(
                    self.style.ERROR(f"  « {name} » : échec en base — {err}")
                )
                num_err += 1
                continue

            num_ok += 1
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Importé : {name} ({parent.name})"))
            else:
                self.stdout.write(self.style.WARNING(f"  Mis à jour : {name} ({parent.name})"))

        self.stdout.write(
            f"Communes : {num_ok} OK, {num_skip} sans département parent, {num_err} erreur(s)."
        )
        return num_ok
