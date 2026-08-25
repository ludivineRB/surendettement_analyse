# MCT — Modèle conceptuel des traitements

La documentation retient les termes Merise **MCT** pour les événements,
opérations et résultats, puis **MOT** pour leur organisation technique. La
désignation MCP n'est pas utilisée par le code ni par la documentation existante.

## Chaîne Banque de France

| Événement | Opération | Résultat | Données affectées |
|---|---|---|---|
| Nouvelle publication structurée | découverte, profilage, lecture et passage bronze/silver/gold | jeu surendettement normalisé et contrôlé | fichiers intermédiaires puis faits analytiques |
| Nouveau fichier Stat Info | téléchargement/lecture, normalisation, dictionnaire et contrôles métier | faits mensuels BDF validés | `fact_bdf_statinfo`, `dim_indicator` |
| Nouveau document inclusion financière | téléchargement, empreinte, extraction et idempotence | document versionné et observations | `source_documents`, `indicators`, `observations` |

Entrées principales : publications Banque de France, fichiers locaux approuvés
et PDF. Les empreintes et clés métier empêchent les doublons documentaires et
d'observations.

## Chaîne INSEE

| Événement | Opération | Résultat | Données affectées |
|---|---|---|---|
| Millésime Dossier complet disponible | découverte, téléchargement, extraction, passage au format long | faits communaux puis départementaux | `fact_insee_macro`, dimensions |
| Séries inflation disponibles | lecture des séries, variations annuelles et moyennes | observations d'inflation | catalogue/observations opérationnels |
| Données Filosofi disponibles | normalisation et import territorial | observations de revenu/pauvreté | catalogue/observations opérationnels |

Les contrôles portent notamment sur la couverture territoriale, les périodes,
les doublons, les valeurs manquantes et la cohérence des indicateurs.

## Dimensions conformes et normalisation

```text
Sources BDF + sources INSEE
        ↓
normalisation des noms, codes et périodes
        ↓
régions + départements + périodes + indicateurs conformes
        ↓
faits BDF / INSEE et observations opérationnelles
```

`src/storage/conformed_dimensions.py` rapproche les deux bases SQLite
historiques sans supprimer leur historique. La base ne matérialise toutefois pas
toutes les FK attendues entre codes et dimensions.

## Contrôles qualité et orchestration

| Événement | Opération | Issue possible |
|---|---|---|
| Demande de rafraîchissement | exécution coordonnée des pipelines | poursuite vers publication ou échec |
| Données préparées | `run_quality_gates` et rapports spécialisés | succès, échec qualité ou avertissements |
| Fin d'étape | enregistrement du statut, résultats et rapport JSON | `pipeline_runs` mis à jour |

`src/pipeline_orchestrator.py` orchestre le rafraîchissement et les quality
gates. Une exécution peut prendre les statuts `running`, `success`, `failed` ou
`quality_failed`. Aucune FK ne relie l'exécution aux lignes produites.

## Calcul du score territorial

| Événement | Opération | Résultat |
|---|---|---|
| Modèle actif et observations disponibles | sélection des indicateurs et contrôle de couverture | population de calcul admissible |
| Population admissible | normalisation, application du sens et des poids | contributions par indicateur |
| Contributions calculées | agrégation, classement du risque et avertissements | score territorial versionné |
| Nouvelle version de modèle | comparaison et analyse de sensibilité | rapport d'écart entre versions |

Le modèle et ses configurations sont versionnés. L'unicité métier permet de
recalculer un score sans multiplier les occurrences pour un même modèle,
territoire et période.

## Publication analytique

Après validation, les données sont exposées par les vues `analytics_*` :
observations, état des pipelines, scores, facteurs, comparaisons de modèles et
macro-régions. L'API et l'agent SQL consomment cette interface en lecture.

La construction analytique reste historiquement réalisée dans SQLite par
`analytics_db.py`, avec publication PostgreSQL optionnelle. Cette dualité est
documentée ; elle n'est pas corrigée dans ce lot.

## Migration SQLite vers PostgreSQL

| Événement | Opération | Résultat |
|---|---|---|
| Base SQLite opérationnelle existante | création du schéma, insertion sans écrasement, réalignement des séquences | stockage opérationnel PostgreSQL |
| Mart SQLite existant | introspection, création/copie des tables, création des vues | entrepôt et publication PostgreSQL |
| Relance identique | détection des clés déjà présentes | résultat inchangé attendu |

Les tests d'intégration refusent une base PostgreSQL dont le nom ne contient pas
un marqueur de test. Les migrations réelles restent des opérations explicites,
pas des effets implicites du générateur documentaire.

## RAG et conversations

### RAG Django

Manifest approuvé → source → document → version par empreinte → fragments →
vecteur de recherche plein texte. Une migration de données a désactivé deux
documents techniques sans supprimer leur historique.

### RAG Assistant API

Un second flux alimente `assistant.corpus_chunks`, avec empreintes source et
contenu, statut actif et index `tsvector`. Le raccord fonctionnel aux tables RAG
Django n'est pas démontré.

### Conversation et agent SQL

- l'utilisateur ouvre une conversation et enregistre les messages ;
- une question SQL est interprétée, générée, validée puis exécutée en lecture ;
- statut, coût estimé, durée, nombre de lignes et versions sont audités dans
  `assistant.sql_executions` ;
- le lien `actor_id`–utilisateur n'est pas contraint par FK.

## Sauvegarde, restauration et rétention

`docker/backup_postgres.sh` produit une sauvegarde PostgreSQL. La restauration
est portée par `docker/restore_postgres.sh` et testée par
`docker/test_restore_postgres.sh`. Ces scripts sont des traitements
d'exploitation ; ils ne modifient pas le modèle logique.

Les conversations disposent d'une commande de purge dédiée. La suppression de
données utilisateur est gérée par `web/accounts/management/commands/delete_user_data.py`.
Ces opérations sont destructives et doivent rester explicites et contrôlées.
