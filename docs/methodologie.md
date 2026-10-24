# Méthode de préparation et limites

## Unités et champ

L'étude future porte sur la présence géographique et la collaboration sur GitHub entre
2020 et 2025. La préparation conserve les observations trimestrielles, sans moyenne
annuelle, normalisation par habitant, classement, mesure de concentration ni test
d'hypothèse. La population Banque mondiale est une table annuelle indépendante. Les
polygones Natural Earth ne sont pas modifiés.

La localisation GitHub est inférée à partir d'adresses IP et de règles décrites par
la datasheet (localisation quotidienne modale, dernière localisation conservée pour
certains jours sans activité). VPN, mobilité, disponibilité de la plateforme et seuils
de publication influencent les observations. Le champ `developers` inclut les comptes
inactifs selon la méthode amont. Public sur GitHub n'est pas synonyme de tout l'OSS.

La collaboration est dirigée : activité de comptes d'une économie vers des dépôts
dont les propriétaires sont associés à une autre économie, ou à la même. Les règles
de localisation des propriétaires et organisations peuvent masquer des coopérations
transnationales internes. `weight` combine pushes et ouvertures de pull requests, pas
des individus uniques. Un push peut inclure plusieurs commits.

## Acquisition et validation

1. Geler les SHA Git et conserver toutes les pages JSON, fichiers de licence et
   méthodologie. Chaque fichier possède un manifeste et une empreinte SHA-256.
2. Vérifier l'intégrité de **tous** les fichiers avant validation. Vérifier les colonnes
   du schéma amont et les types attendus, les clés propres à chaque table, les mesures
   non négatives et les périodes. Les valeurs de mesure absentes restent manquantes.
3. Vérifier les numéros/pages/totaux/taille de page Banque mondiale et la stabilité
   de `lastupdated` et `sourceid`. Vérifier les identifiants et unicités des économies,
   les années et populations sans imposer qu'une observation existe partout.
4. Vérifier la FeatureCollection, les attributs requis, l'unicité de `ADM0_A3`, les
   polygones/multipolygones, anneaux fermés et coordonnées finies dans leurs bornes.
   Ce contrôle structurel ne remplace pas une validation topologique SIG complète.
5. Distinguer les erreurs (corruption, type, clé dupliquée, pagination incomplète,
   géométrie mal formée) des avertissements (lacunes, `null`, codes non appariés).

## Harmonisation géographique prudente

- Joindre un code GitHub à `iso2Code` des **économies non agrégées** Banque mondiale
  seulement en cas de correspondance exacte et unique.
- Pour chaque entité Natural Earth, retenir `ISO_A2` valide, sinon `ISO_A2_EH` valide.
  Un candidat unique par code est nécessaire ; si plusieurs entités partagent ce code,
  la liaison reste ambiguë. Ne pas faire correspondre `-99`, ni déduire une cible des noms.
- Un override explicite revu peut fixer une cible existante ; son relecteur, sa date,
  son motif et sa source sont requis. Les overrides restent séparés du brut.
- Conserver toutes les observations GitHub même sans cible Banque mondiale ou SIG ;
  conserver également les ambiguïtés dans une table d'audit.

L'édition Natural Earth téléchargée contient notamment des subdivisions/territoires
pouvant produire des ambiguïtés sur des codes tels que FR, AU, BR ou KZ. L'absence de
jointure dans ce cas est intentionnelle ; une décision documentée du groupe sera
nécessaire avant une utilisation cartographique complète. Des territoires publiés par
GitHub n'ont pas forcément une population Banque mondiale distincte ou un polygone
Natural Earth autonome. Le code spécial EU publié par GitHub reste visible sans
fabrication d'une population nationale.

## Population et manquants

Les groupes Banque mondiale sont identifiés par `region.id == "NA"` dans les
métadonnées, pas par la longueur du code ou le nom. Leurs observations sont déplacées
dans `excluded_wb_aggregates.csv`. Les autres lignes présentes conservent leur valeur
ou leur `null` dans `population.csv`. Les années/économies absentes sont décrites dans
`population_coverage.csv`, sans interpolation ni estimation.

L'identité des observations Banque mondiale utilise `country.id` vers `iso2Code` des
métadonnées ; si `countryiso3code` est fourni, sa cohérence avec `id` est vérifiée.
Cela permet de traiter explicitement les groupes dont l'API omet l'ISO3. Aucune
jointure n'est fondée sur un nom. Une population annuelle n'est pas créée en sommant
les stocks trimestriels de comptes GitHub.
