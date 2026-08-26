# MPD PostgreSQL

Le modèle physique de référence est généré directement depuis PostgreSQL :

- [MPD DBML interactif](mpd.dbml) ;
- [export SQL du schéma](../extracted/schema.sql) ;
- [métadonnées structurées](../extracted/metadata.json) ;
- [dictionnaire colonne par colonne](../dictionary/data-dictionary.md).

## Instance auditée

| Élément | Valeur |
|---|---|
| PostgreSQL | 16.14 |
| Base | `surendettement_staging` |
| Schémas | `public`, `assistant` |
| Tables | 40 |
| Vues | 12 |
| Séquences | 26 |
| Colonnes documentées | 445 |
| Contraintes | 107 |
| Index | 120 |
| FK | 31 |
| Triggers utilisateur | 0 |
| Vues matérialisées | 0 |
| Enums/domaines personnalisés | 0 |

## Séparation physique

### Schéma `public`

Il réunit actuellement plusieurs responsabilités :

- stockage opérationnel SQLAlchemy ;
- dimensions et faits analytiques ;
- scoring territorial ;
- vues de publication ;
- tables Django, comptes, conversations et corpus RAG.

Cette cohabitation est réelle et volontairement conservée dans le MPD. Les
domaines logiques ne doivent pas être interprétés comme des schémas PostgreSQL.

### Schéma `assistant`

Il contient le corpus plein texte canonique de l'Assistant API, l'audit des exécutions SQL
et son registre de migrations. Il est physiquement séparé de l'application
Django, dont les tables préfixées `assistant_` restent dans `public` mais dont
les cinq tables RAG sont dépréciées depuis le 25/08/2026.

## Stratégie d'identifiants

- tables SQLAlchemy opérationnelles : `integer` auto-incrémenté ;
- tables Django principales : `bigint` et séquences `BigAutoField` ;
- tables Django historiques d'authentification : `integer` auto-incrémenté ;
- dimensions : clés textuelles métier (`region_code`, `period_key`, etc.) ;
- faits BDF/INSEE : clés métier composites garanties par index uniques ;
- corpus Assistant : empreinte `character(64)` comme PK de fragment ;
- audit SQL : UUID comme PK et identifiant de requête.

## Intégrité et idempotence

| Domaine | Mécanisme principal |
|---|---|
| Documents | empreinte SHA-256 unique et version métier composite |
| Observations | `idempotence_key` unique |
| Faits BDF/INSEE | index uniques période/territoire/indicateur |
| Modèles de risque | unicité code/version |
| Scores | unicité modèle/territoire/période |
| Détails | unicité score/indicateur |
| RAG Django déprécié | document/empreinte et version/ordinal uniques, historique conservé |
| RAG Assistant canonique | PK d'empreinte et unicité source/ordinal/empreinte source |
| Corpus Assistant | source/ordinal/empreinte source unique |
| Migrations | version PK dans trois registres distincts |

Les contraintes `CHECK` encadrent notamment statuts, granularités, directions,
poids, scores et ratios de couverture. Le détail exact figure dans le DBML et
le dictionnaire.

## Types physiques notables

- `jsonb` pour citations et métadonnées de conversation Django ;
- `text` contenant du JSON pour plusieurs objets SQLAlchemy et l'audit SQL ;
- `tsvector` et index GIN pour les deux implémentations RAG ;
- `numeric(p,s)` pour scores, poids et contributions ;
- `timestamp with time zone` côté Django/Assistant ;
- dates ISO stockées en `varchar`/`text` dans plusieurs tables SQLAlchemy ;
- `real`/`double precision` dans l'entrepôt et les observations.

## Vues

Six vues `analytics_*` forment l'interface de publication en lecture. Quatre
vues `v_bdf_*`/`v_insee_*` portent les agrégations analytiques actives. Les deux
vues `v_surendettement_*` sont dépréciées mais conservées physiquement.

## Objets historiques et temporaires

Les objets historiques/dépréciés, y compris le corpus RAG Django remplacé par
`assistant.corpus_chunks`, sont listés dans
`../inventory/objects.md`. Les instances Docker temporaires, leur contenu et la
raison de leur création sont recensés dans `../inventory/databases.md`; elles ne
sont pas fusionnées dans ce MPD de référence.

## Régénération

```bash
python3 -m src.storage.generate_database_docs
```

Le générateur interroge uniquement les catalogues, produit un ordre stable et
n'écrit le fichier que si son contenu change.
