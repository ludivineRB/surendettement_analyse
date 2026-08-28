# Lot 19 — Feuille finale de validation

## Périmètre

Modélisation Merise et préparation de la conformité RGPD du projet
Surendettement.

## Synthèse

| Domaine | Livrable ou preuve | Statut |
|---|---|---|
| MCD/MLD/MPD | modèles conceptuel, logique et physique dans `database-doc` | validable |
| MCT/MOT | traitements et organisation documentés | validable |
| Dictionnaire | 445 colonnes et sensibilités recensées | disponible |
| Écarts Merise | écarts ouverts explicitement suivis | à accepter ou planifier |
| Qualification RGPD | aucune catégorie de l'article 9 démontrée ; risque dans les champs libres | documenté |
| Gouvernance | Ludivine Raby, responsable et contact provisoire | validé provisoirement |
| DPO | Ludivine Raby proposée | réserve : conflit d'intérêts à analyser |
| Finalités et bases | registre complété | validé ; test d'intérêt légitime à conserver |
| Conservation | 90 jours conversations, 6 mois audits, 24 mois comptes inactifs | politique retenue, automatisation à vérifier |
| Acteurs et flux | recensement dépôt/OpenAI/sources/observabilité | hébergeur et contrats à compléter |
| Information users | mention complète et avertissement préparés | publication dans l'interface requise |
| Droits | suppression utilisateur et purge existantes | tests d'exécution requis |

## Décisions enregistrées

- Responsable du traitement et contact : Ludivine Raby,
  `ludivine.raby@gmail.com`.
- Révision obligatoire de la gouvernance avant toute intégration à Sofinco.
- Finalités et bases légales du registre acceptées.
- Durées usuelles adaptées au projet retenues comme politique initiale.
- Avertissement obligatoire à proximité des champs libres.
- Aucune donnée de l'article 9 ne doit être collectée intentionnellement sans
  analyse et autorisation spécifiques.

## Conditions restantes avant clôture complète

1. publier la mention d'information et l'avertissement dans Django ;
2. tester les purges à 90 jours, l'effacement utilisateur et l'anonymisation de
   l'audit SQL ;
3. automatiser ou documenter la purge des audits SQL à 6 mois ;
4. identifier l'hébergeur et vérifier le DPA, la région et les transferts OpenAI ;
5. documenter le test de mise en balance de l'intérêt légitime ;
6. statuer sur le conflit d'intérêts DPO/responsable du traitement ;
7. faire accepter les écarts Merise encore ouverts.

## Avis de validation

**Validation documentaire proposée avec réserves.** Le lot ne peut être déclaré
pleinement opérationnel tant que les sept conditions ci-dessus ne sont pas
levées ou acceptées dans un plan d'actions daté.

| Rôle | Nom | Décision | Date |
|---|---|---|---|
| Responsable du traitement | Ludivine Raby | À signer | — |
| Référent métier | Ludivine Raby | À signer | — |
| Relecteur technique | À désigner | À signer | — |
| DPO indépendant ou suppléant | À déterminer si nécessaire | À signer | — |

