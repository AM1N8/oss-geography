# Reproduction et conservation des instantanés

## Ce qu'il faut conserver

Pour un instantané, conserver ensemble : l'état Git du code, `uv.lock`, `config/`,
`data/metadata/` et `data/raw/<fournisseur>/<instantané>/` pour les trois fournisseurs.
Le manifeste associe chaque chemin aux octets précis via SHA-256. Les données
préparées sont régénérables si les entrées, le code et les overrides sont identiques ;
leur manifeste permet également de vérifier leurs empreintes.

Les métadonnées de provenance sont destinées à être commises avec le code. Le dépôt
initialisé ne contient encore aucun commit ; aucune commande de publication n'est
effectuée. Les gros jeux bruts et préparés sont ignorés par Git.

## Copie entre équipiers

Transmettre les répertoires bruts en conservant leur arborescence et les petits
manifestes associés, par le moyen choisi par le groupe. Aucun stockage externe ni
téléversement n'est configuré. Une archive locale peut être faite, depuis la racine :

```bash
tar -czf ossgeo-snapshot.tar.gz data/raw data/metadata config uv.lock
```

Les archives sont elles aussi ignorées. Après extraction dans une copie du **même
code** du projet :

```bash
uv sync --locked
uv run --locked ossgeo status
uv run --locked ossgeo validate
uv run --locked ossgeo prepare
```

Ne pas remplacer un fichier corrompu en réécrivant son SHA dans le manifeste. Restaurer
la copie originale, ou créer volontairement un autre instantané. Si un fichier
enregistré est absent, `fetch` peut essayer de le restaurer mais exige son SHA attendu
**avant** de le rendre définitif. Les réponses d'API et de résolution des branches Git
peuvent avoir changé ; une restauration réseau n'est donc pas garantie. Une URL et la
date `lastupdated` ne remplacent pas les octets de la Banque mondiale.

## Mises à jour et retour à un instantané

```bash
uv run --locked ossgeo fetch --profile all --update
uv run --locked ossgeo validate
uv run --locked ossgeo prepare
```

Chaque `--update` démarre un nouvel instantané, même si l'amont n'a pas changé. En cas
d'interruption, relancer **sans** `--update` reprend celui qui vient d'être créé.
Les anciens manifestes et répertoires restent en place. Pour réactiver un ancien
instantané, restaurer sa version de `data/metadata/sources.lock.json` et le fichier
`config/sources.toml` correspondant depuis la sauvegarde ou l'état Git concerné,
ainsi que ses fichiers bruts ; vérifier ensuite `status` et `validate`.

Une révision des overrides ne modifie pas l'instantané brut ; son SHA entre dans
l'identifiant de préparation. Les changements de code Python sont eux aussi pris en
compte. Les rapports qualité incluent une date UTC d'exécution, donc leurs octets
peuvent changer à chaque validation, même si les tables préparées restent identiques.
