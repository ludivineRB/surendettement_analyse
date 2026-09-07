# E5 — Monitoring et résolution d'incident

Ce dossier rassemble les preuves techniques des compétences C20 et C21 sur la
révision `cf6b525` de `main`.

- [C20_MONITORING.md](C20_MONITORING.md) décrit la supervision locale.
- [C21_INCIDENT.md](C21_INCIDENT.md) documente l'incident Text-to-SQL réel.
- [E5_EVIDENCE_MATRIX.md](E5_EVIDENCE_MATRIX.md) relie les critères aux preuves.

## Démonstration conseillée

1. Montrer l'état nominal avec Docker Compose, Prometheus et Grafana.
2. Reproduire le comportement historique avec le parent de `380c5a9` dans une
   copie de travail temporaire, sans modifier les données de la stack courante.
3. Corréler le symptôme aux logs et à la métrique de rejets SQL.
4. Montrer le diff `380c5a9`, les tests ciblés et le retour au nominal.
5. Déclencher séparément une alerte contrôlée avec le scénario documenté.

L'incident historique n'est pas attribué au monitoring : **NON PROUVÉ À CE
STADE**. La démonstration fait une reproduction contrôlée de l'incident dans un
environnement supervisé.

## Règles de preuve

- Ne pas afficher `.env`, token, cookie, question utilisateur ou chaîne de connexion.
- Masquer les identifiants utilisateurs dans les captures.
- Conserver l'identifiant de requête uniquement lorsqu'il est synthétique.
- Ne pas arrêter PostgreSQL et ne supprimer aucun volume.
- Consigner séparément les résultats réellement obtenus le jour de l'épreuve.

## État des validations

Le dépôt contient `app/reports/ci/pytest.xml`, qui rapporte historiquement 154
tests réussis. Une image CI reconstruite depuis `096d4b9` a installé
`httpx2==2.12.0` avec succès. La validation a obtenu 17 tests Assistant API,
1 test de monitoring Assistant, 44 tests SQL/Assistant combinés et 5 tests
Django/security réussis, sans échec ni test ignoré.
