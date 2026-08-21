# Validation locale et GitHub Actions

La chaîne ne contient aucune étape de déploiement et n'utilise aucun secret de
production. GitHub Actions exécute `docker/run_ci.sh` sur une instance jetable.

Exécution locale :

```bash
python -m pip install -r requirements-ci.txt
sh docker/run_ci.sh
```

Les rapports JUnit, couverture, évaluation RAG hors ligne et validation
PostgreSQL sont produits sous `app/reports/`. GitHub Actions les publie comme
artefact `validation-reports-<run_id>` pendant 14 jours. Le projet Compose CI
est isolé par `COMPOSE_PROJECT_NAME` et ne supprime automatiquement aucun
volume local.

L'évaluation RAG de CI valide sans clé OpenAI le schéma du dataset versionné,
le routage, les méthodes attendues et les refus de sécurité :

```bash
python -m assistant_api.evaluation --offline \
  --output-dir app/reports/ci/rag
```

La recette générative complète reste un contrôle local. Elle appelle les
services démarrés, PostgreSQL et le fournisseur configuré dans `.env` :

```bash
set -a
source .env
set +a
python -m assistant_api.evaluation --base-url http://127.0.0.1:8030
```

Cette recette réelle vérifie aussi la disponibilité, les preuves, les
citations et les éditeurs officiels. Elle n'est pas exécutée dans GitHub
Actions et aucune clé OpenAI n'y est stockée.

Les images ne contiennent aucun fichier du dossier local `data/`. Pour tester
le chemin historique SQLite vers PostgreSQL, la CI génère une base synthétique
minimale sous `app/reports/ci-fixtures/` uniquement lorsque la source configurée
n'existe pas. Une source locale existante n'est jamais remplacée.

Contrôles couverts : lint, typage progressif, analyse Bandit, audit des
dépendances, tests Python/Django/FastAPI/RAG/Text-to-SQL, PostgreSQL jetable,
migrations, validation Compose et construction des trois images applicatives.
