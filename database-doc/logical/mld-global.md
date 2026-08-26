# MLD global simplifié

Ce MLD présente **18 objets logiques**, contre 52 objets dans le MPD. Il répond
à « comment les informations sont organisées ? » ; le MPD répond à « comment
PostgreSQL est implémenté ? ».

## Correspondance avec le MPD

| MLD global | Objets PostgreSQL rattachés | Transformation |
|---|---|---|
| `territoire` | `dim_region`, `dim_department`, codes des observations/scores | généralisation logique ; FK physiques incomplètes |
| `periode` | `dim_period` et périodes textuelles | normalisation logique ; correspondances non toutes contraintes |
| `indicateur` | `indicators`, `dim_indicator` | catalogue conceptuellement unifié ; correspondance à valider |
| `fait_analytique` | `fact_bdf_statinfo`, `fact_insee_macro`, `fact_macro_override` | union logique par source ; aucune fusion physique |
| `document_source` | `source_documents` | attributs HTTP et stockage masqués |
| `observation` | `observations` | attributs d'extraction secondaires masqués |
| `execution_pipeline` | `pipeline_runs`, `pipeline_metadata` | synthèse orchestration/qualité |
| scoring | quatre tables `risk_score_*` | relations conservées, JSON techniques masqués |
| `utilisateur`, `habilitation` | `auth_user`, groupes, permissions et jointures | infrastructure Django aplatie |
| conversation | `assistant_conversation*` | deux entités métier conservées |
| `document_rag`, `fragment_rag` | principalement `assistant.corpus_chunks` | corpus Assistant canonique ; tables `public.assistant_rag*` dépréciées |
| `execution_sql` | `assistant.sql_executions` | audit conservé, détails de modèle réduits |

## Éléments volontairement absents

- séquences, index techniques et registres de migrations ;
- tables Django d'administration, session et content types ;
- vues PostgreSQL de publication ;
- objets historiques ou dépréciés ;
- chemins, ETag, compteurs techniques et JSON sans rôle relationnel majeur.

Ils restent présents dans le MPD, le MLD détaillé et le dictionnaire.

## Relations logiques à valider

Certaines références du DBML global montrent l'organisation logique sans
prétendre qu'une FK PostgreSQL existe :

- territoire avec observations, faits et scores ;
- période avec observations, faits et scores ;
- catalogue unifié d'indicateurs ;
- document logique et fragments du corpus canonique Assistant API.

Le regroupement initial des deux implémentations RAG n'est plus retenu comme
cible : le corpus Django est déprécié depuis le 25/08/2026 et conservé seulement
pour audit. Le MLD global représente désormais le corpus Assistant API actif.

Les FK certaines restent détaillées dans `physical/mpd.dbml`. Toute migration
physique éventuelle nécessiterait une demande distincte.

## Trois niveaux désormais disponibles

| Fichier | Usage |
|---|---|
| `physical/mpd.dbml` | audit PostgreSQL exhaustif |
| `logical/mld.dbml` | MLD relationnel détaillé |
| `logical/mld-global.dbml` | lecture fonctionnelle synthétique |
