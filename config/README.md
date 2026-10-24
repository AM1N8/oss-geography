# Configuration

- `sources.toml` : fournisseurs, branches initiales, profils, période et paramètres
  réseau. Son SHA-256 est figé dans chaque manifeste. Une modification exige un nouvel
  instantané avec `fetch --update`.
- `geography_overrides.csv` : correspondances **revues**, séparées des données brutes.
  Initialement vide : aucune équivalence manuelle supposée. Une ligne doit préciser
  le code GitHub, au moins une cible existante (`wb_iso3`, `ne_adm0_a3`), le relecteur,
  la date, le motif et une URL HTTPS justificative. Une cible vide laisse la recherche
  automatique agir. Ne pas utiliser des noms de pays comme clés.
- `ossgeo-completion.bash` : complétion Bash facultative des commandes et profils ;
  activer avec `source config/ossgeo-completion.bash` après activation de `.venv`.

Après une révision de correspondance : `uv run --locked ossgeo validate`, puis
`uv run --locked ossgeo prepare`. L'empreinte des overrides identifie une nouvelle
préparation. Une ambiguïté ne peut pas être réglée en choisissant arbitrairement la
première entité Natural Earth.
