# Fiche méthodologique — score territorial 1.2.0

## Objet

Le score compare la vulnérabilité territoriale au surendettement. Il ne mesure
pas un risque individuel, ne constitue pas une probabilité et ne doit pas
servir à une décision de crédit.

## Indicateurs et pondérations

| Indicateur | Sens | Poids |
|---|---:|---:|
| Dossiers pour 1 000 habitants | positif | 30 % |
| Taux de chômage | positif | 20 % |
| Taux de pauvreté | positif | 20 % |
| Revenu médian | négatif | 15 % |
| Endettement moyen | positif | 10 % |
| Inflation | positif | 5 % |

Les poids absents sont redistribués proportionnellement. Un score est calculé
à partir de 60 % de couverture et reste `partial` tant que tous les indicateurs
ne sont pas disponibles.

## Normalisation

La version 1.2.0 applique un Min-Max winsorisé aux percentiles 5 et 95 de la
cohorte territoriale et de la période. Les valeurs extérieures sont bornées.
Cette méthode réduit l’effet des valeurs extrêmes, mais reste relative à chaque
période.

Une évolution future à bornes fixes doit utiliser la référence départementale
2023–2024 produite par `src.risk_score.sensitivity.build_reference_bounds`.
Elle devra porter un nouveau numéro de version : les scores 1.2.0 existants ne
seront pas réécrits.

## Sources

- Banque de France : baromètres mensuels et enquêtes typologiques annuelles.
- INSEE : IPC, recensement et Filosofi.
- Les variables annuelles répliquées mensuellement conservent leur année source
  dans `source_fragment`.

## Validation quantitative

Trois pondérations doivent être comparées : référence, poids égaux et poids
renforcé sur les dossiers. Les résultats à documenter sont la corrélation des
rangs, les changements de niveau, les écarts absolus et les territoires les
plus sensibles.

## Validation métier requise

- confirmer la définition de chaque indicateur et son unité ;
- confirmer les six pondérations ;
- valider les seuils des cinq niveaux de risque ;
- décider si les bornes fixes 2023–2024 sont représentatives ;
- vérifier les biais liés aux données annuelles et à l’inflation nationale ;
- approuver les usages autorisés et interdits.

La validation doit être datée, attribuée à un responsable métier et conservée
avec la version du modèle avant toute activation d’une méthode à bornes fixes.
