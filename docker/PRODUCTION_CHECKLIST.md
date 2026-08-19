# Checklist de mise en production

La recette locale ne remplace pas une validation sur l'infrastructure cible.

- [ ] `DJANGO_DEBUG=false` et clés/secrets injectés hors du dépôt.
- [ ] HTTPS terminé par un proxy de confiance ; HTTP redirigé vers HTTPS.
- [ ] `DJANGO_ALLOWED_HOSTS` et `DJANGO_CSRF_TRUSTED_ORIGINS` explicites.
- [ ] Cookies sécurisés, HSTS progressif et en-têtes proxy testés.
- [ ] Ports PostgreSQL, FastAPI et Assistant API non exposés publiquement.
- [ ] Compte `analytics_readonly` vérifié sans droits sur les tables brutes.
- [ ] Quotas adaptés ; cache partagé configuré avant plusieurs instances.
- [ ] Rotation, collecte et alertes sur les journaux JSON actives.
- [ ] Healthchecks PostgreSQL, API, Assistant API et Django au vert.
- [ ] Sauvegarde chiffrée, rétention documentée et restauration testée.
- [ ] Purge des conversations planifiée et testée en simulation.
- [ ] Procédure de suppression d'un compte et de ses conversations validée.
- [ ] Usages interdits affichés : aucun diagnostic individuel ou conseil financier.
- [ ] Tests de sécurité et migrations exécutés avant déploiement.
- [ ] Déploiement automatique désactivé jusqu'à validation explicite.
