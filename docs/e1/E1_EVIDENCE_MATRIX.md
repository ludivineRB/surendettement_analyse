# E1 — Matrice de preuves RNCP37827

Cette matrice référence uniquement des éléments vérifiables dans le dépôt au 1er septembre 2026.

| Critère RNCP | Preuve | Fichier | Test / commande | Statut |
|---|---|---|---|---|
| C1 — collecte automatisée | Pipelines Banque de France, Statinfo et INSEE existantes | `src/surendettement_pipeline.py`, `src/statinfo_pipeline.py`, `src/insee_macro/pipeline.py` | `pytest tests/test_surendettement_pipeline.py tests/test_statinfo_bi_pipeline.py tests/test_insee_macro_pipeline.py` | Couvert par le dépôt |
| C1 — sources et traçabilité | Documents sources et métadonnées persistés | `src/storage/models.py`, `database-doc/dictionary/data-dictionary.md` | `pytest tests/test_ingest.py tests/test_downloader.py` | Couvert par le dépôt |
| C1 — preuve d'exécution sur sources réelles | 13 classeurs officiels 2025 traités, 96 départements, 148 013 dossiers | `src/surendettement_pipeline.py`, `docs/e1/C5_DATA_API.md` | exécution `surendettement_typologie_v2` du 1er septembre 2026 | Couvert pour la collecte surendettement |
| C2 — requêtes fonctionnelles | Quatre `SELECT` compatibles avec les vues autorisées | `docs/e1/sql/*.sql`, `assistant_api/sql_validation.py` | commande de validation dans `C2_SQL_EXTRACTION.md` | Couvert hors base |
| C2 — sélections, filtres, conditions, jointures, objectifs | Fiches détaillées par requête | `docs/e1/C2_SQL_EXTRACTION.md` | Relecture documentaire | Couvert |
| C2 — lecture contrôlée | AST, liste blanche, limites, transaction read-only | `assistant_api/sql_validation.py`, `assistant_api/sql_executor.py` | `pytest tests/test_sql_validation.py tests/test_sql_executor.py` | Couvert |
| C2 — résultats et EXPLAIN réels | 4 extractions exécutées via `analytics_readonly`; lignes, durées, coûts, cardinalités et échantillons relevés | `assistant_api/sql_executor.py`, `docs/e1/C2_SQL_EXTRACTION.md` | commande d'exécution C2 sur le staging | Couvert |
| C2 — optimisation | Plans réels et index utilisés interprétés | `database-doc/extracted/schema.sql`, `assistant_api/sql_executor.py`, `docs/e1/C2_SQL_EXTRACTION.md` | `EXPLAIN (FORMAT JSON)` sur les quatre requêtes | Couvert |
| C3 — préparation / transformation | Nettoyage et transformations reproductibles existants | `src/processing/transform.py`, `src/transformer.py` | `pytest tests/test_transform.py tests/test_statinfo_bi_quality.py` | Couvert par le dépôt |
| C3 — preuve quantitative avant/après | Rapport consolidé des anomalies corrigées et lignes rejetées | Aucun livrable E1 dédié identifié | Produire un rapport depuis une exécution réelle | **À COMPLÉTER** |
| C4 — modélisation des données | Modèle relationnel, dictionnaire, MCD/MLD/MPD et marts | `src/storage/models.py`, `src/marts/build_surendettement_macro.py`, `database-doc/` | `pytest tests/test_surendettement_macro_mart.py tests/test_analytics_views_migration.py` | Couvert par le dépôt |
| C4 — justification métier du modèle | Revue Merise et documentation des objets | `database-doc/review/lot-19-merise.md`, `database-doc/dictionary/data-dictionary.md` | Relecture documentaire | Couvert |
| C5 — API REST fonctionnelle | Routeurs FastAPI de données PostgreSQL existants | `app/main.py`, `app/views/analytics_api.py`, `app/views/risk_scores_api.py` | `uvicorn app.main:app` | Couvert |
| C5 — récupération conforme | Ressources départements, indicateurs et surendettement filtrables/paginées | `app/views/analytics_api.py`, `app/schemas/analytics.py` | `pytest tests/test_data_api.py` | Couvert |
| C5 — authentification / autorisation | Jeton interne factorisé, erreurs 401/403 | `assistant_api/auth.py`, `app/main.py` | `pytest tests/test_data_api.py tests/test_assistant_api.py` | Couvert |
| C5 — OpenAPI | Modèles, descriptions, paramètres et schéma `InternalToken` | `app/schemas/analytics.py`, `app/views/analytics_api.py` | vérifier `/docs`, `/openapi.json`; test OpenAPI | Couvert |
| C5 — read-only | Ressources de preuve uniquement en `GET`, SQL client interdit | `app/views/analytics_api.py`, `tests/test_data_api.py` | test d'absence de méthode d'écriture dans OpenAPI | Couvert |
| C5 — preuve sur PostgreSQL réel | Staging : santé 200, refus 401/403, référentiels et fait Nord 2025 retournés en 200 | `docs/e1/C5_DATA_API.md` | appel HTTP filtré depuis `assistant-api` vers `api:8020` | Couvert |
