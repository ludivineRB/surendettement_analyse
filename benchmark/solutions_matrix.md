# Grille comparative — Text-to-SQL sécurisé

Version 1.0, 2026-08-26. Les notes initiales (1 faible à 5 fort) sont des
appréciations d'architecture, pas encore des résultats expérimentaux. Elles
devront être remplacées par les mesures du dataset commun.

| Approche | Qualité potentielle | Sécurité maîtrisable | Audit | Intégration/maintenance | Dépendance | Coût/sobriété | Décision initiale |
|---|---:|---:|---:|---:|---:|---:|---|
| OpenAI + SQLGlot actuel | 4 | 5 | 5 | 4 | 3 | 3 | Retenue pour benchmark et référence actuelle |
| Intentions déterministes | 3 | 5 | 5 | 5 | 5 | 5 | Retenues en priorité quand une intention couvre la question |
| Vanna AI 2.0 | 4 | 3 | 3 | 3 | 4 | 3 | À évaluer, non retenue en production à ce stade |
| LangChain SQL Agent | 4 | 2 | 4 | 3 | 4 | 2 | Écartée comme exécuteur autonome ; candidate derrière les mêmes contrôles |
| LlamaIndex Text-to-SQL | 4 | 3 | 3 | 3 | 4 | 3 | À évaluer, non retenue en production à ce stade |

## Analyse

**OpenAI + SQLGlot actuel.** Contrat JSON compact, schéma/sémantique fournis au
modèle et séparation nette génération/validation/exécution. SQLGlot permet
l'analyse AST, mais [sa documentation](https://sqlglot.com/sqlglot.html)
rappelle qu'un SQL parsé peut encore échouer : les listes blanches et PostgreSQL
restent indispensables. Avantages : intégration existante, contrôle fin,
auditabilité. Limites : coût/latence réseau, dépendance au modèle, hallucinations,
colonnes non encore validées explicitement et qualification contractuelle RGPD.

**Intentions déterministes.** Neuf opérations Pydantic autorisées exécutent des
appels analytiques bornés, sans SQL libre. Meilleure sécurité, reproductibilité,
latence et sobriété ; aucun coût LLM. Limites : couverture fonctionnelle fermée,
maintenance du parseur français et refus des formulations nouvelles. Elles sont
le premier choix pour les cas connus et la baseline du benchmark.

**Vanna AI 2.0.** La [documentation officielle](https://vanna.ai/docs) décrit
un agent avec outils, mémoire d'interactions réussies et permissions par
utilisateur. Cela peut améliorer l'adaptation au schéma et aux exemples métier.
Prérequis/risques : stockage et gouvernance de la mémoire, séparation des
utilisateurs, contrôle des exemples empoisonnés, connecteurs et validation SQL
indépendante. L'apprentissage automatique des interactions accroît l'effort
d'audit et le périmètre RGPD.

**LangChain SQL Agent.** Écosystème et boucles agentiques flexibles, outils de
schéma/requête et traces possibles. Sa [référence officielle](https://reference.langchain.com/python/langchain-community/agent_toolkits)
avertit qu'il peut exécuter du SQL arbitraire, coûteux ou dangereux et exige des
contrôles serveur et le moindre privilège. Les tours multiples augmentent
latence, coût, variabilité et surface d'injection. Il ne doit jamais recevoir un
compte d'écriture ni contourner SQLGlot.

**LlamaIndex Text-to-SQL.** Offre moteurs NL-SQL, récupération dynamique de
tables et d'exemples, utile aux grands schémas. Le [guide officiel](https://docs.llamaindex.ai/en/stable/examples/pipeline/query_pipeline_sql/)
signale le risque d'exécution arbitraire et recommande rôle restreint, base en
lecture seule et sandbox. Prérequis/risques : index à maintenir, exposition
possible de lignes exemples, dépendances supplémentaires et validation externe.

## Pondération et règle de décision

| Critère | Poids |
|---|---:|
| Sécurité : blocage, injection, refus légitime | 30 % |
| Exactitude SQL, résultat et sémantique métier | 25 % |
| RGPD, traçabilité et auditabilité | 15 % |
| Latence et coût | 10 % |
| Intégration, test et maintenance | 10 % |
| Dépendance fournisseur | 5 % |
| Sobriété estimée | 5 % |

Les critères de sécurité sont éliminatoires avant calcul du score pondéré. Les
coûts sont calculés à partir des jetons réellement observés et du tarif officiel
daté de la campagne, sans figer ici un prix rapidement périssable.

## Recommandation provisoire

Conserver l'architecture hybride : intentions déterministes en priorité, puis
génération LLM pour les questions avancées, toujours derrière validation
SQLGlot, rôle PostgreSQL limité aux vues, transaction en lecture seule, contrôle
de plan, timeout, audit et monitoring. Vanna et LlamaIndex sont des candidats
d'amélioration de contexte, non des frontières de sécurité. LangChain n'est pas
retenu comme agent autonome. La décision finale reste conditionnée aux mesures
reproductibles ; aucune substitution n'a lieu avant le benchmark.

