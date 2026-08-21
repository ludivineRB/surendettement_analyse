# Migration de l'entrepôt analytique vers PostgreSQL

L'API lit désormais les tables analytiques dans la même base PostgreSQL que le
stockage opérationnel. Les images et services ne montent plus la base SQLite.

Le transfert initial est explicite, idempotent et n'efface pas la source :

```bash
set -a
source .env
set +a

export ADMIN_DATABASE_URL="postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}"

docker compose --env-file .env \
  -f docker/compose.yaml \
  run --rm --no-deps \
  -e CONFIRM_ANALYTICS_MIGRATION=yes \
  -e ADMIN_DATABASE_URL="$ADMIN_DATABASE_URL" \
  -v "$PWD/data/processed/analytics/surendettement_macro_analytics.db:/workspace/data/processed/analytics/surendettement_macro_analytics.db:ro" \
  api python -m src.storage.migrate_analytics_to_postgres
```

Après un rapport sans erreur, démarrer les services normalement. Le rôle
`analytics_readonly` continue d'accéder uniquement aux vues autorisées de cette
base.

Pour publier un futur recalcul du pipeline dans PostgreSQL, définir :

```bash
export PUBLISH_ANALYTICS_TO_POSTGRES=yes
export ANALYTICS_DATABASE_URL="$ADMIN_DATABASE_URL"
python -m src.storage.analytics_db
```

Cette publication remplace transactionnellement les faits analytiques et leurs
métadonnées. Elle conserve les données opérationnelles et les overrides manuels.
