# MOT — Modèle organisationnel des traitements

Le MOT rattache chaque traitement à son composant, son déclenchement et ses
contrôles. Les fréquences non configurées explicitement sont indiquées « à la
demande » plutôt que supposées.

| Traitement | Responsable technique | Déclenchement observé | Entrée | Sortie / contrôle |
|---|---|---|---|---|
| Ingestion surendettement BDF | `src/surendettement_pipeline.py` | CLI / orchestration | sources structurées | jeu gold, profil et qualité |
| Ingestion Stat Info BDF | `src/statinfo_pipeline.py`, `src/statinfo_bi_pipeline.py` | CLI / orchestration | fichiers Stat Info | faits BDF et rapports métier |
| Normalisation générique | `src/processing/ingest.py` | appelée par pipeline | tableaux sources | colonnes et périodes normalisées |
| Ingestion INSEE | `src/insee_macro/pipeline.py` | année ou dernier millésime | Dossier complet | faits départementaux et rapport qualité |
| Dimensions conformes | `src/storage/conformed_dimensions.py` | migration explicite | SQLite opérationnel + analytique | dimensions et vues régionales |
| Orchestration | `src/pipeline_orchestrator.py` | CLI / à la demande | configurations de pipelines | statuts et quality gates |
| Import des indicateurs de risque | modules `src/risk_score/*_import.py` | CLI / migration | PDF, séries INSEE, mart analytique | observations idempotentes |
| Calcul des scores | `src/risk_score/service.py`, `cli.py` | API ou CLI | modèle + observations | scores, détails et validation |
| Publication analytique | `src/storage/analytics_db.py` | après construction | mart validé | SQLite et, si configuré, PostgreSQL |
| Migration opérationnelle | `src/storage/migrate_to_postgres.py` | commande explicite | SQLite | PostgreSQL, séquences réalignées |
| Migration analytique | `src/storage/migrate_analytics_to_postgres.py` | commande explicite | mart SQLite | tables/vues PostgreSQL |
| Provisionnement SQL readonly | `src/storage/configure_analytics_readonly.py` | exploitation | URL administrateur | rôle et privilèges minimaux |
| Ingestion RAG Django | commande `ingest_rag_corpus` | commande explicite | manifest approuvé | sources, versions, fragments |
| Recherche RAG Django | `web/assistant/search.py` | requête utilisateur | question | fragments classés |
| Agent SQL | service Assistant API | requête utilisateur | question + schéma autorisé | SQL validé, résultat et audit |
| Sauvegarde PostgreSQL | `docker/backup_postgres.sh` | exploitation | base PostgreSQL | dump de sauvegarde |
| Restauration | `docker/restore_postgres.sh` | exploitation contrôlée | dump | base restaurée |
| Test de restauration | `docker/test_restore_postgres.sh` | validation | sauvegarde | preuve de restaurabilité |
| Purge conversations | commande `purge_conversations` | exploitation / rétention | conversations anciennes | suppression contrôlée |
| Suppression utilisateur | commande `delete_user_data` | demande de confidentialité | utilisateur ciblé | effacement/cascade contrôlé |

## Séparation des responsabilités

- **Producteurs** : pipelines BDF/INSEE et imports de risque.
- **Contrôleurs** : quality gates, validations de score et tests de migration.
- **Stockages** : PostgreSQL opérationnel, entrepôt analytique et couches RAG.
- **Publicateurs** : vues analytiques et API.
- **Consommateurs** : Streamlit, Django, assistant RAG et agent SQL.
- **Exploitants** : sauvegarde, restauration, rôles readonly, rétention et
  observabilité.

## Contrôles organisationnels à formaliser

1. propriétaire métier de chaque indicateur et règle d'agrégation ;
2. fréquence cible et SLA de chaque ingestion ;
3. approbateur des rapports qualité avant publication ;
4. durée de conservation des sauvegardes et preuve périodique de restauration ;
5. durée de conservation des conversations et audits SQL ;
6. responsabilité de synchronisation des deux corpus RAG ;
7. politique de suppression des instances Docker temporaires.

Ces éléments ne sont pas déductibles du seul schéma et restent à valider avec
l'équipe. Le MOT ne leur attribue pas artificiellement de responsable humain.
