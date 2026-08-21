# PostgreSQL migration validation

Status: **PASS**

## Table volumes

| Table | SQLite | PostgreSQL | Match |
|---|---:|---:|:---:|
| dim_period | 17 | 17 | yes |
| dim_region | 13 | 13 | yes |
| indicators | 9 | 9 | yes |
| observations | 11543 | 11543 | yes |
| pipeline_runs | 0 | 0 | yes |
| risk_score_details | 12928 | 12928 | yes |
| risk_score_indicator_configs | 18 | 18 | yes |
| risk_score_models | 3 | 3 | yes |
| risk_scores | 4090 | 4090 | yes |
| source_documents | 1763 | 1763 | yes |
| surendettement_data | 38 | 38 | yes |

## Errors

- None

## Warnings

- None
