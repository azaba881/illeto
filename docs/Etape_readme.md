
1-python manage.py import_hdx_boundaries --schema geoboundaries --level adm1 --update-geometry ( essayer d'importer dans admin)

2-python manage.py geo_import_vector_benin --clear-placeholders --import-communes 

3-python manage.py import_hdx_boundaries --schema geoboundaries --level adm3 --path data/geoBoundaries-BEN-ADM3.geojson --update-geometry  ( importer dans admin )

4-python manage.py geo_import_poi --path data/ben_poi_final.geojson

5-Export Atlas PNG/PDF (html2canvas, Mapbox, filigrane) : voir **docs/README_tools.md** → section *Export PNG / PDF (vue carte)*.