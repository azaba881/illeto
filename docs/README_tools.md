# IlèTô Atlas — Outils, données et procédures

Documentation technique pour l’équipe : stack, configuration, imports géographiques (PostGIS), requêtes Overpass, exports Atlas et maintenance. Pour l’installation générale du projet, se référer aussi au `README` principal si présent.

---

## Sommaire

1. [Stack et prérequis](#1-stack-et-prérequis)
2. [Installation rapide](#2-installation-rapide)
3. [Base PostgreSQL / PostGIS](#3-base-postgresql--postgis)
4. [Configuration (.env)](#4-configuration-env)
5. [Modèles géographiques (rappel)](#5-modèles-géographiques-rappel)
6. [Moteur d’import](#6-moteur-dimport)
7. [Workflow recommandé (ordre des imports)](#7-workflow-recommandé-ordre-des-imports)
8. [Overpass Turbo — requêtes types](#8-overpass-turbo--requêtes-types)
9. [Points d’intérêt (POI)](#9-points-dintérêt-poi)
10. [Exports Atlas (V2)](#10-exports-atlas-v2)
11. [Identité visuelle (référence)](#11-identité-visuelle-référence)
12. [Maintenance et dépannage](#12-maintenance-et-dépannage)

---

## 1. Stack et prérequis

| Composant | Rôle |
|-----------|------|
| **Python 3.11+** | Runtime |
| **Django 5.x** | Backend web |
| **PostgreSQL + PostGIS** | Données et géométries |
| **GDAL / GEOS** (système + bindings Python) | Lecture SHP, KML, GeoJSON via OGR ; exports shapefile serveur |
| **django-environ** | Variables d’environnement |
| **psycopg2** (ou binaire) | Driver PostgreSQL |
| **Pillow** | Images (hors cœur géo) |
| **GeoPandas** (exports shapefile natifs) | Voir endpoint export serveur |

En production : vérifier la présence de **GDAL** au niveau système (`gdal-bin`, `libgdal`) en plus de `pip`.

---

## 2. Installation rapide

```bash
python3 -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
```

Lancer le serveur de développement :

```bash
python manage.py runserver
```

---

## 3. Base PostgreSQL / PostGIS

Exemple sous Linux (utilisateur shell `postgres`) :

```bash
sudo -u postgres psql
```

```sql
CREATE USER ileto_user WITH PASSWORD 'votre_mot_de_passe';
CREATE DATABASE ileto_db OWNER ileto_user;
GRANT ALL PRIVILEGES ON DATABASE ileto_db TO ileto_user;
\c ileto_db
CREATE EXTENSION postgis;
```

La chaîne de connexion typique : `postgis://USER:PASSWORD@HOST:5432/ileto_db` (voir `DATABASE_URL` dans `.env`).

---

## 4. Configuration (.env)

Copier `.env.example` vers `.env` et renseigner au minimum :

- **`SECRET_KEY`**, **`DEBUG`**, **`ALLOWED_HOSTS`**, **`DATABASE_URL`**
- **`ILLETO_MAPBOX_ACCESS_TOKEN`** (carte)

Variables liées aux **imports** (chemins par défaut si une commande est lancée sans fichier explicite) :

| Variable | Usage |
|----------|--------|
| `ILLETO_HDX_ADM1_PATH` | Fichier ADM1 (départements) |
| `ILLETO_HDX_ADM2_PATH` | Fichier ADM2 (communes) |
| `ILLETO_HDX_ADM3_PATH` | Fichier ADM3 (zones / arrondissements selon schéma) |
| `ILLETO_OVERPASS_API_URL` | API Overpass pour `import_osm_pois` |
| `ILLETO_OSM_DISTRICTS_PATH` | Export OSM quartiers / arrondissements |
| `ILLETO_POI_GEOJSON_PATH` | GeoJSON POI |
| `ILLETO_HYDRO_GEOJSON_PATH` | GeoJSON hydro |
| `ILLETO_VECTOR_IMPORT_DEFAULT_PATH` | Chemin vectoriel générique (legacy) |
| `ILLETO_GEO_INCLUDE_PLACEHOLDER_COMMUNES` | Comportement API / filtres communes placeholder |

---

## 5. Modèles géographiques (rappel)

Hiérarchie métier courante :

- **`Departement`** — niveau ADM1 (limites officielles type HDX)
- **`Commune`** — ADM2, rattachée à un département
- **`Zone`** — arrondissement (souvent ADM3 ou OSM `admin_level=8`), rattachée à une **commune**
- **`Quartier`** — OSM `admin_level=10`, rattaché à une commune
- **`PointInteret`** — point ; rattachement spatial `geom__covers` (quartier prioritaire, puis commune)
- **`HydroZone`** — polygones hydro (risque inondation, etc.)

Les imports **HDX** (`geo_import_hdx_boundaries` / `import_hdx_boundaries`) gèrent OCHA + geoBoundaries avec idempotence et option **`--update-geometry`**.

---

## 6. Moteur d’import

### 6.1 Organisation du code

- Logique métier : **`apps/geo_data/importers/`** (HDX, OSM, universel, utilitaires géométrie / spatial).
- Entrées CLI : **`apps/geo_data/management/commands/*.py`** (une commande = un fichier plat ; pas de sous-dossiers, Django ne les charge pas).
- Traçabilité : **`ImportLog`** + **`record_import_run`** ; l’**admin** superuser peut uploader un fichier et consulter les journaux.

### 6.2 Commandes `manage.py`

| Commande | Cible | Notes |
|----------|--------|--------|
| **`import_hdx_boundaries`** / **`geo_import_hdx_boundaries`** | `Departement`, `Commune`, `Zone` (selon `--level` / `--schema`) | Fichier ou chemins `ILLETO_HDX_ADM*_PATH` |
| **`geo_import_vector_benin`** | Départements / communes (legacy, LayerMapping, OGR / GeoJSON / OSM JSON) | Utile pour jeux vectoriels historiques |
| **`geo_import_osm_districts`** | `Zone` (niveau 8) et `Quartier` (niveau 10) | Rattachement commune par centroïde ; `--dry-run` possible |
| **`geo_import_poi`** | `PointInteret` depuis GeoJSON **Point** | |
| **`import_osm_pois`** | `PointInteret` via **Overpass** | `--query-file` ; URL = `ILLETO_OVERPASS_API_URL` |
| **`geo_import_hydro_zones`** | `HydroZone` (polygones GeoJSON) | |
| **`geo_seed_dummy_communes`** | Données de démo | Ne pas utiliser sur une base « officielle » |

### 6.3 Import universel (Python + Admin)

La fonction **`run_universal_import`** (`apps/geo_data/importers/universal/vector_runner.py`) écrit vers :

- **`Departement`**, **`Commune`** (obligatoire : `departement_pk`), **`Zone`** (obligatoire : `commune_pk` ; le champ « code » du formulaire alimente **`osm_id`** si renseigné), **`HydroZone`** (via chemins dédiés plutôt que l’admin hydro dédié).

Formats : **GeoJSON**, **KML**, **Shapefile** (couche index 0).

**Admin Django** : *ImportLog* → **Importer un fichier géographique**. Choix explicite du modèle :

- ADM1 → Département  
- ADM2 → Commune + **département parent**  
- ADM3 / arrondissements → **Zone** + **commune parente** (une commune par fichier pour cet écran ; pour un jeu national ADM3, préférer **`import_hdx_boundaries`** niveau `adm3`)

---

## 7. Workflow recommandé (ordre des imports)

1. **Migrations** : `python manage.py migrate`
2. **Squelette administratif** (HDX ou équivalent) :
   - ADM1 → départements  
   - ADM2 → communes  
   - ADM3 → zones (si jeu geoBoundaries / HDX cohérent)
3. **Détail urbain OSM** (optionnel) : `geo_import_osm_districts` sur export Overpass (niveaux 8 et 10)
4. **POI** : `geo_import_poi` ou `import_osm_pois`
5. **Hydro** : `geo_import_hydro_zones`

Exemples :

```bash
python manage.py import_hdx_boundaries --schema geoboundaries --level adm1 --update-geometry
python manage.py import_hdx_boundaries --schema geoboundaries --level adm2 --update-geometry
python manage.py import_hdx_boundaries --schema geoboundaries --level adm3 --path data/geoBoundaries-BEN-ADM3.geojson --update-geometry

python manage.py geo_import_osm_districts --path data/export_quartiers.geojson --dry-run
python manage.py geo_import_osm_districts --path data/export_quartiers.geojson

python manage.py geo_import_poi --path data/poi.geojson
python manage.py import_osm_pois --query-file queries/pois.txt

python manage.py geo_import_hydro_zones --path data/hydro.geojson
```

**Legacy communes (niveau OSM 6)** — si vous utilisez encore l’ancien pipeline :

```bash
python manage.py geo_import_vector_benin --clear-placeholders --import-communes
```

Imports **multi-fichiers** (ex. un GeoJSON par département) : enchaîner plusieurs fois `geo_import_osm_districts --path …` ; les scripts utilisent en général `update_or_create` / clés stables pour limiter les doublons.

---

## 8. Overpass Turbo — requêtes types

Site : [Overpass Turbo](https://overpass-turbo.eu)  
API publique (référence) : [overpass-api.de](https://overpass-api.de/api/)

### 8.1 Communes (admin_level = 6)

```text
[out:json][timeout:60];
area["name"="Bénin"]->.a;
(
  relation["admin_level"="6"](area.a);
);
out body;
>;
out skel qt;
```

Export → GeoJSON, puis selon votre chaîne : `geo_import_vector_benin --import-communes` ou alignement HDX.

### 8.2 Arrondissements (8) et quartiers (10) — requête combinée

Peut être lourde ; préférer par **département** si timeout.

```text
[out:json][timeout:300];
area["name"="Bénin"]->.a;
(
  relation["admin_level"="8"](area.a);
  way["admin_level"="8"](area.a);
  relation["admin_level"="10"](area.a);
  way["admin_level"="10"](area.a);
);
out body;
>;
out skel qt;
```

### 8.3 Variante : uniquement niveau 8 ou 10

**Niveau 8 :**

```text
[out:json][timeout:300];
area["name"="Bénin"]->.a;
(
  relation["admin_level"="8"](area.a);
  way["admin_level"="8"](area.a);
);
out body;
>;
out skel qt;
```

**Niveau 10 :**

```text
[out:json][timeout:600];
area["name"="Bénin"]->.a;
(
  relation["admin_level"="10"](area.a);
  way["admin_level"="10"](area.a);
);
out body;
>;
out skel qt;
```

### 8.4 Par département (ex. Littoral)

```text
[out:json][timeout:300];
area["name"="Littoral"]->.a;
(
  relation["admin_level"~"8|10"](area.a);
  way["admin_level"~"8|10"](area.a);
);
out body;
>;
out skel qt;
```

Remplacer `"Littoral"` par `"Atlantique"`, `"Ouémé"`, etc., pour alléger la charge sur l’API.

### 8.5 POI (exemple)

```text
[out:json][timeout:120];
area["name"="Bénin"]->.a;
(
  node["amenity"~"market|hospital|bus_station|pharmacy|school|bank"](area.a);
  way["amenity"~"market|hospital|bus_station|pharmacy|school|bank"](area.a);
);
out body;
>;
out skel qt;
```

---

## 9. Points d’intérêt (POI)

- **Import fichier** : `geo_import_poi --path fichier.geojson` (option `--dry-run`)
- Chaque feature : géométrie **Point** ; propriétés utiles : `name` / `name:fr`, `category`, tags OSM (`amenity`, `shop`) pour catégorisation ; `external_id` ou `@id` pour réimport idempotent.
- **Rattachement** : quartier par `geom__covers`, sinon commune.

**API** (exemple) : `GET /geo/api/poi/geojson/?commune_id=<pk>`

**Fichier de test minimal (GeoJSON)** :

```json
{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"Test POI","category":"health"},"geometry":{"type":"Point","coordinates":[2.42,6.37]}}]}
```

---

## 10. Exports Atlas (V2)

### Rôles (`user_type`)

- **STUDENT**, **PROFESSIONAL**, **INSTITUTION** (modèle utilisateur applicatif).
- Mode « Décideur » / pro simulé : flux API dédié (voir code `accounts` / auth Atlas).

### Exports carte (résumé)

- **PNG** : filigrane type simulation pour profils non professionnels selon règles produit.
- **GeoJSON** : drapeau type `illeto_simulation` pour exports « non certifiés » côté métier.
- **Bundle ZIP côté client** : GeoJSON + métadonnées + `.prj` (voir moteur export navigateur).
- **Shapefile natif serveur** : `GET /geo/api/export/shapefile/<territory_type>/<territory_id>/` avec `territory_type` ∈ `commune` | `zone` | `quartier` ; accès typiquement **PROFESSIONAL** / **INSTITUTION** ; archive ZIP avec `.shp`, `.shx`, `.dbf`, `.prj` (EPSG:4326). Dépend de **GDAL** + **GeoPandas** côté serveur.

### Couches et analyses

- **Zones / quartiers** : `GET /geo/api/zones/geojson/?commune_id=<pk>` (propriété `kind` : `zone` / `quartier`).
- **Risque inondation (Atlas)** : intersection hydro (ex. Turf.js `booleanIntersects`) avec le polygone sélectionné.

---

## 11. Identité visuelle (référence)

| Élément | Valeur | Usage |
|---------|--------|--------|
| Fond principal | `#03050C` | Fond sombre |
| Accent émeraude | `#00875A` | Succès, tracés quartiers, certains POI |
| Accent bronze | `#A67C52` | Actions premium, statut décideur, autres POI |
| Titres | Playfair Display | Titres institutionnels |
| Corps / UI | Inter | Données, menus |
| Panneaux | Glass ~16px blur | `rgba(3,5,12,0.8)` |

---

## 12. Maintenance et dépannage

### Réinitialiser le schéma (Docker — destructif)

```bash
docker exec -it ileto_db_container psql -U root -d ileto_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

Puis recréer PostGIS (`CREATE EXTENSION postgis;`) et relancer les migrations.

### Vider les données Django (attention)

```bash
python manage.py flush --no-input
python manage.py migrate
```

### GDAL / ogr2ogr

```bash
sudo apt install gdal-bin
# Exemple conversion SHP → GeoJSON
ogr2ogr -f GeoJSON sortie.geojson entree.shp
```

Si l’export shapefile API renvoie **500**, vérifier les logs : GDAL manquant ou erreur d’écriture.

### Corriger des imports erronés

Les suppressions ciblées se font en **shell Django** ou par requêtes SQL selon votre politique de données ; exemple (à adapter) :

```bash
python manage.py shell
```

```python
from apps.geo_data.models import Departement
# Exemple : supprimer des lignes importées par erreur (critères à définir)
# Departement.objects.filter(...).delete()
```

---

