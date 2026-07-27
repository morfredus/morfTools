# Outils d'administration morfSystem

*Lire dans une autre langue : [English](README.md) · **Français** (ce document).*

[![Version](https://img.shields.io/badge/version-0.4.23-blue)](CHANGELOG.md)

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
- `docs/ECOSYSTEM-PRINCIPLES.md` : les principes fondateurs et les invariants d'architecture valables pour **tout le parc**, y compris les frontières qu'aucun composant ne doit franchir.
- `docs/` : documentation de l'espace de travail.

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

Sous PowerShell, depuis n'importe quel dossier :
Depuis n'importe quel dossier : `python3 <espace>/morfTools/morf.py status` (ou `./morf.py status`, il est exécutable). Une implémentation, toutes les plateformes.

### Arguments

Toutes les commandes n'opèrent que sur les projets déclarés dans
`ecosystem.json`.

| Script / commande | Arguments | Action |
| --- | --- | --- |
| `clone` | aucun | Clone les projets manquants sur la branche du manifeste. |
| `fetch` | aucun | Récupère les dépôts distants et purge les références supprimées. |
| `pull`, `update` | aucun | Tire en avance rapide depuis la branche du manifeste. |
| `build` | preset CMake (demandé si omis) | Compile les projets PlatformIO, ou configure et compile les projets CMake. |
| `install` | aucun | Installe `requirements.txt` s'il existe. |
| `upgrade` | preset CMake (demandé si omis) | Tire puis recompile les projets CMake. |
| `doctor` | `--update`, `--verbose`, `--only` | Vérifie le registre des ports, les copies vendorées, la version active des services installés et les dépôts Git ; **`--update`** ajoute la comparaison à `origin/main` (nouvelle version disponible, morfTools compris - un pas réseau). À lancer avant `push`. |
| `clean` | aucun | Supprime tous les dossiers de compilation (`build`, `build-arm64`, `build-mingw`…). |
| `status` | aucun | Affiche l'état Git court et la branche. |
| `commit` | message (demandé si omis) | Indexe toutes les modifications et valide si nécessaire. |
| `push` | aucun | Pousse la branche du manifeste vers `origin`. |
| `config.py shared` | `status`, `validate`, `edit`, `diff`, `install`, `apply` | Gère la configuration partagée lue par morfMonitor et morfDashboard. |

Sous Linux et Raspberry Pi, on emploie le vocabulaire de CMake : `--preset <nom>`
(ou `-p <nom>`) avec `build` et `upgrade`.

```bash
./morfTools/build.sh --preset linux-arm64
./morfTools/upgrade.sh -p linux
```

Le raccourci accepte aussi un preset en position simple, par exemple
`./morfTools/build.sh linux-arm64`. Sous PowerShell, utiliser `-Preset <nom>` :

```powershell
.\morfTools\build.ps1 -Preset mingw
python3 ./morfTools/morf.py upgrade --preset linux-arm64
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
