# Tests hors ligne

Les observations de `conftest.py` sont **synthétiques**, inventées uniquement pour tester
les contrats, jamais utilisées comme données de recherche. Les requêtes HTTPS sont
simulées et le réseau est interdit par défaut dans les tests. Chaque test travaille
dans un répertoire temporaire isolé des instantanés réels.

Contrats vérifiés : pagination complète/incohérente, réponses d'erreur, échec sans fichier
final, cache et corruption de même taille, restauration contrôlée, SHA Git et profils,
clés naturelles, valeurs nulles et périodes manquantes, exclusion des agrégats,
correspondances/ambiguïtés/overrides, GeoJSON, préparation et codes de retour CLI.

Depuis la racine : `uv run --locked pytest --cov=ossgeo --cov-report=term-missing`.
Les tests ne requièrent ni compte GitHub, ni données brutes, ni services externes.
