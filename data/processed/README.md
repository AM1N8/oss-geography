# Tables préparées

Créées par `uv run --locked ossgeo prepare`, après validation, dans
`<instantané>/<id-préparation>/`. Format CSV UTF-8, en-têtes, séparateur virgule,
cellules vides pour les valeurs manquantes. Période inclusive 2020–2025, trimestre
conservé ; population annuelle. Dictionnaire : `docs/dictionnaire.md`.

Chaque préparation possède son manifeste dans `data/metadata/preparations/` avec
empreintes des entrées, du code, des overrides et des sorties. Hors Git.
