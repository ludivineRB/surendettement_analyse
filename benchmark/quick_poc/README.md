# POC rapide — comparaison de parseurs SQL

Ce POC génère éventuellement un SQL depuis une question, soumet exactement ce
SQL à plusieurs outils, affiche leur verdict et leur temps, puis l'exécute sur
SQLite après validation en lecture seule par SQLGlot.

## Installation et lancement

Depuis `benchmark/quick_poc` :

```bash
python -m pip install -r requirements.txt
python init_db.py
export OPENAI_API_KEY="..."
export OPENAI_MODEL="gpt-5-mini"  # modèle interchangeable
python cli.py "Quels sont les 5 clients qui ont dépensé le plus cette année ?"
```

Pour comparer les parseurs sans appel API :

```bash
python cli.py --sql "SELECT c.name, COUNT(*) FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.name"
python -m pytest -q
```

DataFusion est volontairement optionnel (`python -m pip install datafusion`) :
ses bindings Python installent un moteur Arrow complet et produisent un plan
logique dépendant du schéma, plutôt qu'un simple AST autonome.

## Shortlist pragmatique

| Outil | Rôle | Avantages | Inconvénients | Maturité/maintenance | Python | POC |
|---|---|---|---|---|---|---|
| SQLGlot | Parse, AST, validation, transpilation | Très riche, >30 dialectes, Python pur | Validation sémantique à construire | Mature, actif | Excellente | Baseline et garde-fou |
| sqlparser-rs / sqloxide | Parseur Rust + binding | Rapide, AST structuré, nombreux dialectes | Peu de transformations Python | Actif | Très simple | Oui |
| polyglot-sql | Parseur/transpileur Rust récent | AST, validation et >30 dialectes | Recul limité | Actif mais récent | Binding PyO3 | Oui, candidat direct |
| sqlparse | Tokeniseur/formatter | Léger et stable | Pas un validateur complet | Mature | Excellente | Témoin minimal |
| SQLFluff | Parseur, lint et formatage | Dialectes et diagnostics détaillés | Plus lent/lourd, peu de transpilation | Mature, actif | Bonne | Oui, surtout qualité |
| DataFusion | Parse, planifie, optimise, exécute | Rust/Arrow, robuste et performant | Moteur complet, comparaison AST imparfaite | Apache, actif | Binding officiel | Optionnel |
| JSQLParser | AST Java | Éprouvé, nombreux dialectes | JVM et pont Python nécessaires | Mature, actif | Faible | Phase 2 |
| Apache Calcite | Parser, algèbre et optimiseur | Analyse sémantique avancée | Très lourd pour ce CLI | Apache, mature | Faible | Phase 2 |
| GSP | Parser/transpileur commercial | Couverture enterprise/procédures | Licence et runtime non Python | Commercial | Faible | Seulement si besoin métier |

Polyglot annonce un AST typé, la transpilation et des contrôles schema-aware ;
il constitue donc le candidat le plus proche de SQLGlot à approfondir. Sqloxide
est le meilleur test ciblé si la priorité est uniquement le débit de parsing.

## Cinq cas reproductibles

Les SQL de référence sont dans `test_cli.py`. Sur la fixture, ils donnent :

| Question | Résultat attendu |
|---|---|
| Top 5 clients 2026 | Alice 1500; Benoît 1300; Emma 1000; David 900; Chloé 500 |
| CA total par mois | 2025-12: 600; 2026-01: 1900; 02: 800; 03: 900; 04: 950; 05: 1000 |
| Première catégorie 2026 | Mobilier: 2400 |
| Commandes payées par ville | Paris 3; Lyon 2; Bordeaux 2; Lille 1; Marseille 1 |
| Panier moyen payé 2026 | 693,75 |

Les temps affichés par le CLI sont indicatifs : pour un benchmark sérieux, il
faudrait échauffement, répétitions, percentiles et corpus multi-dialecte.

## Sécurité et conclusion

Le SQL est affiché avant contrôle et exécution. Une seule instruction
`SELECT`/`WITH` est acceptée, les nœuds d'écriture et tables inconnues sont
refusés, puis SQLite est ouvert avec `mode=ro`. Cela fonctionne bien pour une
comparaison rapide. Les AST et niveaux de validation restent non équivalents,
et la génération LLM demeure probabiliste. Le prochain test utile est
SQLGlot contre polyglot-sql sur un corpus multi-dialecte réel. Un benchmark plus
complet vaut l'effort seulement si SQLGlot pose déjà un problème mesurable de
couverture, exactitude ou performance.

Sources : [SQLGlot](https://sqlglot.com/sqlglot.html),
[Polyglot](https://github.com/tobilg/polyglot),
[DataFusion Python](https://datafusion.apache.org/python/),
[SQLFluff](https://docs.sqlfluff.com/en/stable/reference/api.html),
[sqlparse](https://sqlparse.readthedocs.io/en/stable/api.html),
[Calcite](https://calcite.apache.org/docs/adapter).
