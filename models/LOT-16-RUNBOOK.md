# LOT-16 — Procédure d'incident

## Triage

1. Accuser réception, noter l'heure, l'environnement et l'alerte.
2. Vérifier `/health/live` puis `/health/ready` du service concerné.
3. Consulter le dashboard, les cinq dernières minutes de logs via `request_id`, puis PostgreSQL.
4. Classer : **P1** indisponibilité/perte de données, **P2** dégradation majeure, **P3** anomalie contenue.

## Service indisponible

- `live` en échec : vérifier le processus et le dernier déploiement.
- `ready` en échec : contrôler PostgreSQL et les dépendances en aval avant tout redémarrage.
- Ne relancer qu'après avoir capturé les logs et identifié le composant fautif.

## Erreurs HTTP

- Ventiler par `path`, `status` et `request_id`; ne jamais copier token, cookie ou chaîne de connexion.
- Comparer avec le dernier changement et revenir à la version stable selon la procédure de déploiement.

## PostgreSQL

- Contrôler disponibilité, latence, connexions, verrous longs et espace disque.
- Ne jamais tuer une session ni restaurer une sauvegarde sans validation explicite du responsable.

## Pipelines

- Identifier le dernier `pipeline_run`, l'étape en échec et le rapport qualité.
- Corriger la source ou relancer idempotemment; vérifier fraîcheur, complétude et intégrité ensuite.

## RAG et agent SQL

- RAG vide : vérifier corpus actif, date d'indexation et disponibilité PostgreSQL.
- SQL rejeté : analyser uniquement le code de validation; ne pas assouplir les garde-fous en urgence.
- Générateur indisponible : confirmer le fournisseur et basculer vers le message de service dégradé.

## Clôture

Documenter chronologie, impact, cause racine, actions, preuves de retour au vert et propriétaire. Pour P1/P2,
produire un retour d'expérience sous 48 heures et ajouter un test empêchant la récidive.
