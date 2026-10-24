# Petites métadonnées à versionner

- `sources.lock.json` : pointeur vers l'instantané actif (ce n'est pas `uv.lock`).
- `manifests/<instantané>.json` : configuration figée, révisions Git complètes, profils
  terminés et provenance de **chaque fichier** : fournisseur, identifiant, URL demandée
  et finale, UTC de récupération, chemin relatif, taille, SHA-256, révision ou
  métadonnées API (`lastupdated` si présent), lien vers les conditions.
- `quality/<instantané>.json` : diagnostic local le plus récent, erreurs et
  avertissements séparés, périodes, codes, couverture et codes non appariés.
- `preparations/<id>.json` : provenance et SHA-256 de chaque sortie, couverture
  de population et avertissements.

Ces petits fichiers sont destinés à Git ; ils ne remplacent pas la sauvegarde des
octets bruts. `validate` actualise le rapport qualité ; `fetch --update` crée un
nouveau manifeste sans effacer le précédent. Les identifiants sont horodatés en UTC.
