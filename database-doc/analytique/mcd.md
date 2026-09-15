# MCD analytique

Le MCD est découpé en trois vues pour éviter un diagramme unique illisible.
Les fichiers bruts restent hors de PostgreSQL ; leur provenance est enregistrée
dans les documents sources et les exécutions de pipeline.

## 1. Acquisition et traçabilité

```mermaid
flowchart LR
    PRODUCTEUR["Producteur<br/>Banque de France ou INSEE"]
    LOT["Lot brut<br/>PDF, CSV, ZIP ou réponse API"]
    EXECUTION["Exécution du pipeline<br/>statut et rapport qualité"]
    DOCUMENT["Document source<br/>empreinte, période et territoire"]
    OBSERVATION["Observation<br/>valeur extraite et confiance"]
    INDICATEUR["Indicateur<br/>code, libellé et unité"]

    PRODUCTEUR -->|"publie 0..n"| LOT
    EXECUTION -->|"collecte et contrôle 0..n"| LOT
    LOT -->|"est tracé par 0..1"| DOCUMENT
    DOCUMENT -->|"produit 0..n"| OBSERVATION
    INDICATEUR -->|"qualifie 0..n"| OBSERVATION
```

## 2. Mart analytique et agrégations

```mermaid
flowchart LR
    SOURCE["Donnée préparée<br/>curated ou gold"]
    PERIODE["Période<br/>mois ou année"]
    TERRITOIRE["Territoire<br/>département ou région"]
    INDICATEUR["Indicateur analytique<br/>source et règle d’agrégation"]
    FAIT["Fait analytique<br/>une valeur au grain source"]
    AGREGAT["Agrégat régional<br/>somme ou ratio dérivé"]

    SOURCE -->|"alimente 0..n"| FAIT
    PERIODE -->|"date 0..n"| FAIT
    TERRITOIRE -->|"localise 0..n"| FA
    INDICATEUR -->|"qualifie 0..n"| FAIT
    FAIT -->|"contribue à 0..n"| AGREGAT
```

## 3. Scoring et publication

```mermaid
flowchart LR
    OBSERVATION["Observation territoriale"]
    MODELE["Modèle de score<br/>code et version"]
    PARAMETRE["Paramètre d’indicateur<br/>poids, direction, normalisation"]
    SCORE["Score territorial<br/>score, couverture et statut"]
    CONTRIBUTION["Contribution au score<br/>valeur normalisée et poids"]
    VUE["Vue analytique finale<br/>interface en lecture seule"]
    CONSOMMATEUR["API, Django<br/>ou assistant SQL"]

    MODELE -->|"possède 1..n"| PARAMETRE
    MODELE -->|"calcule 0..n"| SCORE
    OBSERVATION -->|"alimente 0..n"| CONTRIBUTION
    PARAMETRE -->|"détermine 0..n"| CONTRIBUTION
    SCORE -->|"est expliqué par 1..n"| CONTRIBUTION
    OBSERVATION -->|"est publiée dans"| VUE
    SCORE -->|"est publié dans"| VUE
    VUE -->|"est consultée par"| CONSOMMATEUR
```

## Cardinalités importantes

| Source | Cardinalité | Cible | Règle |
|---|---:|---|---|
| Document source | 1 → 0..n | Observation | une observation possède exactement un document |
| Indicateur | 1 → 0..n | Observation | une observation possède exactement un indicateur |
| Modèle de score | 1 → 1..n | Paramètre | chaque modèle définit ses indicateurs pondérés |
| Modèle de score | 1 → 0..n | Score | un score appartient à une version de modèle |
| Score | 1 → 1..n | Contribution | les contributions expliquent le résultat |
| Vue finale | 1 → 0..n | Consommateur | la vue ne stocke aucune donnée propre |

