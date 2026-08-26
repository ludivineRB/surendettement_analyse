# Modèle logique de données

Le MLD traduit le MPD PostgreSQL en relations lisibles indépendamment du moteur.
Il ne remplace pas `physical/mpd.dbml`, qui reste la représentation exhaustive
des objets réellement déployés.

## Transformations appliquées

| MPD | MLD | Transformation |
|---|---|---|
| `dim_region`, `dim_department`, `dim_period` | région, département, période | noms métier et types génériques |
| `dim_indicator` | indicateur analytique | séparé du catalogue opérationnel `indicators` |
| `fact_bdf_statinfo`, `fact_insee_macro` | faits BDF et INSEE | clés métier composites conservées |
| `source_documents`, `observations` | document source, observation | champs HTTP/extraction secondaires masqués |
| tables `risk_score_*` | modèle, configuration, score, détail | structure et règles d'unicité conservées |
| tables `auth_*` | utilisateur, rôle, permission et associations | tables de jointure présentées comme associations N–N |
| tables `assistant_rag*` | source, document, version, fragment | préfixes Django retirés |
| `assistant.corpus_chunks` | fragment corpus Assistant | conservé séparément, car aucune équivalence n'est déclarée |
| vues, séquences et registres de migration | absents du MLD | objets techniques conservés uniquement dans le MPD |

Les champs de dates techniques, chemins, compteurs et rapports JSON sont
réduits lorsqu'ils ne portent pas la relation logique. Les JSON qui constituent
un contrat applicatif ou une information métier restent visibles.

## Relations structurantes

- Un document source produit zéro à plusieurs observations ; chaque observation
  référence exactement un document et un indicateur opérationnel.
- Un modèle de risque possède plusieurs configurations d'indicateur et produit
  plusieurs scores territoriaux.
- Un score contient plusieurs détails ; un détail peut référencer un indicateur
  et une observation source.
- Un utilisateur possède plusieurs conversations ; une conversation contient
  plusieurs messages.
- Un document RAG appartient à une source, possède plusieurs versions, et chaque
  version possède plusieurs fragments.
- Utilisateurs et rôles, rôles et permissions, ainsi qu'utilisateurs et
  permissions directes, sont des relations N–N via des tables de jointure
  uniques.

## Relations non matérialisées

La base contient des codes géographiques et temporels sans FK systématique :

- `dim_department.region_code` vers `dim_region.region_code` ;
- périodes des faits vers `dim_period` ;
- codes géographiques d'`observations` et `risk_scores` vers les dimensions ;
- `assistant.sql_executions.actor_id` vers un utilisateur.

Ces rapprochements sont plausibles mais non garantis par PostgreSQL. Ils ne sont
donc pas dessinés comme références dans le MLD et restent des hypothèses à
valider avant le MCD final.

## Règles logiques démontrées

- une observation est unique par `idempotence_key` ;
- un document source est unique par empreinte SHA-256 ;
- un modèle de risque est unique par `(code, version)` ;
- un score est unique par modèle, niveau, code géographique et période ;
- un détail est unique par score et code indicateur ;
- un fragment RAG Django est unique par version et ordinal ;
- les faits BDF et INSEE ont des clés métier uniques, bien que leur MPD n'utilise
  pas de PK déclarée pour ces combinaisons.

## Éléments volontairement séparés

Deux catalogues d'indicateurs (`dim_indicator`, `indicators`) coexistent et
restent distincts. Pour le RAG, `assistant.corpus_chunks` est le corpus canonique
actif ; `public.assistant_rag*` reste visible dans ce MLD détaillé uniquement
comme sous-modèle déprécié conservé pour audit.

Le fait et les deux vues de surendettement historiques sont exclus du diagramme
MLD principal mais restent recensés dans `inventory/objects.md` et dans le MPD.
