# Modèle conceptuel de données

Ce MCD décrit les concepts métier sans reprendre les types PostgreSQL ni les
champs purement techniques. Il est dérivé du schéma observé le 25 août 2026.

## Convention de cardinalité

- `(0,N)` : aucun ou plusieurs ;
- `(1,N)` : au moins un ou plusieurs ;
- `(0,1)` : association facultative vers une occurrence au plus ;
- `(1,1)` : association obligatoire vers une occurrence unique.

Une FK non nullable démontre `(1,1)` du côté de l'objet porteur. En revanche,
elle ne prouve généralement pas qu'un parent possède au moins un enfant : le
côté parent est donc `(0,N)`. Une suppression en cascade ne change pas la
cardinalité d'existence.

## Acquisition et observations

```text
DOCUMENT_SOURCE (0,N) ── PRODUIT ── (1,1) OBSERVATION
INDICATEUR      (0,N) ── QUALIFIE ─ (1,1) OBSERVATION
```

### DOCUMENT_SOURCE

Propriétés principales : source, type de publication, région déclarée, période
de référence, empreinte, emplacement et statut d'extraction.

Règles démontrées :

- une empreinte de document est unique ;
- la version métier est unique par type de publication, région, période et
  empreinte ;
- un document peut exister avant qu'une observation soit extraite.

### INDICATEUR

Propriétés principales : code, libellé, catégorie, description et unité.
Le code est unique dans le catalogue opérationnel.

### OBSERVATION

Propriétés principales : niveau et code géographiques, période, valeur numérique
ou textuelle, unité, variation, méthode d'extraction et confiance.

Règle démontrée : la clé d'idempotence est unique. La base n'impose pas qu'une
et une seule des deux valeurs, numérique ou textuelle, soit renseignée.

## Scoring territorial

```text
MODELE_RISQUE (0,N) ── CONFIGURE ─────── (1,1) CONFIGURATION_INDICATEUR
INDICATEUR    (0,N) ── EST_CONFIGURE ─── (0,1) CONFIGURATION_INDICATEUR
MODELE_RISQUE (0,N) ── PRODUIT ───────── (1,1) SCORE_TERRITORIAL
SCORE_TERRITORIAL (0,N) ── DETAILLE ──── (1,1) DETAIL_SCORE
INDICATEUR    (0,N) ── EXPLIQUE ──────── (0,1) DETAIL_SCORE
OBSERVATION   (0,N) ── JUSTIFIE ──────── (0,1) DETAIL_SCORE
```

`CONFIGURATION_INDICATEUR` et `DETAIL_SCORE` sont des associations porteuses de
propriétés : poids, direction et normalisation pour la première ; valeur brute,
poids effectif et contribution pour la seconde.

Règles démontrées :

- un modèle est unique par code et version ;
- une configuration est unique par modèle et code indicateur ;
- un score est unique par modèle, niveau, territoire et période ;
- un détail est unique par score et code indicateur ;
- score et couverture sont bornés par contraintes PostgreSQL.

Le lien d'une configuration ou d'un détail vers le catalogue INDICATEUR est
facultatif : le code textuel reste obligatoire même lorsque la FK est absente.

## Référentiels et faits analytiques

```text
DEPARTEMENT (0,N) ── LOCALISE ── (1,1) FAIT_BDF
INDICATEUR_ANALYTIQUE (0,N) ── MESURE ── (1,1) FAIT_BDF
DEPARTEMENT (0,N) ── LOCALISE ── (1,1) FAIT_INSEE
INDICATEUR_ANALYTIQUE (0,N) ── MESURE ── (1,1) FAIT_INSEE
PERIODE (0,N) ── DATE ── (1,1) CORRECTION_MACRO
DEPARTEMENT (0,N) ── LOCALISE ── (1,1) CORRECTION_MACRO
INDICATEUR_ANALYTIQUE (0,N) ── CORRIGE ── (1,1) CORRECTION_MACRO
```

La correction macro porte une valeur et une justification. Les faits BDF et
INSEE sont uniques par période/année, département et indicateur.

La relation `REGION ── DEPARTEMENT` est attendue fonctionnellement, mais
`dim_department.region_code` ne possède pas de FK vers `dim_region`. Sa
cardinalité métier est donc une **Hypothèse à valider**. Il en va de même pour
les périodes des faits analytiques qui ne référencent pas toujours `dim_period`.

## Utilisateurs, rôles et conversations

```text
UTILISATEUR (0,N) ── APPARTIENT ── (0,N) ROLE
ROLE        (0,N) ── ACCORDE ───── (0,N) PERMISSION
UTILISATEUR (0,N) ── RECOIT_DIRECTEMENT ── (0,N) PERMISSION
UTILISATEUR (0,N) ── OUVRE ─────── (1,1) CONVERSATION
CONVERSATION (0,N) ── CONTIENT ─── (1,1) MESSAGE
```

Les trois associations N–N sont matérialisées par des tables de jointure avec
unicité de chaque paire. La base permet techniquement une conversation sans
message, d'où `(0,N)` côté conversation.

Le titre, le contenu, les citations, le SQL généré et les métadonnées de réponse
peuvent contenir des informations personnelles ou sensibles. `auth_user`
contient également identifiant, courriel, nom, prénom et mot de passe haché.

## Corpus RAG Django — déprécié

```text
SOURCE_RAG (0,N) ── PUBLIE ── (1,1) DOCUMENT_RAG
DOCUMENT_RAG (0,N) ── VERSIONNE ── (1,1) VERSION_DOCUMENT_RAG
VERSION_DOCUMENT_RAG (0,N) ── DECOUPE ── (1,1) FRAGMENT_RAG
```

La base autorise une source sans document, un document sans version et une
version sans fragment. Une version est unique par document et empreinte ; un
fragment est unique par version et ordinal. Ce sous-modèle est conservé pour
audit mais officiellement déprécié depuis le 25/08/2026. Aucune nouvelle
indexation ne doit l'alimenter hors dérogation explicite.

## Assistant SQL et second corpus

`FRAGMENT_CORPUS_ASSISTANT` est désormais le concept RAG canonique et
`EXECUTION_SQL` porte l'audit autonome du schéma `assistant`. `actor_id` est
facultatif et textuel : aucune association physique avec UTILISATEUR ne peut
être affirmée.

Il n'existe aucune synchronisation démontrée entre `FRAGMENT_CORPUS_ASSISTANT`
et le `FRAGMENT_RAG` Django déprécié. Les deux concepts restent séparés afin de
ne pas inventer un lignage absent.

## Exécution des traitements

`EXECUTION_PIPELINE` représente une exécution nommée, son statut, sa
configuration, ses résultats d'étapes, son rapport qualité et son erreur
éventuelle. Aucune FK ne rattache une exécution aux documents, observations ou
scores produits : ces associations opérationnelles ne peuvent pas être ajoutées
au MCD comme règles démontrées.

## Hypothèses à valider

1. Toute région possède des départements et tout département appartient à une
   région existante.
2. Les périodes textuelles des observations, faits et scores correspondent à
   une occurrence de PERIODE.
3. Les codes géographiques des observations et scores correspondent aux
   référentiels région/département.
4. `execution_sql.actor_id` identifie un utilisateur Django.
5. Une exécution de pipeline peut être reliée aux objets qu'elle produit.
