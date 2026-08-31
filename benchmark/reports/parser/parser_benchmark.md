# Benchmark des parseurs

Parsing capability is not a security verdict; SQLGlot remains the guard.

Date : 2026-08-31T21:43:41.747372+00:00 — répétitions : 20
Corpus invalide : 1 cas seulement; le taux de détection est donc peu robuste.

## Résultats expérimentaux (MESURE DU POC)

| Parseur | Disponible | Parse | SQL invalide détecté | Moyenne | p50 | p95 |
|---|---:|---:|---:|---:|---:|---:|
| sqlglot | oui | 100% | 100% | 0.5778 | 0.2376 | 0.5073 |
| sqloxide | oui | 100% | 100% | 0.0420 | 0.0339 | 0.0847 |
| polyglot-sql | oui | 100% | 100% | 0.0292 | 0.0145 | 0.0354 |
| sqlparse | oui | 100% | 0% | 0.7001 | 0.4253 | 1.6019 |
| sqlfluff | oui | 90% | 100% | 15.7533 | 10.4900 | 35.0784 |
| datafusion | non | 0% | 0% | 0.0860 | 0.0860 | 0.0860 |

## Capacités déclarées/implémentées (FAIT DOCUMENTÉ)

Ces capacités proviennent des adaptateurs et ne sont pas mesurées par cette campagne.

| Parseur | AST | Tables | Colonnes | JOIN | Statement | Dépendance |
|---|---:|---:|---:|---:|---:|---|
| sqlglot | True | True | True | True | True | light |
| sqloxide | True | True | True | True | True | rust binding |
| polyglot-sql | True | True | True | True | True | rust binding |
| sqlparse | False | False | False | False | token_only | light |
| sqlfluff | True | True | True | True | True | medium |
| datafusion | False | True | True | True | logical_plan | heavy/optional |

## Conclusion (RECOMMANDATION)

Comparer richesse, erreurs, temps et dépendances; ne remplacer SQLGlot qu’après équivalence fonctionnelle démontrée.
