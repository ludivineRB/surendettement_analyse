# Inventaire des bases et environnements PostgreSQL

Audit réalisé le 25 août 2026. Les nombres décrivent les objets persistants
visibles dans les catalogues PostgreSQL ; aucune donnée métier n'a été lue.

## Source de vérité

| Élément | Valeur observée |
|---|---|
| Instance Docker | `surendettement_staging_validation-postgres-1` |
| PostgreSQL | 16.14 |
| Base applicative | `surendettement_staging` |
| Base de maintenance | `postgres` |
| Schémas applicatifs | `public`, `assistant` |
| Objets persistants | 40 tables, 12 vues, 26 séquences |
| Schémas temporaires PostgreSQL | aucun objet temporaire observé |

La base `postgres` est la base de maintenance standard de l'instance. Aucun
élément du code audité ne l'utilise comme stockage applicatif.

## Paramètres de connexion prévus par le code

| Variable | Usage | Définition observée |
|---|---|---|
| `DATABASE_URL` | stockage opérationnel et Django | `src/storage/database.py`, `web/config/settings.py` |
| `ANALYTICS_DATABASE_URL` | lecture/publication analytique | `src/storage/analytics_db.py`, `app/core/analytics.py` |
| `ASSISTANT_DATABASE_URL` | API Assistant | `docker/compose.yaml` |
| `ANALYTICS_READONLY_DATABASE_URL` | agent SQL en lecture seule | `docker/compose.yaml` |
| `ADMIN_DATABASE_URL` | migrations et provisionnement | scripts `src/storage/migrate_*` |
| `TARGET_DATABASE_URL` | migration opérationnelle ponctuelle | `src/storage/migrate_to_postgres.py` |
| `TEST_POSTGRES_DATABASE_URL` | tests d'intégration jetables | `app/tests/test_postgres_migration.py` |

Les valeurs et mots de passe ne sont pas documentés. Les trois services
applicatifs pointent actuellement vers la même instance PostgreSQL, mais leurs
responsabilités logiques restent distinctes.

## Instances temporaires conservées

Il s'agit de projets Docker Compose avec volumes isolés, pas de tables SQL
créées avec `CREATE TEMP TABLE`. Leur isolement permet de tester une migration
ou une correction sans écraser une base précédente. La raison est dite
« déduite » lorsqu'aucun rapport du dépôt ne rattache explicitement le nom du
projet à une exécution.

| Projet / base | Création UTC | Objets observés | Finalité |
|---|---:|---|---|
| `surendettement_fix_validation` / `surendettement_ci_test` | 2026-08-24 | 12 tables, 6 vues, 9 séquences | Validation d'une correction incluant `analytics_macro_regions` ; déduit du nom et de la vue supplémentaire. |
| `surendettement_analytics_final` / `surendettement_ci_test` | 2026-08-21 | 12 tables, 5 vues, 9 séquences | Validation finale du stockage opérationnel et de ses vues analytiques ; déduit du nom. |
| `surendettement_analytics_pg_test2` / `surendettement_analytics_test` | 2026-08-21 | 10 tables, 6 vues, 1 séquence | Deuxième essai de migration du mart analytique, avec les vues créées. |
| `surendettement_analytics_pg_test` / `surendettement_analytics_test` | 2026-08-21 | 10 tables, aucune vue, 1 séquence | Premier essai de migration analytique, vraisemblablement arrêté avant les vues ; hypothèse à valider. |
| `surendettement_ci_nodata_final` / `surendettement_ci_test` | 2026-08-21 | 12 tables, 5 vues, 9 séquences | Validation CI du schéma sans reprise de données ; déduit du nom `nodata`. |
| `surendettement_ci_validation_final` / `surendettement_ci_test` | 2026-08-19 | 12 tables, 5 vues, 9 séquences | Validation finale de la migration opérationnelle en CI ; déduit du nom. |
| `surendettement_ci_validation` | 2026-08-19 | base configurée absente | Première exécution incomplète ou base supprimée après test ; hypothèse à valider. |

Toutes proviennent de `docker/compose.yaml`; les projets de validation complète
ajoutent `docker/compose.staging.yaml`. Leur présence simultanée vient de noms de
projets Compose différents, qui créent chacun leur propre volume. Aucune règle
de rétention ou de suppression automatique de ces volumes n'a été identifiée.

## SQLite historique

Deux familles SQLite subsistent dans les traitements : stockage opérationnel
historique (`data/processed/surendettement.db`) et mart analytique construit par
`src/storage/analytics_db.py`. Elles alimentent les migrations vers PostgreSQL.
Les fichiers de données sont exclus de la documentation et n'ont pas été lus.
