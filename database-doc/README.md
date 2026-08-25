# Architecture des données

La source de vérité du MPD est PostgreSQL 16, base `surendettement_staging`,
schémas `public` et `assistant`. Le générateur ne lit que les catalogues système :
aucune ligne métier, aucun mot de passe et aucune chaîne de connexion ne sont
écrits dans la documentation.

## Schémas directement consultables

- [MCD métier](diagrams/mcd.svg)
- [MLD global simplifié](diagrams/mld.svg)
- [Architecture globale et domaines](diagrams/global.svg)
- [Flux de données et traitements](diagrams/data-flow.svg)

Les fichiers `.mmd` correspondants restent les sources Mermaid versionnables.

## Régénération

Depuis la racine du dépôt :

```bash
python3 -m src.storage.generate_database_docs
```

Le résultat est trié avant écriture. Une seconde exécution sur un schéma
inchangé ne modifie donc pas le fichier généré.

## Niveaux de représentation

- ERD/MPD : objets PostgreSQL réellement présents, types, clés, contraintes,
  index et relations.
- MLD : vue relationnelle simplifiée, sans détails propres à PostgreSQL.
- MCD : concepts métier, associations et cardinalités déductibles ; toute règle
  non démontrée sera marquée « Hypothèse à valider ».

## Environnements temporaires observés

Ces objets sont des **instances PostgreSQL Docker persistantes de validation**,
pas des tables `TEMP` PostgreSQL. Ils restent inventoriés pour expliquer
l'historique technique, mais ne constituent pas la source du MPD de référence.

| Projet Docker | Créé le (UTC) | Schéma observé | Raison documentée ou déduite |
|---|---:|---|---|
| `surendettement_fix_validation` | 2026-08-24 | 12 tables, 6 vues | Validation d'une correction et de la vue analytique macro-régionale ; hypothèse déduite du nom et de l'écart de vue. |
| `surendettement_analytics_final` | 2026-08-21 | 12 tables, 5 vues | Validation finale de la publication analytique PostgreSQL ; cohérent avec `migrate_analytics_to_postgres.py`. |
| `surendettement_analytics_pg_test2` | 2026-08-21 | 10 tables, 6 vues | Deuxième essai de migration du mart analytique SQLite vers PostgreSQL. |
| `surendettement_analytics_pg_test` | 2026-08-21 | 10 tables, aucune vue | Premier essai, avant création des vues analytiques ; hypothèse déduite de l'état du schéma. |
| `surendettement_ci_nodata_final` | 2026-08-21 | 12 tables, 5 vues | Validation CI d'un schéma sans reprise de données métier. |
| `surendettement_ci_validation_final` | 2026-08-19 | 12 tables, 5 vues | Validation finale de la migration opérationnelle en CI. |
| `surendettement_ci_validation` | 2026-08-19 | base configurée absente | Première validation abandonnée ou incomplète ; hypothèse à valider. |

Toutes ces instances proviennent de `docker/compose.yaml`, parfois complété par
`docker/compose.staging.yaml`. Leur multiplication correspond à des projets
Compose nommés différemment afin d'isoler les volumes et d'éviter qu'un test de
migration altère une autre base. Leur conservation après validation explique
leur présence simultanée ; le dépôt ne documente pas encore de politique de
nettoyage de ces volumes.

## État initial audité

- Base active : 40 tables (`public`: 37, `assistant`: 3), 12 vues et 26 séquences.
- Migrations : 4 opérationnelles, 2 assistant SQL et 23 Django appliquées.
- Dépréciés : `fact_surendettement`, `v_surendettement_annual` et
  `v_surendettement_with_insee_macro`.
- Écart à suivre : deux stockages RAG coexistent (`public.assistant_rag*` et
  `assistant.corpus_chunks`).

Les inventaires détaillés, MLD, MCD, dictionnaire, flux et règles de maintenance
seront ajoutés par lots courts après validation du MPD initial.
