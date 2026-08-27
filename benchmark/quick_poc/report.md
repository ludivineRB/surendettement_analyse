# Rapport du benchmark SQL

Mode : `live` — 12 cas — 20 répétitions.
Garde-fou correct : **12/12**.
Résultat métier correct : **4/8** (ordre exact : 3/8).

## Synthèse des parseurs

| Parseur | Disponible | Cas acceptés | Médiane | p95 |
|---|---:|---:|---:|---:|
| DataFusion | non | 0/0 | — | — |
| SQLFluff | oui | 11/12 | 23.8462 ms | 56.5191 ms |
| SQLGlot | oui | 11/12 | 0.6525 ms | 1.6985 ms |
| polyglot-sql | oui | 11/12 | 0.0696 ms | 0.1720 ms |
| sqloxide | oui | 11/12 | 0.1490 ms | 0.3088 ms |
| sqlparse | oui | 12/12 | 1.4445 ms | 3.3941 ms |

## Détail des cas

| Cas | Lecture attendue | Garde-fou | Résultat | Ordre | Lignes |
|---|---:|---:|---:|---:|---:|
| top_customers | oui | correct | incorrect | incorrect | 5 |
| monthly_revenue | oui | correct | incorrect | incorrect | 6 |
| best_category | oui | correct | incorrect | incorrect | 1 |
| orders_by_city | oui | correct | correct | incorrect | 5 |
| average_basket_cte | oui | correct | correct | correct | 1 |
| customers_without_orders | oui | correct | correct | correct | 0 |
| product_ranking_window | oui | correct | incorrect | incorrect | 5 |
| conditional_aggregation | oui | correct | correct | correct | 1 |
| delete_rejected | non | correct | — | — | 0 |
| multi_statement_rejected | non | correct | — | — | 0 |
| unknown_table_rejected | non | correct | — | — | 0 |
| malformed_sql | non | correct | — | — | 0 |
