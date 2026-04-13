# Rapport projet Illeto — passation développeur

Document de **prise en main** pour un développeur qui rejoint le projet : contexte, ce qui existe, **types de données attendus**, et **chaîne d’import** jusqu’au tableau de bord cartographique (Atlas). Le détail des commandes, requêtes Overpass et pièges d’export est complété par [`README_tools.md`](README_tools.md).

---

## 1. Objectif produit

**Illeto** est une plateforme SIG web (Django) centrée sur le **Bénin** : limites administratives, zones urbaines, quartiers, POI, hydro, avec une **carte interactive** (`/atlas/`), exports (GeoJSON, shapefile serveur, image), et menus « Cartes & données » alignés sur une charte sombre (dashboard).

Le **dashboard cartographique** côté utilisateur correspond surtout à :

- la page **Atlas** (`apps/website`, template `templates/website/atlas.html`) ;
- les **API GeoJSON** sous le préfixe `/geo/` (`apps/geo_data`) consommées par le JavaScript de la carte et par `static/assets/js/scripts.js` (état `IlletoAtlas`, cascades département → commune → zone/quartier).

---

## 2. Architecture technique (résumé)

| Zone | Rôle |
|------|------|
| **`apps/geo_data`** | Modèles PostGIS, vues API JSON/GeoJSON, commandes `manage.py` d’import, dossier `importers/` (HDX, OSM, universel). |
| **`apps/website`** | Pages vitrine + **Atlas** ; URLs publiques. |
| **`apps/accounts`** (si présent) | Profils / types d’utilisateur pour règles d’export Atlas. |
| **PostgreSQL + PostGIS** | Source de vérité des géométries (SRID **4326**). |
| **Fichiers statiques** | `static/assets/` (CSS `illeto.css`, `scripts.js`, `navigation_atlas.js`) ; le template Atlas embarque aussi une grosse couche JS (Leaflet, option Mapbox). |

**Point d’entrée des URLs géo** : `apps/geo_data/urls.py` (monté sous `/geo/` dans le routeur principal du projet).

---

## 3. Ce qui est en place (état fonctionnel)

### 3.1 Données et API

- **Hiérarchie** : `Departement` → `Commune` → `Zone` (arrondissements, souvent OSM `admin_level=8`) et `Quartier` (`admin_level=10`).
- **Endpoints utiles pour l’Atlas** :
  - `GET /geo/api/departements/` — GeoJSON départements ;
  - `GET /geo/api/communes/geojson/?departement_id=<pk>` — communes d’un département ;
  - `GET /geo/api/zones/geojson/?commune_id=<pk>` — zones + quartiers (`properties.kind` : `zone` | `quartier`) ;
  - `GET /geo/api/poi/geojson/?commune_id=<pk>` — POI ;
  - exports territoire / shapefile (voir `README_tools.md` section 10).

### 3.2 Sérialisation GeoJSON

- Les géométries servies passent par **`geometry_to_geojson_dict`** (`apps/geo_data/serializers.py`) avec **`ST_AsGeoJSON`** PostGIS et une **précision élevée** (paramètre décimal **15** côté vues) pour limiter les écarts visuels (liserés) entre serveur et rendu navigateur.

### 3.3 Qualité géométrique post-import

- La commande **`clean_geometries`** recadre **Zone** et **Quartier** sur la géométrie de la **commune parente** : intersection, **`ST_Buffer(..., 0)`**, **`ST_Snap`** sur la commune (tolérance `0.00001` °), extraction polygonale, **`ST_Multi`**, option **`ST_SnapToGrid`** via `--grid`.
- Usage typique après imports OSM / raccords bancals :

  ```bash
  python manage.py clean_geometries --only zones
  python manage.py clean_geometries --only quartiers
  ```

### 3.4 Interface Atlas (aperçu)

- Carte **Leaflet** + fonds (Carto, satellite, Mapbox selon config) ; couches administratives, POI, vues « hydro / occupation du sol » selon évolutions du template.
- **Sélection territoriale** : état synchronisé entre filtres (`scripts.js`) et polygones ; styles de surbrillance (ex. sélection bleue sans contour épais pour éviter l’effet de débordement).
- Menu **« Cartes & données »** : panneau latéral, flyouts bas de page ; CSS dédiée (`illeto.css`) pour z-index / `pointer-events` lorsque le menu est fermé (ne pas bloquer les clics carte).
- **Exports carte** (PNG/PDF, etc.) : logique sensible à Mapbox / html2canvas — voir `README_tools.md` section 10.

### 3.5 Administration

- **Django Admin** : modèles géographiques ; import fichier via mécanismes prévus (`admin_import`, `ImportLog`).
- Variable **`ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES`** : contrôle l’exposition des communes marquées `is_placeholder` (jeux de démo).

---

## 4. Types de données à fournir

Toutes les géométries côté base sont en **WGS84 (EPSG:4326)**. Les imports attendent en pratique des **fichiers vectoriels** cohérents avec le niveau administratif cible.

### 4.1 Synthèse par modèle

| Modèle | Géométrie | Rattachement / clés | Sources typiques | Fichiers / formats |
|--------|-----------|---------------------|------------------|---------------------|
| **Departement** | `MultiPolygon` | `name`, `code_officiel` (pcode HDX recommandé) | HDX OCHA, geoBoundaries ADM1 | GeoJSON, SHP, KML |
| **Commune** | `MultiPolygon` | FK `departement`, `name`, `code_officiel` | HDX ADM2, OSM `admin_level=6` | Idem |
| **Zone** | `MultiPolygon` | FK `commune`, `name`, `osm_id` (idempotence), `type_zone` optionnel (land use) | OSM 8, geoBoundaries ADM3 si schéma aligné | GeoJSON, Overpass → JSON |
| **Quartier** | `MultiPolygon` | FK `commune`, `name`, `osm_id` | OSM 10 | Idem |
| **PointInteret** | `Point` | `name`, `category`, `external_id`, rattachement quartier/commune à l’import | OSM Overpass, GeoJSON maison | GeoJSON (Point) |
| **HydroZone** | `MultiPolygon` | `name`, `source` | Fichiers maison / partenaires | GeoJSON polygones |

### 4.2 Propriétés utiles dans les GeoJSON

- **Noms** : champs type `name`, `name:fr`, ou mapping dans les commandes d’import.
- **Identifiants stables** : `code_officiel` / pcode pour HDX ; `osm_id` ou `@id` pour réimports OSM ; `external_id` pour POI.
- **Cohérence topologique** : les **zones** et **quartiers** doivent idéalement être **découpés par la commune** ; sinon lancer **`clean_geometries`** après import.

### 4.3 Variables d’environnement (chemins par défaut)

Voir **section 4** de [`README_tools.md`](README_tools.md) : `ILLETO_HDX_ADM1_PATH`, `ADM2`, `ADM3`, `ILLETO_POI_GEOJSON_PATH`, `ILLETO_HYDRO_GEOJSON_PATH`, `ILLETO_OSM_DISTRICTS_PATH`, `ILLETO_OVERPASS_API_URL`, etc.

---

## 5. Processus d’importation → alimentation du dashboard

Le **dashboard** (Atlas) ne lit pas les fichiers directement : il consomme **uniquement** ce qui est **en base** via les API `/geo/api/...`. Le flux standard est donc :

```text
Fichiers sources → commandes manage.py (ou Admin) → PostgreSQL/PostGIS → API → Atlas (JS)
```

### 5.1 Ordre recommandé (à respecter)

1. **Migrations** : `python manage.py migrate`
2. **Squelette national** (limites officielles) :
   - ADM1 → `Departement`
   - ADM2 → `Commune`
   - ADM3 → `Zone` *si* le jeu de données correspond au modèle « zone = arrondissement sous commune » (sinon zones issues d’OSM à l’étape suivante)
3. **Détail urbain OSM** (optionnel mais courant pour l’Atlas) : `geo_import_osm_districts` sur un export Overpass (niveaux 8 et 10)
4. **Post-traitement géométrique** : `clean_geometries` (zones et/ou quartiers)
5. **POI** : `geo_import_poi` ou `import_osm_pois`
6. **Hydro** : `geo_import_hydro_zones`

### 5.2 Commandes principales (entrées CLI)

| Étape | Commande (exemple) |
|-------|---------------------|
| Limites HDX / geoBoundaries | `import_hdx_boundaries` / `geo_import_hdx_boundaries` avec `--level adm1|adm2|adm3` et `--schema geoboundaries` (voir aide de la commande) |
| Zones & quartiers OSM | `geo_import_osm_districts --path data/export.geojson` |
| Nettoyage topologique | `clean_geometries --only zones` puis `--only quartiers` si besoin |
| POI fichier | `geo_import_poi --path data/poi.geojson` |
| POI Overpass | `import_osm_pois --query-file ...` |
| Hydro | `geo_import_hydro_zones --path data/hydro.geojson` |
| Démo uniquement | `geo_seed_dummy_communes` (**ne pas** utiliser sur une base officielle) |

Les **exemples de lignes complètes** et les **requêtes Overpass** copiables sont dans [`README_tools.md`](README_tools.md) sections **7** et **8**.

### 5.3 Import via l’admin Django

- **Super-utilisateur** : écran d’import géographique + consultation des **`ImportLog`**.
- L’import **universel** (`run_universal_import`) accepte GeoJSON / KML / Shapefile ; le **type de cible** (ADM1 → Département, etc.) et le **parent** (ex. département pour une commune) doivent être renseignés — voir section **6.3** de `README_tools.md`.

### 5.4 Vérifications avant de dire « le dashboard est alimenté »

1. **Données** : au moins un département avec géométrie ; communes liées ; pour une commune test, zones/quartiers si la carte doit afficher le fin maillage.
2. **HTTP** : tester dans le navigateur ou avec `curl` :
   - `/geo/api/departements/`
   - `/geo/api/communes/geojson/?departement_id=<id>`
   - `/geo/api/zones/geojson/?commune_id=<id>`
3. **Atlas** : ouvrir `/atlas/` ; choisir le département puis la commune ; vérifier le chargement des sous-couches et des POI si activés.
4. **Config** : `.env` avec `DATABASE_URL`, token Mapbox si utilisé (`ILLETO_MAPBOX_ACCESS_TOKEN` / variable attendue par les templates — voir `core/settings.py` et `.env.example`).

---

## 6. Documentation et maintenance

| Document / emplacement | Contenu |
|------------------------|---------|
| [`docs/README_tools.md`](README_tools.md) | Stack, `.env`, liste détaillée des commandes, Overpass, POI, exports Atlas, dépannage GDAL/html2canvas. |
| `apps/geo_data/models.py` | Schéma relationnel et champs. |
| `apps/geo_data/management/commands/` | Point d’entrée des imports. |
| `apps/geo_data/importers/` | Logique réutilisable (HDX, OSM, spatial). |

**Après tout import massif de polygones sous communes**, prévoir un passage **`clean_geometries`** pour aligner les bords sur les communes parentes et limiter les artefacts à l’affichage.

---

## 7. Glossaire rapide

| Terme | Signification |
|-------|----------------|
| **HDX** | Humanitarian Data Exchange — jeux de limites administratives (OCHA, geoBoundaries, etc.). |
| **Overpass** | API de requête sur la base OSM (export JSON utilisé par les imports POI / districts). |
| **Placeholder** | Commune de démo (`is_placeholder=True`), filtrable en API. |
| **Atlas** | Application carte principale du projet (dashboard géographique public / connecté). |

---

*Document généré pour la passation technique — à maintenir à jour lorsque de nouvelles commandes ou modèles sont ajoutés.*
