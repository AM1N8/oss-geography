# Paquet Python

`cli.py` expose les cinq commandes ; `storage.py` gère HTTPS, cache, SHA-256 et écritures
atomiques ; `acquire.py` gère les fournisseurs et la pagination ; `validate.py` applique
les contrats ; `geography.py` construit les correspondances conservatrices ;
`prepare.py` écrit les tables et audits sans calculer de résultats de recherche.

Identifiants et code en anglais ; documentation du projet en français. Aucune dépendance
d'exécution externe. Depuis la racine : `uv run --locked python -m ossgeo --help`.
