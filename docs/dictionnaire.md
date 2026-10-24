# Dictionnaire des données

Les CSV préparés sont UTF-8, séparateur virgule, avec en-tête. Une cellule vide signifie
une valeur manquante ou une correspondance absente, **jamais un zéro ajouté**. Les clés
des tables GitHub incluent toujours `year` (entier) et `quarter` (1–4). Les nombres de
comptes/événements sont des entiers non négatifs lorsqu'ils sont publiés.

## Observations GitHub, 2020–2025 inclus

| Table | Clé en plus de l'année et du trimestre | Mesure et interprétation |
| --- | --- | --- |
| `developers.csv` | `github_code` | `developer_accounts` : champ amont `developers`, stock de comptes en fin de trimestre, y compris inactifs |
| `git_pushes.csv` | `github_code` | `git_pushes` : nombre de pushes, pas de commits |
| `economy_collaborators.csv` | `source`, `destination` | `weight` : volume dirigé combinant pushes et pull requests vers des dépôts détenus par d'autres ; pas des personnes uniques |
| `languages.csv` (ALL) | `github_code`, `language` | `num_pushers` ; `language_type` est un attribut de la langue, pas une dimension supplémentaire de la clé |
| `licenses.csv` (ALL) | `github_code`, `spdx_license` | `num_pushers` : comptes ayant poussé vers des dépôts classés selon cette licence |
| `topics.csv` (ALL) | `github_code`, `topic` | `num_pushers` : comptes ayant poussé vers des dépôts portant ce topic |
| `repositories.csv` (ALL) | `github_code` | `repositories` : stock de dépôts publics selon la méthodologie amont |
| `organizations.csv` (ALL) | `github_code` | `organizations` : stock d'organisations selon la méthodologie amont |
| `distinct_dataset_counts_by_quarter_by_economy.csv` | `github_code` | `count_of_datasets` : nombre de tables publiées pour cette économie et période |
| `distinct_economy_counts_by_quarter_by_dataset.csv` | `dataset` | `count_distinct_economies` : nombre d'économies publiées par table et période |

Le code amont `iso2_code` est renommé `github_code` ; il exprime le référentiel publié,
pas une garantie d'équivalence ISO/État. `source` et `destination` conservent leurs
noms amont et représentent ces mêmes codes GitHub. Les colonnes `wb_iso3` et
`ne_adm0_a3` enrichissent les tables ayant `github_code`. Pour les collaborations,
elles sont préfixées `source_` et `destination_`. Une cible vide ne fait pas disparaître
l'observation. Les collaborations domestiques ne sont pas filtrées.

Les comptes `num_pushers` ne doivent pas être additionnés entre catégories pour obtenir
des individus uniques : un même compte peut apparaître dans plusieurs catégories.
Les comptes `developers`, dépôts et organisations sont des stocks, pas des flux.
Les définitions complètes restent celles de la [datasheet officielle](https://github.com/github/innovationgraph/blob/main/docs/datasheet.md)
et du [schéma officiel](https://github.com/github/innovationgraph/blob/main/datapackage.json)
conservés à la révision épinglée.

## Population et géographie

| Table / clé | Champs |
| --- | --- |
| `population.csv` / `wb_iso3,year` | `wb_iso3` : `id` des métadonnées Banque mondiale ; `wb_iso2` : `iso2Code` ; `year` : année ; `population` : nombre annuel ou cellule vide pour un `null` API. Pas de lignes estimées pour les observations absentes. |
| `geographic_correspondences.csv` / `github_code` | `wb_iso3`, `wb_iso2`, `ne_adm0_a3` : cibles, éventuellement vides ; `ne_iso_a2`, `ne_iso_a2_eh` : attributs d'origine du candidat retenu ; `wb_method`, `ne_method` : `iso2_exact`, `ISO_A2`, `ISO_A2_EH_fallback`, `reviewed_override` ou `unmatched`. |
| `unmatched_github_codes.csv` / `github_code,target` | `target` : `world_bank` ou `natural_earth` ; `reason` : `no_code_match` ou `ambiguous`. Codes de toutes les périodes brutes téléchargées. |
| `excluded_wb_aggregates.csv` / `wb_iso3,year` | Mêmes mesures que population, plus `name` descriptif et `reason=WB_region_NA_aggregate`. Seules les observations présentes sont listées ; la liste exhaustive des métadonnées reste dans le brut. |

`ne_adm0_a3` est un identifiant **Natural Earth**, pas une promesse de code ISO3.
Les noms Banque mondiale ne sont conservés que pour description, jamais pour jointure.
Définition officielle de population : [SP.POP.TOTL](https://data.worldbank.org/indicator/SP.POP.TOTL).

## Audits de couverture

- `github_coverage.csv`, clé `table,github_code,year,quarter` : `published_rows` compte
  les lignes effectivement publiées pour chaque code observé dans la période, et
  `status` vaut `published` ou `absent_observation`. Pour les collaborations, une ligne
  source/destination contribue à chaque extrémité distincte ; une somme sur les codes
  **n'est pas** le nombre de collaborations. Pour la représentativité par dataset,
  `github_code` est vide et le compte porte sur les lignes de la table. Un zéro dans
  **cet audit** signale zéro ligne publiée, sans imputation d'activité nulle.
- `population_coverage.csv`, clé `wb_iso3,year` : toutes les économies non agrégées des
  métadonnées et les six années. `status=observed` si valeur présente,
  `missing_value` si l'API publie `null`, `absent_observation` si elle ne publie pas la
  ligne. Aucun remplissage de population n'est effectué.
- Le rapport `data/metadata/quality/<instantané>.json` décrit aussi les nombres de
  lignes, périodes et codes du **brut complet**, les trimestres d'étude absents,
  les attributs Natural Earth incomplets et les erreurs bloquantes.
