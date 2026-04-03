

# 📑 README_tools.md

## IlèTô Atlas System (V2.0)

Ce document répertorie l'architecture technique, les commandes
d'administration et les procédures de mise à jour des données
géographiques du projet **IlèTô Atlas**.


------------------------------------------------------------------------


# 🎨 1. Vision & Identité Visuelle (Premium)

Pour maintenir l'aspect **Institutionnel & High-Tech**, respectez
strictement ces codes :

 -----------------------------------------------------------------------
  Élément                 Valeur / Code           Usage
  ----------------------- ----------------------- -----------------------
  Fond Principal          #03050C                 Background sombre
                                                  profond (Slate-950)

  Accent Émeraude         #00875A                 Actions de succès,
                                                  validation, tracés des
                                                  quartiers

  Accent Bronze           #A67C52                 Boutons Premium, Statut
                                                  "Décideur",
                                                  Certification IGN

  Typographie 1           Playfair Display        Titres de sections
                                                  (élégance
                                                  institutionnelle)

  Typographie 2           Inter                   Données techniques,
                                                  coordonnées, menus

  Glassmorphism           Blur: 16px              Panneaux
                                                  semi-transparents
                                                  rgba(3,5,12,0.8)




# 🛠 NOTA BENE

Pillow / Gdal,Bibliothèques système pour traiter les images satellites et les fichiers cartographiques.
Psycopg2-binary,Le connecteur ultra-rapide entre Python et PostgreSQL.

# 🛠 2. Stack Technique & Prérequis

  -----------------------------------------------------------------------
  Outil                   Rôle                    Pourquoi
  ----------------------- ----------------------- -----------------------
  Python 3.11+            Langage Core            Stabilité, performances
                                                  et typage fort

  Django 5.0              Framework Web           Backend robuste et
                                                  support asynchrone

  PostgreSQL + PostGIS    Base de données         Calculs spatiaux et
                                                  gestion des géométries

  django-environ          Sécurité                Gestion des variables
                                                  .env

  Pillow / GDAL           Moteur géospatial       Traitement images
                                                  satellites et SIG

  psycopg2-binary         Connecteur              Interface rapide Python
                                                  ↔ PostgreSQL
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 🚀 3. Installation & Initialisation

## Environnement et dépendances

``` bash
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

# 🗄 Configuration Base de Données (PostgreSQL)

Connexion :

``` bash
sudo -u postgres psql
```

Création :

``` sql
CREATE USER ileto_user WITH PASSWORD 'votre_mot_de_passe';
CREATE DATABASE ileto_db OWNER ileto_user;
GRANT ALL PRIVILEGES ON DATABASE ileto_db TO ileto_user;
```

Activation PostGIS :

``` sql
\c ileto_db;
CREATE EXTENSION postgis;
```

------------------------------------------------------------------------

# 📥 4. Pipeline d'Importation des Données

## Communes (Niveau 6)

``` bash
python manage.py geo_import_vector_benin --clear-placeholders --import-communes
```

## Arrondissements & Quartiers

Migration :

``` bash
python manage.py migrate geo_data
```

Simulation :

``` bash
python manage.py geo_import_osm_districts --path data/export_quartiers.geojson --dry-run
```

Import réel :

``` bash
python manage.py geo_import_osm_districts --path data/export_quartiers.geojson
```

------------------------------------------------------------------------

# 🌍 5. Procédures Overpass Turbo

Site : https://overpass-turbo.eu

## Communes

``` txt
[out:json][timeout:60];
area["name"="Bénin"]->.a;
(
relation["admin_level"="6"](area.a);
);
out body; >; out skel qt;
```

## Quartiers & Arrondissements

``` txt
[out:json][timeout:300];
area["name"="Bénin"]->.a;
(
relation["admin_level"~"8|10"](area.a);
way["admin_level"~"8|10"](area.a);
);
out body; >; out skel qt;
```

------------------------------------------------------------------------

# 💡 6. Maintenance & Troubleshooting

## Export par département

Exemple Littoral :

``` txt
area["name"="Littoral"]->.a;
(
relation["admin_level"~"8|10"](area.a);
way["admin_level"~"8|10"](area.a);
);
out body; >; out skel qt;
```

Import :

``` bash
python manage.py geo_import_osm_districts --path data/export_littoral.geojson
```

------------------------------------------------------------------------

# 🧹 Nettoyage Base de Données (Docker)

``` bash
docker exec -it ileto_db_container psql -U root -d ileto_db -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```


# 🧹 Mes sauvegarde

python manage.py migrate geo_data  

python manage.py geo_import_osm_districts --dry-run

# quartier 

``` bash

[out:json][timeout:250];
area["name"="Bénin"]->.a;
(
  // Niveau 8 : Arrondissements
  relation["admin_level"="8"](area.a);
  way["admin_level"="8"](area.a);
  
  // Niveau 10 : Quartiers et Villages
  relation["admin_level"="10"](area.a);
  way["admin_level"="10"](area.a);
);
out body;
>;
out skel qt;

```

# 1. Code pour les Communes (Niveau 6)

Ce fichier sert pour la base de ton Atlas et le calcul des centroïdes.

Requête Overpass :

``` bash 

[out:json][timeout:60];
area["name"="Bénin"]->.a;
(
  relation["admin_level"="6"](area.a);
);
out body;
>;
out skel qt;

```

# fichier : data/export.geojson


Commande : 

``` bash 

python manage.py geo_import_vector_benin --import-communes

```

# 2. Code pour les Arrondissements & Quartiers (Niveaux 8 & 10)

Ce fichier est le plus lourd, il contient la précision "Premium" d'IlèTô.

Requête Overpass :

/// code global mais lourd 

``` bash 

[out:json][timeout:300];
area["name"="Bénin"]->.a;
(
  // Niveau 8 : Arrondissements
  relation["admin_level"="8"](area.a);
  way["admin_level"="8"](area.a);
  
  // Niveau 10 : Quartiers et Villages
  relation["admin_level"="10"](area.a);
  way["admin_level"="10"](area.a);
);
out body;
>;
out skel qt;

```

// si ca ne marche pas 


# Méthode 1 : Séparer les Arrondissements (8) et les Quartiers (10)
C'est la méthode la plus simple. Fais deux exports distincts.

# Requête A (Arrondissements - Niveau 8) :

Extrait de code

``` bash  

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

# Requête B (Quartiers/Villages - Niveau 10) :

Attention, celle-ci est la plus lourde.

Extrait de code

``` bash 
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

# Méthode 2 : Filtrer par Département (La plus fiable)

Si la méthode 1 échoue encore, exporte les quartiers département par département (ex: Littoral, Atlantique, Ouémé). C'est beaucoup plus léger pour le serveur.

Exemple pour le Littoral (Cotonou) :

Extrait de code

``` bash 

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

# Fichier : data/export_quartiers.geojson

# Commande : python manage.py geo_import_osm_districts


# 3. Code pour les Points d'Intérêt (POI)

Si tu veux mettre à jour les gares, marchés et hôpitaux.

Requête Overpass :

``` bash 

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

# Fichier : data/export_poi.geojson

# Commande d'import POI (IlèTô V2)

```bash
python manage.py geo_import_poi --path data/poi.geojson
python manage.py geo_import_poi --path data/poi.geojson --dry-run
```

Chaque feature doit être un **Point** (`geometry.type === "Point"`). Propriétés utiles : `name` / `name:fr`, `category` (valeurs : `health`, `market`, `transport`, `education`, `culture`, `admin`, `other`), ou tags OSM (`amenity`, `shop`) pour inférence. Optionnel : `external_id` (ou `@id`) pour réimport idempotent. Rattachement : `Quartier.geom__covers(point)` puis sinon `Commune.geom__covers(point)` ; les points hors territoire sont ignorés.

API carte : `GET /geo/api/poi/geojson/?commune_id=<pk>`.

------------------------------------------------------------------------

# La Procédure de Mise à Jour

Sur Overpass Turbo : Tu exécutes les deux requêtes (Communes puis Quartiers).

Remplacement : Tu remplaces les anciens fichiers dans data/ par les nouveaux.

Importation Django : Tu relances les commandes d'importation. Le script est intelligent : grâce au update_or_create, il mettra à jour les géométries existantes et créera les nouvelles sans supprimer ton travail.

------------------------------------------------------------------------

# 💡 Conseil pour ton projet IlèTô

Une fois que tu as téléchargé les fichiers (même si tu en as plusieurs), tu peux les fusionner manuellement ou simplement lancer ta commande Django plusieurs fois sur chaque fichier :

Bash

``` bash 

python manage.py geo_import_osm_districts --path data/export_littoral.geojson
python manage.py geo_import_osm_districts --path data/export_atlantique.geojson

```

------------------------------------------------------------------------

## Change Log V2.0 (Premium SaaS)

### Palette & identité

- **Fond principal** : `#03050C`
- **Accents** : Emerald `#00875A`, Bronze `#A67C52`
- Panneaux type « glass » : flou **16px** (`backdrop-filter`), appliqués aux panneaux latéraux Atlas.

### Rôles utilisateur (`user_type`)

- **STUDENT**, **PROFESSIONAL**, **INSTITUTION** (modèle `accounts.User`).
- **Passer en Mode Décideur** : simulation paiement (modal carte / MoMo) puis `POST /auth/api/atlas/simulate-professional/` ; après succès, rafraîchissement. Les comptes **PROFESSIONAL** affichent le badge **Certifié IGN**.

### Exports

- **PNG** : filigrane diagonal « IlèTô · SIMULATION » pour **STUDENT** et utilisateurs **PUBLIC** (non connectés ou hors pro) ; pas de filigrane pour **PROFESSIONAL**.
- **GeoJSON** : propriété `illeto_simulation: true` pour les exports non professionnels ; exports pro sans ce flag (données « certifiées » côté produit).

### Zones & quartiers

- **API** : `GET /geo/api/zones/geojson/?commune_id=<pk>` — renvoie zones (arrondissements) et quartiers avec `kind` (`zone` / `quartier`).
- Carte : sous-couches en Emerald, `fillOpacity: 0.1`, `weight: 1` ; aperçu SVG aligné sur la zone/quartier sélectionné.

### Analyse risque inondation (Atlas)

- Couche **hydrographie** active (lignes Overpass) + polygone sélectionné (zone ou quartier).
- **Turf.js** : `booleanIntersects` entre chaque ligne hydro et le polygone — si intersection → **Zone humide** (ambre) dans le panneau latéral ; sinon **Normal**.

### Points d’intérêt (POI)

- Modèle **`PointInteret`** (nom, catégorie, `Point`, liens `Commune` / `Quartier`).
- Commande **`python manage.py geo_import_poi --path <fichier.geojson>`** : rattachement `geom__covers` (quartier prioritaire, puis commune).
- Carte : marqueurs **Emerald** (santé, éducation, administration) vs **Bronze** (marché, transport, culture, autre).

### Export Engine (Atlas)

Le **moteur d’export** côté navigateur (`IlletoExportEngine/1`) prépare les fichiers à partir de la sélection courante (département, commune, zone/quartier).

**GeoJSON (`.json`)** : une `FeatureCollection` avec, si l’option *Inclure les métadonnées* est cochée, un bloc `properties` au niveau collection (`generated`, `source`, `engine`) et des propriétés par entité (niveau administratif, `illeto_simulation` pour les profils non professionnels, etc.). Sans métadonnées : géométries seules, `properties` vides.

**Bundle « Shapefile » (`.zip`)** : ce n’est pas encore un jeu `.shp/.shx/.dbf` binaire produit entièrement dans le navigateur ; l’archive contient :

- `territoire.geojson` — géométrie WGS84 (EPSG:4326) ;
- `Illeto_metadata.json` — résumé d’export, nombre d’entités, référence CRS, lien avec le moteur ;
- `WGS84.prj` — chaîne WKT du système **GCS_WGS_1984** pour outils SIG ;
- `LISEZMOI.txt` — notice courte.

**Injection métadonnées dans un vrai Shapefile (pipeline serveur)** : pour produire `.shp/.dbf/.shx`, un service backend (ex. GDAL, GeoPandas ou `ogr2ogr`) lit le GeoJSON exporté et mappe les champs vers le **DBF** : par convention IlèTô, colonnes typiques `NAME` (nom territoire), `LEVEL` (`department` / `commune` / `subdivision`), `DEPT`, `COMMUNE`, `ILLETO_SIM` (0/1 simulation), `GENERATED` (ISO datetime). Le fichier **`.cpg`** peut être fixé à `UTF-8` pour l’alignement avec les chaînes Unicode du GeoJSON. Le **`.prj`** du lot serveur doit reprendre le même référentiel que `WGS84.prj` du bundle.

**PNG / PDF** : capture de l’élément `#map` via **html2canvas** ; le PDF (**jsPDF**, format A4) intègre l’image et, si les métadonnées sont demandées, une ligne de titre et la date de génération. L’option *Haute résolution (300 dpi)* augmente le `scale` de rendu html2canvas (approximation écran).

### Native SHP Engine (serveur Django)

Le **moteur Shapefile natif** tourne côté serveur dans `apps/geo_data/views.py` (`export_shapefile_view`). Il s’appuie sur **GeoPandas** et la pile **GDAL/Fiona** (écriture driver `ESRI Shapefile`) pour produire un jeu de fichiers binaires **`.shp`, `.shx`, `.dbf`, `.prj`** (et éventuellement `.cpg`) directement compatibles **QGIS** et **ArcGIS**.

- **Endpoint** : `GET /geo/api/export/shapefile/<territory_type>/<territory_id>/`  
  - `territory_type` ∈ `commune` | `zone` | `quartier`  
  - `territory_id` : clé primaire du modèle correspondant.
- **Accès** : utilisateur **authentifié** et `user_type` ∈ **PROFESSIONAL** ou **INSTITUTION** ; sinon **401/403** (JSON).
- **Réponse** : `FileResponse` — archive **`application/zip`** nommée `IleTo_Export_<slug>_<YYYYMMDD_HHMM>.zip`, contenant les fichiers du shapefile.
- **Attributs DBF** (noms de champs ≤ 10 caractères) : **`NAME`**, **`KIND`**, **`DEPT`**, **`CODE_INSAE`** (vide tant que non alimenté en base), **`SOURCE`** (`Illeto`).
- **CRS** : EPSG:4326 (WGS 84), fichier `.prj` généré par GDAL.

**Dépendances système** : en production, le serveur doit disposer de **GDAL** (souvent via paquets `gdal` / `libgdal` ou environnement conda). `pip install geopandas` suffit si les bibliothèques GDAL sont présentes sur la machine.

**Atlas (frontend)** : pour le format « Shapefile » dans la modale d’export, les comptes **PRO / INSTITUTION** déclenchent un `fetch` vers cet endpoint ; les profils **STUDENT** (et non connectés) conservent l’archive **client** GeoJSON + `Illeto_metadata.json` avec drapeaux `illeto_simulation` / `limited_export`.

pour le test cree un fichier et tu met ce contenu dedans 

{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"Test POI","category":"health"},"geometry":{"type":"Point","coordinates":[2.42,6.37]}}]}

------------------------------------------------------------------------


# Mes notes perles mele 

{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"Test POI","category":"health"},"geometry":{"type":"Point","coordinates":[2.42,6.37]}}]}

Liaison Spatiale Automatique : Tes POI (Hôpitaux, Marchés, Écoles) sont désormais capables de "savoir" tout seuls dans quel quartier et quelle commune ils se trouvent grâce à geom__covers.

Visualisation Contextuelle : Les marqueurs utilisent ta nouvelle identité visuelle : Émeraude (#00875A) pour les services essentiels et Bronze (#A67C52) pour les activités commerciales et autres.

L'intégration de Turf.js permet de détecter en temps réel si un quartier est en zone inondable.

L'Urbanisme Prédictif : Calculer la croissance d'une ville en comparant la densité de POI entre deux zones.

Le Module de Messagerie : Permettre à un "Décideur" de contacter directement un expert pour une expertise sur un quartier spécifique.


1. La stratégie "Département par Département"
Rends-toi sur overpass-turbo.eu et exécute la requête ci-dessous pour chaque département majeur (commence par l'Atlantique, l'Ouémé, etc.).

Requête à copier (Exemple pour l'Atlantique) :

[out:json][timeout:300];
// On cible un département précis
area["name"="Atlantique"]->.a;
(
  relation["admin_level"~"8|10"](area.a);
  way["admin_level"~"8|10"](area.a);
);
out body;
>;
out skel qt;

Répète l'opération pour les autres :

Remplace "Atlantique" par "Ouémé", "Borgou", "Zou", etc.

Enregistre chaque fichier avec un nom clair : data/export_atlantique.geojson, data/export_oueme.geojson.
https://overpass-api.de/api/
2. Importation groupée dans Django
Une fois que tu as tes fichiers, tu n'as pas besoin de changer ton code. Tu lances simplement la commande pour chaque fichier. Le script est intelligent : il ne créera pas de doublons si tu relances deux fois le même fichier.

# Import de l'Atlantique (Abomey-Calavi, Ouidah, etc.)
python manage.py geo_import_osm_districts --path data/export_atlantique.geojson

# Import de l'Ouémé (Porto-Novo, Sèmè-Kpodji, etc.)
python manage.py geo_import_osm_districts --path data/export_oueme.geojson

# Import du Littoral (Cotonou)
python manage.py geo_import_osm_districts --path data/export_littoral.geojson

(Fiona est le moteur qui permet d'écrire les fichiers .shp).


(si tu n'as pas QGIS, il existe des visualiseurs de Shapefile en ligne gratuits)

À prévoir en production
Présence de GDAL sur le serveur (souvent paquets système en plus de pip).
Si to_file échoue (GDAL manquant), l’API renvoie 500 avec détail dans le JSON.





# Import du Departments (Cotonou)

Fixed Query for Benin Departments (Alibori, Atacora, etc.):

[out:json][timeout:180];

// Get Benin's boundary
area["ISO3166-1"="BJ"]["admin_level"="2"]->.searchArea;

// Query for departments (admin_level=4) - the regions you listed
(
  relation["boundary"="administrative"]["admin_level"="4"](area.searchArea);
  way["boundary"="administrative"]["admin_level"="4"](area.searchArea);
);

out geom;

# Import du Departments (Cotonou) Or if you want communes (admin_level=6) instead:


[out:json][timeout:180];

area["ISO3166-1"="BJ"]["admin_level"="2"]->.searchArea;

(
  relation["boundary"="administrative"]["admin_level"="6"](area.searchArea);
  way["boundary"="administrative"]["admin_level"="6"](area.searchArea);
);

out geom;

# Import du par commune  (Cotonou)

[out:json][timeout:60];

// Test with just one department first
area["name"="Alibori"]["admin_level"="4"]->.a;

(
  relation["boundary"="administrative"](area.a);
);

out geom;







------------------------

enfin


[out:json][timeout:180];

// For Alibori:
area["name"="Alibori"]["admin_level"="4"]->.searchArea;

(
  relation["boundary"="administrative"]["admin_level"="8"]["name"](area.searchArea);
);

out geom;




Installe GDAL si besoin :

sudo apt install gdal-bin

Puis convertis :

ogr2ogr -f GeoJSON benin_admin.geojson gis_osm_admin_a_free_1.shp

Tu obtiens :

benin_admin.geojson

------------------------------------------------------------------------------
python manage.py geo_import_vector_benin --name-field=NOM_OFFICIEL --code-field=ID_IGN_2027

HDX
python manage.py geo_import_hdx --name-field=adm2_name --code-field=adm2_pcode
------------------------------------------------------------------------------

geo_import_hdx_boundaries : Pour le squelette officiel (ADM1/ADM2).

geo_import_osm_districts : Pour les muscles (Quartiers).

geo_import_poi : Pour les organes (Hôpitaux, Écoles).

**geo_import_hydro_zones** : Zones hydrologiques (PostGIS).

**geo_import_vector_benin** : Départements / communes depuis OGR, GeoJSON ou OSM JSON.

**geo_seed_dummy_communes** : Données de test uniquement (jamais sur la base officielle en production).

Exemples **geo_import_hdx_boundaries** (champs `adm1_*` / `adm2_*` HDX gérés en interne) :

```bash
python manage.py geo_import_hdx_boundaries --path data/benin_adm1.geojson --level adm1
python manage.py geo_import_hdx_boundaries --path data/benin_adm2.geojson --level adm2
```



------------------------------------------------------------

Fichier GeoJSON	Commande Django à utiliser
ben_admin1.geojson	python manage.py geo_import_hdx_boundaries --level adm1
ben_admin2.geojson	python manage.py geo_import_hdx_boundaries --level adm2
ben_adminpoints.geojson	python manage.py geo_import_poi
ben_adminlines.geojson	python manage.py geo_import_vector_benin (pour les tracés de frontières)


# 1. Vide la base de données (Attention : supprime TOUTES les données, garde les tables)
python manage.py flush --no-input

# 2. Applique les dernières migrations (pour code_officiel et ImportLog)
python manage.py migrate


🏗️ ÉTAPE 1 : Le Squelette (Administration)
On commence par les limites officielles. C'est la base de tout ton système.

Bash
# A. Importer les 12 Départements (Niveau 1)
python manage.py geo_import_hdx_boundaries --path data/ben_admin1.geojson --level adm1

# B. Importer les 77 Communes (Niveau 2)
python manage.py geo_import_hdx_boundaries --path data/ben_admin2.geojson --level adm2
🫀 ÉTAPE 2 : Les Organes (Points d'Intérêt)
Maintenant que les communes existent, on peut y "piquer" les points importants.

Bash
# Importer les chefs-lieux et points administratifs
python manage.py geo_import_poi --path data/ben_adminpoints.geojson
Note : Si cette commande échoue sur le mapping, utilise geo_import_vector_benin avec les arguments de mapping vus précédemment.

💪 ÉTAPE 3 : Les Muscles (Quartiers & Zones)
On descend dans le détail avec les données issues d'OpenStreetMap (si tu as ton fichier de quartiers).
python manage.py geo_import_poi --path data/ben_admincapitals.geojson
Bash
# Importer les quartiers et zones (OSM)
python manage.py geo_import_osm_districts --path data/export_quartiers.json
🌊 ÉTAPE 4 : Le Système Vital (Hydrologie)
Pour que tes calculs de risques d'inondation fonctionnent sur le Dashboard.

Bash
# Importer les zones humides et cours d'eau
python manage.py geo_import_hydro_zones --path data/hydro.geojson



-------------------------------------------------------------------------