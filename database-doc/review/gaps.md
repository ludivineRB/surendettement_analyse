# Écarts entre code, documentation et PostgreSQL

Les anomalies sont documentées sans modification du modèle ni des données.

## Statuts

- **Résolu** : la réponse est démontrée et l'écart documentaire est fermé.
- **Expliqué** : le comportement est démontré ; une décision de gouvernance peut
  rester nécessaire.
- **Ouvert** : aucune réponse suffisante n'a été trouvée ou l'intégrité reste
  effectivement absente.

## Écarts majeurs

| ID | Statut | Réponse fondée sur le dépôt | Reste à faire |
|---|---|---|---|
| `GAP-01` | **Résolu** | `assistant_api/migrations.py` crée les trois objets et correspond au PostgreSQL observé. | aucun écart de reproductibilité identifié |
| `GAP-02` | **Résolu** | le corpus Django est officiellement déprécié depuis le 25/08/2026 par la migration `assistant.0005`; le remplacement déclaré est `assistant.corpus_chunks`. | conserver l'historique ; aucune suppression dans ce lot |
| `GAP-03` | **Ouvert** | `operational` désigne ailleurs le domaine opérationnel, mais aucune preuve ne dit si `operational.observations` est volontairement logique ou une erreur. | faire valider l'intention par l'auteur de la migration |

## Écarts de modélisation

| ID | Statut | Réponse fondée sur le dépôt | Conséquence |
|---|---|---|---|
| `GAP-04` | **Ouvert** | SQLite ajoute des triggers de contrôle régional, mais ils ne sont pas présents dans PostgreSQL. | intégrité région–département non garantie par la base cible |
| `GAP-05` | **Ouvert** | l'API exige une période pour le calcul, sans FK systématique vers `dim_period`. | périodes orphelines ou formats divergents possibles |
| `GAP-06` | **Ouvert** | le code normalise le niveau géographique, mais ne garantit pas l'existence du code dans une dimension. | territoire contrôlé principalement par le pipeline |
| `GAP-07` | **Expliqué, correspondance ouverte** | `src/risk_score/README.md` indique que les correspondances ambiguës restent volontairement non résolues et fournit un mapping exemple. | valider les correspondances métier avant toute contrainte |
| `GAP-08` | **Expliqué** | Django envoie sa PK sous forme textuelle ; la suppression de compte anonymise l'audit en mettant `actor_id` à `NULL`. | découplage interservice assumé, pas de FK attendue |
| `GAP-09` | **Ouvert** | aucun identifiant de run n'est porté par les objets produits ; le détail reste dans les JSON et journaux. | lignage relationnel incomplet |

## Écarts de cycle de vie

| ID | Statut | Réponse fondée sur le dépôt | Conséquence |
|---|---|---|---|
| `GAP-10` | **Résolu** | la table est historique mais encore utilisée par `legacy_import.py` et une API de compatibilité. | statut corrigé en « historique actif / compatibilité » |
| `GAP-11` | **Résolu** | `src/risk_score/README.md` confirme leur conservation volontaire et leur inscription au registre. | rester visibles mais signalés dépréciés |
| `GAP-12` | **Expliqué** | `docker/CI.md` dit explicitement qu'aucun volume local n'est supprimé ; le script propose un nettoyage manuel après inspection. | définir éventuellement une durée de rétention locale |
| `GAP-13` | **Résolu** | `0002` est une migration de données réversible visant deux documents techniques. | aucune dépréciation de table ne doit en être déduite |

## Écarts techniques et maintenabilité

| ID | Statut | Réponse fondée sur le dépôt | Conséquence |
|---|---|---|---|
| `GAP-14` | **Ouvert** | les trois mécanismes sont confirmés et appelés par des commandes différentes. | ordre de déploiement et responsables encore à formaliser |
| `GAP-15` | **Ouvert** | `dim_region` et `dim_period` ont réellement une responsabilité partagée entre ORM et harmonisation analytique. | propriétaire du schéma à désigner |
| `GAP-16` | **Expliqué** | les modèles SQLAlchemy restent compatibles SQLite/PostgreSQL, contrairement aux modèles Django exclusivement PostgreSQL. | hétérogénéité assumée, à réévaluer après fin de transition SQLite |
| `GAP-17` | **Expliqué** | `analytics_db.py` construit le mart SQLite puis le publie optionnellement vers PostgreSQL. | architecture de transition documentée, pas un écart caché |
| `GAP-18` | **Expliqué** | les règles portables reposent sur `CHECK`, index et code afin de fonctionner aussi sous SQLite. | choix d'architecture ; contrôles PostgreSQL avancés non utilisés |
| `GAP-19` | **Résolu** | l'application `accounts` utilise les modèles Django standard et ajoute seulement rôles et services. | référence initiale obsolète corrigée |

## Points non considérés comme écarts

- la présence des bases Docker de test est légitime pour isoler les migrations ;
  seule leur rétention indéfinie est un point à formaliser ;
- l'absence de modèle ORM pour les vues est normale ;
- les tables Django standard ne nécessitent pas de modèles projet dédiés ;
- l'absence d'exemple métier dans le dictionnaire respecte l'interdiction de
  lire ou fabriquer des données pour compléter la documentation.

## Priorités de revue

1. faire valider la signification de `operational.observations` ;
2. valider les relations géographie/période/indicateur proposées dans le MLD ;
3. définir l'ordre et le responsable des trois systèmes de migration ;
4. compléter le lignage entre exécutions de pipeline et données produites ;
5. adopter, si nécessaire, une durée de rétention des volumes locaux.
