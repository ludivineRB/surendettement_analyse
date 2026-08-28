# Lot 19 — Analyse et règles RGPD

## Gouvernance provisoire

- **Responsable du traitement et contact RGPD** : Ludivine Raby —
  `ludivine.raby@gmail.com`.
- **DPO proposé pour le projet** : Ludivine Raby, à titre provisoire.
- **Évolution prévue** : si le projet est intégré à Sofinco, le responsable du
  traitement, le partage éventuel des responsabilités, le DPO et le contact
  devront être réévalués avant la reprise des traitements.

Le cumul entre décision sur les finalités/moyens et contrôle indépendant de
leur conformité crée un risque de conflit d'intérêts. La qualification « DPO »
doit donc être revue avant toute désignation formelle ; dans l'intervalle,
Ludivine Raby reste le point de contact RGPD et la responsable des décisions.

## 1. Conclusion de qualification

À la date de l'audit, aucune **catégorie particulière de données personnelles**
au sens de l'article 9 du RGPD n'est démontrée dans les colonnes structurées du
projet. Les indicateurs de surendettement et les scores sont territoriaux et
agrégés : ils ne décrivent pas la situation financière d'une personne physique
identifiée ou identifiable.

Le système traite néanmoins des **données personnelles ordinaires** : comptes
Django, noms, identifiants, courriels, sessions, journaux d'administration,
conversations et identifiants d'acteur. Les mots de passe hachés et sessions
sont critiques pour la sécurité, sans devenir pour autant des catégories
particulières de l'article 9.

Les champs libres — messages, questions, SQL, interprétations et documents RAG —
peuvent contenir des données personnelles et peuvent révéler une catégorie de
l'article 9. Leur contenu n'a pas été lu pendant l'audit : ce risque est
possible, mais sa présence effective n'est pas prouvée.

Les données relatives aux condamnations et infractions relèvent de l'article 10,
distinct de l'article 9. Aucune colonne structurée de cette nature n'est
identifiée actuellement.

## 2. Classification documentaire

| Classe | Définition dans ce projet | Exemples | Régime attendu |
|---|---|---|---|
| Public/agrégé | aucune personne identifiable | statistiques territoriales, dimensions | intégrité et traçabilité des sources |
| Interne | donnée technique non destinée au public | configuration, métadonnées pipeline | accès limité selon le besoin |
| Personnel | personne directement ou indirectement identifiable | nom, courriel, identifiant, conversation | ensemble des principes RGPD |
| Sécurité critique | secret ou donnée permettant un accès | mot de passe haché, session, jeton | protection renforcée ; ce n'est pas une classe de l'article 9 |
| Article 9 potentiel | champ libre pouvant révéler santé, opinions, religion, syndicat, origine, biométrie/génétique, vie ou orientation sexuelle | message ou document libre | collecte évitée ; traitement exceptionnel et justifié |

## 3. Règles RGPD proposées

Ces règles deviennent opposables dans le projet après validation par le
responsable de traitement et, le cas échéant, le DPO.

### RGPD-01 — Minimisation

Ne collecter que les données nécessaires à une finalité documentée. Les données
territoriales ne doivent pas être enrichies par des identifiants individuels.

### RGPD-02 — Champs libres

Afficher une consigne interdisant la saisie de secrets et décourageant la saisie
de catégories de l'article 9. Ne pas réutiliser les conversations ou documents
pour une finalité non annoncée. Prévoir un signalement et un effacement ciblé.

### RGPD-03 — Journaux et audit SQL

Ne jamais journaliser mots de passe, jetons, cookies ou chaînes de connexion.
Préférer identifiants techniques, statuts et métriques au contenu complet. Si la
question ou le SQL est conservé, justifier cette nécessité et en limiter l'accès
et la durée.

### RGPD-04 — Habilitations

Appliquer le moindre privilège, séparer lecture analytique et administration,
réviser périodiquement les droits et tracer les accès administratifs.

### RGPD-05 — Conservation

Attribuer à chaque traitement une durée ou un critère de fin. Tester la purge
des sessions, conversations, audits SQL, journaux, sauvegardes et anciens corpus
RAG. Une durée non validée doit rester marquée « à définir », jamais supposée.

### RGPD-06 — Droits des personnes

Documenter un canal et une procédure pour l'accès, la rectification,
l'effacement, la limitation, l'opposition et, lorsqu'elle s'applique, la
portabilité. L'identité doit être vérifiée de façon proportionnée et les actions
doivent être traçables.

### RGPD-07 — Sécurité et violations

Protéger les secrets hors du code, chiffrer les flux, sécuriser les sauvegardes,
tester la restauration et formaliser la détection, l'évaluation et la
notification des violations de données.

### RGPD-08 — Catégories de l'article 9

Aucun traitement intentionnel de ces catégories n'est autorisé sans finalité,
base de l'article 6, exception applicable de l'article 9(2), mesures renforcées
et validation documentée. Une AIPD doit être évaluée si le traitement est
susceptible d'engendrer un risque élevé.

### RGPD-09 — Sous-traitants et transferts

Inventorier hébergeurs, fournisseurs de modèles, services externes et lieux de
traitement. Documenter les contrats, instructions, garanties et transferts hors
EEE éventuels.

### RGPD-10 — Protection dès la conception

Toute nouvelle table, source ou fonctionnalité doit préciser finalité,
catégories de données, personnes concernées, accès, conservation, suppression et
impact sur les droits avant sa mise en production.

## 4. Registre validé et politique de conservation initiale

| Traitement | Données | Finalité validée | Base légale retenue | Conservation retenue |
|---|---|---|---|---|
| Comptes et habilitations | identité, contact, rôles | fournir et sécuriser l'accès demandé | exécution du service demandé, art. 6(1)(b) ; intérêt légitime pour la sécurité, art. 6(1)(f) | vie du compte ; suppression après 24 mois d'inactivité, avec préavis |
| Conversations | titre, questions, réponses, citations | fournir l'assistant et son historique | exécution du service demandé, art. 6(1)(b) | 90 jours après la dernière activité, sauf suppression anticipée |
| Audit SQL | acteur, question, SQL, résultat technique | sécurité, diagnostic et traçabilité | intérêt légitime, art. 6(1)(f), sous réserve du test de mise en balance | 6 mois en base active, puis suppression ou anonymisation |
| Corpus RAG | sources, fragments, métadonnées | recherche documentaire sur un corpus approuvé | intérêt légitime, art. 6(1)(f), si une donnée personnelle est présente | durée d'approbation de la source ; revue annuelle ; retrait sous 30 jours après dépublication |
| Analyse territoriale | indicateurs publics agrégés | analyse et restitution territoriales | hors RGPD si l'agrégation empêche toute identification | selon licence et politique d'archivage de la source |

Ces durées constituent une politique proportionnée au projet, pas des délais
légaux propres à ce service. Elles seront réexaminées si le contexte ou
l'intégration à Sofinco change. Les sauvegardes contenant des données
personnelles auront une rétention glissante proposée de 30 jours. Les journaux
applicatifs auront une rétention proposée de 6 mois ; Prometheus et Loki sont
actuellement configurés à 15 jours.

## 5. Recensement des acteurs, destinataires et flux

| Acteur ou service | Rôle observé | Données reçues | Localisation/transfert | Décision requise |
|---|---|---|---|---|
| Ludivine Raby | responsable du traitement et contact provisoire | accès administratif potentiel | France présumée, à confirmer | documenter les habilitations |
| Utilisateurs habilités | personnes concernées et destinataires de leurs résultats | compte, conversations, résultats | selon accès | information et droits |
| Administrateurs techniques | exploitation et sécurité | comptes, journaux, sauvegardes selon habilitation | à recenser nominativement | matrice d'accès |
| OpenAI API | fournisseur de génération si la clé est configurée | instructions et question envoyées à `/v1/responses` | région et transferts à vérifier contractuellement | qualifier le rôle, contrôler le DPA et informer |
| Hébergeur PostgreSQL/Django | hébergement de production | comptes, conversations, audits, corpus | non identifiable dans le dépôt | renseigner entité, pays, contrat et mesures |
| Banque de France | source publique | aucune donnée utilisateur envoyée d'après le code | France | documenter les conditions des sources |
| INSEE et `geo.api.gouv.fr` | sources publiques | aucune donnée utilisateur envoyée d'après le code | France | documenter les conditions des sources |
| Grafana, Loki, Prometheus | observabilité auto-hébergée dans Docker | métriques et journaux techniques | infrastructure du projet | vérifier filtrage et habilitations |

Aucun service de messagerie, publicité, paiement ou analytique comportementale
tiers n'est identifié dans la configuration auditée. Ce constat porte sur le
dépôt, pas sur une infrastructure de production non documentée.

## 6. Contrôles et preuves déjà identifiés

- dictionnaire avec classification de sensibilité ;
- rôle analytique en lecture seule ;
- commande de purge des conversations ;
- commande de suppression des données d'un utilisateur ;
- anonymisation de `sql_executions.actor_id` lors de cette suppression ;
- sauvegarde et test de restauration PostgreSQL ;
- ancien corpus RAG Django déprécié et bloqué en écriture par défaut.

Ces mécanismes sont des éléments de preuve, pas une démonstration suffisante de
conformité. Leur configuration, leur fréquence et leur efficacité doivent être
testées.

## 7. Écarts et décisions attendues

1. analyser le risque de conflit d'intérêts avant désignation formelle du DPO ;
2. exécuter des tests de purge avec les durées retenues ;
3. identifier l'hébergeur et vérifier le cadre contractuel OpenAI ;
4. publier l'information des utilisateurs et le mécanisme d'exercice des droits ;
5. afficher l'avertissement relatif aux champs libres dans l'interface ;
6. documenter la conservation effective des sauvegardes et volumes Docker ;
7. planifier le retrait physique du corpus RAG déprécié ;
8. conserver le test de mise en balance de l'intérêt légitime.

## 8. Sources juridiques

- Règlement (UE) 2016/679 : articles 5, 6, 9, 10, 25, 30, 32 à 35 ;
- CNIL, définition des données sensibles ;
- Comité européen de la protection des données, principes et bases légales.

