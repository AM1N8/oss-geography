# Catalogue des sources

## GitHub Innovation Graph

- Dépôt officiel : <https://github.com/github/innovationgraph>
- Méthodologie : <https://github.com/github/innovationgraph/blob/main/docs/datasheet.md>
- Schémas : <https://github.com/github/innovationgraph/blob/main/datapackage.json>
- Conditions : <https://github.com/github/innovationgraph/blob/main/LICENSE.md>
- Révision de l'acquisition initiale : `078fb62ee4395d321bec9f4f06694cca68f6b6cb`.
  Les URL réellement utilisées et empreintes figurent dans le manifeste.

| Profil | Chemins vérifiés dans cette révision |
| --- | --- |
| CORE | `data/developers.csv`, `data/economy_collaborators.csv`, `data/git_pushes.csv` |
| ALL, en plus | `data/languages.csv`, `data/repositories.csv`, `data/organizations.csv`, `data/licenses.csv`, `data/topics.csv` |
| Représentativité | `representativeness_data/distinct_dataset_counts_by_quarter_by_economy.csv`, `representativeness_data/distinct_economy_counts_by_quarter_by_dataset.csv` |
| Contexte | `datapackage.json`, `docs/datasheet.md`, `LICENSE.md`, `README.md`, `CITATION.cff` |

Le `datapackage.json` de cette révision préfixe à tort les tables de représentativité
par `data/`. Le code vérifie l'arbre Git épinglé, puis emploie le chemin réel. Il
n'utilise pas une URL supposée ou une branche mutable pour les fichiers de données.

CSV trimestriels publiés depuis 2020, avec un seuil de publication lié à 100 comptes
pertinents dans la méthodologie amont. Ils sont des agrégats, pas des journaux individuels.
La datasheet récupérée est la version 1.0.10, mise à jour le 8 mai 2026. Les fichiers
bruts incluent les périodes supplémentaires publiées ; seul `prepare` filtre l'étude.

## Banque mondiale

API officielle : <https://api.worldbank.org/v2/>.
Documentation : <https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation>.
Indicateur : <https://data.worldbank.org/indicator/SP.POP.TOTL>.

Requêtes utilisées (paramètres `format=json`, `per_page=500`, `page=1..pages`) :

- `/country` : identifiants, noms descriptifs, régions, distinction des agrégats ;
- `/indicator/SP.POP.TOTL` : définition, source et organismes producteurs ;
- `/country/all/indicator/SP.POP.TOTL?date=2020:2025&source=2` : population annuelle.

`SP.POP.TOTL` représente la population totale, selon la définition en milieu d'année
et le concept de population de fait décrits dans les métadonnées ; les producteurs
mentionnés incluent notamment Nations unies, offices nationaux et Eurostat. Consulter
le texte source exact et les réserves propres aux économies. La liste des économies
de `/country` peut être plus large que celle présente dans les observations.

Chaque page est conservée avec son enveloppe de pagination et `lastupdated` lorsqu'il
existe. Les totaux, numéros et dates doivent rester cohérents entre pages. L'acquisition
initiale de population porte `lastupdated=2026-10-08`. Les séries, y compris historiques,
peuvent être révisées : **seul l'instantané sauvegardé garantit les mêmes octets**.
Le suffixe `countryiso3code` peut être vide pour certains groupes ; le code relie alors
exactement `country.id` à `iso2Code` des métadonnées, avec avertissement.

## Natural Earth

- Dépôt maintenu : <https://github.com/nvkelso/natural-earth-vector>
- Chemin vérifié : <https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_10m_admin_0_countries.geojson>
- Termes officiels : <https://www.naturalearthdata.com/about/terms-of-use/>
- Révision initiale : `ca96624a56bd078437bca8184e78163e5039ad19` ; le fichier `VERSION`
  contient **`5.2.0-pre`**. Il s'agit d'une révision du dépôt maintenu, pas d'une release
  stable annoncée. `VERSION`, `LICENSE.md` et `README.md` sont conservés.

Échelle **1:10 millions**, environ 13,3 Mo pour le GeoJSON : compromis raisonnable
pour inclure des petites économies. Les attributs et géométries d'origine sont
préservés. Les limites et unités cartographiques ne coïncident pas nécessairement avec
les économies de GitHub ou de la Banque mondiale. `ISO_A2`, `ISO_A2_EH` et `ADM0_A3`
sont inspectés séparément ; `-99` n'est pas un code ISO valide.
