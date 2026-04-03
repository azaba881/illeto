

<img width="305" height="306" alt="favicon" src="https://github.com/user-attachments/assets/13a6536a-ae95-49a8-8a11-052ea972de8c" />

# IlèTô - Plateforme d'Intelligence Territoriale du Bénin

IlèTô  est un Système d'Information Géographique (SIG) de nouvelle génération dédié à la visualisation, l'analyse et la gestion des données administratives, hydrologiques et socio-économiques du Bénin.

## 🚀 Fonctionnalités Clés

* **Atlas Interactif** : Visualisation dynamique des 12 départements et 77 communes avec mode sombre/clair spécifique à la carte.
* **Données Officielles** : Intégration des PCodes HDX/OCHA pour une conformité avec les standards internationaux et gouvernementaux.
* **Analyse de Risque** : Calcul spatial via PostGIS (ST_Intersection) pour évaluer l'aléa inondation par zone.
* **Système d'Importation Robuste** : Suite de commandes geo_import_* pour absorber des données OSM, HDX, et IGN.
* **Espace Professionnel** : Exportation de données aux formats SHP (Shapefile), KML et CSV pour les experts en urbanisme.

## 🛠 Stack Technique

* **Backend** : Django 5.x (Python 3.12)
* **Base de données** : PostgreSQL + PostGIS (Extension spatiale)
* **Cartographie** : Mapbox GL JS / Leaflet
* **Traitement de données** : GDAL/OGR, GeoPandas

## 📂 Architecture des Commandes (Moteur SIG)

Pour maintenir l'intégrité du système, les imports doivent suivre cette hiérarchie (le "Corps Humain") :

* **Squelette (Admin)** : geo_import_hdx_boundaries — Définit les limites ADM1/ADM2.
* **Muscles (Quartiers)** : geo_import_osm_districts — Découpage fin issu d'OpenStreetMap.
* **Organes (POI)** : geo_import_poi — Écoles, hôpitaux, marchés.
* **Système Vital (Eau)** : geo_import_hydro_zones — Zones hydrologiques et risques.
* **Adaptateur Universel** : geo_import_vector_benin — Pour tout fichier externe (IGN, etc.) avec mapping dynamique.

## ⚙️ Installation & Configuration

### 1. Clonage et Environnement

```bash
git clone https://github.com/votre-repo/illeto.git
cd illeto
python -m venv venv
source venv/bin/activate  # ou venv\Scripts\activate sur Windows
pip install -r requirements.txt
```

### 2. Base de données

Assurez-vous que PostGIS est activé sur votre instance PostgreSQL :

```sql
CREATE EXTENSION postgis;
```

### 3. Initialisation des données

```bash
python manage.py migrate
# Importation du squelette officiel (HDX)
python manage.py geo_import_hdx_boundaries --path data/ben_admin1.geojson --level adm1
python manage.py geo_import_hdx_boundaries --path data/ben_admin2.geojson --level adm2
```

## 📊 Observabilité & Audit

Chaque action d'importation est tracée dans le modèle `ImportLog`. Vous pouvez consulter l'état de santé des données et les journaux d'erreurs via le tableau de bord de maintenance :

👉 [/admin/geo-maintenance/](http://127.0.0.1:8000/admin/geo-maintenance/)

## 🎨 Guide de Style (UI/UX)

* **Thème Global** : Light Premium (Effets de transparence, Glassmorphism).
* **Thème Carte** : Toggle spécifique (Dark par défaut / Light).
* **Code Couleurs POI** :

  * Santé : Émeraude (#50C878)
  * Marchés & Transport : Bronze (#CD7F32)
  * Sélection Active : Bleu Électrique (#007BFF)

## 📝 Licence

Propriété exclusive de Innocent Kpade. Tous droits réservés.

## 💡 Note 

Pour toute modification massive de la structure géographique, utilisez toujours la commande `python manage.py flush` avant de réimporter les fichiers ADM pour éviter les doublons de PCodes.
