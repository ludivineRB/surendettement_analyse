# C20 — Monitoring et journalisation

## 1. Objectif et périmètre

La supervision détecte l'indisponibilité et les dégradations des API FastAPI,
de l'Assistant, de Django et de PostgreSQL. Elle suit aussi les recherches RAG,
les exécutions Text-to-SQL, la fraîcheur des données, l'intégrité et les pipelines.
Streamlit n'est pas directement collecté par Prometheus.

## 2. Architecture et flux

```text
API / Assistant / Django / postgres-exporter
                  │ /metrics
                  ▼
             Prometheus ──► règles ──► Alertmanager ──► notifier local
                  │
                  └──────────────► Grafana

stdout JSON ──► Docker json-file ──► Promtail ──► Loki ──► Grafana

bases opérationnelle/analytique ──► rapport observability ──► Streamlit
```

Les images sont épinglées dans `docker/compose.yaml` : Prometheus 3.5.0,
Alertmanager 0.28.1, Loki/Promtail 3.5.3 et Grafana 12.1.1. Les interfaces
Prometheus, Alertmanager et Grafana sont liées à `127.0.0.1` par défaut.

## 3. Justification des outils

- **Prometheus** : collecte pull, langage PromQL et validation des règles par
  `promtool`, adaptés aux compteurs HTTP et métier.
- **Grafana** : vue commune des séries Prometheus et des logs Loki ; provisioning
  versionné du dashboard et des sources.
- **Alertmanager** : groupement, déduplication et cycle de vie des alertes.
- **Loki** : centralisation locale des journaux avec rétention de 360 heures.
- **Promtail** : découverte des conteneurs Docker et transfert des sorties JSON.
- **Notifier local** : notification Linux sans secret ni service tiers. Il est
  limité à une session graphique active.

## 4. Métriques

| Métrique | Type logique | Labels | Finalité/source |
|---|---|---|---|
| `fastapi_http_requests_total` | compteur | method, path, status | trafic API (`app/main.py`) |
| `fastapi_http_request_duration_seconds_{count,sum}` | résumé simple | method, path, status | latence API |
| `assistant_http_requests_total` | compteur | method, path, status | trafic Assistant |
| `assistant_http_request_duration_seconds_{count,sum}` | résumé simple | method, path, status | latence Assistant |
| `django_http_requests_total` | compteur | method, path, status | trafic Django |
| `django_http_request_duration_seconds_{count,sum}` | résumé simple | method, path, status | latence Django |
| `assistant_decisions_total` | compteur | decision, category | execute/clarify/refuse |
| `assistant_provider_errors_total` | compteur | provider | erreurs du générateur |
| `assistant_rag_retrievals_total` | compteur | status | hit/empty |
| `assistant_rag_retrieval_duration_seconds_{count,sum}` | résumé simple | aucun | durée RAG |
| `assistant_rag_retrieval_results_{count,sum}` | résumé simple | aucun | nombre de résultats |
| `assistant_sql_executions_total` | compteur | status, reason | accepté/rejeté |
| `assistant_sql_audit_errors_total` | compteur | aucun | échec de persistance d'audit |
| `assistant_sql_execution_duration_seconds_{count,sum}` | résumé simple | aucun | durée SQL |
| `assistant_sql_result_rows_{count,sum}` | résumé simple | aucun | lignes SQL |
| `pg_stat_activity_count` | gauge exporté | labels postgres-exporter | connexions PostgreSQL |
| rapport métier | rapport JSON | sans labels Prometheus | fraîcheur, intégrité, pipelines |

Les métriques applicatives sont conservées en mémoire du processus et repartent
à zéro au redémarrage. Prometheus conserve ses séries 15 jours.

## 5. Collecte et dashboard

`docker/monitoring/prometheus.yml` collecte toutes les 15 secondes :

| Job | Cible | Endpoint |
|---|---|---|
| fastapi | `api:8020` | `/metrics` |
| assistant | `assistant-api:8030` | `/metrics/prometheus` |
| django | `django:8000` | `/metrics/` |
| postgres | `postgres-exporter:9187` | `/metrics` par défaut |

Le dashboard provisionné « Surendettement — Vue opérationnelle » comporte sept
panneaux : disponibilité, requêtes par statut, latence moyenne, connexions
PostgreSQL, recherches RAG, exécutions SQL et logs centralisés.

## 6. Seuils d'alerte

| Alerte | Expression résumée | Seuil | `for` | Sévérité | Composant |
|---|---|---:|---:|---|---|
| `ServiceUnavailable` | `up == 0` | indisponible | 2 min | critical | quatre jobs |
| `ApiErrorRateHigh` | ratio 5xx API sur 5 min | > 2 % | 10 min | warning | API |
| `AssistantErrorRateHigh` | ratio 5xx Assistant sur 5 min | > 2 % | 10 min | warning | Assistant |
| `AssistantLatencyHigh` | latence moyenne sur 5 min | > 5 s | 10 min | warning | Assistant |
| `RagEmptyResultsHigh` | ratio vide sur 15 min | > 20 % | 15 min | warning | RAG |
| `SqlRejectionRateHigh` | ratio rejeté sur 15 min | > 25 % | 15 min | warning | Text-to-SQL |
| `PostgreSQLConnectionsHigh` | somme connexions | > 80 | 10 min | warning | PostgreSQL |

Les sept scénarios sont testés dans `docker/monitoring/alerts.test.yml`. La
constante Python `http_latency_p95_warning_seconds=1.0` ne correspond pas à
l'alerte Prometheus (moyenne > 5 s) : cette seconde source concerne le rapport
métier et ne doit pas être présentée comme le seuil déployé de l'alerte.

## 7. Santé et disponibilité

| Service | Liveness | Readiness/health utilisé |
|---|---|---|
| API | `/health/live` | `/api/data/health` dans Compose |
| Assistant | `/health/live` | `/health/ready` avec `SELECT 1` |
| Django | `/health/live/` | `/health/ready/` avec `SELECT 1` |
| PostgreSQL | — | `pg_isready` |
| Grafana | — | `/api/health` |

## 8. Logs, corrélation et données personnelles

Les trois backends créent ou valident un `X-Request-ID`, le renvoient dans la
réponse et journalisent méthode, chemin, statut et durée. Ni corps, ni paramètres
de requête, ni headers, cookies ou chaînes de connexion ne sont journalisés.

Le formateur Django masque les motifs `password`, `token`, `secret` et
`authorization`. L'identifiant de compte `actor_id` a été retiré des logs HTTP.
Les exceptions sont soumises au même masquage. Les questions et SQL peuvent
être présents dans l'audit SQL en base ; ils ne sont pas ajoutés aux logs Loki.

Promtail conserve `service`, `container` et `level` comme labels. `request_id`
est extrait mais n'est pas promu en label, ce qui évite une forte cardinalité ;
il reste recherchable dans la ligne JSON.

## 9. Installation et lancement local

Préparer hors Git les variables obligatoires `POSTGRES_PASSWORD`,
`GRAFANA_ADMIN_PASSWORD`, `DJANGO_SECRET_KEY` et, selon le scénario,
`ASSISTANT_INTERNAL_TOKEN`/`OPENAI_API_KEY`, puis :

```bash
docker compose -f docker/compose.yaml up -d --build
docker compose -f docker/compose.yaml ps
sh docker/test_observability.sh
```

Le script vérifie les sept scénarios d'alerte, trois endpoints de métriques,
toutes les cibles Prometheus et la santé Grafana. Il ne supprime aucun volume.

## 10. Vérifications opérationnelles

1. Prometheus `/targets` : quatre cibles `UP`.
2. Requête `up{job=~"fastapi|assistant|django|postgres"}` : valeur `1`.
3. Dashboard : trafic et latence visibles après quelques requêtes.
4. Explore/Loki : `{service=~"api|assistant-api|django"}`.
5. Alertmanager : aucune alerte active en état nominal.

## 11. Test contrôlé d'une alerte

Sur une stack dédiée, sans données de production :

```bash
sh docker/test_observability.sh --demo-django-outage
```

Le script arrête Django pendant 150 secondes et garantit son redémarrage par un
trap. Observer `up{job="django"}=0`, puis `ServiceUnavailable` après deux minutes,
et enfin la résolution. Cette démonstration ne doit pas être exécutée sur une
stack partagée.

[PREUVE À FOURNIR — E5-P01]
Description : état nominal des conteneurs.
Procédure pour obtenir la capture : exécuter `docker compose -f docker/compose.yaml ps`.
Éléments qui doivent être visibles : services UP/healthy, sans valeurs d'environnement.

[PREUVE À FOURNIR — E5-P02]
Description : cibles Prometheus nominales.
Procédure pour obtenir la capture : ouvrir Prometheus > Status > Targets.
Éléments qui doivent être visibles : les quatre jobs et l'état UP.

[PREUVE À FOURNIR — E5-P03]
Description : dashboard nominal.
Procédure pour obtenir la capture : ouvrir le dashboard provisionné après quelques requêtes.
Éléments qui doivent être visibles : disponibilité à 1, trafic, latence et période sélectionnée.

[PREUVE À FOURNIR — E5-P04]
Description : alerte contrôlée.
Procédure pour obtenir la capture : lancer la démonstration Django dédiée et ouvrir Alertmanager après deux minutes.
Éléments qui doivent être visibles : `ServiceUnavailable`, `job=django`, sévérité critical et état actif.

[PREUVE À FOURNIR — E5-P05]
Description : résolution de l'alerte.
Procédure pour obtenir la capture : attendre le redémarrage et un nouveau scrape.
Éléments qui doivent être visibles : Django revenu à 1 et absence/résolution de l'alerte.

## 12. Diagnostic et boucle d'amélioration MLOps

Partir de l'alerte, vérifier liveness/readiness, filtrer les métriques par service
et statut, puis rechercher le même request ID dans Loki. Pour RAG/SQL, comparer
les ratios aux versions de prompt, modèle, corpus et pipeline. Les tendances de
rejets, résultats vides et évaluations servent à prioriser un correctif, ajouter
un test, versionner le traitement et contrôler le retour au nominal.

## 13. Limites

- notification distante et historique de réception : **NON PROUVÉS À CE STADE** ;
- persistance des métriques applicatives après redémarrage : absente ;
- authentification Loki interne : absente, acceptable uniquement en réseau local ;
- disponibilité de Streamlit : non collectée ;
- exécution locale réussie de la recette : **NON PROUVÉE À CE STADE**.
