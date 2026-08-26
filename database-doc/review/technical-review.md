# Revue technique de la documentation des données

Revue réalisée le 26 août 2026 sur la base PostgreSQL
`surendettement_staging`, schémas `public` et `assistant`.

## Conclusion

Le lot documentaire est **prêt pour validation**. Les anomalies encore ouvertes
sont décrites dans [gaps.md](gaps.md) et ne sont pas corrigées dans ce lot,
conformément au périmètre. Elles ne remettent pas en cause la fidélité du MPD à
la base auditée.

## Contrôles réalisés

| Critère | Résultat | Preuve |
|---|---|---|
| Toutes les tables actives figurent dans le MPD | Conforme | 40 tables couvertes dans `physical/mpd.dbml` et `mapping/models-to-tables.md` |
| PK, FK, contraintes et index sont documentés | Conforme | extraction des catalogues PostgreSQL et `physical/mpd.md` |
| Objets PostgreSQL et migrations recensés | Conforme | `inventory/objects.md` et `inventory/migrations.md` |
| MCD, MLD et cardinalités importantes disponibles | Conforme avec hypothèses signalées | `conceptual/` et `logical/` |
| Domaines opérationnels, analytiques et applicatifs distingués | Conforme | `domains/README.md` et diagramme global |
| Modèles SQLAlchemy et Django rattachés aux tables | Conforme | `mapping/models-to-tables.md` |
| Tables temporaires et raison de leur présence documentées | Conforme | `inventory/databases.md` ; ce sont des instances Docker de validation, pas des tables SQL `TEMP` |
| Objets historiques et dépréciés signalés | Conforme | `inventory/objects.md`, dont l'ancien corpus RAG Django |
| Sensibilité des données identifiée | Conforme | `dictionary/data-dictionary.md` |
| Diagrammes textuels et rendus consultables | Conforme | sources Mermaid/DBML et rendus SVG |
| Régénération reproductible et sans lecture métier | Conforme | `src/storage/generate_database_docs.py` interroge uniquement les catalogues |
| Écarts code/documentation/base explicités | Conforme | `review/gaps.md` |

## Réserves acceptées

Les écarts `GAP-03`, `GAP-04`, `GAP-05`, `GAP-06`, `GAP-09`, `GAP-14` et
`GAP-15` restent ouverts faute de preuve ou parce qu'ils demandent une décision
d'architecture. Ils doivent être instruits séparément ; aucune relation ni règle
métier n'a été inventée pour les fermer.

## Validation fonctionnelle

Après application de la migration de dépréciation du corpus RAG historique,
l'application Django et ses pages Assistant ont été testées manuellement le
26 août 2026 et déclarées fonctionnelles par le demandeur.

Contrôles automatisés exécutés le même jour :

- deux exécutions successives de `python3 -m src.storage.generate_database_docs` :
  aucun changement des quatre artefacts générés ;
- `python web/manage.py test assistant` dans le conteneur Django : 17 tests
  réussis, aucun échec et aucun problème détecté par le contrôle système Django.

## Texte proposé pour la Pull Request

```text
Documente l'architecture des données PostgreSQL : inventaires, MPD, MLD, MCD,
dictionnaire, traitements, flux, domaines, écarts et environnements temporaires.

Déprécie officiellement l'ancien corpus RAG Django au profit de
assistant.corpus_chunks, sans supprimer les tables historiques.

Refs #17
```

La Pull Request ne doit employer ni `Closes #17` ni `Fixes #17` avant la
validation de la documentation.
