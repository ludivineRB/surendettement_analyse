# POC — décodage Text-to-SQL

Ce POC compare cinq stratégies de transformation d'une question en SQL, avec
le même sous-ensemble de six cas et le validateur SQLGlot du projet. Il ne se
connecte jamais à PostgreSQL et ne remplace aucune implémentation de production.

| Stratégie | Hypothèse testée |
|---|---|
| `current` | Prompt complet et sémantique du projet |
| `schema_only` | Schéma complet avec consigne minimale |
| `few_shot` | Ajout d'exemples question/SQL, analogue à une mémoire d'exemples |
| `retrieval` | Réduction préalable aux vues jugées pertinentes |
| `review` | Deuxième appel chargé de contrôler et corriger le premier SQL |

Vérification gratuite du câblage, avec les SQL de référence :

```shell
python -m benchmark.poc
python -m pytest benchmark/test_poc.py -q
```

Campagne réelle, volontairement explicite :

```shell
OPENAI_API_KEY=... python -m benchmark.poc \
  --live --confirm-paid-calls --model gpt-5.6-terra
```

Le mode réel produit `benchmark/poc_report.json`. Ce fichier contient, pour
chaque stratégie, le taux de réussite, le nombre d'appels, les jetons et la
latence. Le POC ne prétend pas mesurer Vanna, LangChain ou LlamaIndex eux-mêmes :
il isole les principales stratégies de décodage qu'ils peuvent mettre en œuvre.
