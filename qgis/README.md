# Futurs travaux QGIS

Aucun projet QGIS n'existe encore. Après `fetch`, `validate` et `prepare` :

1. Charger `data/raw/natural_earth/<instantané>/geojson/ne_10m_admin_0_countries.geojson`
   comme couche vecteur (coordonnées géographiques WGS84 / longitude-latitude).
2. Charger `geographic_correspondences.csv` et la table d'observations choisie comme
   tables sans géométrie. Préserver les codes comme texte.
3. Examiner `unmatched_github_codes.csv` **avant** une jointure. Natural Earth contient
   des identifiants manquants (`-99`) et plusieurs entités pouvant partager un code.
4. Utiliser la cible revue `ne_adm0_a3` vers `ADM0_A3`, jamais les noms. Sélectionner
   explicitement un trimestre avant de relier un stock à une géométrie pour éviter
   des relations multiples non voulues. Ne pas sommer les stocks trimestriels.
5. Conserver les géométries originales et enregistrer ultérieurement un projet avec
   chemins relatifs. Tout choix de projection ou de périmètre fera l'objet d'une note.

Le 1:10 millions améliore la couverture des petites économies par rapport aux échelles
plus grossières sans garantir que chaque territoire publié possède une géométrie
distincte. Les fichiers QGIS binaires et couches dérivées sont ignorés par défaut.
