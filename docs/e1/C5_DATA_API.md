# C5 — API REST de mise à disposition des données

## 1. Objectif

L'API FastAPI existante expose les données analytiques réelles du projet sans dépendre d'un LLM. Elle conserve PostgreSQL comme source de vérité et accepte uniquement des filtres métier prédéfinis.

## 2. Architecture

```text
PostgreSQL
  -> tables de faits, dimensions et vues analytiques
  -> app/core/analytics.py ou repositories SQLAlchemy
  -> routeurs FastAPI app/views/*
  -> client HTTP / Swagger
```

`app/main.py` est le serveur existant. Aucun serveur ni endpoint concurrent n'a été créé. `assistant_api/analytics.py` en est déjà un client autorisé.

## 3. Ressources exposées

Les principales ressources de consultation sont les départements, indicateurs, faits Banque de France, observations de surendettement, inclusion financière, données INSEE, macroéconomie régionale, jeux joints et scores de risque. Les contrats Pydantic explicites ajoutés pour la preuve C5 couvrent les départements, indicateurs et observations de surendettement.

## 4. Endpoints

| Méthode et chemin | Rôle | Accès |
|---|---|---|
| `GET /` | Découverte et lien vers Swagger | Public |
| `GET /health/live` | Santé du processus | Public |
| `GET /api/data/health` | Santé PostgreSQL | Protégé |
| `GET /api/data/departments` | Référentiel territorial paginé | Protégé |
| `GET /api/data/indicators` | Catalogue filtrable des indicateurs | Protégé |
| `GET /api/data/surendettement` | Observations annuelles filtrables | Protégé |
| `GET /api/data/bdf`, `/insee`, `/macro-economic`, `/macro-economic-regions` | Faits analytiques | Protégé |
| `GET /api/risk-scores` et routes associées | Scores et facteurs territoriaux | Protégé |

Les routes `POST/PATCH /api/data/macro-overrides` et `POST /api/risk-scores/calculate` sont des fonctions d'administration/calcul déjà présentes. Elles sont protégées mais ne constituent pas la preuve read-only C5. La ressource `/api/data/surendettement` n'expose que `GET`.

## 5. Paramètres et filtres

`GET /api/data/surendettement` accepte `departement_code`, `indicator_code`, `reference_year` (1900–2100), `limit` (1–500, défaut 100) et `offset` (positif). Les valeurs deviennent des paramètres liés (`:departement_code`, etc.) : aucun SQL brut client n'est accepté. Les référentiels utilisent également `limit`/`offset`; `indicators` accepte `source_system`.

## 6. Authentification et autorisation

Toutes les routes incluses par les routeurs analytiques exigent `X-Internal-Token`. La valeur attendue vient exclusivement de `ASSISTANT_INTERNAL_TOKEN`; aucun secret n'est écrit dans le dépôt. Le schéma OpenAPI `InternalToken` est de type `apiKey` dans le header.

- header absent : `401 Authentification requise`;
- jeton invalide ou configuration absente : `403 Accès non autorisé`;
- `/` et `/health/live` restent publics.

La même dépendance est utilisée conditionnellement par le mode SQL avancé de `assistant_api/main.py`; aucun second système d'authentification n'a été ajouté.

## 7. Protection des données

L'API publie des statistiques territoriales et des métadonnées, pas des dossiers individuels. Les listes de filtres sont construites par le serveur et les valeurs sont liées par SQLAlchemy. FastAPI/Pydantic rejette les bornes invalides avec `422`.

## 8. Read-only

Les trois ressources C5 typées n'offrent que `GET`. Elles exécutent des `SELECT` sur PostgreSQL. Les opérations d'administration historiques sont identifiées séparément ci-dessus et ne sont pas présentées comme des extractions C5 read-only.

## 9. OpenAPI / Swagger

Le schéma est disponible sur `/openapi.json` et l'interface sur `/docs`. Il décrit modèles de réponse, filtres, bornes, réponses `401`, `403`, `422` et le header de sécurité.

## 10. Tests automatisés

`tests/test_data_api.py` couvre le jeton valide, les refus `401/403`, les filtres, la pagination, le contrat JSON Pydantic, l'absence de méthode d'écriture sur la ressource et OpenAPI. `tests/test_assistant_api.py` couvre la protection du SQL avancé.

### Validation réelle sur le staging — 1er septembre 2026

| Appel | Résultat |
|---|---|
| `GET /api/data/health` sans jeton | `200`, PostgreSQL disponible |
| `GET /api/data/surendettement?limit=1` sans jeton | `401` |
| Même appel avec un mauvais jeton | `403` |
| `GET /api/data/departments?limit=2` autorisé | `200`, 2 objets conformes |
| `GET /api/data/indicators?limit=2` autorisé | `200`, 2 objets conformes |
| `GET /api/data/surendettement?departement_code=59&indicator_code=surendettement_dossiers_deposes&reference_year=2025` autorisé | `200`, Nord : 9 154 dossiers |

La pipeline `surendettement_typologie_v2` a traité 13 classeurs régionaux officiels Banque de France 2025 : 96 départements, aucun doublon, 148 013 dossiers. Ce total égale le total national publié. Le snapshot PostgreSQL contient 96 lignes dans `fact_surendettement`; l'API restitue ces faits avec leurs fichiers sources.

## 11. Exemples curl

```bash
curl http://localhost:8000/
curl -H "X-Internal-Token: $ASSISTANT_INTERNAL_TOKEN" "http://localhost:8000/api/data/departments?limit=20&offset=0"
curl -H "X-Internal-Token: $ASSISTANT_INTERNAL_TOKEN" "http://localhost:8000/api/data/indicators?source_system=banque_de_france&limit=50"
curl -H "X-Internal-Token: $ASSISTANT_INTERNAL_TOKEN" "http://localhost:8000/api/data/surendettement?departement_code=59&reference_year=2024&limit=100"
```

## 12. Fichiers constituant les preuves

- `app/main.py` : application, routes publiques et protection des routeurs.
- `docker/compose.yaml` : transmission du même jeton interne au service API.
- `app/views/analytics_api.py` : endpoints, filtres et SQL paramétré.
- `app/schemas/analytics.py` : contrats Pydantic.
- `assistant_api/auth.py` : authentification factorisée et schéma OpenAPI.
- `assistant_api/analytics.py` : client allow-listé consommant l'API.
- `tests/test_data_api.py` et `tests/test_assistant_api.py` : preuves automatisées.
- `src/storage/schema_migrations.py` et `database-doc/dictionary/data-dictionary.md` : vues et dictionnaire PostgreSQL.
