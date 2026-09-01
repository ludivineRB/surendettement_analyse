# C12 — Tests automatisés et CI

Les tests par défaut sont hors ligne : providers, API distante et vues Django sont
mockés. `OPENAI_API_KEY` est vide dans `.github/workflows/ci.yml`.

| Exigence | Test | Fichier | Type | CI |
|---|---|---|---|---|
| API, validation, auth, décisions | `test_*answer*`, `test_*authentication*` | `tests/test_assistant_api.py` | API/unitaire | oui |
| Provider et erreurs | `test_*` | `tests/test_assistant_openai_provider.py` | unitaire mocké | oui |
| Orchestration | `test_*` | `tests/test_assistant_orchestration.py` | unitaire | oui |
| Validation/exécution SQL | `test_*` | `tests/test_sql_validation.py`, `test_sql_executor.py`, `test_sql_service.py` | unitaire | oui |
| Monitoring | `test_summary_*` | `tests/test_assistant_monitoring.py` | unitaire | oui |
| Client Django | `AssistantClientTests` | `web/assistant/test_client.py` | mock HTTP | oui |
| Vue/formulaire/auth | `AssistantViewTests` | `web/assistant/test_views.py` | Django | oui |
| Build et smoke | `package-assistant` | `.github/workflows/ci.yml` | conteneur | oui |

Campagne E3 locale exacte :

```bash
pytest -q tests/test_assistant_api.py tests/test_assistant_monitoring.py \
  tests/test_assistant_openai_provider.py tests/test_assistant_orchestration.py \
  tests/test_sql_validation.py tests/test_sql_executor.py tests/test_sql_service.py
python web/manage.py test web.assistant --testrunner=django.test.runner.DiscoverRunner
```

La campagne reproductible complète est `sh docker/run_ci.sh`. Elle exécute contrôles
statiques, audits de dépendances, build, pytest, évaluations hors ligne, tests Django,
migrations PostgreSQL et validation Compose. Les rapports JUnit, couverture et
évaluations sont publiés comme artifacts. Un test live éventuel ne doit jamais bloquer
ce workflow standard.
