# Rapport du benchmark SQL

Mode : `live` — 12 cas — 20 répétitions.
Garde-fou correct : **12/12**.
Résultat métier correct : **8/8** (ordre exact : 8/8).

## Synthèse des parseurs

| Parseur | Disponible | Cas acceptés | Médiane | p95 |
|---|---:|---:|---:|---:|
| DataFusion | non | 0/0 | — | — |
| SQLFluff | oui | 11/12 | 29.8049 ms | 75.7480 ms |
| SQLGlot | oui | 11/12 | 0.7576 ms | 1.8666 ms |
| polyglot-sql | oui | 11/12 | 0.0738 ms | 0.1759 ms |
| sqloxide | oui | 11/12 | 0.1573 ms | 0.3960 ms |
| sqlparse | oui | 12/12 | 1.6130 ms | 4.2505 ms |

## Détail des cas

| Cas | Lecture attendue | Garde-fou | Résultat | Ordre | Lignes |
|---|---:|---:|---:|---:|---:|
| top_customers | oui | correct | correct | correct | 5 |
| monthly_revenue | oui | correct | correct | correct | 6 |
| best_category | oui | correct | correct | correct | 1 |
| orders_by_city | oui | correct | correct | correct | 5 |
| average_basket_cte | oui | correct | correct | correct | 1 |
| customers_without_orders | oui | correct | correct | correct | 0 |
| product_ranking_window | oui | correct | correct | correct | 5 |
| conditional_aggregation | oui | correct | correct | correct | 1 |
| delete_rejected | non | correct | — | — | 0 |
| multi_statement_rejected | non | correct | — | — | 0 |
| unknown_table_rejected | non | correct | — | — | 0 |
| malformed_sql | non | correct | — | — | 0 |
