# Geography of GitHub — 2020–2025

Projet universitaire Big Data : **la présence de GitHub devient-elle plus répartie
géographiquement, tandis que la collaboration internationale reste concentrée autour
de quelques économies ?** Cette question guide de futures analyses ; le dépôt fournit
uniquement leur socle de données, sans résultats de recherche, rapport académique ni
figures finales.

Les CSV ouverts d'Innovation Graph sont des **agrégats trimestriels issus de données
de plateforme à grande échelle**, pas un téléchargement de milliards d'événements.
Le terme « économie » n'implique pas nécessairement un État souverain.

## Organisation

```text
ossgeo/             Acquisition, validation et préparation Python
config/             Sources TOML et correspondances géographiques revues
data/raw/           Originaux complets, par fournisseur et instantané (hors Git)
data/processed/     Tables harmonisées, par instantané et préparation (hors Git)
data/metadata/      Verrou de sources, manifestes SHA-256, rapports qualité
docs/               Catalogue, dictionnaire, méthode, conditions, reproduction
notebooks/          Espace pour les futures analyses du groupe
qgis/               Instructions pour les futurs travaux cartographiques
sparql/             Piste d'extension RDF/SPARQL
tests/              Tests hors ligne, fixtures explicitement synthétiques
.github/workflows/  Intégration continue légère
src/open_sauce/     Squelette initial conservé ; la chaîne actuelle est ossgeo/
```

## Installation reproductible

Depuis la racine, avec Python **3.11+** et [uv](https://docs.astral.sh/uv/getting-started/installation/) :

```bash
uv sync --locked
uv run --locked ossgeo --help
uv run --locked ossgeo --version
```

`uv.lock` a été généré par `uv lock`. Il fixe les outils de développement ; le paquet
n'a **aucune dépendance d'exécution externe** (bibliothèque standard). `.python-version`
indique Python 3.11. Pour utiliser uniquement les commandes, `uv sync --locked --no-dev`
suffit. Une alternative sans uv : `python -m venv .venv`, activer cet environnement,
puis `python -m pip install -e .` ; les outils de développement ne sont alors pas
verrouillés par pip. `python -m ossgeo` expose les mêmes commandes que `ossgeo`.

## Acquisition réelle

```bash
# CORE : comptes, collaborations et pushes + Banque mondiale + Natural Earth
uv run --locked ossgeo fetch --profile core

# ALL : ajoute langues, dépôts, organisations, licences et topics
uv run --locked ossgeo fetch --profile all
```

Les deux profils récupèrent aussi les schémas, la méthodologie, les conditions et les
tables de représentativité disponibles. `all` complète le même instantané ; les CSV
bruts sont conservés **entièrement**, même hors 2020–2025.

Au premier lancement, les branches GitHub et Natural Earth sont résolues chacune en
un SHA Git complet. Les fichiers suivants proviennent de ces révisions. Les lancements
suivants réutilisent ces SHA et le cache après vérification des tailles et SHA-256.
Les réponses JSON paginées de la Banque mondiale sont conservées page par page.

Les téléchargements passent par HTTPS, avec délai de 60 secondes par opération réseau,
au plus trois tentatives pour les erreurs transitoires et attente bornée. Un fichier
temporaire situé sur le même système de fichiers est validé avant renommage atomique.
Une corruption, une page HTML, un mauvais statut HTTP ou une réponse incohérente
provoquent une erreur explicite. Les originaux déjà répertoriés ne sont pas écrasés.
La reprise se fait en relançant la même commande. Ne pas lancer deux acquisitions
simultanées dans la même copie de travail.

## Validation et préparation

```bash
uv run --locked ossgeo status
uv run --locked ossgeo validate
uv run --locked ossgeo prepare
```

Ces trois commandes sont **hors ligne**. `status` contrôle tous les fichiers bruts.
`validate` vérifie schémas, types, comptes non négatifs, périodes, clés naturelles,
pagination, géométries et identifiants. Une erreur bloquante produit le code retour 1 ;
les lacunes de couverture et correspondances absentes sont des avertissements.
`prepare` revalide puis affiche le répertoire de sortie.

Les sorties sont dans `data/processed/<instantané>/<id-préparation>/`. Cet identifiant
dépend des empreintes des entrées, du code Python et des overrides. Une nouvelle
préparation conserve donc les précédentes ; une sortie existante est vérifiée avant
réutilisation. Une préparation interrompue doit être conservée/renommée avant reprise
si elle contient déjà des fichiers sans manifeste final.

| Sortie | Contenu |
| --- | --- |
| `developers.csv` | Observations de comptes (`developer_accounts`), économie/trimestre, 2020–2025 |
| `git_pushes.csv` | Nombre de pushes, économie/trimestre, 2020–2025 |
| `economy_collaborators.csv` | Poids dirigé source/destination/trimestre, toutes les observations publiées, y compris domestiques |
| `population.csv` | Population annuelle disponible par économie individuelle ; valeurs nulles conservées |
| `geographic_correspondences.csv` | Codes GitHub, Banque mondiale et Natural Earth et méthode de liaison |
| `unmatched_github_codes.csv` | Codes non appariés ou ambigus, par cible ; aucune suppression silencieuse |
| `github_coverage.csv` | Présence/absence de publication par table, code présent dans la période et trimestre ; nombre de lignes, pas volume d'activité |
| `population_coverage.csv` | Chaque économie individuelle et année : valeur observée, nulle, ou observation absente |
| `excluded_wb_aggregates.csv` | Observations de groupes Banque mondiale exclues, avec motif |
| `distinct_*.csv` | Tables de représentativité publiées, filtrées sur 2020–2025 |
| Cinq CSV optionnels | Tables ALL, préparées uniquement lorsqu'elles ont été téléchargées |

Les données géographiques originales restent dans `data/raw/natural_earth/` ; elles
ne sont ni découpées ni simplifiées. Voir le [dictionnaire](docs/dictionnaire.md), la
[méthode](docs/methodologie.md) et le [catalogue officiel](docs/sources.md).

## Répéter sur la machine d'un équipier

1. Récupérer le même état Git du projet, y compris `uv.lock`, `config/` et
   `data/metadata/` (ces petits fichiers sont destinés à être versionnés).
2. Échanger l'arborescence `data/raw/` **en conservant les chemins relatifs**, par un
   moyen convenu dans le groupe. Les tables préparées peuvent être échangées aussi ou
   régénérées. Rien n'est téléversé automatiquement.
3. Exécuter `uv sync --locked`, puis `status`, `validate` et `prepare` ci-dessus.

**L'URL de l'API Banque mondiale ne suffit pas à reproduire des octets historiques :**
les données sont révisables. Conserver l'instantané téléchargé avec son manifeste est
indispensable. Sans cette copie, `fetch` peut tenter de restaurer un fichier absent,
mais refuse des octets différents de l'empreinte enregistrée. Les réponses de résolution
des branches Git sont elles aussi à conserver. Voir [reproduction](docs/reproduction.md).

## Mettre à jour volontairement

```bash
# Nouvel identifiant, nouvelles résolutions Git, nouvelles réponses de l'API
uv run --locked ossgeo fetch --profile core --update
# Ou directement : uv run --locked ossgeo fetch --profile all --update
uv run --locked ossgeo validate
uv run --locked ossgeo prepare
```

`--update` garde les anciens fichiers et manifestes et déplace le pointeur actif
`data/metadata/sources.lock.json`. Sans cette option, une modification de
`config/sources.toml` est refusée. Modifier les correspondances revues dans
`config/geography_overrides.csv` puis relancer `validate` et `prepare` suffit pour
produire une nouvelle préparation sans télécharger de nouvelles sources.

## Définitions à respecter

- `developers` compte des **comptes**, y compris potentiellement inactifs ; ce n'est
  pas une mesure de « développeurs actifs ».
- Un **push n'est pas un commit**.
- Le poids de collaboration combine pushes et pull requests ; il ne dénombre pas
  des personnes uniques.
- Une observation absente n'est pas nécessairement zéro. Les cellules vides restent
  manquantes ; aucune estimation de population n'est fabriquée.
- Ne pas additionner les stocks trimestriels de comptes pour obtenir une population
  annuelle. La population Banque mondiale est annuelle, non trimestrielle.
- L'activité publique GitHub ne représente pas l'ensemble du logiciel libre mondial.
- Aucune jointure n'est faite sur les noms de pays. Les territoires, codes particuliers,
  ambiguïtés Natural Earth et différences de couverture sont conservés dans les audits.

## Tests et conditions

```bash
uv run --locked pytest --cov=ossgeo --cov-report=term-missing
uv run --locked mypy
uv run --locked ruff check ossgeo tests
uv run --locked black --check ossgeo tests
```

Les fixtures des tests sont **synthétiques**, isolées dans des répertoires temporaires ;
la CI ne télécharge aucun jeu de données. Les conditions des données tierces sont
séparées de celles du code dans [docs/conditions.md](docs/conditions.md).
L'[état d'exécution initial](docs/execution.md) consigne les commandes réellement tentées.
