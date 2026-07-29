# Score territorial de risque de surendettement

Ce module calcule un indice statistique explicable entre 0 et 100 par territoire
et période. Il s'agit d'un outil d'aide à l'analyse territoriale, et non d'une
décision individuelle de crédit ou d'une mesure certaine du risque d'une
personne.

## Modèle

Les tables `risk_score_models` et `risk_score_indicator_configs` versionnent la
méthode, les correspondances, les poids, le sens des indicateurs et le seuil de
couverture. Les tables `risk_scores` et `risk_score_details` stockent les
résultats et chaque contribution.

La version initiale utilise Min-Max entre territoires du même niveau, de la
même période et du même indicateur :

- sens `positive` : `(valeur - min) / (max - min)` ;
- sens `negative` : `1 - ((valeur - min) / (max - min))` ;
- si `min == max` : `0.5`.

Les poids disponibles sont renormalisés. La contribution en points vaut
`valeur_normalisée × poids_effectif × 100`. Aucun score valide n'est produit
sous 60 % de couverture. Les indicateurs absents ne sont pas imputés.

## Sélection des observations

Pour un territoire, une période et un indicateur, la sélection privilégie :

1. le meilleur `confidence_score` ;
2. le document le plus récemment mis à jour ;
3. l'observation la plus récemment créée ;
4. l'identifiant le plus élevé.

Les unités incompatibles, valeurs non finies et codes géographiques absents
sont ignorés avec avertissement.

Les traitements internes sélectionnent désormais les indicateurs par
`indicator_id`. Le champ `indicator_code` reste dénormalisé dans
`observations` pour préserver les contrats API ; des déclencheurs SQL refusent
toute divergence entre les deux champs.

## Dimensions conformes

Les bases analytique et opérationnelle partagent le même contrat :

- `dim_region(region_code, region_name)` ;
- `dim_period(period_key, reference_year, reference_month_number, granularity)`.

`dim_department.region_code` porte le rapprochement technique avec la région.
Les vues macro régionales exposent toujours `region_name` pour compatibilité,
mais leurs jointures et ratios utilisent `region_code`.

La migration idempotente s'exécute avec :

```bash
.venv/bin/python -m src.storage.conformed_dimensions
```

`fact_surendettement` et ses deux vues historiques sont conservés, mais inscrits
dans `schema_deprecations`. `fact_macro_override` possède des clés étrangères
physiques vers les dimensions période, département et indicateur.

## Migration et mapping

Le dépôt n'utilise pas Alembic. La migration idempotente repose sur les
métadonnées SQLAlchemy existantes :

```bash
.venv/bin/python -m src.risk_score.cli migrate
```

Le seed crée `default` version `1.0.0`. Les correspondances ambiguës restent
volontairement non résolues. Copier puis compléter
`src/risk_score/default_mapping.example.json` avec les codes réels :

```bash
.venv/bin/python -m src.risk_score.cli seed --mapping-json mapping.json
```

Créer une nouvelle version consiste à ajouter une spécification versionnée et à
désactiver explicitement la précédente ; une seule version active est chargée
par code.

## Passerelle analytique v1

```bash
.venv/bin/python -m src.risk_score.cli bridge-analytics --dry-run
.venv/bin/python -m src.risk_score.cli bridge-analytics
```

La passerelle calcule le taux de chômage départemental et régional à partir de
`P22_CHOM1564 / P22_ACT1564 × 100`. Elle calcule aussi, au niveau régional,
les dossiers mensuels pour 1 000 habitants.

Le dernier millésime INSEE antérieur ou égal au mois cible est propagé. Son
année et la version `risk-score-analytics-bridge-v1` restent inscrites dans la
provenance. La commande est idempotente et ne modifie pas les données sources.

Elle active `default` version `1.1.0`. La couverture reste volontairement à
50 % en région et 20 % en département avant l'import Filosofi.

## Revenus et pauvreté — Filosofi 2021

La source officielle est le fichier Insee « Principaux indicateurs sur les
revenus et la pauvreté aux niveaux national et local en 2021 » :
<https://www.insee.fr/fr/statistiques/7756729>.

```bash
.venv/bin/python -m src.risk_score.cli import-filosofi \
  --source-zip /chemin/base-cc-filosofi-2021-geo2025_csv.zip \
  --dry-run
.venv/bin/python -m src.risk_score.cli import-filosofi \
  --source-zip /chemin/base-cc-filosofi-2021-geo2025_csv.zip
```

L'import utilise les valeurs publiées `PR_MD60` (taux de pauvreté) et `MED_SL`
(niveau de vie médian). Elles ne sont jamais sommées. Le millésime, l'URL et
l'empreinte SHA-256 de l'archive sont conservés. Après import, la couverture
est de 85 % en région et de 55 % en département. Les régions disposant d'un
nombre mensuel de dossiers obtiennent un score `partial`.

Les sources actuelles ne permettent toujours pas de fabriquer un taux
départemental de dossiers.

## Calculs

```bash
.venv/bin/python -m src.risk_score.cli calculate --level region --period 2025-06 --dry-run
.venv/bin/python -m src.risk_score.cli calculate --level department --period 2024
.venv/bin/python -m src.risk_score.cli calculate --level region --all-periods
.venv/bin/python -m src.risk_score.cli explain 1
```

Le mode `dry-run` n'écrit rien. Un recalcul persistant effectue un upsert et
remplace transactionnellement les détails précédents.

## API

- `GET /api/risk-score-models`
- `GET /api/risk-scores`
- `GET /api/risk-scores/{niveau}/{code}`
- `GET /api/risk-scores/{niveau}/{code}/{période}`
- `POST /api/risk-scores/calculate`

Les listes acceptent les filtres de niveau, code, période, modèle, niveau de
risque, pagination et tri `score_asc` ou `score_desc`.

## Import historique

```bash
.venv/bin/python -m src.risk_score.cli import-legacy --dry-run
.venv/bin/python -m src.risk_score.cli import-legacy
```

L'import de `surendettement_data` est idempotent, conserve `source_file` et
refuse les lignes sans code département explicite. La table historique n'est
jamais supprimée.

## Extension future

`RiskScoreCalculator` sépare chargement, normalisation, calcul et persistance.
Une future stratégie pourra remplacer Min-Max par percentiles, z-score, bornes
fixes ou winsorisation. Un futur moteur entraîné pourra implémenter régression,
Random Forest ou gradient boosting après constitution d'un historique fiable,
validation croisée temporelle et calibration. Aucune métrique ou performance
de modèle n'est simulée dans cette version.

## Limites actuelles

- Endettement moyen et inflation restent à importer.
- Le millésime INSEE actuellement disponible est 2022.
- Les dossiers de surendettement départementaux ne sont pas disponibles.
- Les comparaisons restent descriptives et dépendent de la qualité des sources.
