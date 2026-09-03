# C17 — Audit de réalisation de l’application

## 1. Objet

Ce document évalue la réalisation effective de l’application d’analyse du surendettement au regard de la compétence C17 du RNCP37827. Il compare le code, les tests et les flux présents dans `main` aux spécifications fonctionnelles C14 et techniques C15.

L’audit distingue ce qui est conforme aux spécifications, partiellement démontré, non démontré ou en écart. Il ne constitue ni une certification OWASP, ni un audit RGAA, ni une homologation de sécurité. Il ne modifie aucun code.

Référence du code audité : branche `main`, commit `41c0ef1bd532c8caed3e2b795932740f0227ccf3`.

## 2. Références fonctionnelles et techniques

| Référence | Usage dans l’audit | Fichier |
|---|---|---|
| Spécifications fonctionnelles C14 | User stories, comportements, rôles et critères d’acceptation | `docs/e4/C14_SPECIFICATIONS_FONCTIONNELLES.md` |
| Conception technique C15 | Architecture, flux, stack, sécurité et POC attendu | `docs/e4/C15_CONCEPTION_TECHNIQUE_ET_FAISABILITE.md` |
| Conduite de projet C16 | Historique, validations et gestion des corrections | `docs/e4/C16_CONDUITE_DE_PROJET.md` |
| Routes Django | Navigation réellement exposée | `web/config/urls.py`, `web/accounts/urls.py`, `web/dashboard/urls.py`, `web/assistant/urls.py` |
| Réalisation web | Vues, formulaires, templates et scripts | `web/accounts/`, `web/dashboard/`, `web/assistant/`, `web/templates/`, `web/static/` |
| Services | API analytique et Assistant API | `app/`, `assistant_api/` |
| Données | Modèles, migrations, vues et documentation PostgreSQL | `src/storage/`, `web/assistant/migrations/`, `assistant_api/migrations.py`, `database-doc/` |
| Validation | Tests, CI, audits et benchmarks | `tests/`, `app/tests/`, `web/`, `docker/run_ci.sh`, `.github/workflows/ci.yml` |

Échelle utilisée :

- **conforme** : comportement implémenté et preuve de test adaptée ;
- **partiel** : implémentation présente mais preuve incomplète ou condition externe ;
- **non démontré** : aucune preuve suffisante dans le dépôt ;
- **écart** : comportement incompatible, ambigu ou insuffisamment maîtrisé par rapport aux spécifications.

## 3. Conformité interface et navigation

### 3.1 Navigation générale

La configuration racine expose l’accueil, la confidentialité, l’administration Django, les comptes, le dashboard et les assistants. Le template de base adapte la navigation selon l’authentification et le statut superuser. Les pages métier sont protégées dans les vues et non uniquement masquées dans l’interface.

Les retours d’erreur principaux sont prévus : identifiants invalides, indisponibilité analytique, indisponibilité Assistant, état vide du dashboard, refus/clarification de l’Assistant et erreurs qualité. Les messages Django sont rendus dans une zone `aria-live`.

### 3.2 Matrice des user stories C14

| User story | Interface attendue | Implémentation réelle | Test | Statut |
|---|---|---|---|---|
| US-01 — Demander puis obtenir un accès | Inscription, confirmation, approbation et rôle | Formulaire public ; compte inactif ; écran superuser d’approbation | `web/accounts/tests.py` : inscription, rôle, activation et refus non-superuser | Conforme |
| US-02 — Se connecter et se déconnecter | Login, erreur, redirection dashboard, logout POST | Vues Django d’authentification, template d’erreur et formulaire de déconnexion CSRF | `web/dashboard/tests.py` : redirection anonyme et login | Partiel : déconnexion non couverte par un test dédié |
| US-03 — Consulter et filtrer le dashboard | Filtres et restitution score/facteurs/séries | Formulaire validé, clients API et états résultat/vide/erreur | `web/dashboard/tests.py`, `web/analytics/tests.py` | Conforme au niveau serveur ; rendu visuel manuel |
| US-04 — Explorer carte et tendance | Contrôles, sélection souris/clavier, statut et graphique | Carte SVG, appels `fetch`, touches Entrée/Espace, courbe et messages | Aucun test navigateur JavaScript identifié | Partiel |
| US-05 — Méthodologie et qualité | Méthodologie viewer ; qualité superuser | Deux vues distinctes et alertes de service | `web/dashboard/tests.py` : permissions et qualité superuser | Conforme à C14 |
| US-06 — Assistant analytique avec sources | Question, réponse, sources, références et refus | Interface conversation, appel API, persistance des citations et erreurs sûres | `web/assistant/test_views.py`, `web/assistant/test_client.py`, `tests/test_assistant_api.py` | Conforme par composants ; parcours réel avec LLM à recetter |
| US-07 — Retrouver ses conversations | Liste personnelle et historique séparé par type | 20 conversations récentes, filtrage propriétaire/type, ordre des messages | `web/assistant/test_views.py`, `web/assistant/test_retention.py` | Conforme |
| US-08 — Assistant SQL read-only | Accès analyste, SQL, résultat, clarification/refus | Vue protégée, réponse et SQL persistés, validation/exécution séparées | `web/assistant/test_views.py`, `tests/test_sql_validation.py`, `tests/test_sql_executor.py` | Conforme par composants ; base read-only réelle à vérifier |
| US-09 — Évaluer une réponse | Boutons utile/inutile et retour conversation | POST, contrôle propriétaire/message assistant et persistance | `web/assistant/test_views.py` | Conforme |
| US-10 — Administrer les comptes | Approbation administrator ; modification/suppression superuser avec garde-fous | Permission `manage_application` pour les demandes ; opérations sensibles maintenues au superuser | `web/accounts/tests.py`, `web/accounts/test_privacy.py` | Conforme |

### 3.3 Limites de preuve d’interface

- Aucun test de bout en bout dans un navigateur réel n’a été identifié.
- La carte, le focus, les raccourcis clavier, les graphiques et les états dynamiques sont à recetter manuellement.
- La synthèse cartographique construit ses éléments avec `createElement`, affecte les données externes avec `textContent`, puis utilise `replaceChildren`.
- Aucune campagne multi-navigateurs ni mesure de performance front n’est présente.

**Conclusion interface : conforme sous réserve d’une recette navigateur**, le puits DOM dynamique identifié ayant été supprimé.

## 4. Conformité des composants métier

| Composant | Spécification | Implémentation | Test | Statut |
|---|---|---|---|---|
| Authentification | Session et accès réservé | Middleware/session Django, LoginView, décorateurs | `web/dashboard/tests.py` | Conforme |
| Comptes | Inscription inactive, approbation et gestion | Formulaires, services et vues dédiées | `web/accounts/tests.py` | Conforme |
| Rôles | Viewer, analyst, administrator | Groupes et permissions créés par migration ; `manage_application` appliquée à l’approbation | Tests de rôles et d’administrator dans `web/accounts/tests.py` | Conforme |
| Dashboard | Score territorial, couverture et erreurs | Vue orchestrant modèles, scores, séries, facteurs et observabilité | `web/dashboard/tests.py` | Conforme par composants |
| Filtres | Niveau, territoire, période et versions | `DashboardFilterForm`, valeurs par défaut et paramètres API | `web/analytics/tests.py` | Conforme |
| Scores | Modèles et scores territoriaux | Routes FastAPI, ORM et schémas | `app/tests/test_risk_score.py`, `app/tests/views/test_analytics_api.py` | Conforme |
| Facteurs | Contributions explicatives | Route dédiée et affichage tabulaire | Tests API/bridge et contrats web | Conforme |
| Séries temporelles | Évolution par territoire | Endpoint et client avec échappement de chemin | `web/analytics/tests.py::test_series_escapes_path_and_validates_nested_scores` | Conforme |
| Assistant analytique | Réponse fondée, structurée ou hybride | Routage, orchestration, corpus et génération séparés | `tests/test_assistant_orchestration.py`, `tests/test_assistant_api.py` | Conforme hors disponibilité externe |
| Conversations | Historique privé par utilisateur/type | Modèles Django, filtre propriétaire et messages ordonnés | `web/assistant/test_views.py` | Conforme |
| Citations | Sources et références de données distinctes | Contrat Pydantic, génération et persistance JSON | `tests/test_assistant_generation.py`, `web/assistant/test_views.py` | Conforme |
| Feedback | Utile/inutile sur réponse possédée | Valeurs bornées et contrôle propriétaire | `web/assistant/test_views.py` | Conforme |
| Assistant SQL | Génération, validation, exécution et restitution | Modules SQL dédiés et route mode `sql` | Tests SQL et benchmark | Conforme par composants |
| Validation SQL | Une lecture bornée sur vues autorisées | AST SQLGlot, colonnes/fonctions/vues et limites | `tests/test_sql_validation.py` | Conforme aux spécifications auditées |
| Exécution read-only | `EXPLAIN`, seuils, timeout et rollback | Transaction `READ ONLY`, plan contrôlé, rollback `finally` | `tests/test_sql_executor.py` | Conforme ; privilèges réels du compte à vérifier en environnement |
| Audit SQL | Acceptations et refus persistés | Table `assistant.sql_executions`, enregistrement borné | `tests/test_sql_audit.py`, `tests/test_sql_service.py` | Conforme |
| RAG actif | Corpus approuvé, versionné et traçable | `assistant.corpus_chunks` et registre contrôlé | `tests/test_assistant_corpus.py`, `tests/test_assistant_repository.py` | Conforme ; contenu réel dépend de l’indexation |

Les tests démontrent les composants avec doubles, fixtures ou PostgreSQL jetable selon les cas. Ils ne démontrent pas à eux seuls qu’une instance complète, avec données et fournisseur IA réel, est disponible au moment de la soutenance.

**Conclusion métier : conforme par composants, partiellement démontré de bout en bout.**

## 5. Droits d’accès

### 5.1 Permissions définies

La migration `web/accounts/migrations/0001_initial_roles.py` crée :

- `view_dashboard` pour `viewer`, `analyst` et `administrator` ;
- `use_analytics` pour `analyst` et `administrator` ;
- `manage_application` uniquement pour `administrator`.

`web/accounts/services.py` garantit qu’un compte ne conserve qu’un seul de ces trois groupes lors d’une attribution par l’application.

### 5.2 Contrôles réellement appliqués

| Fonction | viewer | analyst | administrator | superuser | Implémentation réelle | Conforme ? |
|---|---:|---:|---:|---:|---|---|
| Dashboard | Oui | Oui | Oui | Oui par superuser | `login_required` + `accounts.view_dashboard` | Oui |
| Méthodologie | Oui | Oui | Oui | Oui | `login_required` + `accounts.view_dashboard` | Oui |
| Carte et indicateurs | Oui | Oui | Oui | Oui | Routes GET avec `accounts.view_dashboard` | Oui |
| Assistant information | Oui | Oui | Oui | Oui | `login_required` + `accounts.view_dashboard` | Oui |
| Assistant SQL | Non | Oui | Oui | Oui | `login_required` + `accounts.use_analytics` | Oui |
| Feedback sur sa réponse | Oui si conversation accessible | Oui | Oui | Oui | `login_required`, POST, propriétaire et rôle assistant contrôlés par requête | Oui |
| Approbation des demandes | Non | Non | Oui | Oui | `accounts.manage_application` ; liste des comptes existants masquée hors superuser | Oui |
| Modification/suppression des comptes | Non | Non | Non | Oui | Contrôle `is_superuser` conservé pour empêcher l’élévation technique | Oui, séparation volontaire |
| Page qualité | Non | Non | Non | Oui | Contrôle `is_superuser`, testé aussi avec un administrator | Oui, fonction technique |
| Administration Django | Non | Non | Non sauf attributs Django séparés | Oui / staff autorisé selon Django | Contrôle Django `is_staff`/permissions | Cohérent avec Django, distinct du rôle applicatif |

Un superuser Django bénéficie normalement des permissions sans appartenir à un groupe. Les colonnes ci-dessus décrivent donc les capacités effectives, pas seulement l’appartenance aux groupes.

### 5.3 Tests d’accès

- dashboard anonyme redirigé, viewer accepté et compte sans rôle refusé : `web/dashboard/tests.py` ;
- méthodologie protégée et page qualité réservée au superuser : `web/dashboard/tests.py` ;
- viewer refusé sur SQL, analyst accepté et conversation d’autrui inaccessible : `web/assistant/test_views.py` ;
- gestion des comptes refusée au non-superuser et garde-fous du dernier superuser : `web/accounts/tests.py`.

### 5.4 Conclusion sur `administrator` / `superuser`

L’écart a été corrigé sans donner accès aux attributs techniques. `manage_application` autorise désormais la consultation et l’approbation des demandes. Les vues d’édition/suppression restent superuser, car leur formulaire expose notamment `is_staff` et `is_superuser`. La page qualité et l’administration Django restent également techniques.

**Classement après correction : conforme.** Les tests prouvent qu’un administrator approuve une demande, ne voit pas les liens sensibles et reçoit un refus sur édition, suppression et qualité.

## 6. Intégration des flux de données

| Flux | Spécification C15 | Implémentation | Contrôle | Statut |
|---|---|---|---|---|
| Dashboard | Django → API analytique → PostgreSQL → Django | `DashboardFilterForm` → `AnalyticsClient` → routes FastAPI/ORM → contrats web | Permission, validation formulaire/réponse, jeton interne et timeout | Conforme par composants |
| Carte | Navigateur → Django → API analytique ; contours externes → cache → navigateur | `fetch` vers routes Django protégées, client analytique et URL data.gouv.fr fixe | Niveaux autorisés, timeout contours, cache 24 h, erreurs 400/503 | Partiel : JavaScript non testé en navigateur |
| Assistant analytique | Django → Assistant API → orchestration → corpus/API analytique/LLM → Django | `AssistantClient`, routage, repository, client analytique et fournisseur OpenAI | Permission, token interne, Pydantic, corpus approuvé, refus, timeouts | Conforme ; fournisseur réel à recetter |
| Assistant SQL | Django → Assistant API → LLM → validation → DB read-only → audit → Django | Modules `sql_generation`, `sql_validation`, `sql_executor`, `sql_service` | Permission analyst, AST, listes blanches, limites, `EXPLAIN`, rollback et audit | Conforme par composants ; droits DB réels à prouver |
| Authentification | Django → base/session → permission → écran | Middleware Django, backend auth standard, session PostgreSQL et décorateurs | CSRF, compte actif, session et permissions | Conforme |

### Écritures et lectures

- Le dashboard réalise des lectures analytiques ; la carte ajoute une lecture HTTP externe des contours.
- Django écrit comptes, sessions, conversations, messages et feedbacks dans PostgreSQL.
- L’Assistant analytique lit le corpus et les données structurées ; Django persiste la réponse et ses citations.
- L’Assistant SQL lit les vues avec une connexion dédiée ; il écrit seulement l’audit dans `assistant.sql_executions` via une autre frontière de stockage.
- Le rollback SQL est exécuté dans un bloc `finally`.

### Gestion des erreurs

Les clients Django normalisent timeouts, réponses invalides, erreurs HTTP et indisponibilités (`web/analytics/client.py`, `web/assistant/client.py`). L’Assistant normalise les erreurs du fournisseur sans exposer son corps de réponse (`assistant_api/openai_provider.py`). Les contrôles sont testés séparément, mais aucun test automatisé ne traverse les quatre processus réels avec navigateur et fournisseur externe.

**Conclusion flux : partiellement conforme au niveau système, conforme par composants testés.**

## 7. Mesures OWASP

La correspondance est proportionnée au projet et reprend les catégories OWASP Top 10 comme grille de lecture. Le statut « mesures présentes » ne vaut pas conformité ou certification OWASP.

| Risque OWASP | Mesure présente | Preuve | Limite | Statut |
|---|---|---|---|---|
| A01 — Contrôle d’accès défaillant | Sessions, décorateurs, permission `manage_application`, propriété des conversations/messages et token interservice | `web/*/views.py`, `assistant_api/auth.py`, tests web | Administration technique toujours distincte et réservée au superuser | Mesures présentes |
| A02 — Défaillances cryptographiques | Secrets par environnement, comparaison constante du token, cookies sécurisables, HSTS configurable | `web/config/settings.py`, `assistant_api/auth.py`, `docker/compose.yaml` | TLS, HSTS et cookies sécurisés dépendent de la cible non démontrée | Partiel |
| A03 — Injection | ORM/requêtes paramétrées, AST SQLGlot, listes blanches ; données cartographiques affectées avec `textContent` | Code et tests SQL ; `web/static/js/site.js` | Défense SQL dépend aussi des privilèges DB réels | Mesures présentes |
| A04 — Conception non sécurisée | Séparation génération/validation/exécution, refus sans preuve, limites, quotas et séparation administration applicative/technique | `assistant_api/`, `web/security/middleware.py`, vues comptes | Pas de threat model formalisé | Partiel |
| A05 — Mauvaise configuration | Paramètres Django de sécurité, hôtes/origines, debug configurable, ports liés localement, checklist | `web/config/settings.py`, `docker/PRODUCTION_CHECKLIST.md` | Image Django utilise `runserver`; configuration cible non prouvée | Partiel |
| A06 — Composants vulnérables | Versions fixées et `pip-audit` en CI | fichiers `requirements*`, `docker/run_ci.sh` | Résultat courant de l’audit dépend de chaque exécution ; images tierces à surveiller | Mesures présentes |
| A07 — Authentification défaillante | Validateurs de mot de passe, sessions Django, rate limit de connexion, compte inactif avant approbation | `web/config/settings.py`, `web/security/middleware.py`, `web/accounts/forms.py` | Pas de MFA, verrouillage durable ou test de session complet démontré | Partiel adapté au POC |
| A08 — Intégrité logicielle et des données | Git, CI, images taguées au SHA, corpus approuvé et empreintes | `.github/workflows/ci.yml`, `assistant_api/corpus.py`, `assistant_api/ingestion.py` | Pas de signature d’image/SBOM ni protection GitHub prouvée dans le dépôt | Partiel |
| A09 — Journalisation et supervision | IDs de requête, logs JSON, métriques, alertes, audits SQL et tests de panne | `web/security/`, `assistant_api/monitoring.py`, `docker/monitoring/` | Exploitation et alertes réelles non démontrées sur une cible | Mesures présentes, validation externe requise |
| A10 — SSRF | URLs analytiques configurées, URL GeoJSON fixe, registre de corpus borné à des hôtes officiels | clients HTTP, `web/dashboard/views.py`, `assistant_api/corpus.py` | Toute nouvelle source ou URL configurable doit conserver une liste d’autorisation | Mesures présentes |

### Observation DOM

Le puits DOM identifié a été supprimé. `web/static/js/site.js` crée désormais les mêmes éléments et classes avec `document.createElement`, affecte les libellés variables par `textContent` et remplace le contenu avec `replaceChildren`. Un test statique ciblé empêche la réintroduction de l’affectation dynamique précédente.

## 8. Éco-conception

Le projet ne mesure pas son empreinte environnementale et ne peut pas être déclaré « éco-conçu ». Les pratiques suivantes sont néanmoins réellement implémentées.

| Bonne pratique | Implémentation | Preuve | Statut |
|---|---|---|---|
| Images de base allégées | Python slim et PostgreSQL Alpine | `docker/Dockerfile`, `docker/compose.yaml` | Conforme à C15 |
| Installation sans cache pip | `pip install --no-cache-dir` | `docker/Dockerfile` | Conforme |
| Requêtes SQL bornées | 200 lignes, trois jointures, coût/volume et timeout limités | `assistant_api/sql_validation.py`, `assistant_api/sql_executor.py` | Conforme |
| Appels HTTP bornés | Timeouts clients analytique, Assistant, OpenAI et contours | clients HTTP et vues | Conforme |
| Cache des contours | Cache Django pendant 86 400 secondes | `web/dashboard/views.py` | Conforme |
| CI obsolète annulée | `cancel-in-progress: true` par référence | `.github/workflows/ci.yml` | Conforme |
| Artefacts à rétention bornée | Rapports/images conservés 14 jours | `.github/workflows/ci.yml` | Conforme |
| Métriques et logs bornés | Rétention Prometheus 15 jours, rotation JSON 10 Mo × 5 | `docker/compose.yaml` | Conforme |
| Résultats Assistant bornés | Contrats, limites de recherche et maximum de lignes retournées | `assistant_api/schemas.py`, `assistant_api/orchestration.py` | Conforme |
| Démarrage ciblé des services | Profils uniquement pour le conteneur CI | `docker/compose.yaml` | Partiel : supervision et autres services ne sont pas profilés |

Améliorations non bloquantes : mesurer temps CPU, taille des images, volume réseau et tokens ; séparer les dépendances des images ; ajouter des profils Compose ; fixer des objectifs de consommation fondés sur des mesures.

## 9. Couverture de tests

| Fonction | Type de test | Fichier | Cas couverts | Statut |
|---|---|---|---|---|
| Comptes | Django unitaire/intégration | `web/accounts/tests.py` | Inscription inactive, approbation, rôles, édition, suppression et dernier superuser | Couvert |
| Confidentialité compte | Django/service | `web/accounts/test_privacy.py` | Simulation et suppression conversations/utilisateur | Couvert |
| Permissions dashboard | Django | `web/dashboard/tests.py` | Anonyme, viewer, sans rôle, méthodologie et qualité | Couvert |
| Dashboard | Django avec client simulé | `web/dashboard/tests.py` | Accès et API indisponible | Partiel : combinaisons de filtres/rendu non exhaustives |
| Client analytique | Unitaire HTTP/contrat | `web/analytics/tests.py` | Filtres, échappement, timeout, HTTP, JSON et schéma | Couvert |
| API analytique | FastAPI/intégration | `app/tests/views/test_analytics_api.py`, `tests/test_data_api.py` | Endpoints, sécurité et contrats | Couvert |
| Scores | Unitaire/intégration | `app/tests/test_risk_score.py`, `app/tests/test_model_comparison.py` | Calculs, couverture et comparaison | Couvert |
| Assistant web | Django/client | `web/assistant/test_views.py`, `web/assistant/test_client.py` | Accès, propriété, persistance, rôles, feedback et erreurs | Couvert |
| Assistant API | FastAPI | `tests/test_assistant_api.py` | Authentification, validation, refus, citations, SQL et erreurs | Couvert |
| Orchestration | Unitaire | `tests/test_assistant_orchestration.py` | Documents, hybride et intention structurée | Couvert |
| Corpus/citations | Unitaire/repository | `tests/test_assistant_corpus.py`, `tests/test_assistant_repository.py`, `tests/test_assistant_generation.py` | Hôtes, recherche, preuves et refus | Couvert |
| Validation SQL | Unitaire adversarial | `tests/test_sql_validation.py` | Écriture, vues, colonnes, fonctions, jointures et limites | Couvert |
| Exécution SQL | Unitaire avec connexion simulée | `tests/test_sql_executor.py` | Validation avant connexion, read-only, plan, rollback | Couvert ; privilèges réels à tester |
| Audit SQL | Unitaire/intégration | `tests/test_sql_audit.py`, `tests/test_sql_service.py` | Acceptation, refus et panne de l’audit | Couvert |
| Benchmark Text-to-SQL | Hors ligne et PostgreSQL jetable | `tests/test_text_to_sql_benchmark.py`, `benchmark/` | Dataset, cas adversariaux et oracles | Couvert |
| Migrations PostgreSQL | Intégration | `app/tests/test_postgres_migration.py`, scripts Docker | Schéma, données et idempotence | Couvert sous configuration de test |
| Sécurité middleware | Django | `web/security/tests.py` | ID de requête et rate limit général | Partiel : scénarios login/quota à étendre |
| Smoke test | Conteneur CI | `.github/workflows/ci.yml` | Démarrage et `/health` de l’Assistant | Couvert pour l’image Assistant |
| Carte et JavaScript | Navigateur | Aucun fichier identifié | Interactions souris/clavier, erreurs `fetch`, DOM | Non démontré |
| Parcours E2E complet | Système/navigateur | Aucun fichier identifié | Django + deux APIs + PostgreSQL + OpenAI | Non démontré |
| Accessibilité | Audit automatisé/manuel | Aucun rapport complet identifié | RGAA/WCAG | Non démontré |

### 9.1 Validation des corrections C17

| Suite | Avant modification | Après permissions | Après permissions + DOM |
|---|---:|---:|---:|
| `web.accounts.tests`, `web.accounts.test_privacy`, `web.dashboard.tests`, `web.assistant.test_views` | 28/28 réussis | 30/30 réussis | 32/32 réussis |
| Suite Django `web` | Non exécutée avant modification | Non exécutée à cette étape | 55/55 réussis |

Aucun test qui réussissait avant la modification n’échoue après celle-ci. Les quatre tests ajoutés couvrent l’approbation administrator, le maintien des vues sensibles au superuser, la qualité refusée à l’administrator et l’absence du puits DOM dynamique.

Le minimum RNCP — composants métier et gestion des accès — est couvert par plusieurs familles de tests. Les lacunes concernent surtout l’intégration complète, le navigateur et l’environnement réel.

## 10. Versionnement des sources

| Élément | Preuve | Statut |
|---|---|---|
| Dépôt Git | Historique de `main` du 8 avril au 3 septembre 2026 | Démontré |
| Branche de référence | `main` au SHA audité | Démontré |
| Lots et intégrations | Branches dédiées et commits de fusion de pull requests | Démontré par Git |
| CI sur les sources | Déclencheurs `push`, `pull_request`, `workflow_dispatch` | Démontré dans `.github/workflows/ci.yml` |
| Dépendances | Fichiers `requirements.txt`, `web/requirements.txt`, `assistant_api/requirements.txt`, `requirements-ci.txt` | Versionnées |
| Infrastructure | Dockerfile, Compose, monitoring et scripts | Versionnés dans `docker/` |
| Migrations | Django, stockage et Assistant API | Versionnées |
| Corpus/benchmarks | Registre et datasets d’évaluation | Versionnés |
| Secrets | `.env*` exclus ; valeurs réelles non requises dans les fichiers applicatifs | Mesure présente ; historique complet à scanner séparément |

La CI contient des valeurs explicitement éphémères destinées aux tests, pas des secrets de production. L’audit du fichier courant ne remplace pas une recherche de secrets sur l’intégralité de l’historique et les paramètres GitHub.

## 11. Écarts identifiés

| ID | Écart | Impact C17 | Gravité | Correction recommandée |
|---|---|---|---|---|
| C17-E01 | Permission `manage_application` initialement inutilisée | Matrice des droits incohérente | Corrigée | Permission appliquée à l’approbation ; opérations techniques maintenues au superuser |
| C17-E02 | `summary.innerHTML` interpolait des données de catalogue/GeoJSON | Surface d’injection DOM | Corrigée | Nœuds créés explicitement et valeurs affectées par `textContent` |
| C17-E03 | Aucun test navigateur de la carte et de la navigation dynamique | Comportements d’interface non démontrés automatiquement | Modérée | Ajouter quelques tests E2E ciblés clavier, chargement, erreur et sélection |
| C17-E04 | Aucun test E2E traversant Django, APIs et PostgreSQL réels | Flux global C15 seulement démontré par composants | Modérée | Ajouter un smoke test intégré Compose sans fournisseur externe, puis une recette IA manuelle |
| C17-E05 | Droits effectifs du compte `analytics_readonly` non prouvés dans l’environnement de soutenance | La sécurité SQL dépend d’une configuration externe | Majeure pour déploiement, modérée pour code | Exécuter le test de privilèges et capturer son résultat sur la cible |
| C17-E06 | Génération OpenAI réelle absente de la CI | Qualité/disponibilité IA non garanties par l’automatisation | Modérée | Conserver CI hors ligne et exécuter une recette réelle contrôlée avant démonstration |
| C17-E07 | Image Django lancée avec `runserver` | Configuration non adaptée à une production publique | Majeure pour production, non bloquante pour POC local | Ajouter ultérieurement un serveur WSGI et valider TLS/proxy |
| C17-E08 | Aucun audit complet RGAA, OWASP ou secret historique | Impossible de revendiquer une conformité globale | Modérée | Réaliser audits proportionnés et conserver leurs rapports |
| C17-E09 | Aucune mesure environnementale chiffrée | Éco-conception seulement qualitative | Mineure pour le POC | Définir quelques indicateurs mesurables |
| C17-E10 | Déconnexion et certains scénarios de quota/rate limit sans test dédié identifié | Couverture d’accès/erreur perfectible | Mineure | Ajouter des tests ciblés après décision de correction |

Aucun écart ne justifie de modifier le code dans cette étape documentaire.

## 12. Conclusion de conformité

Les composants métier principaux, la gestion des accès usuels, les flux internes, la validation SQL et le versionnement sont effectivement réalisés et largement couverts par des tests. Le dépôt montre aussi plusieurs mesures concrètes vis-à-vis de l’OWASP Top 10 et de la sobriété des traitements.

La permission d’administration applicative et le puits DOM identifiés ont été corrigés et couverts par des tests. Les réserves restantes portent sur les parcours navigateur/système non testés de bout en bout et sur plusieurs garanties dépendant de l’environnement réel.

**Statut global : C17 conforme sous réserve de corrections mineures.**

La matrice d’autorisation est désormais cohérente : administration des demandes pour `administrator`, administration technique pour le superuser. Les réserves majeures concernent une éventuelle mise en production ; elles n’empêchent pas une démonstration locale contrôlée si les preuves manuelles sont réalisées.

## 13. Corrections recommandées

### A. Corrections nécessaires avant rédaction finale E4

1. Vérifier sur l’environnement de démonstration les privilèges du compte SQL read-only, les healthchecks et les refus SQL.
2. Réaliser la recette manuelle navigateur de la carte et de la navigation.
3. Présenter les limites de production séparément de la conformité du POC local.

### B. Améliorations non bloquantes

- ajouter des tests navigateur ciblés et un smoke test Compose intégré ;
- tester explicitement déconnexion, limites de connexion et quotas Assistant ;
- produire un rapport automatisé d’accessibilité ;
- analyser les secrets sur l’historique et générer un SBOM ;
- mesurer taille des images, temps CPU, réseau et tokens ;
- remplacer `runserver` avant tout déploiement public.

### C. Preuves manuelles à capturer

- comportements visuels, clavier et erreurs de la carte ;
- matrice des rôles avec comptes viewer, analyst, administrator et superuser ;
- résultat réel du compte PostgreSQL read-only ;
- parcours Assistant avec fournisseur configuré ;
- état CI, healthchecks et tests ;
- configuration de sécurité de l’environnement sans afficher les secrets.

## 14. Preuves à capturer

| Capture | Contenu attendu | Critère C17 |
|---|---|---|
| Login | Formulaire, erreur contrôlée et redirection après succès | Interface, authentification et erreurs |
| Dashboard viewer | Score, filtres et navigation protégée | Composants métier et droits |
| Filtres | Changement de territoire/période/version et résultat associé | Conformité fonctionnelle |
| Carte clavier | Focus visible, sélection Entrée/Espace et statut dynamique | Interface et navigation |
| Méthodologie | Limites du score territorial | Respect des spécifications |
| Assistant analytique | Question, réponse, citations et références | Flux IA intégré |
| Refus Assistant | Refus sans preuve ou demande individuelle | Garde-fous métier |
| Assistant SQL analyst | SQL généré et résultat borné | Composant métier SQL |
| Assistant SQL viewer | Accès refusé | Gestion des accès |
| Refus SQL dangereux | Message de refus et absence d’exécution | OWASP/injection |
| Conversations/feedback | Isolation de l’historique et feedback persisté | Métier et accès |
| Administrator sans superuser | Approbation autorisée ; édition, suppression et qualité refusées | Preuve de la séparation applicative/technique |
| Superuser | Gestion des comptes et page qualité | Matrice des droits réelle |
| Privilèges read-only | Test SELECT accepté et écriture refusée | Sécurité SQL externe |
| Tests | Résumé pytest/Django/benchmark | Couverture métier et accès |
| GitHub Actions | Jobs de validation et packaging réussis | Intégration et versionnement |
| Healthchecks | PostgreSQL, API, Assistant et Django au vert | Intégration du POC |

## 15. Matrice RNCP C17

| Critère C17 | Preuve | Statut | Écart restant |
|---|---|---|---|
| 1. Interface et navigation conformes aux spécifications | Routes, vues, templates et matrice US section 3 | Conforme sous réserve de recette | Carte sans test navigateur complet |
| 2. Composants métier conformes | Matrice section 4 et tests associés | Conforme par composants | Parcours complet avec dépendances réelles à recetter |
| 3. Droits d’accès implémentés | Migration des rôles, décorateurs et tests section 5 | Conforme | Séparation administrator/superuser volontaire et testée |
| 4. Flux de données intégrés | Clients, APIs, stockage et contrôles section 6 | Partiel | Pas de test E2E système complet |
| 5. Bonnes pratiques d’éco-conception | Images légères, limites, cache et rétentions section 8 | Mesures présentes | Aucune mesure environnementale chiffrée |
| 6. Recommandations OWASP prises en compte | Analyse proportionnée section 7 | Partiel | Configuration cible, DOM, audits complets et rôle à traiter |
| 7. Tests métier et accès | Matrice détaillée section 9 | Conforme au minimum attendu | Couverture navigateur/intégrée à renforcer |
| 8. Sources versionnées | Git, CI, dépendances, migrations et configuration section 10 | Conforme | Scan historique des secrets à conserver comme contrôle externe |

La décision de correction et son implémentation doivent faire l’objet d’une étape séparée, avec modification minimale des fichiers concernés et ajout des tests adaptés.
