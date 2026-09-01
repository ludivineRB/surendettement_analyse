# C11 — Monitoring du service IA

## Collecte et restitution

`assistant_api/monitoring.py` collecte en mémoire, sous verrou, les requêtes HTTP,
latences, décisions, erreurs provider, recherches RAG, validations et exécutions SQL.
Le modèle configuré est une étiquette de compteur. Les tokens ne sont pas exposés car
l'adaptateur actuel ne les retourne pas ; aucune valeur n'est estimée.

Prometheus collecte `/metrics/prometheus`. Grafana, Loki et Alertmanager sont configurés
dans `docker/monitoring/`. La synthèse JSON protégée est disponible sur
`/monitoring/summary`. Son stockage est `process_memory` : un redémarrage remet les
compteurs à zéro ; Prometheus assure l'historique lorsqu'il est démarré.

| Seuil | Valeur | Traitement |
|---|---:|---|
| Indisponibilité | 2 minutes | alerte critique `ServiceUnavailable` |
| Taux HTTP 5xx assistant | > 2 % pendant 10 minutes | `AssistantErrorRateHigh` |
| Rejets SQL | > 25 % pendant 15 minutes | `SqlRejectionRateHigh` |
| Latence moyenne | > 5 s pendant 10 minutes | investigation logs/provider ; seuil documentaire |

Les logs HTTP contiennent méthode, chemin, statut, durée et identifiant de requête,
mais ni header Authorization, ni token, ni contenu intégral de la question.

## Preuve réelle

```bash
curl -H "X-Internal-Token: $ASSISTANT_INTERNAL_TOKEN" \
  http://localhost:8030/monitoring/summary
docker compose -f docker/compose.yaml up prometheus grafana alertmanager
```

Après plusieurs appels couvrant les trois décisions et une erreur contrôlée, capturer
la synthèse puis le dashboard Grafana. Test de calcul :
`pytest -q tests/test_assistant_monitoring.py`.

Limites : mémoire locale par processus, absence de quantiles natifs et absence de
métriques de tokens tant que le contrat provider reste textuel.
