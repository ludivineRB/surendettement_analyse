# C13 — Livraison continue

## Pipeline réel

Le workflow `.github/workflows/ci.yml` se déclenche sur push, pull request ou lancement
manuel. Le job `validate` installe les outils verrouillés, teste et construit. Après son
succès, `package-assistant` :

1. construit la cible Docker `assistant-api` ;
2. la tague `surendettement-assistant:<git-sha>` ;
3. démarre exactement cette image ;
4. contrôle `/health` sans appel LLM ni base ;
5. exporte image compressée et métadonnées ;
6. publie l'artifact `assistant-image-<git-sha>` pendant 14 jours.

Le smoke test échoue si le processus ne répond pas après 40 secondes. Le endpoint de
readiness reste destiné à l'environnement complet avec PostgreSQL.

## Publication et staging

Le pipeline GitHub réellement validé reste inchangé jusqu'à l'artifact. `render.yaml`
prépare maintenant PostgreSQL, deux services privés et Django public. Le Blueprint est
une configuration de staging, pas la preuve d'un déploiement réussi.

La connexion GitHub/Render, la saisie des secrets, **Deploy Blueprint**, l'import des
données et les contrôles restent manuels. Aucun déploiement Render n'est ajouté à GitHub
Actions avant validation du premier staging. Voir `C13_RENDER_STAGING.md`.

## Rollback documenté

Conserver le SHA de la dernière image dont le smoke test et le health staging sont
valides. Si la version N échoue, redéployer explicitement ce tag N-1, attendre la
readiness puis rejouer le smoke test fonctionnel. Ce rollback est une procédure ; il
n'est ni automatisé ni prétendu testé faute de cible réelle.

## Preuves

Dans GitHub Actions, capturer le job `package-assistant`, le tag SHA dans les logs, le
smoke test vert et l'artifact téléchargeable. Pour le valider : télécharger l'archive,
faire `docker load` puis démarrer le tag indiqué et appeler `/health`.
