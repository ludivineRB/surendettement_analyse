# C21 — Incident Text-to-SQL

## 1. Contexte et fonction concernée

L'Assistant traduit une question analytique en SQL PostgreSQL, valide la requête,
l'exécute en lecture seule et audite le résultat. Le cas retenu est le défaut
corrigé par `380c5a99356c88cdb4b85f413f14519f3d9b99e7`, fusionné dans la PR #43
par `bf041016b5cec4f418adfa6402bd7c97434b78ff`.

## 2. État nominal, déclencheur et symptômes

État attendu : une question précise produit une requête conforme aux vues
autorisées et une réponse contenant des lignes pertinentes.

Déclencheur historique identifiable : le générateur produit une requête refusée
par le validateur, invalide pour PostgreSQL, ou une requête valide sans résultat.

Avant le correctif, `run_text_to_sql` n'effectuait qu'une génération et une
exécution. Un SQL invalide provoquait un rejet ; un résultat vide était retourné
sans tentative corrective. L'utilisateur pouvait donc recevoir une erreur ou
une réponse vide alors qu'une correction bornée du SQL était possible.

L'impact quantifié et les utilisateurs réellement touchés sont **NON PROUVÉS À
CE STADE**.

## 3. Périmètre et chronologie prouvée

| Étape | Preuve |
|---|---|
| Version vulnérable | parent `380c5a9^` (`f8a28b1`) |
| Correctif | commit `380c5a9`, daté par Git du 3 septembre 2026 |
| Fusion | merge `bf04101`, message Git « Merge pull request #43 » |
| Tests | `tests/test_sql_service.py` ajouté/modifié par le correctif |

Aucune heure d'apparition, alerte historique ou durée d'incident n'est établie.

## 4. Diagnostic et cause racine

Le diff du parent vers `380c5a9` montre la cause :

1. une seule sortie probabiliste du générateur était acceptée ;
2. le motif du rejet n'était pas renvoyé au générateur ;
3. `ProgrammingError` n'entrait pas dans une correction contrôlée ;
4. un résultat vide n'était pas considéré comme corrigeable ;
5. le prompt omettait des contraintes géographiques et SQL utiles.

La cause racine est donc une orchestration sans boucle corrective bornée, aggravée
par un contexte de génération incomplet. Les garde-fous SQL eux-mêmes ne sont
pas en cause : ils ont correctement refusé les requêtes interdites.

## 5. Hypothèses écartées ou non démontrées

- panne PostgreSQL : non nécessaire pour reproduire le défaut ;
- indisponibilité OpenAI : autre classe d'erreur ;
- corruption de données : aucune preuve ;
- détection historique par Prometheus/Alertmanager : **NON PROUVÉE À CE STADE**.

## 6. Reproduction contrôlée

Ne pas modifier la branche courante. Créer deux worktrees temporaires ou deux
clones locaux : l'un sur `380c5a9^`, l'autre sur `380c5a9`. N'utiliser qu'une
base de test et un générateur simulé ; aucun appel OpenAI n'est requis.

Dans l'état antérieur, reprendre le scénario déterministe du test actuel : le
générateur retourne d'abord une requête vers `forbidden_view`. Le validateur
lève `SQLValidationError("table_forbidden", ...)`. Vérifier qu'aucune seconde
génération n'a lieu et que l'appel échoue.

Dans l'état corrigé :

```bash
python -m pytest -q tests/test_sql_service.py \
  -k 'invalid_generated_sql_is_corrected_once or empty_result_is_retried_once'
```

Résultat obtenu dans l'image reconstruite `surendettement-e5-validation:096d4b9` :
2 tests réussis et 4 désélectionnés en 0,52 s. Le lot SQL/Assistant complet a
également obtenu 44 tests réussis. La démonstration doit néanmoins conserver une
capture lisible des deux tests spécifiques.

[PREUVE À FOURNIR — E5-P06]
Description : reproduction du comportement avant correction.
Procédure pour obtenir la capture : exécuter le test adapté dans le worktree `380c5a9^`.
Éléments qui doivent être visibles : SHA parent, échec/rejet et absence de seconde génération ; aucune donnée réelle.

## 7. Observations de monitoring et logs

Un rejet final incrémente
`assistant_sql_executions_total{status="rejected",reason="..."}`. Les requêtes
HTTP Assistant alimentent aussi les compteurs par statut et les durées. Les logs
de requête contiennent request ID, chemin, statut et durée, mais ni token ni corps.

Une occurrence isolée ne déclenche pas `SqlRejectionRateHigh`. La règle exige
plus de 25 % de rejets calculés sur 15 minutes, maintenus pendant 15 minutes.
Pour l'oral, montrer la hausse de la métrique lors de la reproduction et utiliser
le test `promtool` pour prouver séparément que l'alerte fonctionne au seuil prévu.

[PREUVE À FOURNIR — E5-P07]
Description : symptôme monitoré et corrélation.
Procédure pour obtenir la capture : appeler le cas contrôlé puis interroger la métrique et Loki avec le request ID synthétique.
Éléments qui doivent être visibles : compteur rejeté, reason normalisée, statut HTTP et même request ID ; aucune question utilisateur.

## 8. Correction

`assistant_api/sql_generation.py` :

- ajoute couverture et noms géographiques ;
- interdit explicitement CTE et sous-requête ;
- précise les contraintes d'agrégation ;
- transmet `rejected_sql` et `rejection_reason` au second prompt.

`assistant_api/sql_service.py` :

- limite la génération à deux tentatives ;
- retente après `SQLValidationError`, `ProgrammingError` ou premier résultat vide ;
- laisse remonter l'erreur après le second échec ;
- conserve l'audit et les métriques finales.

`tests/test_sql_service.py` prouve la correction unique et le traitement du
résultat vide. Le bornage à deux tentatives prévient boucle et surconsommation.

## 9. Validation et non-régression

Commandes prévues :

```bash
python -m pytest -q tests/test_sql_service.py tests/test_sql_validation.py tests/test_sql_executor.py
python -m pytest -q tests/test_assistant_api.py tests/test_assistant_monitoring.py
```

Le rapport historique `app/reports/ci/pytest.xml` indique 154 tests, zéro échec
et zéro erreur. Nouvelle exécution Docker sur l'image reconstruite : 17 tests
Assistant API, 1 test de monitoring Assistant et 44 tests SQL/Assistant combinés
réussis, sans échec ni test ignoré. L'échec de collecte antérieur provenait d'une
image CI obsolète dans laquelle `httpx2` n'était pas encore installé ; la
dépendance déclarée `httpx2==2.12.0` est correcte pour Starlette 1.6.0.

[PREUVE À FOURNIR — E5-P08]
Description : tests après correction.
Procédure pour obtenir la capture : exécuter les commandes ciblées dans l'environnement CI/Docker.
Éléments qui doivent être visibles : SHA `380c5a9` ou ultérieur, tests sélectionnés et résultat réussi.

[PREUVE À FOURNIR — E5-P09]
Description : correction versionnée.
Procédure pour obtenir la capture : ouvrir le commit `380c5a9` et la PR #43 sur GitHub.
Éléments qui doivent être visibles : fichiers SQL concernés, tests ajoutés et état fusionné ; masquer les données de compte.

[PREUVE À FOURNIR — E5-P10]
Description : CI verte associée à la version corrigée.
Procédure pour obtenir la capture : ouvrir les checks GitHub de la PR #43 ou d'un commit descendant.
Éléments qui doivent être visibles : SHA, workflow, tests réussis et date réelle.

## 10. Retour nominal et mesures préventives

Le retour nominal est défini par : test ciblé passant, deuxième SQL accepté,
réponse non vide pour le scénario, compteur accepté incrémenté et absence de
hausse durable du ratio de rejets. Sa constatation en stack locale est **NON
PROUVÉE À CE STADE**.

Prévention déjà présente : tests déterministes, limite de deux tentatives,
validateur inchangé, exécution read-only, motif normalisé, métrique de rejets et
audit. À chaque évolution du schéma ou du prompt, ajouter un exemple de
non-régression et surveiller le ratio rejeté ainsi que les résultats RAG vides.

## 11. Enseignements

Une sortie de modèle doit être traitée comme une proposition non fiable. La
validation demeure stricte ; la résilience vient d'une correction bornée et
observable, jamais de l'assouplissement des garde-fous.
