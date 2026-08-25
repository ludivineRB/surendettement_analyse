# Inventaire des migrations

## Migrations opérationnelles

Registre physique : `public.schema_migrations`. Implémentation :
`src/storage/schema_migrations.py`.

| Version | Description | Appliquée le (UTC) |
|---|---|---:|
| `001_application_schema` | création du schéma SQLAlchemy opérationnel | 2026-07-29 20:32:25 |
| `002_operational_indexes` | index pipeline, documents et observations | 2026-07-29 20:32:25 |
| `003_readonly_analytics_views` | vues analytiques en lecture seule | 2026-08-19 12:26:39 |
| `004_macro_region_analytics_view` | vue des indicateurs macro-régionaux | 2026-08-24 09:56:55 |

Ce registre crée d'abord les tables via `Base.metadata.create_all`, puis applique
des opérations SQL versionnées compatibles SQLite/PostgreSQL. Il ne s'agit pas
d'Alembic.

## Migrations Assistant API

Registre physique : `assistant.schema_migrations`.

| Version | Rôle | Appliquée le (UTC) |
|---|---|---:|
| `001_corpus_chunks` | corpus RAG et index plein texte | 2026-08-14 08:29:48 |
| `002_sql_execution_audit` | audit des exécutions de l'agent SQL | 2026-08-19 12:25:49 |

Ces migrations utilisent un schéma PostgreSQL dédié `assistant` et ne sont pas
des migrations Django malgré le nom fonctionnel commun.

## Migrations Django propres au projet

Registre physique : `public.django_migrations`.

| Application | Migration | Effet principal | Appliquée le (UTC) |
|---|---|---|---:|
| `accounts` | `0001_initial_roles` | groupes et permissions viewer/analyst/administrator | 2026-07-30 09:27:23 |
| `assistant` | `0001_initial` | sources, documents, versions, chunks et exécutions RAG | 2026-07-30 12:32:11 |
| `assistant` | `0002_retire_technical_corpus` | désactivation réversible de deux documents techniques | 2026-07-30 13:06:08 |
| `assistant` | `0003_conversations` | conversations et messages rattachés à l'utilisateur | 2026-08-18 21:41:16 |
| `assistant` | `0004_conversation_kind_and_response_metadata` | type de conversation, SQL, feedback et métadonnées JSON | 2026-08-19 12:50:08 |

Migrations Django standard également appliquées :

- `contenttypes` : `0001` à `0002` ;
- `auth` : `0001` à `0012` ;
- `admin` : `0001` à `0003` ;
- `sessions` : `0001`.

Le fichier `web/accounts/models.py` référencé dans le cadrage n'existe pas. Les
comptes utilisent le modèle Django standard `auth.User`; l'application
`accounts` ajoute des rôles par migration de données.

## Migrations de données entre moteurs

| Traitement | Source | Cible | Propriété observée |
|---|---|---|---|
| `src/storage/migrate_to_postgres.py` | SQLite opérationnel | PostgreSQL | insertion sans écrasement et réalignement des séquences |
| `src/storage/migrate_analytics_to_postgres.py` | mart SQLite | PostgreSQL | création/copie idempotente puis publication des vues |
| `src/storage/conformed_dimensions.py` | deux SQLite historiques | dimensions conformes | migration sans suppression de l'historique |

Ces scripts sont des transferts de données et non des registres de version du
schéma. Ils sont documentés ici pour éviter de les confondre avec les trois
systèmes de migrations précédents.

## Écarts et points de vigilance

1. Trois mécanismes de migration coexistent : registre SQLAlchemy, registre SQL
   Assistant et migrations Django.
2. Les tables analytiques physiques sont principalement créées par SQL dans
   `analytics_db.py`/`conformed_dimensions.py`, pas par les modèles SQLAlchemy.
3. La migration Django `0002` modifie des lignes de corpus mais ne déprécie pas
   les tables RAG Django elles-mêmes.
4. Les dates PostgreSQL confirment l'application des migrations, mais pas le
   code exact du commit utilisé lors de chaque exécution.
