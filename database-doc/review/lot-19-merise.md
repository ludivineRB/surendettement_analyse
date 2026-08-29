# Lot 19 — Validation de la modélisation Merise

## Objet

Le lot 19 s'appuie sur la documentation de données existante, dérivée du schéma
PostgreSQL de référence sans lecture des lignes métier. Il ne crée pas un second
modèle concurrent.

## Livrables de référence

| Niveau | Livrable | Statut |
|---|---|---|
| MCD | [`conceptual/mcd.md`](../conceptual/mcd.md) et source Mermaid | disponible |
| MLD | [`logical/mld.md`](../logical/mld.md) et DBML | disponible |
| MPD | [`physical/mpd.md`](../physical/mpd.md), DBML et export SQL | disponible |
| MCT | [`treatments/mct.md`](../treatments/mct.md) | disponible |
| MOT | [`treatments/mot.md`](../treatments/mot.md) | disponible |
| Dictionnaire | [`dictionary/data-dictionary.md`](../dictionary/data-dictionary.md) | disponible |
| Correspondances | [`mapping/models-to-tables.md`](../mapping/models-to-tables.md) | disponible |
| Revue | [`review/technical-review.md`](technical-review.md) | prêt pour validation |

## Preuves couvertes

- 40 tables, 12 vues, 26 séquences et 445 colonnes documentées sur PostgreSQL 16 ;
- clés, contraintes, index et relations extraits des catalogues PostgreSQL ;
- cardinalités démontrées séparées des hypothèses métier ;
- domaines opérationnel, analytique, Django et Assistant distingués ;
- objets historiques et dépréciés explicitement signalés ;
- génération reproductible par `src.storage.generate_database_docs`.

## Réserves à conserver

Les écarts ouverts sont suivis dans [`gaps.md`](gaps.md). Ils concernent
principalement l'intégrité région–département, les périodes et codes
géographiques non systématiquement contraints, le lignage des pipelines et la
gouvernance des migrations. Ils ne doivent pas être fermés sans preuve.

## Critère de clôture

Le volet Merise du lot 19 pourra être déclaré validé après revue métier des
cardinalités proposées et acceptation explicite des écarts ouverts. Le MPD
physique, déjà contrôlé contre la base auditée, constitue la preuve technique de
référence.

