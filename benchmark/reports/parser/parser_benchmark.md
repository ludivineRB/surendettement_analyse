# Benchmark des parseurs

Parsing capability is not a security verdict; SQLGlot remains the guard.

Date : 2026-08-31T20:48:36.474082+00:00 — répétitions : 20

| Parseur | Disponible | Parse | SQL invalide détecté | Moyenne | p50 | p95 | AST | Dépendance |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| sqlglot | oui | 100% | 100% | 0.4205 | 0.2147 | 0.4766 | True | light |
| sqloxide | oui | 100% | 100% | 0.0443 | 0.0407 | 0.0696 | True | rust binding |
| polyglot-sql | oui | 100% | 100% | 0.0220 | 0.0108 | 0.0229 | True | rust binding |
| sqlparse | oui | 100% | 0% | 0.6746 | 0.6393 | 1.5518 | False | light |
| sqlfluff | oui | 90% | 100% | 16.3712 | 10.6923 | 35.2578 | True | medium |
| datafusion | non | 0% | 0% | 0.0900 | 0.0900 | 0.0900 | False | heavy/optional |

## Conclusion (RECOMMANDATION)

Comparer richesse, erreurs, temps et dépendances; ne remplacer SQLGlot qu’après équivalence fonctionnelle démontrée.
