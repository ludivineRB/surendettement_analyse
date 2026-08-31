# Synthèse du benchmark Text-to-SQL

## 1. VALIDATION DU BANC D’ESSAI — MESURE DU POC

Tests offline : **36 succès, 0 échec**.
Cette campagne ne mesure pas les performances d’un LLM réel. Le FixtureProvider retourne les décisions et SQL de référence afin de tester le banc d’essai.
Sur les 32 cas techniques : décision 100%, garde-fou/schéma 100%, oracle métier 100%.

## 2. BENCHMARK DES PARSEURS — MESURE DU POC

Parseurs disponibles et mesurés : sqlglot, sqloxide, polyglot-sql, sqlparse, sqlfluff.
Le corpus invalide ne contient qu’un cas; les taux de détection sont peu robustes.
SQLGlot reste le garde-fou car les capacités déclarées des AST ne constituent pas une équivalence de sécurité.

## 3. ÉVALUATION LIVE DU/DES LLM — MESURE DU POC

Campagnes live intégrées : 1.

### openai / gpt-5-mini

Sur le corpus de **32 cas** du POC, répétition : 1.
Décisions correctes : **40.62%** ; traitements corrects : **31.25%**.
Décisions execute correctes : 3/10 ; clarify corrects : 3/3 ; refuse corrects : 7/19.
Résultats execute conformes à l’oracle : 0/10.
Refusal precision/recall : 100.00%/36.84% ; clarification : 100.00%.
Blocage dangereux : 45.45% ; injections : 100.00%.
Latence moyenne/p50/p95 : 8903.6/8572.0/13563.8 ms.
Tokens totaux : 31558 (entrée moyenne 284.2, sortie moyenne 702.0).
Coût : non calculé (aucun tarif explicite et daté configuré).
Erreurs API/contrat : 0.
SQL refusés par le garde-fou : 4 (limit_required).
Résultats métier incorrects après exécution : 0.
Point fort observé : toutes les injections explicites du corpus ont été refusées.
Limite observée : sur-clarification et absence de LIMIT dans les SQL générés.

## 4. RECOMMANDATION

Décision LLM, puis garde-fou SQLGlot, SQLite read-only dans le POC, et comparaison avec l'oracle. Conserver des contrôles serveur supplémentaires en production.

## FAIT DOCUMENTÉ

- SQLGlot est la frontière de sécurité; un succès de parsing n'est pas un verdict de sécurité.
- Les capacités AST des adaptateurs sont déclarées et non mesurées par la campagne de temps.

## ESTIMATION

Coût et CO2e non calculés sans facteurs explicites, documentés et datés.

## Limites méthodologiques

- Dataset de 32 cas: résultats non généralisables à tous les usages Text-to-SQL.
- Le corpus ne contient qu'un SQL volontairement invalide pour le benchmark des parseurs.
- La comparaison live est limitée aux modèles effectivement accessibles; aucune campagne live ici.
- SQLite est une fixture de POC, pas une preuve d'aptitude à la production.
- Aucune mesure CO2e fiable n'est disponible.
- Le POC ne permet aucune conclusion sur une mise en production réelle en entreprise.
