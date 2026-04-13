🌍 2. OÙ TROUVER DES DONNÉES PROPRES (TRÈS IMPORTANT)

Je vais être direct :

👉 90% des données gratuites sont imparfaites

Donc tu dois savoir où prendre + comment nettoyer

🥇 1. Humanitarian Data Exchange (RECOMMANDÉ)

👉 Meilleure source pour Afrique

✔️ Tu trouves :
départements
communes
limites officielles
✔️ Avantages :
propres
cohérentes
utilisées par ONG
❗ Problème :
pas toujours à jour
pas de quartiers
🥈 2. OpenStreetMap

👉 indispensable pour :

quartiers
routes
POI
✔️ Avantages :
très riche
gratuit
❗ Problèmes :
erreurs
incohérences
limites parfois mal tracées

👉 donc :
👉 toujours passer par ton clean_geometries

🥉 3. geoBoundaries

👉 alternative HDX

✔️ Avantages :
très structuré
bon pour API
🧠 4. Données LOCALES (le vrai jackpot)

👉 au Bénin :

IGN Bénin (Institut Géographique)
Ministère de l’Urbanisme
ANPC (inondation)

💡 PRO TIP :
👉 ces données sont les meilleures
👉 mais souvent :

payantes
ou difficiles d’accès

⚠️ 5. Ce que TU DOIS FAIRE (très important)

Même avec bonnes données :

👉 tu dois toujours :

✔️ nettoyer
ST_MakeValid
ST_Buffer(0)
✔️ aligner
ST_Snap
ST_Intersection
✔️ simplifier
ST_Simplify