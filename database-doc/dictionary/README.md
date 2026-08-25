# Dictionnaire de données

Le fichier [data-dictionary.md](data-dictionary.md) est généré automatiquement
depuis les catalogues PostgreSQL par :

```bash
python3 -m src.storage.generate_database_docs
```

## Principes

- les noms, types, nullabilités, PK, FK, contraintes uniques, contrôles et
  valeurs par défaut proviennent de PostgreSQL ;
- la source, la définition, la sensibilité et le statut sont classés selon des
  règles versionnées dans le générateur ;
- aucune ligne métier n'est lue ;
- aucune valeur fictive n'est créée pour remplir la colonne « Exemple » ;
- une valeur par défaut PostgreSQL peut servir d'exemple structurel réel ;
- les vues sont incluses, même si leurs colonnes ne portent pas directement les
  contraintes de leurs tables sources.

## Niveaux de sensibilité

| Niveau | Usage documentaire |
|---|---|
| Public | statistiques agrégées, référentiels et publications publiques |
| Interne | configuration, exploitation, corpus ou métadonnées applicatives |
| Personnel | donnée rattachable à un utilisateur |
| Sensible | authentification, session ou contenu conversationnel libre |
| Potentiellement personnel/sensible | question ou SQL libre dont le contenu dépend de l'utilisateur |

La classification est prudente : elle décrit le risque possible du champ, pas
le contenu réel des lignes. Une revue métier et une revue RGPD restent requises.

## Maintenance

Après chaque migration PostgreSQL :

1. régénérer la documentation ;
2. vérifier le diff de `metadata.json`, du MPD et du dictionnaire ;
3. compléter les définitions métier trop génériques dans les règles du
   générateur, pas directement dans le fichier généré ;
4. valider les changements de source, sensibilité et statut ;
5. faire relire les changements par le propriétaire technique et le référent
   métier du domaine.
