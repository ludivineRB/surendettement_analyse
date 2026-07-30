# Service Django

Ce service gère les comptes, sessions, rôles et pages web. FastAPI reste
responsable des routes analytiques existantes.

## Variables requises

```bash
export DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/surendettement_local'
export DJANGO_SECRET_KEY='generate-a-long-random-local-value'
export DJANGO_DEBUG=true
export DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1'
```

Aucun secret ne doit être ajouté au dépôt.

## Développement local

```bash
pip install -r requirements.txt -r web/requirements.txt
python web/manage.py migrate
python web/manage.py runserver
```

L'accueil est disponible sur `http://127.0.0.1:8000/`, la connexion sur
`/accounts/login/`, le tableau de bord protégé sur `/dashboard/` et la santé
sur `/health/`.

Le tableau de bord utilise FastAPI via `ANALYTICS_API_BASE_URL` avec un délai
configurable par `ANALYTICS_API_TIMEOUT_SECONDS`. Sous Docker Compose, Django
démarre FastAPI comme dépendance, sans démarrer Streamlit.

Une personne disposant du rôle `viewer` peut filtrer les scores par niveau,
territoire, période et version du modèle, puis consulter la couverture, les
facteurs, l'évolution temporelle et les comparaisons.

## Docker Compose

Les variables locales sont lues depuis le fichier racine `.env`, exclu de Git.

```bash
docker compose \
  --env-file .env \
  -f docker/compose.yaml \
  -f docker/compose.staging.yaml \
  run --rm django python web/manage.py migrate

docker compose \
  --env-file .env \
  -f docker/compose.yaml \
  -f docker/compose.staging.yaml \
  up -d django
```

Créer ensuite un administrateur avec :

```bash
docker compose \
  --env-file .env \
  -f docker/compose.yaml \
  -f docker/compose.staging.yaml \
  run --rm django python web/manage.py createsuperuser
```

## Tests

Les tests Django utilisent PostgreSQL et créent une base de test jetable :

```bash
python web/manage.py test web
```

Les rôles initiaux sont `viewer`, `analyst` et `administrator`. Le score
présenté reste un indicateur statistique territorial et ne doit jamais servir
au diagnostic ou à la décision individuelle.

## Corpus documentaire RAG

Le corpus technique initial a été rejeté : les documents d'exploitation
Django et de validation PostgreSQL sont conservés pour audit, mais désactivés
et interdits de réingestion. Ils ne sont pas des sources métier.

Le futur corpus devra contenir uniquement des sources métier approuvées,
versionnées et traçables sur le surendettement et les indicateurs
macro-économiques. L'ingestion sera pilotée par l'API Assistant autonome.
