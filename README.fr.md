# Outils d'administration morfSystem

*Lire dans une autre langue : [English](README.md) · **Français** (ce document).*

[![Version](https://img.shields.io/badge/version-0.31.0-blue)](CHANGELOG.md)

`morfTools` est le projet d'administration de morfSystem. Il peut être déplacé
ou renommé : les scripts déduisent la racine de l'espace de travail de leur
propre emplacement et ne s'appuient jamais sur un chemin absolu.

> **Note.** La sortie des scripts est en **anglais**, délibérément et de façon
> uniforme. Ce document traduit la documentation, pas les messages.

## Organisation

- `ecosystem.json` : manifeste des projets, modèle d'URL de clonage, registre
  d'adressage des ports et registre des copies vendorées.
- scripts à la racine du projet : commandes portables d'administration.
- `scripts/ecosystem-check.py` : implémentation partagée des vérifications à
  l'échelle de l'écosystème, exécutées par `doctor`.
- dossiers voisins : les projets morfSystem, indépendants les uns des autres.
- [`docs/ENVIRONNEMENT-DEV.md`](docs/ENVIRONNEMENT-DEV.md) : environnement de développement et **dépendances de compilation** (toolchain, composants Qt6, OpenSSL/libssh2/… par projet, installation par plateforme). À lire pour compiler le parc sans erreur sur une machine neuve.
- [`docs/EXPLOITATION.md`](docs/EXPLOITATION.md) : chaque script (options, action, quand l'utiliser) et les commandes Linux/Windows indispensables au suivi et à la maintenance au quotidien (`systemctl`, `journalctl`, `schtasks`, redémarrage, journaux). La référence d'exploitation.
- [`docs/SCRIPTS.md`](docs/SCRIPTS.md) : le catalogue **exhaustif** de tous les scripts du parc (commandes globales `morf`, `service.py`, et les scripts locaux de chaque projet, y compris les outils de packaging et de build), avec leurs actions et leurs options.
- `docs/ECOSYSTEM-PRINCIPLES.md` : les principes fondateurs et les invariants d'architecture valables pour **tout le parc**, y compris les frontières qu'aucun composant ne doit franchir.
- [`docs/ACTIVATE-CLI.md`](docs/ACTIVATE-CLI.md) : exposer les commandes du parc (`morf`, `screenctl`, …) dans `~/.local/bin` via `activate-cli.sh`, sans déplacer les scripts hors de leur projet.
- `docs/` : documentation de l'espace de travail.

## Activation des commandes CLI (`activate-cli.sh`)

Pour appeler les commandes du parc (`morf`, `screenctl`, …) depuis **n'importe
quel dossier**, `morfTools/activate-cli.sh` les expose dans `~/.local/bin` sans
déplacer ni copier les scripts hors de leur projet :

```bash
cd ~/01-Travail/morfTools    # ou ~/morfSystem/morfTools
./activate-cli.sh            # active l'espace de CETTE copie de morfTools
./activate-cli.sh --status   # espace actif + commandes gérées
./activate-cli.sh --dry-run  # aperçu sans rien modifier
```

L'espace activé est le dossier **parent** de cette copie de morfTools : une
activation ne mélange jamais deux racines (`01-Travail` vs `morfSystem`). C'est
une action **volontaire**, indépendante de `install`/`update`, qui ne touche que
`~/.local/bin` (aucun service, rien sous `/opt`, `/etc`, `/var/lib`). Chaque
projet déclare ses vraies commandes dans un `cli.manifest` à sa racine : mode
`direct` (lien symbolique, pour un script indépendant du répertoire courant) ou
`project` (lanceur qui entre dans le projet avant d'exécuter). Le mode est
déclaré, jamais deviné. Guide complet :
[`docs/ACTIVATE-CLI.md`](docs/ACTIVATE-CLI.md).

## Espace bac à sable et espace de production

Les outils déterminent quels projets piloter à partir de **leur propre nom de
dossier**. Les mêmes scripts servent donc les deux espaces sans aucune
configuration :

| Dossier des outils | Projets pilotés | Usage |
| --- | --- | --- |
| `morfTools` | `ComponentHub`, `SiteWatch`, … | Espace de production. |
| `morfTools_travail` | `ComponentHub_travail`, `SiteWatch_travail`, … | Espace bac à sable. |

`ecosystem.json` ne contient que des noms canoniques (`ComponentHub`) ; le
suffixe `_travail` est ajouté à l'exécution lorsque le dossier des outils le
porte. Renommer ce dossier bascule donc l'espace de travail entier, et un projet
dont le dossier ne correspond pas au nom attendu est signalé
`[SKIP] <nom> (not cloned)` plutôt que d'être touché.

## Commandes

Depuis n'importe quel dossier : `python3 <espace>/morfTools/morf.py status` (ou
`./morf.py status`, il est exécutable). Une implémentation, toutes les plateformes.

### Arguments

Toutes les commandes n'opèrent que sur les projets déclarés dans
`ecosystem.json`. Ce sont les 15 commandes `morf`. La configuration et les bits
exécutables passent par des **scripts séparés** à la racine (voir la note sous le
tableau), pas par des sous-commandes `morf`.

**Deux surfaces.** Administrer une machine (`install`/`deploy`, `update`,
`upgrade`, `purge`, `uninstall`, `doctor`) est un métier différent de travailler
sur les clones en tant que code source (Git et build). Ces dernières -- `clone`,
`fetch`, `pull`, `status`, `push`, `commit`, `build`, `clean` -- sont aussi
accessibles sous un espace **`morf dev <sous-commande>`**, pour que les deux
surfaces se lisent comme deux. Les formes plates restent valables ; `morf dev`
sans sous-commande les liste. (`morf update` comme git pull est déprécié au
profit de `morf dev pull`.)

| Commande `morf` | Arguments | Action |
| --- | --- | --- |
| `clone` | `--protocol auto\|ssh\|https`, `--yes` | Clone les projets manquants sur la branche du manifeste. Détecte d'abord l'accès Git réel de la machine (aucune config SSH supposée) : `auto` utilise SSH s'il s'authentifie vraiment à GitHub, sinon propose HTTPS ; `ssh` échoue proprement si SSH n'est pas opérationnel (en disant ce qui manque) ; `https` clone via HTTPS. Ne génère jamais de clé ni ne modifie `~/.ssh`. `--yes` autorise le repli HTTPS en non-interactif. |
| `fetch` | aucun | Récupère les dépôts distants et purge les références supprimées. |
| `pull` | `--dry-run` | Tire en avance rapide depuis la branche du manifeste. `--dry-run` récupère et liste les commits entrants sans fusionner. Préférer `morf dev pull`. |
| `update` | `--dry-run` | **Déprécié comme opération Git** : affiche un avertissement et se comporte comme `pull`. Utiliser `morf dev pull` pour Git. `morf update` est réservé au sens « mettre à jour les composants installés » dans une version ultérieure. |
| `build` | preset CMake (auto-détecté pour la plateforme, sinon demandé), `--gui` | Compile les projets PlatformIO, ou configure et compile les projets CMake. Sous Windows, les chemins de toolchain figés dans le preset `mingw` sont **surchargés par ce que la machine possède réellement** (ninja, compilateur MinGW et préfixe Qt détectés sur le PATH / l'env) : une machine avec une autre disposition Qt/MinGW compile sans éditer les presets ; un élément manquant est signalé clairement (voir `morf doctor`). Le firmware PlatformIO est sauté avec un avis si `pio` est absent. Les apps desktop sont sautées sur une machine sans écran (Linux) ; `--gui` force. |
| `install` | `[<projet>…]`, `--all`, `--config keep\|merge\|replace`, `--preset`, `--dry-run`, `--yes`, `--services` | **La primo-installation.** Compile les services choisis **et** pose leur configuration, en une passe. `morf install` seul propose un choix numéroté ; nommer des services ou `--all` pour scripter. `--config` : `keep` (défaut, ne jamais écraser), `merge` (ajoute les clés nouvelles, garde les valeurs locales), `replace` (écrase depuis le dépôt, sauvegarde d'abord). `--dry-run` affiche le plan sans rien toucher. Compile sous votre compte, n'élève que l'installation. `install --services` = `--all` (compatibilité). À lancer **sans `sudo`**. |
| `deploy` | comme `install` | **Alias rétrocompatible** de `install` (affiche une note qui pointe vers lui). |
| `setup` | aucune | Setup générique par langage seulement (dépendances Python `requirements.txt` si présent). Les services sont installés par `install` ; ici ils sont simplement sautés. |
| `uninstall` | `[<projet>…]`, `--all`, `--only NAME`, `--purge`, `--backup DIR`, `--dry-run`, `--yes` | Désinstalle des services : les nommer, `--all` (ou forme nue) pour tous, `--only` pour un (compat). `--purge` retire aussi configuration et données ; `--backup DIR` copie d'abord la configuration. `--dry-run` liste ce qui partirait sans rien toucher. Retirer des services demande confirmation ; `--purge` demande un jeton saisi (`PURGE`, ou `PURGE ALL` sur toute la machine) ; le non-interactif exige `--yes`. |
| `purge` | `[<projet> [<id>…]]`, `--all`, `--dry-run`, `--yes`, `--force` | Efface des catégories de données déclarées. Chaque projet annonce ce qu'il sait effacer (`service.py purge --list`) ; morfTools ne lit jamais un service.json. `morf purge` seul liste ce qui est purgeable ici ; `morf purge <projet> <id>…` ou `--all` cible ; `morf purge --all` balaie tous les projets de la machine. `--dry-run` prévisualise sans rien supprimer ; une purge réelle destructive demande une confirmation saisie sauf `--yes`. Une purge réelle est refusée tant que le service tourne (écriture possible en cours) ; `--force` outrepasse. |
| `upgrade` | preset CMake (auto-détecté pour la plateforme, sinon demandé), `--gui`, `--force`, `--dry-run` | Tire, recompile les projets CMake, **puis met à jour les services installés ici et fusionne le contrat de config partagée `morfsystem.json`** (ajoute les clés nouvelles du clone, garde toutes les valeurs locales ; sauté avec `--only`). `--force` redéploie et redémarre chaque service même sans changement (transmis à `service.py update`). `--dry-run` affiche le plan par projet (commits entrants, recompilation, mise à jour du service, fusion de config partagée) sans rien exécuter. |
| `doctor` | `--update`, `--verbose`, `--only` | Vérifie le registre des ports, les copies vendorées, la version active des services installés et les dépôts Git ; **`--update`** ajoute la comparaison à `origin/main` (nouvelle version disponible, morfTools compris - un pas réseau). À lancer avant `push`. |
| `clean` | aucun | Supprime tous les dossiers de compilation (`build`, `build-arm64`, `build-mingw`…). |
| `status` | aucun | Affiche l'état Git court et la branche. |
| `commit` | message (demandé si omis) | Indexe toutes les modifications et valide si nécessaire. |
| `push` | aucun | Pousse la branche du manifeste vers `origin`. |

Il n'existe **ni `morf config` ni `morf exec-bits`**. Ces fonctions vivent dans des
scripts séparés à la racine de morfTools :

| Script | Usage | Action |
| --- | --- | --- |
| `./config.py shared <action>` | `status`, `validate`, `edit`, `diff`, `merge`, `install`, `apply` | Gère le fichier partagé `morfsystem.json` lu par morfMonitor et morfDashboard. `merge` = mise à niveau non destructive (ce que lance `morf upgrade`) ; `install`/`apply` = écrasement volontaire depuis le clone. |
| `./config.py deploy <projet>` | nom de projet (les liste si omis) | Déploie la config propre d'un projet, en déléguant à son `service.py config push --force`. |
| `./exec-bits.sh` / `.ps1` | `--check`, `--project NAME` | Restaure le bit exécutable de tout script portant un shebang. |

Sous Linux et Raspberry Pi, on emploie le vocabulaire de CMake : `--preset <nom>`
(ou `-p <nom>`) avec `build` et `upgrade`.

```bash
python3 morfTools/morf.py build --preset linux-arm64
python3 morfTools/morf.py upgrade -p linux
```

Une seule implémentation sur toutes les plateformes (`python3 morf.py ...`, ou
`morf ...` une fois la CLI activée) ; il n'y a pas de wrapper par plateforme. Sous
Windows, le même appel tourne sous PowerShell :

```powershell
python3 .\morfTools\morf.py build --preset mingw
```

Le preset sélectionne le preset CMake de configuration et de compilation du
projet. Les presets courants sont `mingw` (Windows/MSYS2), `linux` (Linux x86_64
natif ou WSL2), `linux-arm64` (Raspberry Pi 64 bits natif) et, là où il est
défini, `linux-arm64-cross` (compilation croisée). Il est ignoré pour les
projets PlatformIO. `--profile` et `-Profile` restent acceptés comme alias de
compatibilité.

Sans preset, `build` et `upgrade` listent ceux que déclarent les projets clonés
et demandent lequel utiliser, plutôt que de retomber sur un dossier de
compilation par défaut :

```text
No preset given for 'build'. Available presets:
  1) linux                (10/10 projects)
  2) linux-arm64          (10/10 projects)
  3) linux-arm64-cross    (3/10 projects)
  4) mingw                (10/10 projects)
Choice [1-4]:
```

Le compte indique combien de projets déclarent chaque preset. Un projet qui ne
déclare pas le preset choisi est signalé `[SKIP]` et ne fait pas échouer la
commande. `commit` demande son message de la même façon. Sans terminal (cron,
CI, entrée redirigée), les deux commandes listent les valeurs valides et
sortent en code 2 plutôt que de deviner.

### Configuration partagée sous Linux

`morfMonitor` et `morfDashboard` lisent tous deux
`/etc/morfsystem/morfsystem.json`. La source modifiable et versionnée est
`morfMonitor/config/morfsystem.example.json` ; elle est délibérément conservée
dans le dépôt pour que les changements soient relus et validés.

```bash
python3 ./morfTools/config.py shared status
python3 ./morfTools/config.py shared edit
python3 ./morfTools/config.py shared diff
python3 ./morfTools/config.py shared install
python3 ./morfTools/config.py shared apply
```

`edit` ouvre `$EDITOR` (ou `nano`) et valide le JSON. `install` crée une
sauvegarde datée avant de copier vers `/etc` ; `apply` redémarre en plus les
deux services. Ces deux commandes ne demandent sudo que pour les écritures
système.

Sous Windows, l'emplacement installé équivalent est
`%ProgramData%\morfSystem\morfsystem.json`. morfMonitor et morfDashboard
l'y cherchent par défaut (sauf si `MORFSYSTEM_CONFIG` est défini). L'outil
PowerShell reste entièrement local :

```powershell
python3 ./morfTools/config.py shared edit
python3 ./morfTools/config.py shared diff
python3 ./morfTools/config.py shared install
```

`Install` valide d'abord, crée une sauvegarde datée si nécessaire, puis copie le
fichier localement. `-ConfigPath` permet de choisir un autre emplacement.

## Vérifications d'écosystème

`doctor` commence par deux vérifications qu'aucun projet ne peut faire seul,
parce qu'elles portent sur une ressource partagée par tout le parc :

- **Registre des ports.** `ecosystem.json` détient le plan d'adressage sous la
  clé `ports`. Chaque attribution nomme le fichier de configuration et la clé
  JSON censés la déclarer ; la vérification signale les collisions, les écarts,
  et les ports déclarés dans une configuration mais absents du registre.
- **Copies vendorées.** Les bibliothèques recopiées dans `third_party/morf/`
  sont comparées à leur projet canonique. Toute dérive est signalée avec les
  fichiers en cause et la commande de resynchronisation.

La sortie est **un résumé**, pas la liste de tout ce qui a été vérifié : sain,
une soixantaine de lignes vertes noieraient le seul échec qui compte. Les
vérifications conformes sont comptées, les exceptions détaillées, et le rapport
se termine par ce qu'il faut faire :

```text
morf doctor

Écosystème
  OK  5 conforme(s) : Plan d'adressage, Versions, Copies vendorées, ...

Projets
  OK  12 conforme(s)
   X  morfMonitor

Résumé  17 OK   0 avertissement(s)   1 échec(s)

À corriger
   X  morfMonitor - active version 0.5.5 differs from project 0.5.6
        -> python3 morf.py upgrade --only morfMonitor
```

Par défaut, `doctor` reste **local et instantané** : il ne va pas sur le réseau.
Il termine alors par `Tout est conforme (versions non vérifiées).` et rappelle la
commande pour aller plus loin.

### Vérifier les nouvelles versions : `doctor --update`

Le contrôle des versions est un pas **réseau** - un `git fetch` par clone - donc
il ne s'exécute qu'à la demande, avec `--update` :

```text
morf doctor --update

Projets
  OK  12 conforme(s)
   ^  ComponentHub

Outil
  OK  1 conforme(s) : morfTools

Résumé  17 OK   1 mise(s) à jour   0 avertissement(s)   0 échec(s)

Mises à jour disponibles
   ^  morfMonitor - nouvelle version disponible : 1 commit en retard sur origin/main
        -> python3 morf.py upgrade --only morfMonitor
   ^  ComponentHub - nouvelle version disponible : 2 commits en retard sur origin/main
        -> python3 morf.py update --only ComponentHub
```

**La commande proposée dépend de ce qui tourne ici.** Si le service du projet est
actif sur cette machine, le remède est `upgrade` : reconstruire et redéployer le
service en place. S'il n'est **pas actif** - non installé ici, application de
bureau sans service, ou service arrêté - le remède est `update` : tirer la
source, sans rien redéployer. Proposer `upgrade` pour un service qui ne tourne
pas reviendrait à reconstruire et relancer ce que cette machine n'exécute pas.

Le signal est « le distant a des commits que je n'ai pas », valable pour tout le
parc - les releases GitHub ne sont publiées que pour certains projets - et sans
autre dépendance que `git`, rien qui puisse manquer sur le Pi. **morfTools s'y
vérifie lui-même** (remède : un `git pull` en place). Une mise à jour disponible
n'est **pas un échec** : elle n'affecte pas le code de retour. Une ligne de
progression sur `stderr` évite de laisser l'utilisateur dans le flou le temps des
`fetch` ; hors-ligne, le contrôle se dégrade proprement en `[SKIP]`.

L'action affichée réutilise le remède que la vérification imprime elle-même
(commande de resynchronisation, de mise à niveau) quand il existe ; sinon elle
est déduite du message. `doctor --verbose` rétablit la sortie ligne par ligne.

Attribuer un port se fait dans `ecosystem.json` **avant** de l'écrire dans la
configuration d'un service ; `doctor` échoue tant que les deux divergent. Voir
[`docs/ECOSYSTEM-CHECKS.md`](docs/ECOSYSTEM-CHECKS.md) pour le format des
registres, les plages réservées et la marche à suivre en cas de dérive.

## Synchronisation de déploiement

`scripts/windows/sync-to-morfsystem.ps1` est un utilitaire de déploiement
spécifique à Windows. Il lit `ecosystem.json` et copie le contenu des composants
vers une racine de production, sans copier ni supprimer les dossiers `.git` de
destination. Il n'effectue jamais de remplacement de texte global.

Commencer par une simulation :

```powershell
.\scripts\windows\sync-to-morfsystem.ps1 -DestinationRoot ..\..\morfSystem -DryRun
```

Lancé depuis l'espace bac à sable, la destination par défaut est le dossier
`morfSystem` voisin. Un `-DestinationRoot morfSystem` relatif est résolu depuis
le parent de l'espace bac à sable. Relancer ensuite la même commande sans
`-DryRun`. `-SkipToolProject` exclut le déploiement de morfTools lui-même.

## Licence

GPL-3.0-only. Voir [LICENSE](LICENSE).
