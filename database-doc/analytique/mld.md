# MLD analytique

Chaque relation indique explicitement la colonne source et la colonne cible.
`FK` signifie clé étrangère physique ; `lien logique` signifie que le
rapprochement est réalisé sans contrainte PostgreSQL.

## 1. Mart BDF et INSEE

```mermaid
flowchart LR
    REGION["DIM_REGION<br/><b>PK region_code</b><br/>region_name<br/>is_metropolitan_scope"]
    DEPT["DIM_DEPARTMENT<br/><b>PK departement_code</b><br/>departement_name<br/>region_code<br/>region_name"]
    PERIOD["DIM_PERIOD<br/><b>PK period_key</b><br/>reference_year<br/>reference_month_number<br/>granularity"]
    IND["DIM_INDICATOR<br/><b>PK indicator_key</b><br/>source_system<br/>indicator_code<br/>indicator_name<br/>aggregation_rule"]
    BDF["FACT_BDF_STATINFO<br/>reference_period<br/>reference_year<br/><b>FK departement_code</b><br/><b>FK indicator_key</b><br/>value"]
    INSEE["FACT_INSEE_MACRO<br/>reference_year<br/><b>FK departement_code</b><br/><b>FK indicator_key</b><br/>value"]
    OVERRIDE["FACT_MACRO_OVERRIDE<br/><b>PK id</b><br/><b>FK period_key</b><br/><b>FK departement_code</b><br/><b>FK indicator_key</b><br/>value"]

    DEPT -->|"region_code → dim_region.region_code<br/>lien logique"| REGION
    BDF -->|"departement_code → dim_department.departement_code<br/>FK"| DEPT
    BDF -->|"indicator_key → dim_indicator.indicator_key<br/>FK"| IND
    BDF -->|"reference_period → dim_period.period_key<br/>lien logique"| PERIOD
    INSEE -->|"departement_code → dim_department.departement_code<br/>FK"| DEPT
    INSEE -->|"indicator_key → dim_indicator.indicator_key<br/>FK"| IND
    INSEE -->|"reference_year → dim_period.reference_year<br/>lien logique"| PERIOD
    OVERRIDE -->|"period_key → dim_period.period_key<br/>FK"| PERIOD
    OVERRIDE -->|"departement_code → dim_department.departement_code<br/>FK"| DEPT
    OVERRIDE -->|"indicator_key → dim_indicator.indicator_key<br/>FK"| IND
```

### Clés métier du mart

| Relation | Clé ou unicité |
|---|---|
| `dim_region` | `region_code` |
| `dim_department` | `departement_code` |
| `dim_period` | `period_key` |
| `dim_indicator` | `indicator_key` |
| `fact_bdf_statinfo` | `(reference_period, departement_code, indicator_key)` |
| `fact_insee_macro` | `(reference_year, departement_code, indicator_key)` |

## 2. Observations et traçabilité

```mermaid
flowchart LR
    DOC["SOURCE_DOCUMENTS<br/><b>PK id</b><br/>UQ pdf_sha256<br/>publication_type<br/>region_code<br/>reference_period<br/>extraction_status"]
    IND["INDICATORS<br/><b>PK id</b><br/>UQ code<br/>label<br/>default_unit"]
    OBS["OBSERVATIONS<br/><b>PK id</b><br/><b>FK source_document_id</b><br/><b>FK indicator_id</b><br/>UQ idempotence_key<br/>geographic_level<br/>geographic_code<br/>reference_period<br/>value_numeric"]

    OBS -->|"source_document_id → source_documents.id<br/>FK"| DOC
    OBS -->|"indicator_id → indicators.id<br/>FK"| IND
```

| Relation | Cardinalité |
|---|---|
| `source_documents.id` ← `observations.source_document_id` | 1 document → 0..n observations |
| `indicators.id` ← `observations.indicator_id` | 1 indicateur → 0..n observations |

## 3. Scores territoriaux

```mermaid
flowchart LR
    MODEL["RISK_SCORE_MODELS<br/><b>PK id</b><br/>UQ code + version<br/>normalization_method<br/>minimum_coverage_ratio"]
    CONFIG["RISK_SCORE_INDICATOR_CONFIGS<br/><b>PK id</b><br/><b>FK risk_score_model_id</b><br/><b>FK indicator_id</b><br/>indicator_code<br/>weight<br/>direction"]
    SCORE["RISK_SCORES<br/><b>PK id</b><br/><b>FK risk_score_model_id</b><br/>geographic_level<br/>geographic_code<br/>reference_period<br/>score<br/>coverage_ratio"]
    DETAIL["RISK_SCORE_DETAILS<br/><b>PK id</b><br/><b>FK risk_score_id</b><br/><b>FK indicator_id</b><br/><b>FK source_observation_id</b><br/>normalized_value<br/>contribution"]
    IND["INDICATORS<br/><b>PK id</b><br/>UQ code"]
    OBS["OBSERVATIONS<br/><b>PK id</b><br/>UQ idempotence_key"]

    CONFIG -->|"risk_score_model_id → risk_score_models.id<br/>FK"| MODEL
    CONFIG -->|"indicator_id → indicators.id<br/>FK nullable"| IND
    SCORE -->|"risk_score_model_id → risk_score_models.id<br/>FK"| MODEL
    DETAIL -->|"risk_score_id → risk_scores.id<br/>FK"| SCORE
    DETAIL -->|"indicator_id → indicators.id<br/>FK nullable"| IND
    DETAIL -->|"source_observation_id → observations.id<br/>FK nullable"| OBS
```

### Unicités du scoring

| Relation | Unicité métier |
|---|---|
| `risk_score_models` | `(code, version)` |
| `risk_score_indicator_configs` | `(risk_score_model_id, indicator_code)` |
| `risk_scores` | `(risk_score_model_id, geographic_level, geographic_code, reference_period)` |
| `risk_score_details` | `(risk_score_id, indicator_code)` |

## 4. Dépendances des vues finales

```mermaid
flowchart LR
    OBS[observations] --> AO[analytics_observations]
    IND[indicators] --> AO
    SCORE[risk_scores] --> AR[analytics_risk_scores]
    MODEL[risk_score_models] --> AR
    DETAIL[risk_score_details] --> AF[analytics_score_factors]
    SCORE --> AF
    MODEL --> AF
    SCORE --> AMC[analytics_model_comparisons]
    MODEL --> AMC
    REGION[v_insee_macro_region_selected] --> AMR[analytics_macro_regions]
    RUN[pipeline_runs] --> APS[analytics_pipeline_status]
```

Les vues `analytics_*` constituent la seule interface SQL accordée au rôle
`analytics_readonly` de l’assistant.

