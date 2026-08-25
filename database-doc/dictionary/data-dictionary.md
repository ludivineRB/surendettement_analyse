# Dictionnaire de données

Généré depuis les catalogues PostgreSQL. Aucune ligne métier n'est lue.
Les exemples sont limités aux défauts déclarés dans le schéma ; sinon
ils sont indiqués « Non extrait » afin de ne pas créer de donnée fictive.

## `assistant.corpus_chunks`

**Type :** table  
**Définition :** Fragments recherchables du corpus de l'Assistant API.  
**Source :** Assistant API  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `chunk_id` | Identifiant de référence vers chunk. | `character(64)` | Oui | PK, Unique (index, composite possible) | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_id` | Identifiant de référence vers source. | `character varying(200)` | Oui | Unique | Assistant API | Non extrait | UNIQUE (source_id, ordinal, source_sha256) | Interne | Actif |
| `source_url` | Champ source url de l'objet documenté. | `text` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_title` | Champ source title de l'objet documenté. | `text` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `publisher` | Champ publisher de l'objet documenté. | `character varying(100)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(100)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `geographic_scope` | Champ geographic scope de l'objet documenté. | `character varying(200)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `section` | Champ section de l'objet documenté. | `text` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `ordinal` | Champ ordinal de l'objet documenté. | `integer` | Oui | Unique | Assistant API | Non extrait | CHECK (ordinal >= 0); UNIQUE (source_id, ordinal, source_sha256) | Interne | Actif |
| `content` | Contenu textuel enregistré. | `text` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `content_sha256` | Champ content sha256 de l'objet documenté. | `character(64)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_sha256` | Champ source sha256 de l'objet documenté. | `character(64)` | Oui | Unique | Assistant API | Non extrait | UNIQUE (source_id, ordinal, source_sha256) | Interne | Actif |
| `is_active` | Indique si l'objet est actif. | `boolean` | Oui | — | Assistant API | `true` | DEFAULT true | Interne | Actif |
| `indexed_at` | Date et heure de indexed. | `timestamp with time zone` | Oui | — | Assistant API | `CURRENT_TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Interne | Actif |
| `search_vector` | Vecteur PostgreSQL utilisé pour la recherche plein texte. | `tsvector` | Non | — | Assistant API | `((setweight(to_tsvector('french'::regconfig, COALESCE(source_title, ''::text)), 'A'::"char") \|\| setweight(to_tsvector('french'::regconfig, COALESCE(section, ''::text)), 'A'::"char")) \|\| setweight(to_tsvector('french'::regconfig, COALESCE(content, ''::text)), 'B'::"char"))` | DEFAULT ((setweight(to_tsvector('french'::regconfig, COALESCE(source_title, ''::text)), 'A'::"char") \|\| setweight(to_tsvector('french'::regconfig, COALESCE(section, ''::text)), 'A'::"char")) \|\| setweight(to_tsvector('french'::regconfig, COALESCE(content, ''::text)), 'B'::"char")) | Interne | Actif |

## `assistant.schema_migrations`

**Type :** table  
**Définition :** Registre technique des migrations appliquées.  
**Source :** Assistant API  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `version` | Champ version de l'objet documenté. | `character varying(64)` | Oui | PK, Unique (index, composite possible) | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `applied_at` | Date et heure de applied. | `timestamp with time zone` | Oui | — | Assistant API | `CURRENT_TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Interne | Actif |

## `assistant.sql_executions`

**Type :** table  
**Définition :** Audit des générations et exécutions de SQL.  
**Source :** Assistant API  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `execution_id` | Identifiant de référence vers execution. | `uuid` | Oui | PK, Unique (index, composite possible) | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `request_id` | Identifiant de référence vers request. | `uuid` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `actor_id` | Identifiant de référence vers actor. | `character varying(128)` | Non | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Potentiellement personnel/sensible | Actif |
| `question` | Champ question de l'objet documenté. | `text` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Potentiellement personnel/sensible | Actif |
| `interpretation_json` | Structure JSON contenant interpretation. | `text` | Oui | — | Assistant API | `'{}'::text` | DEFAULT '{}'::text | Potentiellement personnel/sensible | Actif |
| `schema_version` | Champ schema version de l'objet documenté. | `character varying(64)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `generated_sql` | Instruction SQL générée par l'assistant. | `text` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Potentiellement personnel/sensible | Actif |
| `validation_status` | Champ validation status de l'objet documenté. | `character varying(32)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `validation_error` | Champ validation error de l'objet documenté. | `character varying(512)` | Non | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `duration_ms` | Champ duration ms de l'objet documenté. | `integer` | Non | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `row_count` | Champ row count de l'objet documenté. | `integer` | Non | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `plan_cost` | Champ plan cost de l'objet documenté. | `double precision` | Non | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `prompt_version` | Champ prompt version de l'objet documenté. | `character varying(64)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `model_version` | Champ model version de l'objet documenté. | `character varying(128)` | Oui | — | Assistant API | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `timestamp with time zone` | Oui | — | Assistant API | `CURRENT_TIMESTAMP` | DEFAULT CURRENT_TIMESTAMP | Interne | Actif |

## `public.analytics_macro_regions`

**Type :** vue  
**Définition :** Objet PostgreSQL analytics_macro_regions.  
**Source :** Vue de publication  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `character varying(255)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_code` | Code de indicator. | `text` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_name` | Champ indicator name de l'objet documenté. | `text` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_group` | Champ indicator group de l'objet documenté. | `text` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `aggregation_rule` | Champ aggregation rule de l'objet documenté. | `text` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `value_numeric` | Valeur numérique de l'observation. | `double precision` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.analytics_model_comparisons`

**Type :** vue  
**Définition :** Objet PostgreSQL analytics_model_comparisons.  
**Source :** Vue de publication  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `geographic_level` | Champ geographic level de l'objet documenté. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_code` | Code de geographic. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_name` | Champ geographic name de l'objet documenté. | `character varying(255)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(16)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `model_code` | Code de model. | `character varying(128)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `version_a` | Champ version a de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `version_b` | Champ version b de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `score_a` | Champ score a de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `score_b` | Champ score b de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `score_change` | Champ score change de l'objet documenté. | `numeric` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.analytics_observations`

**Type :** vue  
**Définition :** Objet PostgreSQL analytics_observations.  
**Source :** Vue de publication  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_code` | Code de indicator. | `character varying(128)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_label` | Champ indicator label de l'objet documenté. | `character varying(512)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_level` | Champ geographic level de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_code` | Code de geographic. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_name` | Champ geographic name de l'objet documenté. | `character varying(255)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_code` | Code de region. | `character varying(16)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(7)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `value_numeric` | Valeur numérique de l'observation. | `double precision` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `unit` | Champ unit de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `observation_type` | Champ observation type de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `comparison_period` | Champ comparison period de l'objet documenté. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `variation_numeric` | Champ variation numeric de l'objet documenté. | `double precision` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `variation_unit` | Champ variation unit de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `confidence_score` | Champ confidence score de l'objet documenté. | `double precision` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.analytics_pipeline_status`

**Type :** vue  
**Définition :** Objet PostgreSQL analytics_pipeline_status.  
**Source :** Vue de publication  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `pipeline_name` | Champ pipeline name de l'objet documenté. | `character varying(128)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `status` | État courant selon le cycle de vie de l'objet. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `started_at` | Date et heure de début du traitement. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `finished_at` | Date et heure de fin du traitement. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.analytics_risk_scores`

**Type :** vue  
**Définition :** Objet PostgreSQL analytics_risk_scores.  
**Source :** Vue de publication  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_level` | Champ geographic level de l'objet documenté. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_code` | Code de geographic. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_name` | Champ geographic name de l'objet documenté. | `character varying(255)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(16)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `score` | Champ score de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `risk_level` | Champ risk level de l'objet documenté. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `coverage_ratio` | Champ coverage ratio de l'objet documenté. | `numeric(8,6)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `status` | État courant selon le cycle de vie de l'objet. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `model_code` | Code de model. | `character varying(128)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `model_version` | Champ model version de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `model_is_active` | Champ model is active de l'objet documenté. | `boolean` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `calculated_at` | Date et heure de calculated. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.analytics_score_factors`

**Type :** vue  
**Définition :** Objet PostgreSQL analytics_score_factors.  
**Source :** Vue de publication  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_level` | Champ geographic level de l'objet documenté. | `character varying(32)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_code` | Code de geographic. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `geographic_name` | Champ geographic name de l'objet documenté. | `character varying(255)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(16)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `model_code` | Code de model. | `character varying(128)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `model_version` | Champ model version de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_code` | Code de indicator. | `character varying(128)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `raw_value` | Champ raw value de l'objet documenté. | `numeric(20,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `unit` | Champ unit de l'objet documenté. | `character varying(64)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `normalized_value` | Champ normalized value de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `configured_weight` | Champ configured weight de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `effective_weight` | Champ effective weight de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `contribution` | Champ contribution de l'objet documenté. | `numeric(12,8)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `direction` | Champ direction de l'objet documenté. | `character varying(16)` | Non | — | Vue de publication | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.assistant_conversation`

**Type :** table  
**Définition :** Conversations d'un utilisateur avec l'assistant Django.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | PK, FK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED | Personnel | Actif |
| `title` | Titre lisible. | `character varying(200)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `created_at` | Date et heure de création. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `user_id` | Identifiant de référence vers user. | `integer` | Oui | FK | Application Django / Assistant | Non extrait | FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED | Personnel | Actif |
| `kind` | Champ kind de l'objet documenté. | `character varying(16)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |

## `public.assistant_conversationmessage`

**Type :** table  
**Définition :** Messages et résultats enregistrés dans une conversation.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | FOREIGN KEY (conversation_id) REFERENCES assistant_conversation(id) DEFERRABLE INITIALLY DEFERRED | Sensible | Actif |
| `role` | Champ role de l'objet documenté. | `character varying(16)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `content` | Contenu textuel enregistré. | `text` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `method` | Champ method de l'objet documenté. | `character varying(16)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `request_id` | Identifiant de référence vers request. | `uuid` | Non | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `citations` | Structure JSON contenant citations. | `jsonb` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `created_at` | Date et heure de création. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `conversation_id` | Identifiant de référence vers conversation. | `bigint` | Oui | FK | Application Django / Assistant | Non extrait | FOREIGN KEY (conversation_id) REFERENCES assistant_conversation(id) DEFERRABLE INITIALLY DEFERRED | Sensible | Actif |
| `category` | Champ category de l'objet documenté. | `character varying(48)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `response_metadata` | Structure JSON contenant response metadata. | `jsonb` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `generated_sql` | Instruction SQL générée par l'assistant. | `text` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `feedback` | Champ feedback de l'objet documenté. | `character varying(16)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |

## `public.assistant_ragchunk`

**Type :** table  
**Définition :** Fragments recherchables d'une version de document RAG.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | FOREIGN KEY (document_version_id) REFERENCES assistant_ragdocumentversion(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `ordinal` | Champ ordinal de l'objet documenté. | `integer` | Oui | Unique | Application Django / Assistant | Non extrait | CHECK (ordinal >= 0); UNIQUE (document_version_id, ordinal) | Interne | Actif |
| `title` | Titre lisible. | `character varying(300)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `section` | Champ section de l'objet documenté. | `character varying(500)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `content` | Contenu textuel enregistré. | `text` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `content_sha256` | Champ content sha256 de l'objet documenté. | `character varying(64)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `page_number` | Champ page number de l'objet documenté. | `integer` | Non | — | Application Django / Assistant | Non extrait | CHECK (page_number >= 0) | Interne | Actif |
| `territory` | Champ territory de l'objet documenté. | `character varying(200)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(32)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `indicator_code` | Code de indicator. | `character varying(120)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_url` | Champ source url de l'objet documenté. | `character varying(200)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `search_vector` | Vecteur PostgreSQL utilisé pour la recherche plein texte. | `tsvector` | Non | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `document_version_id` | Identifiant de référence vers document version. | `bigint` | Oui | FK, Unique | Application Django / Assistant | Non extrait | FOREIGN KEY (document_version_id) REFERENCES assistant_ragdocumentversion(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (document_version_id, ordinal) | Interne | Actif |

## `public.assistant_ragdocument`

**Type :** table  
**Définition :** Documents logiques du corpus RAG Django.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | FOREIGN KEY (source_id) REFERENCES assistant_ragsource(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `slug` | Champ slug de l'objet documenté. | `character varying(200)` | Oui | Unique | Application Django / Assistant | Non extrait | UNIQUE (slug) | Interne | Actif |
| `title` | Titre lisible. | `character varying(300)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `document_type` | Champ document type de l'objet documenté. | `character varying(32)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_url` | Champ source url de l'objet documenté. | `character varying(200)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `is_active` | Indique si l'objet est actif. | `boolean` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `metadata` | Structure JSON contenant metadata. | `jsonb` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_id` | Identifiant de référence vers source. | `bigint` | Oui | FK | Application Django / Assistant | Non extrait | FOREIGN KEY (source_id) REFERENCES assistant_ragsource(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |

## `public.assistant_ragdocumentversion`

**Type :** table  
**Définition :** Versions approuvées des documents RAG Django.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | FOREIGN KEY (document_id) REFERENCES assistant_ragdocument(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `version_label` | Champ version label de l'objet documenté. | `character varying(100)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_path` | Champ source path de l'objet documenté. | `character varying(500)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `sha256` | Champ sha256 de l'objet documenté. | `character varying(64)` | Oui | Unique | Application Django / Assistant | Non extrait | UNIQUE (document_id, sha256) | Interne | Actif |
| `approved_at` | Date et heure de approved. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `chunking_algorithm_version` | Champ chunking algorithm version de l'objet documenté. | `character varying(100)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `indexed_at` | Date et heure de indexed. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `document_id` | Identifiant de référence vers document. | `bigint` | Oui | FK, Unique | Application Django / Assistant | Non extrait | FOREIGN KEY (document_id) REFERENCES assistant_ragdocument(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (document_id, sha256) | Interne | Actif |

## `public.assistant_ragindexrun`

**Type :** table  
**Définition :** Exécutions d'indexation du corpus RAG Django.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | PK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `status` | État courant selon le cycle de vie de l'objet. | `character varying(16)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `manifest_path` | Champ manifest path de l'objet documenté. | `character varying(500)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `chunking_algorithm_version` | Champ chunking algorithm version de l'objet documenté. | `character varying(100)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `started_at` | Date et heure de début du traitement. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `finished_at` | Date et heure de fin du traitement. | `timestamp with time zone` | Non | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `documents_created` | Champ documents created de l'objet documenté. | `integer` | Oui | — | Application Django / Assistant | Non extrait | CHECK (documents_created >= 0) | Interne | Actif |
| `versions_created` | Champ versions created de l'objet documenté. | `integer` | Oui | — | Application Django / Assistant | Non extrait | CHECK (versions_created >= 0) | Interne | Actif |
| `documents_skipped` | Champ documents skipped de l'objet documenté. | `integer` | Oui | — | Application Django / Assistant | Non extrait | CHECK (documents_skipped >= 0) | Interne | Actif |
| `chunks_created` | Champ chunks created de l'objet documenté. | `integer` | Oui | — | Application Django / Assistant | Non extrait | CHECK (chunks_created >= 0) | Interne | Actif |
| `error_message` | Champ error message de l'objet documenté. | `text` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.assistant_ragsource`

**Type :** table  
**Définition :** Sources documentaires du corpus RAG Django.  
**Source :** Application Django / Assistant  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | PK, Unique (index, composite possible) | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `name` | Nom de l'occurrence. | `character varying(200)` | Oui | Unique | Application Django / Assistant | Non extrait | UNIQUE (name) | Interne | Actif |
| `publisher` | Champ publisher de l'objet documenté. | `character varying(200)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `base_url` | Champ base url de l'objet documenté. | `character varying(200)` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `timestamp with time zone` | Oui | — | Application Django / Assistant | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.auth_group`

**Type :** table  
**Définition :** Objet PostgreSQL auth_group.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `name` | Nom de l'occurrence. | `character varying(150)` | Oui | Unique | Application Django | Non extrait | UNIQUE (name) | Interne | Actif |

## `public.auth_group_permissions`

**Type :** table  
**Définition :** Objet PostgreSQL auth_group_permissions.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django | Non extrait | FOREIGN KEY (permission_id) REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED; FOREIGN KEY (group_id) REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `group_id` | Identifiant de référence vers group. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (group_id) REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (group_id, permission_id) | Interne | Actif |
| `permission_id` | Identifiant de référence vers permission. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (permission_id) REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (group_id, permission_id) | Interne | Actif |

## `public.auth_permission`

**Type :** table  
**Définition :** Objet PostgreSQL auth_permission.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | FK, PK, Unique (index, composite possible) | Application Django | Non extrait | FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `name` | Nom de l'occurrence. | `character varying(255)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `content_type_id` | Identifiant de référence vers content type. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (content_type_id, codename) | Interne | Actif |
| `codename` | Champ codename de l'objet documenté. | `character varying(100)` | Oui | Unique | Application Django | Non extrait | UNIQUE (content_type_id, codename) | Interne | Actif |

## `public.auth_user`

**Type :** table  
**Définition :** Objet PostgreSQL auth_user.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `password` | Empreinte du mot de passe gérée par Django. | `character varying(128)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `last_login` | Champ last login de l'objet documenté. | `timestamp with time zone` | Non | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `is_superuser` | Indique si superuser. | `boolean` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `username` | Identifiant de connexion de l'utilisateur. | `character varying(150)` | Oui | Unique | Application Django | Non extrait | UNIQUE (username) | Personnel | Actif |
| `first_name` | Champ first name de l'objet documenté. | `character varying(150)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `last_name` | Champ last name de l'objet documenté. | `character varying(150)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `email` | Adresse électronique de l'utilisateur. | `character varying(254)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `is_staff` | Indique si staff. | `boolean` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `is_active` | Indique si l'objet est actif. | `boolean` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `date_joined` | Champ date joined de l'objet documenté. | `timestamp with time zone` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |

## `public.auth_user_groups`

**Type :** table  
**Définition :** Objet PostgreSQL auth_user_groups.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django | Non extrait | FOREIGN KEY (group_id) REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED; FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `user_id` | Identifiant de référence vers user. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (user_id, group_id) | Interne | Actif |
| `group_id` | Identifiant de référence vers group. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (group_id) REFERENCES auth_group(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (user_id, group_id) | Interne | Actif |

## `public.auth_user_user_permissions`

**Type :** table  
**Définition :** Objet PostgreSQL auth_user_user_permissions.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | FK, PK, Unique (index, composite possible) | Application Django | Non extrait | FOREIGN KEY (permission_id) REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED; FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED | Interne | Actif |
| `user_id` | Identifiant de référence vers user. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (user_id, permission_id) | Interne | Actif |
| `permission_id` | Identifiant de référence vers permission. | `integer` | Oui | FK, Unique | Application Django | Non extrait | FOREIGN KEY (permission_id) REFERENCES auth_permission(id) DEFERRABLE INITIALLY DEFERRED; UNIQUE (user_id, permission_id) | Interne | Actif |

## `public.dim_department`

**Type :** table  
**Définition :** Référentiel analytique des départements.  
**Source :** Référentiel conformé  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `departement_code` | Code de departement. | `text` | Oui | PK, Unique (index, composite possible) | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_name` | Champ departement name de l'objet documenté. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `is_metropolitan_scope` | Indique si metropolitan scope. | `integer` | Oui | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_code` | Code de region. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.dim_indicator`

**Type :** table  
**Définition :** Catalogue analytique multi-sources des indicateurs.  
**Source :** Référentiel conformé  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `indicator_key` | Champ indicator key de l'objet documenté. | `text` | Oui | PK, Unique (index, composite possible) | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `source_system` | Champ source system de l'objet documenté. | `text` | Oui | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_code` | Code de indicator. | `text` | Oui | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_name` | Champ indicator name de l'objet documenté. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_group` | Champ indicator group de l'objet documenté. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `unit` | Champ unit de l'objet documenté. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `aggregation_rule` | Champ aggregation rule de l'objet documenté. | `text` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.dim_period`

**Type :** table  
**Définition :** Référentiel des périodes annuelles et mensuelles.  
**Source :** Référentiel conformé  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `period_key` | Champ period key de l'objet documenté. | `character varying(16)` | Oui | PK, Unique (index, composite possible) | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_year` | Année de référence de la mesure. | `integer` | Oui | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_month_number` | Numéro du mois dans l'année de référence. | `integer` | Non | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `granularity` | Champ granularity de l'objet documenté. | `character varying(16)` | Oui | — | Référentiel conformé | Non extrait | CHECK (granularity::text = ANY (ARRAY['month'::character varying, 'year'::character varying]::text[])) | Public | Actif |

## `public.dim_region`

**Type :** table  
**Définition :** Référentiel analytique des régions.  
**Source :** Référentiel conformé  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `region_code` | Code de region. | `character varying(16)` | Oui | PK, Unique (index, composite possible) | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `character varying(255)` | Oui | Unique | Référentiel conformé | Non extrait | UNIQUE (region_name) | Public | Actif |
| `is_metropolitan_scope` | Indique si metropolitan scope. | `boolean` | Oui | — | Référentiel conformé | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.django_admin_log`

**Type :** table  
**Définition :** Objet PostgreSQL django_admin_log.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | FK, PK, Unique (index, composite possible) | Application Django | Non extrait | FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) DEFERRABLE INITIALLY DEFERRED; FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED | Personnel | Actif |
| `action_time` | Champ action time de l'objet documenté. | `timestamp with time zone` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `object_id` | Identifiant de référence vers object. | `text` | Non | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `object_repr` | Champ object repr de l'objet documenté. | `character varying(200)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `action_flag` | Champ action flag de l'objet documenté. | `smallint` | Oui | — | Application Django | Non extrait | CHECK (action_flag >= 0) | Personnel | Actif |
| `change_message` | Champ change message de l'objet documenté. | `text` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Personnel | Actif |
| `content_type_id` | Identifiant de référence vers content type. | `integer` | Non | FK | Application Django | Non extrait | FOREIGN KEY (content_type_id) REFERENCES django_content_type(id) DEFERRABLE INITIALLY DEFERRED | Personnel | Actif |
| `user_id` | Identifiant de référence vers user. | `integer` | Oui | FK | Application Django | Non extrait | FOREIGN KEY (user_id) REFERENCES auth_user(id) DEFERRABLE INITIALLY DEFERRED | Personnel | Actif |

## `public.django_content_type`

**Type :** table  
**Définition :** Objet PostgreSQL django_content_type.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `app_label` | Champ app label de l'objet documenté. | `character varying(100)` | Oui | Unique | Application Django | Non extrait | UNIQUE (app_label, model) | Interne | Actif |
| `model` | Champ model de l'objet documenté. | `character varying(100)` | Oui | Unique | Application Django | Non extrait | UNIQUE (app_label, model) | Interne | Actif |

## `public.django_migrations`

**Type :** table  
**Définition :** Objet PostgreSQL django_migrations.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `bigint` | Oui | PK, Unique (index, composite possible) | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `app` | Champ app de l'objet documenté. | `character varying(255)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `name` | Nom de l'occurrence. | `character varying(255)` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `applied` | Champ applied de l'objet documenté. | `timestamp with time zone` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.django_session`

**Type :** table  
**Définition :** Objet PostgreSQL django_session.  
**Source :** Application Django  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `session_key` | Champ session key de l'objet documenté. | `character varying(40)` | Oui | PK, Unique (index, composite possible) | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `session_data` | Champ session data de l'objet documenté. | `text` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |
| `expire_date` | Champ expire date de l'objet documenté. | `timestamp with time zone` | Oui | — | Application Django | Non extrait | Aucune contrainte spécifique déclarée | Sensible | Actif |

## `public.fact_bdf_statinfo`

**Type :** table  
**Définition :** Faits mensuels issus de Banque de France Stat Info.  
**Source :** Banque de France / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_period` | Période de référence de la mesure ou du document. | `text` | Oui | Unique (index, composite possible) | Banque de France / pipeline | Non extrait | INDEX UNIQUE uq_bdf_fact: CREATE UNIQUE INDEX uq_bdf_fact ON public.fact_bdf_statinfo USING btree (reference_period, departement_code, indicator_key) | Public | Actif |
| `reference_year` | Année de référence de la mesure. | `integer` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_month_number` | Numéro du mois dans l'année de référence. | `integer` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_code` | Code de departement. | `text` | Oui | FK, Unique (index, composite possible) | Banque de France / pipeline | Non extrait | FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code); INDEX UNIQUE uq_bdf_fact: CREATE UNIQUE INDEX uq_bdf_fact ON public.fact_bdf_statinfo USING btree (reference_period, departement_code, indicator_key) | Public | Actif |
| `indicator_key` | Champ indicator key de l'objet documenté. | `text` | Oui | FK, Unique (index, composite possible) | Banque de France / pipeline | Non extrait | FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key); INDEX UNIQUE uq_bdf_fact: CREATE UNIQUE INDEX uq_bdf_fact ON public.fact_bdf_statinfo USING btree (reference_period, departement_code, indicator_key) | Public | Actif |
| `value` | Valeur numérique de la mesure. | `real` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `source_file` | Champ source file de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `pipeline_version` | Champ pipeline version de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.fact_insee_macro`

**Type :** table  
**Définition :** Faits macroéconomiques départementaux issus de l'INSEE.  
**Source :** INSEE / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Oui | Unique (index, composite possible) | INSEE / pipeline | Non extrait | INDEX UNIQUE uq_insee_fact: CREATE UNIQUE INDEX uq_insee_fact ON public.fact_insee_macro USING btree (reference_year, departement_code, indicator_key) | Public | Actif |
| `departement_code` | Code de departement. | `text` | Oui | FK, Unique (index, composite possible) | INSEE / pipeline | Non extrait | FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code); INDEX UNIQUE uq_insee_fact: CREATE UNIQUE INDEX uq_insee_fact ON public.fact_insee_macro USING btree (reference_year, departement_code, indicator_key) | Public | Actif |
| `indicator_key` | Champ indicator key de l'objet documenté. | `text` | Oui | FK, Unique (index, composite possible) | INSEE / pipeline | Non extrait | FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key); INDEX UNIQUE uq_insee_fact: CREATE UNIQUE INDEX uq_insee_fact ON public.fact_insee_macro USING btree (reference_year, departement_code, indicator_key) | Public | Actif |
| `value` | Valeur numérique de la mesure. | `real` | Oui | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `source_dataset` | Champ source dataset de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `pipeline_version` | Champ pipeline version de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.fact_macro_override`

**Type :** table  
**Définition :** Corrections analytiques explicites et traçables.  
**Source :** Application / pipeline interne  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application / pipeline interne | `nextval('fact_macro_override_id_seq'::regclass)` | DEFAULT nextval('fact_macro_override_id_seq'::regclass) | Public | Actif |
| `period_key` | Champ period key de l'objet documenté. | `text` | Oui | FK | Application / pipeline interne | Non extrait | FOREIGN KEY (period_key) REFERENCES dim_period(period_key) | Public | Actif |
| `reference_year` | Année de référence de la mesure. | `integer` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_code` | Code de departement. | `text` | Oui | FK | Application / pipeline interne | Non extrait | FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code) | Public | Actif |
| `indicator_key` | Champ indicator key de l'objet documenté. | `text` | Oui | FK | Application / pipeline interne | Non extrait | FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key) | Public | Actif |
| `indicator_code` | Code de indicator. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_name` | Champ indicator name de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_group` | Champ indicator group de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `value` | Valeur numérique de la mesure. | `real` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `source_note` | Champ source note de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `created_at` | Date et heure de création. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.fact_surendettement`

**Type :** table  
**Définition :** Ancien fait départemental de surendettement.  
**Source :** Application / pipeline interne  
**Statut :** Déprécié

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `departement_code` | Code de departement. | `text` | Oui | FK | Application / pipeline interne | Non extrait | FOREIGN KEY (departement_code) REFERENCES dim_department(departement_code) | Public | Déprécié |
| `indicator_key` | Champ indicator key de l'objet documenté. | `text` | Oui | FK | Application / pipeline interne | Non extrait | FOREIGN KEY (indicator_key) REFERENCES dim_indicator(indicator_key) | Public | Déprécié |
| `value` | Valeur numérique de la mesure. | `real` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `source_file` | Champ source file de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |

## `public.indicators`

**Type :** table  
**Définition :** Catalogue opérationnel des indicateurs.  
**Source :** Application / pipeline interne  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application / pipeline interne | `nextval('indicators_id_seq'::regclass)` | DEFAULT nextval('indicators_id_seq'::regclass) | Interne | Actif |
| `code` | Code métier stable. | `character varying(128)` | Oui | Unique | Application / pipeline interne | Non extrait | UNIQUE (code) | Interne | Actif |
| `label` | Libellé métier. | `character varying(512)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `category` | Champ category de l'objet documenté. | `character varying(255)` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `description` | Description fonctionnelle. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `default_unit` | Champ default unit de l'objet documenté. | `character varying(64)` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.observations`

**Type :** table  
**Définition :** Mesures extraites d'un document pour un territoire et une période.  
**Source :** Banque de France / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | FK, PK, Unique (index, composite possible) | Banque de France / pipeline | `nextval('observations_id_seq'::regclass)` | FOREIGN KEY (indicator_id) REFERENCES indicators(id); FOREIGN KEY (source_document_id) REFERENCES source_documents(id); DEFAULT nextval('observations_id_seq'::regclass) | Interne | Actif |
| `source_document_id` | Identifiant de référence vers source document. | `integer` | Oui | FK | Banque de France / pipeline | Non extrait | FOREIGN KEY (source_document_id) REFERENCES source_documents(id) | Interne | Actif |
| `indicator_id` | Identifiant de référence vers indicator. | `integer` | Oui | FK | Banque de France / pipeline | Non extrait | FOREIGN KEY (indicator_id) REFERENCES indicators(id) | Interne | Actif |
| `idempotence_key` | Champ idempotence key de l'objet documenté. | `character varying(64)` | Oui | Unique | Banque de France / pipeline | Non extrait | UNIQUE (idempotence_key) | Interne | Actif |
| `indicator_code` | Code de indicator. | `character varying(128)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `region_code` | Code de region. | `character varying(16)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(7)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `geographic_level` | Champ geographic level de l'objet documenté. | `character varying(64)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `geographic_code` | Code de geographic. | `character varying(64)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `geographic_name` | Champ geographic name de l'objet documenté. | `character varying(255)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `value_numeric` | Valeur numérique de l'observation. | `double precision` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `value_text` | Valeur textuelle lorsque la mesure n'est pas numérique. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `unit` | Champ unit de l'objet documenté. | `character varying(64)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `observation_type` | Champ observation type de l'objet documenté. | `character varying(64)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `comparison_period` | Champ comparison period de l'objet documenté. | `character varying(32)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `variation_numeric` | Champ variation numeric de l'objet documenté. | `double precision` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `variation_unit` | Champ variation unit de l'objet documenté. | `character varying(64)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `page_number` | Champ page number de l'objet documenté. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_label` | Champ source label de l'objet documenté. | `character varying(512)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_fragment` | Champ source fragment de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `extraction_method` | Champ extraction method de l'objet documenté. | `character varying(64)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `confidence_score` | Champ confidence score de l'objet documenté. | `double precision` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.pipeline_metadata`

**Type :** table  
**Définition :** Métadonnées techniques de construction de l'entrepôt.  
**Source :** Application / pipeline interne  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `database_version` | Champ database version de l'objet documenté. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_system` | Champ source system de l'objet documenté. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_path` | Champ source path de l'objet documenté. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `built_at` | Date et heure de built. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.pipeline_runs`

**Type :** table  
**Définition :** Exécutions et contrôles qualité des pipelines.  
**Source :** Application / pipeline interne  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application / pipeline interne | `nextval('pipeline_runs_id_seq'::regclass)` | DEFAULT nextval('pipeline_runs_id_seq'::regclass) | Interne | Actif |
| `pipeline_name` | Champ pipeline name de l'objet documenté. | `character varying(128)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `status` | État courant selon le cycle de vie de l'objet. | `character varying(32)` | Oui | — | Application / pipeline interne | Non extrait | CHECK (status::text = ANY (ARRAY['running'::character varying, 'success'::character varying, 'failed'::character varying, 'quality_failed'::character varying]::text[])) | Interne | Actif |
| `started_at` | Date et heure de début du traitement. | `character varying(32)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `finished_at` | Date et heure de fin du traitement. | `character varying(32)` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `configuration_json` | Structure JSON contenant configuration. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `step_results_json` | Structure JSON contenant step results. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `quality_report_json` | Structure JSON contenant quality report. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `error_message` | Champ error message de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.risk_score_details`

**Type :** table  
**Définition :** Contributions des indicateurs à un score.  
**Source :** Calcul de score  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | FK, PK, Unique (index, composite possible) | Calcul de score | `nextval('risk_score_details_id_seq'::regclass)` | FOREIGN KEY (indicator_id) REFERENCES indicators(id); FOREIGN KEY (risk_score_id) REFERENCES risk_scores(id); FOREIGN KEY (source_observation_id) REFERENCES observations(id); DEFAULT nextval('risk_score_details_id_seq'::regclass) | Interne | Actif |
| `risk_score_id` | Identifiant de référence vers risk score. | `integer` | Oui | FK, Unique | Calcul de score | Non extrait | FOREIGN KEY (risk_score_id) REFERENCES risk_scores(id); UNIQUE (risk_score_id, indicator_code) | Interne | Actif |
| `indicator_id` | Identifiant de référence vers indicator. | `integer` | Non | FK | Calcul de score | Non extrait | FOREIGN KEY (indicator_id) REFERENCES indicators(id) | Interne | Actif |
| `indicator_code` | Code de indicator. | `character varying(128)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (risk_score_id, indicator_code) | Interne | Actif |
| `raw_value` | Champ raw value de l'objet documenté. | `numeric(20,8)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `unit` | Champ unit de l'objet documenté. | `character varying(64)` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `population_min` | Champ population min de l'objet documenté. | `numeric(20,8)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `population_max` | Champ population max de l'objet documenté. | `numeric(20,8)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `normalized_value` | Champ normalized value de l'objet documenté. | `numeric(12,8)` | Oui | — | Calcul de score | Non extrait | CHECK (normalized_value >= 0::numeric AND normalized_value <= 1::numeric) | Interne | Actif |
| `configured_weight` | Champ configured weight de l'objet documenté. | `numeric(12,8)` | Oui | — | Calcul de score | Non extrait | CHECK (configured_weight > 0::numeric) | Interne | Actif |
| `effective_weight` | Champ effective weight de l'objet documenté. | `numeric(12,8)` | Oui | — | Calcul de score | Non extrait | CHECK (effective_weight > 0::numeric) | Interne | Actif |
| `contribution` | Champ contribution de l'objet documenté. | `numeric(12,8)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `direction` | Champ direction de l'objet documenté. | `character varying(16)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `source_observation_id` | Identifiant de référence vers source observation. | `integer` | Non | FK | Calcul de score | Non extrait | FOREIGN KEY (source_observation_id) REFERENCES observations(id) | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.risk_score_indicator_configs`

**Type :** table  
**Définition :** Poids et règles d'un indicateur dans un modèle.  
**Source :** Calcul de score  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | FK, PK, Unique (index, composite possible) | Calcul de score | `nextval('risk_score_indicator_configs_id_seq'::regclass)` | FOREIGN KEY (indicator_id) REFERENCES indicators(id); FOREIGN KEY (risk_score_model_id) REFERENCES risk_score_models(id); DEFAULT nextval('risk_score_indicator_configs_id_seq'::regclass) | Interne | Actif |
| `risk_score_model_id` | Identifiant de référence vers risk score model. | `integer` | Oui | FK, Unique | Calcul de score | Non extrait | FOREIGN KEY (risk_score_model_id) REFERENCES risk_score_models(id); UNIQUE (risk_score_model_id, indicator_code) | Interne | Actif |
| `indicator_id` | Identifiant de référence vers indicator. | `integer` | Non | FK | Calcul de score | Non extrait | FOREIGN KEY (indicator_id) REFERENCES indicators(id) | Interne | Actif |
| `indicator_code` | Code de indicator. | `character varying(128)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (risk_score_model_id, indicator_code) | Interne | Actif |
| `logical_code` | Code de logical. | `character varying(128)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `weight` | Champ weight de l'objet documenté. | `numeric(12,8)` | Oui | — | Calcul de score | Non extrait | CHECK (weight > 0::numeric) | Interne | Actif |
| `direction` | Champ direction de l'objet documenté. | `character varying(16)` | Oui | — | Calcul de score | Non extrait | CHECK (direction::text = ANY (ARRAY['positive'::character varying, 'negative'::character varying]::text[])) | Interne | Actif |
| `normalization_method` | Champ normalization method de l'objet documenté. | `character varying(64)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `fixed_min` | Champ fixed min de l'objet documenté. | `numeric(20,8)` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `fixed_max` | Champ fixed max de l'objet documenté. | `numeric(20,8)` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `expected_unit` | Champ expected unit de l'objet documenté. | `character varying(64)` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `is_required` | Indique si required. | `boolean` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `is_active` | Indique si l'objet est actif. | `boolean` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.risk_score_models`

**Type :** table  
**Définition :** Modèles de score de risque versionnés.  
**Source :** Calcul de score  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Calcul de score | `nextval('risk_score_models_id_seq'::regclass)` | DEFAULT nextval('risk_score_models_id_seq'::regclass) | Interne | Actif |
| `code` | Code métier stable. | `character varying(128)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (code, version) | Interne | Actif |
| `name` | Nom de l'occurrence. | `character varying(255)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `version` | Champ version de l'objet documenté. | `character varying(64)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (code, version) | Interne | Actif |
| `description` | Description fonctionnelle. | `text` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `normalization_method` | Champ normalization method de l'objet documenté. | `character varying(64)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `minimum_coverage_ratio` | Champ minimum coverage ratio de l'objet documenté. | `numeric(8,6)` | Oui | — | Calcul de score | Non extrait | CHECK (minimum_coverage_ratio >= 0::numeric AND minimum_coverage_ratio <= 1::numeric) | Interne | Actif |
| `is_active` | Indique si l'objet est actif. | `boolean` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `configuration_json` | Structure JSON contenant configuration. | `text` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.risk_scores`

**Type :** table  
**Définition :** Scores calculés par territoire, période et modèle.  
**Source :** Calcul de score  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, FK, Unique (index, composite possible) | Calcul de score | `nextval('risk_scores_id_seq'::regclass)` | FOREIGN KEY (risk_score_model_id) REFERENCES risk_score_models(id); DEFAULT nextval('risk_scores_id_seq'::regclass) | Interne | Actif |
| `risk_score_model_id` | Identifiant de référence vers risk score model. | `integer` | Oui | FK, Unique | Calcul de score | Non extrait | FOREIGN KEY (risk_score_model_id) REFERENCES risk_score_models(id); UNIQUE (risk_score_model_id, geographic_level, geographic_code, reference_period) | Interne | Actif |
| `geographic_level` | Champ geographic level de l'objet documenté. | `character varying(32)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (risk_score_model_id, geographic_level, geographic_code, reference_period) | Interne | Actif |
| `geographic_code` | Code de geographic. | `character varying(64)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (risk_score_model_id, geographic_level, geographic_code, reference_period) | Interne | Actif |
| `geographic_name` | Champ geographic name de l'objet documenté. | `character varying(255)` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(16)` | Oui | Unique | Calcul de score | Non extrait | UNIQUE (risk_score_model_id, geographic_level, geographic_code, reference_period) | Interne | Actif |
| `score` | Champ score de l'objet documenté. | `numeric(12,8)` | Non | — | Calcul de score | Non extrait | CHECK (score IS NULL OR score >= 0::numeric AND score <= 100::numeric) | Interne | Actif |
| `risk_level` | Champ risk level de l'objet documenté. | `character varying(32)` | Non | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `coverage_ratio` | Champ coverage ratio de l'objet documenté. | `numeric(8,6)` | Oui | — | Calcul de score | Non extrait | CHECK (coverage_ratio >= 0::numeric AND coverage_ratio <= 1::numeric) | Interne | Actif |
| `status` | État courant selon le cycle de vie de l'objet. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | CHECK (status::text = ANY (ARRAY['valid'::character varying, 'partial'::character varying, 'insufficient_data'::character varying, 'error'::character varying]::text[])) | Interne | Actif |
| `missing_indicators_json` | Structure JSON contenant missing indicators. | `text` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `warnings_json` | Structure JSON contenant warnings. | `text` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `calculated_at` | Date et heure de calculated. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Calcul de score | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.schema_deprecations`

**Type :** table  
**Définition :** Registre des objets analytiques dépréciés.  
**Source :** Application / pipeline interne  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `object_name` | Champ object name de l'objet documenté. | `text` | Oui | PK, Unique (index, composite possible) | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `object_type` | Champ object type de l'objet documenté. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `deprecated_since` | Champ deprecated since de l'objet documenté. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `replacement` | Champ replacement de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `reason` | Champ reason de l'objet documenté. | `text` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.schema_migrations`

**Type :** table  
**Définition :** Registre technique des migrations appliquées.  
**Source :** Application / pipeline interne  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `version` | Champ version de l'objet documenté. | `character varying(64)` | Oui | PK, Unique (index, composite possible) | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `description` | Description fonctionnelle. | `character varying(512)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `applied_at` | Date et heure de applied. | `character varying(32)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.source_documents`

**Type :** table  
**Définition :** Documents sources collectés et versions d'extraction.  
**Source :** Banque de France / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Banque de France / pipeline | `nextval('source_documents_id_seq'::regclass)` | DEFAULT nextval('source_documents_id_seq'::regclass) | Interne | Actif |
| `source_name` | Champ source name de l'objet documenté. | `character varying(255)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `publication_type` | Champ publication type de l'objet documenté. | `character varying(255)` | Oui | Unique | Banque de France / pipeline | Non extrait | UNIQUE (publication_type, region_code, reference_period, pdf_sha256) | Interne | Actif |
| `region_code` | Code de region. | `character varying(16)` | Oui | Unique | Banque de France / pipeline | Non extrait | UNIQUE (publication_type, region_code, reference_period, pdf_sha256) | Interne | Actif |
| `region_name` | Champ region name de l'objet documenté. | `character varying(255)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `reference_period` | Période de référence de la mesure ou du document. | `character varying(7)` | Oui | Unique | Banque de France / pipeline | Non extrait | UNIQUE (publication_type, region_code, reference_period, pdf_sha256) | Interne | Actif |
| `publication_date` | Champ publication date de l'objet documenté. | `character varying(32)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_date` | Champ updated date de l'objet documenté. | `character varying(32)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `page_url` | Champ page url de l'objet documenté. | `text` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `pdf_url` | Champ pdf url de l'objet documenté. | `text` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `pdf_filename` | Champ pdf filename de l'objet documenté. | `character varying(512)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `pdf_sha256` | Champ pdf sha256 de l'objet documenté. | `character varying(64)` | Oui | Unique | Banque de France / pipeline | Non extrait | UNIQUE (publication_type, region_code, reference_period, pdf_sha256); UNIQUE (pdf_sha256) | Interne | Actif |
| `pdf_size_bytes` | Champ pdf size bytes de l'objet documenté. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `storage_path` | Champ storage path de l'objet documenté. | `text` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `http_etag` | Champ http etag de l'objet documenté. | `character varying(255)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `http_last_modified` | Champ http last modified de l'objet documenté. | `character varying(255)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `downloaded_at` | Date et heure de downloaded. | `character varying(32)` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `extraction_status` | Champ extraction status de l'objet documenté. | `character varying(64)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `extractor_version` | Champ extractor version de l'objet documenté. | `character varying(64)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `created_at` | Date et heure de création. | `character varying(32)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |
| `updated_at` | Date et heure de dernière mise à jour. | `character varying(32)` | Oui | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Interne | Actif |

## `public.surendettement_data`

**Type :** table  
**Définition :** Ancien stockage générique région-année-indicateur.  
**Source :** Application / pipeline interne  
**Statut :** Historique

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `id` | Identifiant technique de l'occurrence. | `integer` | Oui | PK, Unique (index, composite possible) | Application / pipeline interne | `nextval('surendettement_data_id_seq'::regclass)` | DEFAULT nextval('surendettement_data_id_seq'::regclass) | Interne | Historique |
| `year` | Champ year de l'objet documenté. | `integer` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Historique |
| `region` | Champ region de l'objet documenté. | `character varying(255)` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Historique |
| `indicator` | Champ indicator de l'objet documenté. | `character varying(255)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Historique |
| `value` | Valeur numérique de la mesure. | `double precision` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Historique |
| `source_file` | Champ source file de l'objet documenté. | `character varying(255)` | Oui | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Interne | Historique |

## `public.v_bdf_total_deposits`

**Type :** vue  
**Définition :** Objet PostgreSQL v_bdf_total_deposits.  
**Source :** Banque de France / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_period` | Période de référence de la mesure ou du document. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_year` | Année de référence de la mesure. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `reference_month_number` | Numéro du mois dans l'année de référence. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_code` | Code de departement. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_name` | Champ departement name de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `bdf_total_deposits_value` | Champ bdf total deposits value de l'objet documenté. | `real` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.v_bdf_total_deposits_with_insee_macro`

**Type :** vue  
**Définition :** Objet PostgreSQL v_bdf_total_deposits_with_insee_macro.  
**Source :** Banque de France / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `bdf_reference_period` | Champ bdf reference period de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `bdf_reference_year` | Champ bdf reference year de l'objet documenté. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `bdf_reference_month_number` | Champ bdf reference month number de l'objet documenté. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_code` | Code de departement. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `departement_name` | Champ departement name de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `bdf_total_deposits_value` | Champ bdf total deposits value de l'objet documenté. | `real` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `macro_reference_year` | Champ macro reference year de l'objet documenté. | `integer` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `macro_indicator_code` | Code de macro indicator. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `macro_indicator_name` | Champ macro indicator name de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `macro_indicator_group` | Champ macro indicator group de l'objet documenté. | `text` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `macro_value` | Champ macro value de l'objet documenté. | `real` | Non | — | Banque de France / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.v_insee_macro_region`

**Type :** vue  
**Définition :** Objet PostgreSQL v_insee_macro_region.  
**Source :** INSEE / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_code` | Code de region. | `character varying(16)` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `character varying(255)` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_code` | Code de indicator. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_name` | Champ indicator name de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_group` | Champ indicator group de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `aggregation_rule` | Champ aggregation rule de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `value` | Valeur numérique de la mesure. | `real` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.v_insee_macro_region_selected`

**Type :** vue  
**Définition :** Objet PostgreSQL v_insee_macro_region_selected.  
**Source :** INSEE / pipeline  
**Statut :** Actif

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_code` | Code de region. | `character varying(16)` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `region_name` | Champ region name de l'objet documenté. | `character varying(255)` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_code` | Code de indicator. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_name` | Champ indicator name de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `indicator_group` | Champ indicator group de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `aggregation_rule` | Champ aggregation rule de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |
| `value` | Valeur numérique de la mesure. | `double precision` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Actif |

## `public.v_surendettement_annual`

**Type :** vue  
**Définition :** Objet PostgreSQL v_surendettement_annual.  
**Source :** Application / pipeline interne  
**Statut :** Déprécié

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `departement_code` | Code de departement. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `departement_name` | Champ departement name de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `region_name` | Champ region name de l'objet documenté. | `text` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `surendettement_value` | Champ surendettement value de l'objet documenté. | `real` | Non | — | Application / pipeline interne | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |

## `public.v_surendettement_with_insee_macro`

**Type :** vue  
**Définition :** Objet PostgreSQL v_surendettement_with_insee_macro.  
**Source :** INSEE / pipeline  
**Statut :** Déprécié

| Colonne | Définition | Type PostgreSQL | Obligatoire | Clé | Source | Exemple | Règle | Sensibilité | Statut |
|---|---|---|---|---|---|---|---|---|---|
| `reference_year` | Année de référence de la mesure. | `integer` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `departement_code` | Code de departement. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `departement_name` | Champ departement name de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `region_name` | Champ region name de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `surendettement_value` | Champ surendettement value de l'objet documenté. | `real` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `macro_reference_year` | Champ macro reference year de l'objet documenté. | `integer` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `macro_indicator_code` | Code de macro indicator. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `macro_indicator_name` | Champ macro indicator name de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `macro_indicator_group` | Champ macro indicator group de l'objet documenté. | `text` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
| `macro_value` | Champ macro value de l'objet documenté. | `real` | Non | — | INSEE / pipeline | Non extrait | Aucune contrainte spécifique déclarée | Public | Déprécié |
