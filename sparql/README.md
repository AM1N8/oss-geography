# Extension RDF/SPARQL possible

Piste pour une phase ultérieure, sans serveur, base RDF ni jeu de triples installé.
Une observation pourrait être décrite avec RDF Data Cube : économie, période
trimestrielle et mesure (comptes, pushes ou poids de collaboration). Les collaborations
nécessiteraient deux dimensions géographiques dirigées. PROV-O pourrait relier chaque
observation au fichier brut, au SHA Git, au manifeste et à la transformation.

Créer des URI stables basées sur les **codes et leurs référentiels**, conserver les
correspondances incertaines, éviter un `owl:sameAs` automatique entre territoire,
économie et État. Les valeurs absentes ne deviendraient pas des zéros. Des requêtes
SPARQL de couverture ou de provenance seraient pertinentes avant toute analyse.

Cette extension reste à spécifier et tester ; aucun résultat SPARQL n'est revendiqué.
