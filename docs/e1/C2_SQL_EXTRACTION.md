# C2 — Requêtes SQL d'extraction PostgreSQL

## Périmètre vérifié

PostgreSQL est la source de vérité. Les exemples ciblent uniquement les vues créées par `src/storage/schema_migrations.py` et autorisées par `assistant_api/sql_validation.py`. Le chemin d'exécution impose un `SELECT` unique, des colonnes connues, au plus trois jointures, un `LIMIT` de 1 à 200, une transaction `READ ONLY`, un délai de 5 s et un contrôle préalable par `EXPLAIN (FORMAT JSON)`.

Les quatre fichiers ont été validés par `validate_analytical_sql`, puis exécutés le 1er septembre 2026 sur le PostgreSQL de staging via le rôle `analytics_readonly`. Ce rôle a `default_transaction_read_only=on`, un `statement_timeout` de 5 s, le droit `SELECT` sur les six vues analytiques et aucun droit `INSERT`, `UPDATE` ou `DELETE` sur `observations`. Les durées ci-dessous sont des mesures ponctuelles de l'exécuteur applicatif ; les coûts et cardinalités proviennent de `EXPLAIN (FORMAT JSON)`.

## 1. Classement territorial

- **Objectif métier :** identifier les dix départements dont le score actif est le plus élevé en février 2025.
- **Données recherchées :** code, libellé, score et niveau de risque.
- **SQL :** [`sql/01_scores_territoriaux.sql`](sql/01_scores_territoriaux.sql).
- **Vue / colonnes :** `analytics_risk_scores` ; `geographic_code`, `geographic_name`, `score`, `risk_level`.
- **Filtres et conditions :** niveau `department`, période `2025-02`, modèle actif.
- **Jointure / agrégation :** aucune.
- **Résultat obtenu :** 10 lignes en 100 ms. Les trois premiers départements sont l'Aisne (`87.33811047`), le Nord (`84.56112667`) et l'Aude (`83.02166046`), tous classés `very_high`.
- **Optimisation :** projection explicite et résultat borné. La vue s'appuie sur `risk_scores`; l'index `ix_risk_scores_model_level_period_score` couvre modèle, niveau, période et score.
- **EXPLAIN :** coût `184.48`, 10 lignes estimées au nœud `Limit`. PostgreSQL choisit un parcours séquentiel de `risk_scores`, puis `Sort`, et un `Index Scan` sur `risk_score_models_pkey`. Sur ce volume, le planificateur estime le parcours séquentiel moins coûteux que l'index composite.
- **Tests :** `tests/test_sql_validation.py::test_accepts_bounded_select_on_allowlisted_view`, benchmark `quality_ranking_01`.

## 2. Agrégation macroéconomique

- **Objectif métier :** calculer la part moyenne des familles monoparentales entre régions en 2022.
- **Données recherchées :** moyenne de `value_numeric`.
- **SQL :** [`sql/02_moyenne_macro_regions.sql`](sql/02_moyenne_macro_regions.sql).
- **Vue / colonnes :** `analytics_macro_regions` ; `value_numeric`, `reference_year`, `indicator_code`.
- **Filtres et conditions :** année 2022 et indicateur `part_familles_monoparentales`.
- **Jointure :** aucune au niveau de la requête ; la vue publie le mart régional sélectionné.
- **Agrégation :** `AVG`, une ligne maximum.
- **Résultat obtenu :** une ligne en 189 ms, moyenne `16.323726060143606`.
- **Optimisation :** réduction précoce sur année et code indicateur, projection d'une seule mesure.
- **EXPLAIN :** coût `276.14`, une ligne estimée. Le plan agrège les branches de la vue régionale et utilise notamment `idx_insee_indicator`, `dim_department_pkey` et `dim_region_pkey`. Des parcours séquentiels subsistent sur les petites dimensions et une branche de `fact_insee_macro`.
- **Tests :** `tests/test_sql_validation.py::test_accepts_allowlisted_aggregate_with_boolean_filters`, benchmark `quality_macro_02`.

## 3. Jointure score–facteur

- **Objectif métier :** relier le score actif d'une région à la contribution du facteur pauvreté.
- **Données recherchées :** territoire, score, indicateur explicatif, contribution.
- **SQL :** [`sql/03_scores_facteurs.sql`](sql/03_scores_facteurs.sql).
- **Vues / colonnes :** `analytics_risk_scores` et `analytics_score_factors`; colonnes territoriales, période, modèle, score et contribution.
- **Filtres et conditions :** régions, période `2025-02`, modèle actif, facteur `taux_pauvrete`.
- **Jointure :** égalité sur niveau, code, période, code modèle et version. Ces cinq conditions évitent de mélanger territoires, périodes ou versions.
- **Agrégation :** aucune ; classement par contribution décroissante.
- **Résultat obtenu :** 13 lignes en 64 ms. Les premières contributions pauvreté sont la Corse (`22.22222222`), les Hauts-de-France (`22.09487424`) et l'Occitanie (`20.50302451`).
- **Optimisation :** filtres sélectifs, colonnes explicites, jointure sur clés métier complètes. Les tables sources disposent notamment de `ix_risk_scores_geo_period`, `ix_risk_scores_model_level_period_score` et `ix_risk_score_details_risk_score_id`.
- **EXPLAIN :** coût `45.14`, une ligne estimée contre 13 obtenues. Les boucles imbriquées utilisent `ix_risk_scores_model_level_period_score`, `ix_risk_scores_geo_period` et `uq_risk_score_details_score_code`. L'écart de cardinalité justifie un futur `ANALYZE` si le volume augmente, sans nécessiter d'index supplémentaire aujourd'hui.
- **Tests :** `tests/test_sql_validation.py::test_accepts_qualified_columns_and_projection_alias`.

## 4. Évolution temporelle d'une observation

- **Objectif métier :** suivre un indicateur de surendettement du Nord entre 2024 et 2025.
- **Données recherchées :** période, valeur, variation et unité de variation.
- **SQL :** [`sql/04_evolution_observations.sql`](sql/04_evolution_observations.sql).
- **Vue / colonnes :** `analytics_observations` ; `reference_period`, `value_numeric`, `variation_numeric`, `variation_unit`.
- **Filtres et conditions :** département `59`, indicateur `dossiers_surendettement_1000_habitants`, intervalle fermé `2024-01`–`2025-12`.
- **Jointure / agrégation :** aucune dans l'extraction ; la vue joint déjà `observations` et `indicators`.
- **Résultat obtenu :** 11 lignes en 148 ms. Les premières périodes 2025-02, 2025-03 et 2025-04 valent chacune `4.25`; les variations sont absentes (`NULL`) dans ces lignes.
- **Optimisation :** filtres compatibles avec `ix_observations_code_level_period` et `ix_observations_period_level_code`; tri et volume bornés.
- **EXPLAIN :** coût `260.8`, 7 lignes estimées contre 11 obtenues. Un `BitmapAnd` combine `ix_observations_indicator_code` et `ix_observations_period_level_code`, puis la vue joint la petite table `indicators` par hachage.
- **Tests :** `tests/test_text_to_sql_benchmark.py::test_offline_dataset_contract_and_adversarial_sql_pass` (sécurité générale) ; validation des quatre fichiers lors du contrôle final.

## Reproduction

Validation hors base, pour chaque fichier :

```bash
.venv/bin/python -c "from pathlib import Path; from assistant_api.sql_validation import validate_analytical_sql as v; [print(p, v(p.read_text())) for p in sorted(Path('docs/e1/sql').glob('*.sql'))]"
```

Exécution read-only et collecte du coût (répéter avec chaque fichier après configuration de `ANALYTICS_READONLY_DATABASE_URL`) :

```bash
.venv/bin/python -c "from pathlib import Path; from assistant_api.sql_executor import execute_readonly_sql as run; r=run(Path('docs/e1/sql/01_scores_territoriaux.sql').read_text()); print({'rows': r.rows, 'duration_ms': r.duration_ms, 'plan_cost': r.plan_cost, 'plan_rows': r.plan_rows})"
```

Le détail du plan peut être obtenu dans `psql` avec `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)` sur une base de démonstration non productive. `ANALYZE` exécute la requête : conserver le rôle read-only et ne l'utiliser que pour ces `SELECT` bornés.
