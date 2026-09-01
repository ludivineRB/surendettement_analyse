# C9 — API du service IA

## Rôle et architecture

`assistant_api/main.py` expose le service FastAPI. Il orchestre recherche documentaire,
API analytique, génération et SQL en lecture seule. Les contrats Pydantic sont dans
`assistant_api/schemas.py` et l'authentification dans `assistant_api/auth.py`.

| Endpoint | Méthode | Authentification | Entrée / sortie | Codes principaux |
|---|---|---|---|---|
| `/v1/answers` | POST | `X-Internal-Token` | `AnswerRequest` / `AnswerResponse` | 200, 401, 403, 422, 503 |
| `/v1/retrieval/search` | POST | aucune | recherche / résultats sourcés | 200, 422, 503 |
| `/health` | GET | aucune | aucune / état du processus | 200 |
| `/health/ready` | GET | aucune | aucune / état PostgreSQL | 200, 503 |
| `/monitoring/summary` | GET | `X-Internal-Token` | aucune / synthèse | 200, 401, 403 |

`AnswerResponse.decision` vaut `execute`, `clarify` ou `refuse`. Les champs historiques
`method` et `category` sont conservés. Le token n'est jamais placé dans les exemples,
les erreurs ou les logs.

## Appels de preuve

```bash
curl http://localhost:8030/health
curl -i -X POST http://localhost:8030/v1/answers \
  -H 'Content-Type: application/json' \
  -d '{"question":"Quels sont les facteurs territoriaux ?"}'
curl -X POST http://localhost:8030/v1/answers \
  -H "X-Internal-Token: $ASSISTANT_INTERNAL_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"question":"Quels sont les facteurs territoriaux ?","mode":"information"}'
```

Pour Swagger, démarrer le service, ouvrir `http://localhost:8030/docs`, déplier
`POST /v1/answers`, cliquer sur **Authorize** et fournir une valeur locale. Capturer le
schéma de réponse et une exécution réelle sans faire apparaître le token.

Tests associés : `tests/test_assistant_api.py`, `tests/test_assistant_monitoring.py`,
`tests/test_assistant_openai_provider.py`, `tests/test_sql_validation.py` et
`tests/test_sql_executor.py`.
