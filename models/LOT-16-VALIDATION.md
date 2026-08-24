# LOT-16 — Recette d'observabilité

Cette recette s'exécute uniquement sur la stack staging. Elle ne supprime ni conteneur ni volume.

## Validation sans interruption

Avec les variables Docker habituelles déjà exportées :

```bash
sh docker/test_observability.sh
```

Le script valide les six scénarios d'alerte avec `promtool`, les trois endpoints de métriques, toutes les
cibles Prometheus et la santé Grafana.

## Démonstration visuelle contrôlée

```bash
sh docker/test_observability.sh --demo-django-outage
```

Le script arrête Django pendant 150 secondes puis le redémarre, y compris en cas d'interruption du script.
Cette durée couvre les deux minutes de temporisation de la règle et les intervalles de collecte.
Pendant la démonstration :

1. vérifier `django = 0` dans Grafana ;
2. vérifier `ServiceUnavailable` dans Alertmanager ;
3. vérifier les logs de scrape dans Loki ;
4. confirmer la notification locale ;
5. après redémarrage, vérifier le retour à `django = 1` et la résolution de l'alerte.

Les alertes HTTP, RAG, SQL et PostgreSQL sont testées par séries synthétiques afin de ne pas injecter
d'erreurs ni de charge artificielle dans les applications et la base staging.
