# Outils d'administration morfSystem

*Lire dans une autre langue : [English](README.md) · **Français** (ce document).*

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
| `doctor` | aucun | Vérifie le registre des ports, les copies vendorées et la version active des services installés, puis les dépôts Git et leur `origin` ; à lancer avant `push`. |
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

```text
[ecosystem]
--- addressing plan ---
[OK] morfSensor: 8788
--- vendored copies ---
[OK] morfSensor/third_party/morf/beacon matches morfBeacon
```

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
