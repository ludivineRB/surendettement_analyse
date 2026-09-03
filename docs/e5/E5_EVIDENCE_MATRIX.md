# E5 — Matrice des preuves C20/C21

Référence auditée : `main` à `cf6b525`. Les numéros de ligne correspondent à
cette révision avant ajout du présent dossier.

## C20

| Critère | Preuve | Emplacement/commit | Type | Statut |
|---|---|---|---|---|
| Liste des métriques | Tableau et appels d'instrumentation | `C20_MONITORING.md` §4 ; `app/main.py:23-40` ; `assistant_api/main.py:48-80` | documentation/code | couvert |
| Métriques RAG/SQL | Compteurs et durées | `assistant_api/repository.py:103-108` ; `assistant_api/sql_service.py:152-178` | code | couvert |
| Collecte | Quatre jobs, scrape 15 s | `docker/monitoring/prometheus.yml:1-28` | configuration | couvert |
| Seuils à risque | Sept règles documentées | `docker/monitoring/alerts.yml:1-62` ; `C20_MONITORING.md` §6 | configuration/documentation | couvert |
| Validation des alertes | Sept scénarios `promtool` | `docker/monitoring/alerts.test.yml:6-106` | test | couvert |
| Justification des outils | Raisons et limites de chaque composant | `C20_MONITORING.md` §3 | documentation | couvert |
| Installation locale | Variables, Compose et recette | `C20_MONITORING.md` §9 ; `docker/compose.yaml` | documentation/configuration | couvert |
| Outils fonctionnels localement | Recette automatisée présente | `docker/test_observability.sh` | test | partiel — stack complète à capturer |
| Dashboard | Sept panneaux provisionnés | `docker/monitoring/grafana/dashboards/overview.json` | configuration | couvert |
| Alertmanager | Routage et temporisations | `docker/monitoring/alertmanager.yml:1-11` | configuration | couvert localement |
| Notification opérationnelle | Polling, déduplication, notification Linux | `src/local_alert_notifier.py:22-67` ; tests dédiés | code/test | partiel — capture réelle requise |
| Logs structurés | JSON horodaté | `web/security/logging.py` ; `app/main.py:38-40` ; `assistant_api/main.py:68-80` | code | couvert |
| Correlation ID | Création/validation et réponse HTTP | `app/main.py:25-41` ; `assistant_api/main.py:50-81` ; `web/security/middleware.py:25-32` | code | couvert |
| Minimisation des données | Aucun corps/header/query ; suppression actor ID | `web/security/middleware.py` ; `web/security/logging.py` | code/test | couvert |
| Masquage des secrets | Redaction message et exception | `web/security/logging.py` ; `web/security/tests.py` | code/test | couvert |
| Rétention des logs | 360 heures | `docker/monitoring/loki.yml:27-33` | configuration | couvert |
| Collecte des logs | Découverte Docker et pipeline JSON | `docker/monitoring/promtail.yml:10-27` | configuration | couvert |
| Health/readiness | Probes des services et dépendances | `docker/compose.yaml:10-14,113-122,156-165,209-218` | configuration/code | couvert |
| Runbook incident | Triage par santé, logs, DB et composant | `models/LOT-16-RUNBOOK.md` | documentation | couvert |
| Boucle MLOps | Fraîcheur, intégrité, pipelines, RAG/SQL | `src/observability.py` ; `src/observability_thresholds.py` ; `C20_MONITORING.md` §12 | code/documentation | couvert |
| Démonstration nominale | Services et dashboard | E5-P01 à E5-P03 | capture à réaliser | manquant |
| Démonstration alerte | FIRING puis résolution | E5-P04 et E5-P05 | capture à réaliser | manquant |
| Canal distant | Aucun receiver email/Slack/Teams | `docker/monitoring/alertmanager.yml:8-11` | configuration | manquant, hors périmètre local |

Estimation documentaire et technique C20 : **88 % après les présents changements**.
Cette estimation ne vaut pas validation RNCP et reste conditionnée aux preuves
d'exécution E5-P01 à E5-P05.

## C21

| Critère | Preuve | Emplacement/commit | Type | Statut |
|---|---|---|---|---|
| Incident réel | Correctif explicitement versionné | `380c5a9` | Git | couvert |
| PR/merge | Merge GitHub #43 | `bf04101` | Git | couvert |
| Comportement attendu/observé | SQL valide/renseigné contre rejet ou vide | `C21_INCIDENT.md` §2 | documentation/diff | couvert |
| Cause racine | Absence de correction bornée et prompt incomplet | diff `380c5a9^..380c5a9` | Git/code | couvert |
| Reproduction avant correction | Scénario déterministe sur le parent | `C21_INCIDENT.md` §6 ; E5-P06 | test/capture à réaliser | partiel |
| Diagnostic | Exceptions normalisées, audit, métriques, logs | `assistant_api/sql_service.py:138-166` ; `C21_INCIDENT.md` §4-7 | code/documentation | couvert |
| Lien monitoring | `assistant_sql_executions_total` et alerte >25 % | `assistant_api/sql_service.py:152-156` ; `alerts.yml:47-55` | code/configuration | couvert techniquement |
| Détection historique | Aucun artefact d'alerte retrouvé | — | preuve absente | NON PROUVÉ À CE STADE |
| Correction | Seconde tentative et contexte de rejet | `assistant_api/sql_service.py:117-145` ; `sql_generation.py` ; `380c5a9` | code/Git | couvert |
| Test SQL invalide | Correction au second essai | `tests/test_sql_service.py:27-70` | test | couvert |
| Test résultat vide | Seconde tentative bornée | `tests/test_sql_service.py:73-116` | test | couvert |
| Non-régression exécutée | 30 tests observabilité/SQL et 3 tests Django réussis ; 154 historiques | exécution Docker ; `app/reports/ci/pytest.xml` | test actuel/historique | partiel — Assistant API bloqué par `httpx2` absent |
| Retour au fonctionnement actuel | Tests SQL ciblés réussis | exécution Docker ; E5-P08 | test/capture à réaliser | partiel |
| Preuve GitHub | Commit, PR et checks | E5-P09 et E5-P10 | capture à réaliser | manquant |
| Mesures préventives | Tests, limite de deux essais, validation read-only, métriques | `C21_INCIDENT.md` §10 | code/documentation | couvert |

Estimation documentaire et technique C21 : **86 % après les présents changements**.
Elle atteindra un niveau défendable uniquement après reproduction avant/après et
capture d'une exécution actuelle réussie.

## Registre minimal des captures

| ID | Capture | Utilité jury |
|---|---|---|
| E5-P01 | `docker compose ps` nominal | prouve l'installation locale |
| E5-P02 | Prometheus Targets | prouve la collecte |
| E5-P03 | Dashboard nominal | prouve la visualisation |
| E5-P04 | Alertmanager FIRING | prouve l'alerte opérationnelle |
| E5-P05 | Retour à la normale | prouve la résolution |
| E5-P06 | Test/comportement avant correctif | prouve la reproduction C21 |
| E5-P07 | Métrique et logs corrélés | relie C20 et C21 |
| E5-P08 | Tests après correctif | prouve la correction/non-régression |
| E5-P09 | Commit et PR #43 | prouve la version Git |
| E5-P10 | Checks CI verts | prouve la validation automatisée |

Une capture séparée de la page d'erreur applicative n'est utile que si elle ne
contient aucune question ou donnée personnelle. Les séries Prometheus brutes
n'ont pas besoin d'une capture supplémentaire si E5-P03 et E5-P07 sont lisibles.
