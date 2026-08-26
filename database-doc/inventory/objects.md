# Inventaire et statut des objets

La liste correspond à la base PostgreSQL de référence au 25 août 2026. Le MPD
détaillé (colonnes, types, contraintes et index) est dans
`database-doc/physical/mpd.dbml`.

## Acquisition et stockage opérationnel

| Objet | Type | Statut | Rôle |
|---|---|---|---|
| `public.source_documents` | table | actif | versions des documents Banque de France et traçabilité d'extraction |
| `public.indicators` | table | actif | catalogue opérationnel des indicateurs |
| `public.observations` | table | actif | observations extraites, avec clé d'idempotence |
| `public.pipeline_runs` | table | actif | exécutions, résultats et contrôles qualité du pipeline |
| `public.surendettement_data` | table | historique actif / compatibilité | premier format générique, encore lu par l'import legacy et une API |
| `public.schema_migrations` | table technique | actif | registre des migrations SQLAlchemy |

## Référentiels et entrepôt analytique

| Objet | Type | Statut | Rôle |
|---|---|---|---|
| `public.dim_region` | dimension | actif | référentiel régional partagé |
| `public.dim_department` | dimension | actif | référentiel départemental et rattachement régional |
| `public.dim_period` | dimension | actif | périodes annuelles ou mensuelles |
| `public.dim_indicator` | dimension | actif | indicateurs analytiques multi-sources |
| `public.fact_bdf_statinfo` | fait | actif | faits mensuels Banque de France Stat Info |
| `public.fact_insee_macro` | fait | actif | faits macroéconomiques INSEE |
| `public.fact_macro_override` | fait applicatif | actif | corrections analytiques explicites |
| `public.pipeline_metadata` | table technique | actif | métadonnées de construction du mart |
| `public.schema_deprecations` | table technique | actif | registre des objets dépréciés |
| `public.fact_surendettement` | fait | déprécié | modèle départemental historique vide |

## Scoring territorial

| Objet | Type | Statut | Rôle |
|---|---|---|---|
| `public.risk_score_models` | configuration | actif | modèles de risque versionnés |
| `public.risk_score_indicator_configs` | configuration/jointure | actif | indicateurs, poids et sens par modèle |
| `public.risk_scores` | fait calculé | actif | score d'un territoire pour une période et un modèle |
| `public.risk_score_details` | détail de fait | actif | contribution de chaque indicateur au score |

## Assistant SQL et RAG natif

| Objet | Type | Statut | Rôle |
|---|---|---|---|
| `assistant.corpus_chunks` | table RAG | actif, corpus d'exécution | fragments consultés par l'Assistant API en production |
| `assistant.sql_executions` | audit | actif | requêtes générées, validation, durée et acteur |
| `assistant.schema_migrations` | table technique | actif | registre des migrations de l'Assistant API |

## Django, comptes et conversations

| Groupe d'objets | Objets | Statut |
|---|---|---|
| Authentification | `auth_user`, `auth_group`, `auth_permission` | actif, données personnelles pour `auth_user` |
| Jointures d'autorisation | `auth_group_permissions`, `auth_user_groups`, `auth_user_user_permissions` | actif |
| Infrastructure Django | `django_content_type`, `django_migrations`, `django_session`, `django_admin_log` | actif, technique ; sessions et journal potentiellement personnels |
| Conversations | `assistant_conversation`, `assistant_conversationmessage` | actif, personnel/sensible selon le contenu |
| Corpus Django | `assistant_ragsource`, `assistant_ragdocument`, `assistant_ragdocumentversion`, `assistant_ragchunk`, `assistant_ragindexrun` | **déprécié officiellement le 25/08/2026** |

Le chemin d'exécution courant est démontré : Django appelle l'Assistant API par
HTTP, puis celle-ci recherche dans `assistant.corpus_chunks`. Le corpus Django a
été officiellement déprécié par la migration
`assistant.0005_deprecate_legacy_rag_corpus`. Elle désactive les documents actifs
et inscrit les cinq tables dans `schema_deprecations` lorsque ce registre est
présent. Aucune table ni donnée historique n'est supprimée.

La commande `ingest_rag_corpus` refuse désormais toute nouvelle écriture par
défaut. `--allow-deprecated` constitue une dérogation explicite réservée à une
reprise historique autorisée. `lexical_search` reste disponible pour lecture
d'audit et émet un `DeprecationWarning`.

`surendettement_data` est historique mais pas inactif. Le module
`src/risk_score/legacy_import.py` le convertit de manière idempotente en
observations et l'API conserve un endpoint de compatibilité. Son absence du
registre `schema_deprecations` est donc cohérente avec le code actuel.

## Vues actives

- Exposition opérationnelle : `analytics_observations`,
  `analytics_pipeline_status`, `analytics_risk_scores`,
  `analytics_score_factors`, `analytics_model_comparisons` et
  `analytics_macro_regions`.
- Entrepôt BDF/INSEE : `v_bdf_total_deposits`,
  `v_bdf_total_deposits_with_insee_macro`, `v_insee_macro_region` et
  `v_insee_macro_region_selected`.
- Historiques dépréciées : `v_surendettement_annual` et
  `v_surendettement_with_insee_macro`.

## Objets dépréciés enregistrés

| Objet | Depuis | Remplacement déclaré | Motif enregistré |
|---|---|---|---|
| `fact_surendettement` | 2026-07-29 | `operational.observations` | modèle départemental historique vide |
| `v_surendettement_annual` | 2026-07-29 | `operational.observations` | vue fondée sur un fait historique vide |
| `v_surendettement_with_insee_macro` | 2026-07-29 | `risk_score analytics bridge` | rapprochement remplacé par la passerelle versionnée |
| `assistant_ragsource` | 2026-08-25 | `assistant.corpus_chunks` | corpus RAG Django remplacé par le corpus de l'Assistant API |
| `assistant_ragdocument` | 2026-08-25 | `assistant.corpus_chunks` | corpus RAG Django remplacé par le corpus de l'Assistant API |
| `assistant_ragdocumentversion` | 2026-08-25 | `assistant.corpus_chunks` | corpus RAG Django remplacé par le corpus de l'Assistant API |
| `assistant_ragchunk` | 2026-08-25 | `assistant.corpus_chunks` | corpus RAG Django remplacé par le corpus de l'Assistant API |
| `assistant_ragindexrun` | 2026-08-25 | `assistant.corpus_chunks` | corpus RAG Django remplacé par le corpus de l'Assistant API |

Écart : le schéma PostgreSQL `operational` n'existe pas dans la base observée ;
la table physique est `public.observations`. Le remplacement semble employer un
nom de domaine logique et doit être clarifié dans la gouvernance.

## Objets PostgreSQL absents

- aucune vue matérialisée ;
- aucun trigger utilisateur ;
- aucun enum ni domaine personnalisé ;
- aucun objet persistant dans un schéma temporaire PostgreSQL.
