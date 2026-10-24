# Exécution initiale : état constaté

Cette note décrit les vérifications réellement effectuées localement, pas des résultats
de recherche. Les horodatages UTC précis sont ceux des manifestes.

## Environnement et tests

- Python 3.11.15, uv 0.13.1 ; `uv lock` a généré le verrou, puis `uv sync --locked`
  a installé l'environnement.
- `uv run --locked ossgeo --help`, `--version`, `fetch --help` et
  `uv run --locked python -m ossgeo status` : exécutés avec succès.
- `uv run --locked pytest --cov=ossgeo --cov-report=term-missing --cov-fail-under=90` :
  **78 tests réussis**, couverture des lignes **98,36 %** (671 instructions, 11 non
  couvertes). Les tests sont hors ligne et les fixtures sont synthétiques.
- `uv run --locked mypy` : succès sur les huit fichiers source.
- `uv run --locked ruff check ossgeo tests` et
  `uv run --locked black --check ossgeo tests` : succès.
- Le workflow CI est fourni ; il n'a pas été exécuté sur GitHub depuis cet environnement.

## Sources effectivement téléchargées

Instantané actif : `2026-10-24T225637.714765Z-d1269b80`.

- CORE a réellement téléchargé les trois tables, les fichiers de contexte, la Banque
  mondiale et Natural Earth : 23 fichiers, 15 445 482 octets.
- Les cinq chemins optionnels ont été vérifiés dans l'arbre amont, puis ALL a
  réellement complété cet instantané : **28 fichiers, 23 831 810 octets** au total.
- Révision GitHub : `078fb62ee4395d321bec9f4f06694cca68f6b6cb`.
- Révision Natural Earth : `ca96624a56bd078437bca8184e78163e5039ad19`, `VERSION=5.2.0-pre`,
  couche pays 1:10 millions.
- Population Banque mondiale : quatre pages conservées, avec
  `lastupdated=2026-10-08` ; métadonnées économies et indicateur également conservées.

Une première validation a révélé que l'API omettait l'ISO3 de certains agrégats. Le
contrat a été corrigé pour utiliser l'identifiant exact `country.id` vers `iso2Code`
des métadonnées, sans jointure sur les noms. Les tests couvrent ce cas.

La vérification finale a exécuté exactement :

```bash
uv run --locked ossgeo fetch --profile core
uv run --locked ossgeo fetch --profile all
uv run --locked ossgeo validate
uv run --locked ossgeo prepare
uv run --locked ossgeo prepare
uv run --locked ossgeo status
```

Ces deux dernières commandes `fetch` ont **réutilisé et vérifié le cache**, sans
prétendre effectuer un second téléchargement. Tous les retours ont été zéro.
La seconde préparation a vérifié les sorties déjà produites et retourné le même chemin :

```text
data/processed/2026-10-24T225637.714765Z-d1269b80/0b4fda875d3da453/
```

Cette préparation finale contient **16 tables CSV**, dont les tables ALL, les deux
tables de représentativité et les audits. Les préparations intermédiaires générées
pendant le développement sont conservées ; pour le code final, utiliser le chemin
ci-dessus ou celui retourné par `prepare`.

## Avertissements conservés

Validation finale : **0 erreur bloquante, 4 avertissements** :

1. Six valeurs de population `null` dans les réponses API, agrégats compris ; aucune
   imputation n'a été effectuée.
2. ISO3 vide pour les identifiants Banque mondiale XD, XM, XN, XT et XY ; liaison exacte
   sur `country.id` documentée dans le rapport qualité.
3. Identifiants `ISO_A2`/`ISO_A2_EH` incomplets pour 23 entités Natural Earth ; ces
   attributs bruts sont inchangés.
4. **31 couples code GitHub/cible** absents ou ambigus, sans suppression des observations.
   Parmi les ambiguïtés Natural Earth : AU, BR, FR et KZ. Les overrides revus restent
   vides ; une décision documentée du groupe est nécessaire avant ces jointures SIG.

Le détail est dans `data/metadata/quality/2026-10-24T225637.714765Z-d1269b80.json`
et `unmatched_github_codes.csv`. Ces diagnostics portent sur la disponibilité et
l'intégrité des données ; ils ne répondent pas à la question de recherche.

Les fichiers bruts et préparés ont été confirmés comme ignorés par Git. Le dépôt
initial n'avait aucun commit ; aucun commit, publication ou ressource externe n'a
été créé lors de cette initialisation.
