# Validation locale et GitHub Actions

La chaîne ne contient aucune étape de déploiement et n'utilise aucun secret de
production. GitHub Actions exécute `docker/run_ci.sh` sur une instance jetable.

Exécution locale :

```bash
python -m pip install -r requirements-ci.txt
sh docker/run_ci.sh
```

Les rapports JUnit, couverture et validation PostgreSQL sont produits sous
`app/reports/`. Le projet Compose CI est isolé par `COMPOSE_PROJECT_NAME` et ne
supprime automatiquement aucun volume local.

Contrôles couverts : lint, typage progressif, analyse Bandit, audit des
dépendances, tests Python/Django/FastAPI/RAG/Text-to-SQL, PostgreSQL jetable,
migrations, validation Compose et construction des trois images applicatives.
