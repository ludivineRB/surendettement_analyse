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

Aucun registry, credential, serveur ou nom de domaine réel n'est configuré dans le
dépôt. Il n'existe donc volontairement aucun push. `docker/compose.staging.yaml` est un
overlay de configuration et ne constitue pas une cible de déploiement.

Pour publier réellement, il faudra choisir un registry, créer un dépôt d'images et
fournir à GitHub un secret d'identité avec droit d'écriture. Pour staging, il faudra une
cible, son mécanisme d'accès, ses variables/secrets et une URL de health. Ces éléments
ne doivent jamais être inscrits en clair dans Git.

## Rollback documenté

Conserver le SHA de la dernière image dont le smoke test et le health staging sont
valides. Si la version N échoue, redéployer explicitement ce tag N-1, attendre la
readiness puis rejouer le smoke test fonctionnel. Ce rollback est une procédure ; il
n'est ni automatisé ni prétendu testé faute de cible réelle.

## Preuves

Dans GitHub Actions, capturer le job `package-assistant`, le tag SHA dans les logs, le
smoke test vert et l'artifact téléchargeable. Pour le valider : télécharger l'archive,
faire `docker load` puis démarrer le tag indiqué et appeler `/health`.
