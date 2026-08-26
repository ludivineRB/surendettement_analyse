# Correspondance entre code et tables PostgreSQL

Audit réalisé le 25 août 2026 à partir du code présent et des catalogues de la
base `surendettement_staging`.

## Modèles SQLAlchemy

Source : `src/storage/models.py`. Les 11 tables déclarées existent dans
`public`.

| Classe | Table PostgreSQL | Domaine | État du rattachement |
|---|---|---|---|
| `GeographicRegion` | `public.dim_region` | référentiel | confirmé |
| `ReferencePeriod` | `public.dim_period` | référentiel | confirmé |
| `SurendettementData` | `public.surendettement_data` | stockage historique | confirmé |
| `InclusionSourceDocument` | `public.source_documents` | acquisition | confirmé |
| `InclusionIndicator` | `public.indicators` | indicateurs opérationnels | confirmé |
| `PipelineRun` | `public.pipeline_runs` | orchestration/qualité | confirmé |
| `InclusionObservation` | `public.observations` | observations | confirmé |
| `RiskScoreModel` | `public.risk_score_models` | scoring | confirmé |
| `RiskScoreIndicatorConfig` | `public.risk_score_indicator_configs` | scoring | confirmé |
| `RiskScore` | `public.risk_scores` | scoring | confirmé |
| `RiskScoreDetail` | `public.risk_score_details` | scoring | confirmé |

`Base.metadata.create_all` est appelé par la migration opérationnelle initiale.
Les migrations suivantes sont gérées par le registre maison
`src/storage/schema_migrations.py`, pas par Alembic.

## Modèles Django propres au projet

Source : `web/assistant/models.py`. Django utilise son nommage par défaut.

| Classe | Table PostgreSQL | Migration de création | État |
|---|---|---|---|
| `RagSource` | `public.assistant_ragsource` | `assistant.0001_initial` | confirmé, déprécié le 25/08/2026 |
| `RagDocument` | `public.assistant_ragdocument` | `assistant.0001_initial` | confirmé, déprécié le 25/08/2026 |
| `RagDocumentVersion` | `public.assistant_ragdocumentversion` | `assistant.0001_initial` | confirmé, déprécié le 25/08/2026 |
| `RagChunk` | `public.assistant_ragchunk` | `assistant.0001_initial` | confirmé, déprécié le 25/08/2026 |
| `RagIndexRun` | `public.assistant_ragindexrun` | `assistant.0001_initial` | confirmé, déprécié le 25/08/2026 |
| `Conversation` | `public.assistant_conversation` | `assistant.0003_conversations` | confirmé |
| `ConversationMessage` | `public.assistant_conversationmessage` | `assistant.0003` puis `0004` | confirmé |

`web/accounts/models.py` n'existe pas. L'application utilise les modèles Django
standard `auth.User`, `auth.Group` et `auth.Permission`. La migration
`accounts.0001_initial_roles` ajoute des groupes et permissions, sans créer de
modèle métier supplémentaire.

La migration `assistant.0005_deprecate_legacy_rag_corpus`, appliquée le
26/08/2026, désactive les documents RAG Django et inscrit les cinq tables dans
`schema_deprecations`. Les classes restent présentes uniquement pour compatibilité
et audit ; le remplacement officiel est `assistant.corpus_chunks`.

## Tables Django fournies par le framework

| Famille | Tables |
|---|---|
| Authentification | `auth_user`, `auth_group`, `auth_permission` |
| Jointures | `auth_user_groups`, `auth_user_user_permissions`, `auth_group_permissions` |
| Administration | `django_admin_log`, `django_content_type` |
| Infrastructure | `django_migrations`, `django_session` |

Leur source est Django et ses migrations standard, non un fichier `models.py`
propre au projet.

## Objets créés par SQL ou migration programmatique

### Entrepôt analytique

`src/storage/analytics_db.py` crée ou alimente :

- `dim_department`, `dim_indicator` ;
- `fact_bdf_statinfo`, `fact_insee_macro`, `fact_surendettement` ;
- `pipeline_metadata` ;
- les vues `v_bdf_total_deposits*`, `v_insee_macro_region*` et
  `v_surendettement_*`.

`src/storage/conformed_dimensions.py` ajoute ou harmonise :

- `dim_region`, `dim_period`, `fact_macro_override` ;
- `schema_deprecations` ;
- les vues régionales conformées.

Ces objets n'ont pas de modèles ORM exhaustifs. `dim_region` et `dim_period`
sont toutefois aussi représentées par SQLAlchemy, ce qui crée une responsabilité
partagée entre modèle opérationnel et traitement analytique.

### Publication analytique

`src/storage/schema_migrations.py` crée `public.schema_migrations` et les six
vues `analytics_*`. Ces vues constituent l'interface de lecture autorisée pour
l'API et l'agent SQL.

### Schéma Assistant API

Source retrouvée après élargissement du périmètre :
`assistant_api/migrations.py`. Le module `assistant_api/cli.py` expose les
commandes administratives `migrate` et `index` ; `assistant_api/storage.py`
porte la connexion dédiée.

| Table | Migration source | Accès applicatif |
|---|---|---|
| `assistant.corpus_chunks` | `001_corpus_chunks` | `assistant_api/repository.py` |
| `assistant.sql_executions` | `002_sql_execution_audit` | `assistant_api/repository.py` |
| `assistant.schema_migrations` | créée par `apply_migrations` | `assistant_api/migrations.py` |

Les définitions SQL du dépôt correspondent aux colonnes, contraintes et index
observés dans PostgreSQL. Ces tables n'ont volontairement pas de modèle ORM :
les lectures et écritures utilisent des requêtes SQLAlchemy `text()` dans le
repository de l'Assistant API.

## Rattachement entre Django et l'Assistant API

`web/assistant/views.py` enregistre les conversations dans les tables Django,
puis appelle le service autonome avec `web/assistant/client.py`. Pour les
questions documentaires, `assistant_api/orchestration.py` recherche dans
`assistant.corpus_chunks`. Pour le SQL, l'API écrit l'audit dans
`assistant.sql_executions`.

Le `actor_id` envoyé par Django est `str(request.user.pk)`. Cette référence reste
textuelle afin de découpler les services. Lors d'une suppression de compte,
`web/accounts/services.py` conserve l'audit mais remplace cet identifiant par
`NULL`.

## Synthèse de couverture

| Origine | Tables physiques couvertes |
|---|---:|
| SQLAlchemy projet | 11 |
| Django projet | 7 |
| Django standard et jointures | 10 |
| SQL analytique/programmatique | 9 |
| Assistant API, migrations SQL explicites | 3 |
| **Total** | **40** |
