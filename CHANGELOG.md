# Changelog

## [0.35.2] - 2026-09-06

### Changed

- **`scripts/host/wifi-stability/morfNetWatchdog.sh`**: step 3 (Wi-Fi driver
  reload) now only runs when the monitored interface is actually wireless.
  It is a driver-specific action and must not fire just because some interface
  lost connectivity: on an Ethernet host the pi4dev test showed the auto-detected
  driver would be `eth0`'s, so an unguarded step 3 would bounce Ethernet. The
  interface type is read from sysfs (`wireless` dir or `phy80211` link), so the
  guard depends on neither `brcmfmac` nor `iw`, and the driver stays
  auto-detected. A non-Wi-Fi interface logs `palier 3 ignore : <iface> n'est pas
  une interface Wi-Fi` and the escalation moves on.

## [0.35.1] - 2026-09-06

### Fixed

- **`scripts/host/wifi-stability/morfNetWatchdog.sh`**: step 1 (reconnect) used
  `nmcli device reconnect`, which some NetworkManager builds reject ("argument
  'reconnect' not understood", seen on pi4dev). Replaced with the portable
  `nmcli device connect <iface>` (also safer: no `disconnect` that could leave the
  interface stuck offline if the bring-up fails). The first real run on pi4dev
  otherwise validated the mechanism end to end: LAN loss counted every minute,
  escalation all the way to the step-4 reboot (~12 min), and after the reboot the
  watchdog auto-detected the link back over `eth0` (gateway 192.168.1.1) --
  confirming the monitoring is not tied to `wlan0`.

## [0.35.0] - 2026-09-06

### Added

- **`scripts/host/wifi-stability/`**: host-hardening kit for a Wi-Fi machine that
  must stay reachable. It answers a real incident on a Raspberry Pi: the Broadcom
  `brcmfmac` driver froze during a mesh roam (802.11v band steering), leaving the
  host powered on but offline for hours. Two independent parts, installed once per
  host, fully parameterised (nothing hard-coded to a given interface, SSID,
  gateway or BSSID). Naming follows the parc convention: `morfNet`-prefixed
  scripts, lowercase systemd service (`morfnetwatchdog`):
  - `morfNetStabilize.sh` applies the NetworkManager settings that curb the
    driver lock-up (disable power save, optionally pin band/BSSID); connection is
    auto-detected or passed as an argument.
  - `morfNetWatchdog.sh` plus its systemd `.service`/`.timer` add a progressive
    network watchdog, independent of the morf\* services (systemd + `nmcli` +
    `modprobe` only). It tests the LAN gateway every minute and escalates on
    consecutive failures: reconnect -> restart NetworkManager -> reload the Wi-Fi
    driver -> reboot as a last resort (with a 30 min anti-loop guard). Each step
    is configurable through `/etc/morfsystem/morfnetwatchdog.conf` and can be
    disabled by setting it to `0`.
  - `morfNetInstall.sh` deploys and enables the watchdog (idempotent; the `/etc`
    config is never overwritten), or removes it with `--uninstall`.

## [0.34.28] - 2026-09-03

### Fixed

- **`scripts/windows/sync-to-morfsystem.ps1`**: exclude `build-arm64` and
  `build-arm64-cross` (and `.codex`) from the robocopy consolidation. These CMake
  build trees were copied sandbox -> production, carrying absolute paths from the
  sandbox in their `CMakeCache.txt`, so a later `cmake --preset linux-arm64-cross`
  in production failed ("source does not match", "directory is different"). Build
  directories must be rebuilt in place, never mirrored; `build` and `build-mingw`
  were already excluded, the arm64 ones were missing.

## [0.34.27] - 2026-09-03

### Changed

- **`publish-releases.sh`** now prints a clear red banner when the chain aborts
  (it runs under `set -e`), naming the failing step and reminding that the later
  steps -- the arm64 packaging included -- did not run. It no longer lets the real
  cause drown in the verbose output.
- **`publish-releases.sh` step 3** notes, when `--with-arm64-cross` is set, that
  the arm64 cross-build is produced at step 5 (packaging), not here: the
  `auto-detected ... : linux` line only concerns the native warm-up and was being
  misread as "arm64 skipped".
- **`create-source-releases.py`** ends with an explicit summary of every repo it
  refused (dirty working tree, or a branch ahead of origin) and states that the
  chain stops before packaging, so a single blocked repo is obvious rather than
  buried mid-run.

## [0.34.26] - 2026-09-03

### Changed

- **`create-source-releases.py`** now fails cleanly when the GitHub CLI (`gh`) is
  not installed, instead of raising an uncaught `FileNotFoundError`. The message
  gives the install command and `gh auth login`, and states that `gh` uses its own
  token -- independent of the git remote protocol (SSH or HTTPS). This is the case
  hit when publishing from a fresh WSL where `gh` is absent.

## [0.34.25] - 2026-09-03

### Added

- **`morf remotes`**: inspect every clone's `origin` protocol across the parc and,
  only on an explicit `--to ssh|https`, uniformise them. The conversion is shown
  first, confirmed (or `--yes`), and preserves the real remote repository name read
  from the URL -- never derived from the local folder, which keeps a renamed repo
  (e.g. `morfSync` whose origin still points at `HomeServerHub`) correct. `--only`
  scopes it to one repo; `--dry-run` previews without touching anything.

### Changed

- **`morf doctor`** now reports each repo's `origin` protocol (INFO, shown with
  `--verbose`) and a parc-wide `origin: N SSH, M HTTPS` line. HTTPS/SSH coexistence
  is stated as a supported configuration, never a warning: heterogeneity is not a
  defect. A repo with no recognisable `origin` is the only case that warns.
- **Remote git operations** (`morf dev pull`/`push`/`clone`) now print a targeted,
  protocol-aware hint when access is *refused* (missing HTTPS credentials, or an
  unaccepted SSH key). The hint distinguishes an authentication problem from an
  invalid protocol -- it never presents HTTPS as an error and never rewrites a
  remote. Nothing about protocol selection changed: `origin` is used exactly as
  each repo configures it, so a parc can be all-HTTPS, all-SSH, or mixed.

## [0.34.24] - 2026-09-03

### Added

- **`package-all.py --with-arm64-cross`**: opt-in, additionally cross-builds each
  project's Linux arm64 target from an x86_64 Linux host (WSL). It widens the target
  selection; the project's own `service.py package` routes the named non-native arm64
  target to the `linux-arm64-cross` CMake preset (morfdeploy). Needs a prepared
  sysroot (`MORF_SYSROOT`); a declared no-op on any other host, so the same
  invocation stays safe everywhere.
- **`publish-releases.sh --with-arm64-cross` / `publish-releases.ps1 -WithArm64Cross`**:
  forward the switch through the release chain, for multi-arch publishing (win64 +
  linux-x64 + linux-arm64) from a single PC.

## [0.34.23] - 2026-08-25

### Ajouté

- **`package-all.py` : stratégie de packaging `source-bundle`.** Un projet non
  compilé (ex. morfDashboard) peut déclarer une cible `format: source-bundle` ;
  package-all délègue alors à son `service.py package` (le projet sait quels
  fichiers sont distribuables) et collecte l'archive `<projet>-<version>-source-
  bundle.tar.gz`. Nom d'artefact dédié (l'extension `.tar.gz` diffère du format).
  Le flux compilé (.deb/.zip/firmware) est inchangé.

## [0.34.22] - 2026-08-25

### Corrigé

- **Résilience aux coupures SSH/réseau sur les opérations git distantes.** Une
  connexion GitHub qui saute (« Connection closed by ... port 22 », « closed by
  remote host », blip DNS...) pendant `morf dev pull`/`push` ou
  `create-source-releases.py` faisait échouer toute la chaîne de publication. Un
  nouveau helper `lib/morftools/gitretry.py` réessaie avec backoff **uniquement**
  ces hoquets de transport transitoires (jamais un vrai refus : auth,
  non-fast-forward, conflit, clé d'hôte). Utilisé par `commands.py`
  (clone/fetch/pull/push) et `create-source-releases.py` (fetch/pull).

## [0.34.21] - 2026-08-25

### Corrigé

- **`morf doctor` était faussement vert sur « Bits exécutables ».** Il appelle
  `scripts/exec-bits.py --check`, mais celui-ci liste les scripts fautifs sans
  marqueur `[FAIL]` et signale l'échec par son seul code de sortie ; ce code
  était ignoré et le rapport ne juge que sur les marqueurs, si bien qu'un vrai
  manque de bit exécutable passait pour conforme. Le verdict est désormais
  relayé via `forced_fail`, et un bit manquant ressort bien en échec.

## [0.34.20] - 2026-08-23

### Modifié

- GUIDE-DEMARRAGE (« Ce qu'il vous faut ») nomme désormais explicitement **Ninja**
  et **exiftool** (runtime de morfPhoto) dans la liste rapide des prérequis, et
  renvoie à la ligne `apt` unique de ENVIRONNEMENT-DEV §3.1. Prérequis validés en
  conditions réelles : primo-installation complète depuis zéro sur pi4dev le
  2026-08-23 (9 services buildés et démarrés).

## [0.34.19] - 2026-08-23

### Corrigé

- Les étapes de déploiement privilégiées (`sudo python3 service.py ...`)
  laissaient un cache bytecode `__pycache__/*.pyc` **root:root** dans l'arbre
  source de l'utilisateur (la copie vendorée morfdeploy). Ces fichiers n'étaient
  ensuite ni supprimables ni reconstruisibles sans sudo : un `rm -rf ~/Codage`
  en simple utilisateur (script de remise à blanc) échouait en « Permission
  denied ». `elevated()` lance désormais Python avec `-B` (pas d'écriture du
  cache) : l'arbre source reste entièrement à l'utilisateur.

## [0.34.18] - 2026-08-23

### Ajouté

- `morf install/deploy --all` respecte une **priorité de déploiement** déclarée
  dans `ecosystem.json` (`deployPriority`) : les services fondamentaux
  (morfBeacon, puis morfUpdate avant morfMonitor) passent en tête pour une
  première installation prévisible. C'est un simple tri de la sélection, **pas
  une dépendance** : un service fondamental non sélectionné n'est jamais tiré de
  force et n'empêche pas les autres de s'installer (morfMonitor tolère l'absence
  de morfUpdate). L'autonomie de chaque service reste entière.

## [0.34.17] - 2026-08-23

### Corrigé

- `morf doctor` (contrôle des copies vendorées) comparait `morfdeploy` via une
  liste de fichiers figée : seuls 5 des 12 fichiers du paquet étaient contrôlés.
  Les fichiers arrivés depuis (`package.py`, `provenance.py`, `builddeps.py`,
  `configmerge.py`, `morfproject.py`, `record_compile.*`, `sysdeps.py`) et
  `VERSION` échappaient au contrôle, laissant une dérive de la logique de
  packaging passer inaperçue. Le manifeste passe en mode `compareRoot` : tout le
  dossier `morfdeploy` est comparé (couvre d'office les fichiers futurs) et
  `VERSION` est enfin vérifié, via `versionSource` pour son emplacement décalé.

## [0.34.16] - 2026-08-23

### Modifié

- `package-all --sync` récupère tous les assets déjà indexés, construit le
  livrable natif de la machine, puis publie **tous** les sidecars de la version
  (`.deb` Linux et `.zip` Windows). PhotoHub a un zip Windows. Les scripts
  `.ps1` s'exécutent avec `pwsh` ou `powershell`.

## [0.34.15] - 2026-08-20

### Corrigé

- Le guide de démarrage indique le chemin réellement utilisé par les paquets :
  `/etc/morfsystem/<service>`, et non l'ancien `/etc/<service>`.

## [0.34.14] - 2026-08-20

### Corrigé

- Le guide supprime les commandes historiques contradictoires et conserve un
  seul parcours vérifié pour Windows, Linux AMD64 et Linux ARM64.

## [0.34.13] - 2026-08-20

### Ajouté

- `package-all --no-publish` construit les livrables et leurs sidecars sans
  publication, afin de réunir tous les formats avant une passe unique de
  `publish-dist`.

### Documentation

- Le workflow fournit le parcours complet du parc sur Windows, Linux AMD64 et
  Linux ARM64, avec des blocs de commandes homogènes et une publication finale
  unique.

## [0.34.12] - 2026-08-20

### Documentation

- Le workflow rend explicite que les releases source sont vides et que
  `publish-dist` exige un livrable et son sidecar produits par `package-all`.

## [0.34.11] - 2026-08-20

### Ajouté

- Le port HTTP 8794 est réservé à l'agent local morfUpdate.

## [0.34.10] - 2026-08-20

### Modifié

- Le workflow distingue désormais la release utilisateur unique du projet et
  l'index technique de provenance maintenu par morfPackages.

## [0.34.9] - 2026-08-20

### Corrigé

- `create-source-releases.py --all` inclut désormais morfTools, afin que ses
  versions reçoivent elles aussi leur release GitHub source.

## [0.34.8] - 2026-08-20

### Modifié

- Le workflow présente désormais, dans l'ordre, les commandes complètes pour
  Windows, Linux AMD64, Linux ARM64 et la publication finale depuis `dist`.

## [0.34.7] - 2026-08-20

### Ajouté

- `publish-dist.py` publie en une passe les livrables déjà réunis dans `dist`
  et les rend disponibles dans les releases source des projets.

## [0.34.6] - 2026-08-20

### Corrigé

- Les archives collectées depuis un script de projet sont identifiées par leur
  nom canonique, y compris après une synchronisation préalable de la release.

## [0.34.5] - 2026-08-20

### Corrigé

- Une provenance existante mais incomplète est détectée avant publication et
  régénérée automatiquement, notamment pour les firmwares ESP32.

## [0.34.4] - 2026-08-20

### Corrigé

- Le collecteur d'archives produites par les scripts de projet reçoit désormais
  la version attendue et ne s'arrête plus après une archive Windows réussie.

## [0.34.3] - 2026-08-20

### Documentation

- Le workflow de packaging s'adresse désormais à tous les utilisateurs, avec
  des instructions à l'infinitif plutôt qu'à la première personne.

## [0.34.2] - 2026-08-20

### Corrigé

- Un firmware déjà présent sans sidecar est reconstruit et reçoit sa provenance
  au lieu d'être refusé comme livrable ambigu lors de la reprise.

## [0.34.1] - 2026-08-20

### Documentation

- La création groupée des releases source est maintenant présentée explicitement
  pour Windows et Linux, comme une étape unique exécutée depuis l'une des deux
  plateformes avant les packagings.

## [0.34.0] - 2026-08-20

### Corrigé

- Les projets qui possèdent leur script de packaging sont maintenant configurés
  et compilés par `package-all` avant la création de leur archive.

### Documentation

- Le workflow décrit la barrière stricte entre le commit du tag source et tous
  les artefacts réunis dans une release de distribution.

## [0.33.2] - 2026-08-20

### Documentation

- Le workflow rappelle que chaque projet conserve sa propre version et distingue
  les créations directes de release publique des tests sur remotes privés.

## [0.33.1] - 2026-08-20

### Documentation

- Le workflow contient maintenant les commandes complètes pour créer les
  releases source puis construire et publier tout le parc depuis Windows,
  Linux AMD64 et Linux ARM64.

## [0.33.0] - 2026-08-20

### Ajouté

- La première release de distribution reçoit automatiquement un résumé court de
  la section correspondant à sa version dans `CHANGELOG.md`.
- Un `RELEASE-NOTES.md` facultatif permet une introduction personnelle par
  projet et le marqueur `{{changelog_summary}}` choisit l'emplacement du résumé.

## [0.32.1] - 2026-08-20

### Corrigé

- La collecte Linux des scripts de projet reconnaît aussi l'extension
  `AppImage` utilisée par linuxdeploy.

## [0.32.0] - 2026-08-20

### Corrigé

- Les firmwares déclarés avec un seul identifiant matériel produisent désormais
  une provenance publiable.
- Les archives déjà construites et vérifiées sont publiées lors d'un nouveau
  passage, sans reconstruction inutile.
- Les projets ayant leur propre script de paquet sont centralisés dans le
  répertoire commun avec un nom conforme avant publication.

## [0.31.2] - 2026-08-20

### Corrigé

- La vérification GitHub interroge maintenant l'API au lieu de se fier à une
  session locale mémorisée mais devenue invalide.

## [0.31.1] - 2026-08-20

### Corrigé

- `create-source-releases.py` vérifie la connexion GitHub avant tout préflight
  et rapporte les erreurs de commande sans traceback.

## [0.31.0] - 2026-08-20

### Modifié

- Les releases source se créent maintenant aussi depuis la sandbox, sur le
  remote privé déduit de chaque clone. La production reste une synchronisation
  manuelle, puis le même workflow sur ses remotes canoniques.

## [0.30.0] - 2026-08-20

### Ajouté

- `create-source-releases.py` : crée en une passe les releases source après la
  synchronisation manuelle de la production, avec `--all` ou `--only`.

## [0.29.0] - 2026-08-20

### Ajouté

- `--release-notes` pour donner le texte de la première release morfPackages,
  et le guide `docs/WORKFLOW-PACKAGING.md` qui décrit le passage source,
  Windows, Linux et reprise manuelle.

## [0.28.0] - 2026-08-20

### Modifié

- **Publication intégrée à `package-all.py`** : le dépôt morfPackages est
  précontrôlé et mis à jour avant toute production, puis chaque livrable propre
  et prouvé est envoyé automatiquement vers sa release GitHub privée. Les
  binaires restent exclusivement des assets de release, jamais des fichiers Git.

## [0.27.0] - 2026-08-20

### Ajouté

- **Sidecar de provenance de distribution** : chaque livrable effectivement
  produit par `package-all.py` reçoit un fichier `.metadata.json` voisin,
  contenant le commit Git complet, la cible, la plateforme et le SHA-256. Une
  source sale ou un livrable ambigu est refusé ; morfPackages peut donc publier
  sans réinterpréter l'origine du fichier.

## [0.26.0] - 2026-08-20

### Ajouté

- **`package-all.py --sync`** : avant de produire une cible locale, récupère les
  assets déjà publiés pour cette même release dans le dossier de distribution
  commun. La lecture passe par le script de `morfPackages` et donc uniquement par
  `gh release`, sans écrire de binaire dans Git ni publier quoi que ce soit.

## [0.25.0] - 2026-08-19

### Modifié

- **`morf install` devient la vraie commande de primo-installation.** Le verbe
  naturel installe désormais les services (tout ou partie) **et** leur
  configuration en une passe - c'est l'ancien moteur `deploy` :
  - `morf install` : sélection interactive (tous ou une partie) + choix du mode de
    config ; `morf install --all` ; `morf install morfCollector morfMonitor` ;
    `--config keep|merge|replace` (keep par défaut, jamais d'écrasement sans
    demande) ; `--dry-run` ; `--yes`.
  - `morf deploy` reste un **alias rétrocompatible** (affiche une note qui pointe
    vers `install`). `morf install --services` reste accepté (= `--all`).
- **`morf setup`** : nouvelle commande pour l'ancien comportement générique de
  `install` (dépendances Python ; « SKIP » pour les services C++). Il ne
  monopolise plus le mot `install`.

## [0.24.1] - 2026-08-19

### Ajouté

- **`sync-to-morfsystem.ps1` promeut aussi `.morfredus`.** Le dossier personnel
  `.morfredus_travail` (journaux de session, notes de travail) est désormais
  synchronisé vers `<prod>/.morfredus`, avec le même nommage `_travail` → prod, les
  mêmes exclusions et le même `-WhatIf`/dry-run que les projets. Absent → simple
  avertissement, jamais un échec.

## [0.24.0] - 2026-08-19

### Ajouté

- **`package-all.py` : l'orchestrateur de packaging** (Phase 4), **hors
  `morf.py`** - packaging = un métier à part, morfTools reste le chef d'orchestre
  sans recette. Il lit chaque `morfproject.json`, ne garde que les targets
  **buildables sur cette machine** (natif = os+arch de l'hôte ; firmware = toute
  machine avec PlatformIO), et délègue au bon producteur :
  - provider `morfdeploy` → `service.py package --target … --out …` (build prouvé
    + `.deb`/`.zip`) ;
  - provider `project` → le script de packaging déclaré sur la target ;
  - firmware (`build.tool` platformio) → build PlatformIO + `firmware.bin` renommé ;
  - provider `none` / pas de target native → signalé et ignoré.
  - **Idempotent** (saute un livrable `morfdeploy` déjà présent, `--force` pour
    refaire), `--dry-run` (plan sans rien construire), `--out` (dossier de
    distribution commun), `--only`. Ne **publie** rien : la distribution vers
    morfPackages (assets de Releases) est la Phase 5, volontairement séparée.

## [0.23.1] - 2026-08-19

### Corrigé

- **`morf install` (sans `--services`) : message clair pour un service.** Un
  parc C++ n'a aucun `requirements.txt` : un `morf install` nu affichait
  « [SKIP] no generic install definition » pour chaque projet, sans dire quoi
  faire. Un projet portant un `service.py` (hors template) affiche désormais
  « [SKIP] service — run 'morf install --services' to deploy it », qui pointe la
  commande qui l'installe réellement.

## [0.23.0] - 2026-08-19

### Modifié

- **`morfproject.json` : schéma v1 riche.** Le contrat gagne `schema_version`,
  `project` (`id` + `type` parmi service/application/firmware/library/tool/
  documentation/meta/template) et un `packaging` où `targets` est **une map par
  livrable** : chaque target porte `platform` (`os`/`arch`), `build`
  (`preset` pour morfdeploy, `script` ou `tool` pour un projet) et `package`
  (`format`, `architecture`, et un `provider` **optionnel qui surcharge** le
  provider par défaut du projet). `packaging.provider` est le **provider par
  défaut** (none/morfdeploy/project) ; la **classification** reste portée par
  `project.type`. Architectures normalisées en interne (`x86_64`, `arm64`).
  Le loader ne connaît que le schéma ; il découvre les dépôts et agrège.

## [0.22.0] - 2026-08-19

### Ajouté

- **Contrat projet `morfproject.json` (schéma + loader).** morfTools lit un
  manifeste uniforme à la racine de chaque dépôt - `type`
  (`service`/`application`/`firmware`) et `packaging` (provider `morfdeploy` ou
  `project`, cibles) - distinct de `service.json` (une UI ou un firmware n'est pas
  un service). morfTools ne connaît que le **schéma**, jamais la liste des
  projets : il découvre les dépôts et agrège leurs déclarations
  (`lib/morftools/morfproject.py`). Un fichier absent = projet pas encore
  onboardé (ignoré) ; un fichier malformé = erreur.
- **Provenance dans `morf build`.** Après un build CMake réussi, un service
  standardisé (`provider: morfdeploy`) est marqué : `morf build` appelle
  `service.py build-info` (morfdeploy localise l'artefact et écrit
  `build-info.json`). **Aucune heuristique de localisation** côté morfTools ; les
  projets qui possèdent leur packaging (`provider: project`) écrivent leur
  provenance dans leurs propres scripts. Jamais bloquant pour un build.

## [0.21.2] - 2026-08-19

### Modifié

- **`docs/GUIDE-DEMARRAGE.md` §2 renvoie à `ENVIRONNEMENT-DEV.md`.** La section
  « Ce qu'il vous faut » listait les prérequis sans mener au guide d'installation
  détaillée par plateforme ni au piège des bibliothèques non-Qt (OpenSSL, libssh2,
  nlohmann_json, zlib) sur une toolchain neuve. Le lien manquant est ajouté :
  celui qui part de zéro trouve désormais l'installation complète avant de compiler.

## [0.21.1] - 2026-08-18

### Ajouté

- **`docs/ENVIRONNEMENT-DEV.md`** : guide d'installation de l'environnement de
  développement et des **dépendances de compilation** du parc (toolchain commune,
  composants Qt6 utilisés, bibliothèques non-Qt par projet - OpenSSL, libssh2,
  nlohmann_json, zlib -, installation par plateforme Debian/Mint/Pi et Windows
  MSYS2 vs Qt officielle, firmware PlatformIO, dépendances runtime, récapitulatif
  par projet). Référencé depuis `README.md` et `README.fr.md`. Objectif : compiler
  le parc sans erreur sur une machine neuve, en documentant explicitement le point
  qui a piégé l'Asus (la toolchain Qt officielle ne fournit pas OpenSSL/libssh2/
  nlohmann_json/zlib, donc morfCollector/morfSync/SiteWatch n'y compilent pas sans
  ces bibliothèques).

## [0.21.0] - 2026-08-18

### Ajouté

- **`morf build` et `morf deploy` résolvent les dépendances de build AVANT de
  compiler** (via morfDeploy 0.9.0). Avant `cmake --preset`, chaque projet qui
  déclare des `build_dependencies` (par `service.py build-deps`) voit ses
  bibliothèques de compilation vérifiées : sur Debian, installées avec validation
  (`--yes` transmis depuis `deploy --yes`) ; sur une toolchain sans gestionnaire
  (Qt officielle Windows), simplement annoncées, le build restant le juge. Une
  dépendance obligatoire non satisfaite marque le projet **FAILED** (rattrapé, pas
  de cascade) avec un message clair au lieu d'une erreur `find_package` opaque.
  Un projet non-service (sans `service.py`) n'a pas encore ce contrat : no-op.

## [0.20.1] - 2026-08-18

### Corrigé

- **`morf deploy` ne s'arrête plus au premier échec de build.** Une erreur de
  compilation d'un service (ex. une dépendance introuvable comme OpenSSL)
  remontait en **traceback non rattrapé** et abandonnait tout le déploiement.
  `run_deploy` rattrape désormais l'exception par projet, la marque **FAILED**
  dans le résumé, et poursuit les services suivants -- comme la boucle générique
  de `build`/`upgrade` le fait déjà.

## [0.20.0] - 2026-08-18

### Corrigé

- **`morf deploy` / `install --services` / `upgrade` n'assument plus la commande
  `python3`.** Les appels au `service.py` de chaque projet utilisaient le
  littéral `"python3"` ; sur une machine Windows fraîche (Python installé comme
  `python`/`py`, sans alias `python3`), `deploy` plantait avec `WinError 2` au
  moment d'appeler `service.py install`. Tous ces appels utilisent désormais
  **`sys.executable`** (l'interpréteur réellement en cours), comme le code de
  purge/uninstall le faisait déjà. Même leçon que la toolchain de build : ne pas
  supposer l'environnement du poste principal.
- **`build_as_user` de morfDeploy adapté aussi** (via morfDeploy 0.8.0) : si un
  `service.py install` recompile sur une machine à la toolchain différente, il
  surcharge le preset `mingw` figé comme `morf build`.

## [0.19.0] - 2026-08-18

### Corrigé / Ajouté

- **`morf build` s'adapte à la toolchain réellement présente** (Windows). Le
  preset `mingw` figeait les chemins MSYS2 d'une machine (`C:/msys64/mingw64/bin/
  ninja.exe`, `c++.exe`, `CMAKE_PREFIX_PATH`), donc échouait sur une machine
  neuve avec une autre disposition (toolchain Qt officielle sous `C:/Qt/...`) :
  `'…/ninja.exe' failed with: no such file or directory` sur les 15 projets.
  morfTools **détecte** désormais ninja, le compilateur MinGW (g++/gcc) et le
  préfixe Qt (via `CMAKE_PREFIX_PATH`/`Qt6_DIR`/`qmake` sur le PATH) et
  **surcharge** les valeurs figées du preset avec des `-D` — sans éditer les 13
  presets. Un élément manquant est signalé clairement une fois (pas 13 échecs
  cryptiques). Détection mise en cache (une fois par run).
- **PlatformIO absent géré proprement** : `morf build` saute le firmware ESP32
  avec un avis (« installer PlatformIO ») au lieu de crasher sur `pio`
  introuvable (`WinError 2`).
- **`morf doctor` : section « Toolchain build (Windows) »** (ninja, compilateur,
  préfixe Qt), pour comprendre l'état de compilation d'une machine avant de
  builder.

## [0.18.0] - 2026-08-18

### Ajouté

- **`morf clone` détecte l'accès Git au lieu de le supposer**, pour tourner sur
  une machine neuve sans la préparation implicite du poste de dev. Nouveau module
  `gitaccess.py` (lecture seule : git/ssh présents, clé présente, **accès GitHub
  SSH réellement vérifié** par `git ls-remote` en batch, HTTPS joignable). Option
  **`--protocol auto|ssh|https`** :
  - `auto` (défaut) : SSH s'il s'authentifie vraiment à GitHub, sinon propose
    HTTPS (menu interactif ; repli HTTPS en non-interactif avec `--yes`).
  - `ssh` : échoue proprement si SSH n'est pas opérationnel, en disant ce qui
    manque et comment poursuivre.
  - `https` : clone via HTTPS (mode d'accès valide, pas un simple fallback) ;
    URL dérivée de la template SSH (`git@host:owner/…` → `https://host/owner/…`)
    ou `httpsUrlTemplate` du manifeste.
  - **Ne configure jamais SSH** (aucune génération de clé, aucune modif `~/.ssh`) :
    l'option « configurer SSH » montre seulement la marche à suivre. `--yes`
    autorise le repli HTTPS en non-interactif.
- **`morf doctor` : section « Accès Git »** (git, ssh, clé SSH, accès GitHub SSH,
  clone HTTPS). Les tests réseau (SSH/HTTPS) sont gated sur `--update` ; les
  vérifications locales s'affichent toujours. On comprend l'état d'une machine
  neuve avant même de cloner.

## [0.17.0] - 2026-08-17

### Ajouté

- **Détection automatique du preset plateforme** (§18) quand `--preset` est omis :
  Windows → `mingw`, Raspberry Pi / ARM64 → `linux-arm64`, Linux x64 → `linux`,
  et seulement si le projet déclare ce preset. Priorité `--preset` explicite >
  détection fiable > question interactive. L'architecture décide, jamais
  l'identité de la machine (un serveur ARM64 vaut un Pi).

### Modifié

- **`morf update` comme opération Git est déprécié** (transition, §17) : il
  affiche un avertissement et **renvoie vers `morf dev pull`**, tout en continuant
  de faire le pull (habitudes et scripts préservés). `update` quitte la surface
  `dev` (le git pull s'y nomme `pull`). `morf update` est réservé au sens futur
  « mettre à jour les composants installés ». `morf upgrade` reste la mise à
  niveau complète de la machine (pull + build + déploiement).

## [0.16.0] - 2026-08-17

### Ajouté

- **`--dry-run` transverse à `update`/`pull` et `upgrade`.** `pull`/`update
  --dry-run` récupère et liste les commits entrants sans fusionner. `upgrade
  --dry-run` affiche le plan par projet (commits entrants, recompilation prévue,
  mise à jour du service installé, fusion de la config partagée) sans rien
  exécuter, et **ne demande plus de preset** (aucune compilation en dry-run). La
  simulation traverse jusqu'au clone/service, elle ne prétend pas côté morfTools.

## [0.15.0] - 2026-08-17

### Ajouté

- **`morf uninstall` refondu** avec sélection, aperçu et protections (§12) :
  nommer des services, `--all` (ou forme nue) pour tous, `--only` pour un
  (compat). **`--dry-run`** liste ce qui serait désinscrit et, avec `--purge`,
  supprimé, sans rien toucher (traverse jusqu'au `service.py` du projet). Retirer
  des services demande une confirmation ; **`--purge`** exige un **jeton saisi**
  (`PURGE`, ou `PURGE ALL` pour un balayage machine) ; un run non interactif
  exige `--yes`. Un `Entrée` trop rapide ne peut plus détruire des données.
- **Garde-fou de purge sur service actif** câblé dans `morf purge` : `--force`
  transmis à `service.py purge`, qui refuse d'effacer des données qu'un service en
  cours d'exécution pourrait être en train d'écrire (voir morfDeploy 0.4.0).

## [0.14.0] - 2026-08-17

### Ajouté

- **Commande `morf deploy` : installation sélective des services avec choix de
  configuration.** Le cœur de la façade d'administration (§6 du chantier).
  - **Sélection** selon la priorité du brief : une liste explicite ou `--all`
    l'emporte ; sinon un terminal propose un **choix numéroté** (`[x]` du brief,
    resté un simple script terminal utilisable en SSH) ; un run non interactif
    sans sélection est une **erreur**, jamais une supposition.
  - **`--config keep|merge|replace`** décide du sort de la configuration de
    chaque service : `keep` (défaut sûr, n'écrase jamais), `merge` (ajoute les
    clés nouvelles du clone, garde les valeurs locales), `replace` (écrase depuis
    le dépôt, sauvegarde horodatée d'abord). Mappé sur ce que `service.py config`
    sait déjà faire. Le mode n'est demandé qu'en interactif ; un run scripté garde
    `keep` sauf `--config`.
  - **`--dry-run`** affiche le plan (build/install/config par service) sans rien
    exécuter. **Résumé final** par service. `replace` non interactif exige `--yes`.
  - Réutilise la machinerie éprouvée (`install --services` reste la forme « tout
    le parc ») : compile sous le compte utilisateur, n'élève que l'installation
    et l'écriture de config.

## [0.13.0] - 2026-08-17

### Ajouté

- **Espace de noms `morf dev <sous-commande>`** pour la surface développeur (Git
  et build) : `clone`, `fetch`, `pull`, `update`, `status`, `push`, `commit`,
  `build`, `clean`. Sépare visuellement l'administration d'une machine
  (`deploy`/`install`, `update`, `upgrade`, `purge`, `uninstall`, `doctor`) du
  travail sur les clones en tant que code source. **Additif et rétrocompatible** :
  les formes plates (`morf clone`) restent valables (habitudes, `activate-cli`,
  scripts) ; `morf dev` seul liste les sous-commandes ; `morf dev <admin>` est
  refusé avec un rappel. Une seule et même implémentation par commande (le `dev`
  n'est qu'une réécriture vers la commande plate, mêmes contrôles et élévation).

## [0.12.0] - 2026-08-17

### Ajouté

- **Commande `morf purge` : effacement de données orchestré, piloté par ce que
  chaque projet annonce.** morfTools ne lit aucun `service.json` et ne connaît
  aucun emplacement de données : il demande à chaque clone ce qu'il sait effacer
  (`service.py purge --list`, découverte JSON de morfDeploy 0.3.0) et renvoie les
  catégories choisies au `service.py` du projet, qui exécute. La connaissance
  reste dans le projet, morfTools orchestre.
  - `morf purge` seul **liste** ce qui est purgeable sur cette machine (n'affiche
    que les projets clonés qui déclarent des catégories) et montre comment cibler.
  - `morf purge <projet> <id>…` ou `morf purge <projet> --all` cible un projet ;
    `morf purge --all` balaie tous les projets de la machine.
  - **`--dry-run`** prévisualise sans rien supprimer, en traversant jusqu'au
    `service.py` du projet (la simulation est réelle, pas une prétention côté
    morfTools).
  - **Confirmation renforcée** d'une purge réelle destructive : saisie d'un jeton
    (`PURGE`, ou `PURGE ALL` pour un balayage machine), refus en non-interactif
    sans `--yes` (un cron doit dire `--yes` pour effacer, jamais par défaut).
  - **Résumé final** par projet/catégorie (OK / FAILED), sans masquer ce que les
    projets ont réellement exécuté.
  - Une catégorie inconnue, `--all` combiné à des ids, un projet inconnu, ou ces
    options hors `purge` sont refusés proprement (code 2).

## [0.11.0] - 2026-08-17

### Modifié

- **Bascule de la source canonique de `morfdeploy` vers le dépôt dédié
  `morfDeploy`.** Le registre `vendored` d'`ecosystem.json` pointait encore sur
  `morfTools/lib/morfdeploy` alors que les `scripts/sync-morf.*` tiraient déjà
  leur source de `morfDeploy` (avec repli transitoire). Le détecteur de dérive
  (`ecosystem-check vendor`) et la synchronisation désignent maintenant la même
  et unique source de vérité. Changement **purement structurel** : les copies
  vendorées dans les 13 consommateurs sont inchangées (elles étaient déjà
  synchronisées depuis `morfDeploy`), vérifié par `ecosystem-check` intégral.

### Supprimé

- **`lib/morfdeploy`** : la copie qui servait de graine canonique quitte
  morfTools. Elle n'était jamais importée ni exécutée par morfTools (qui invoque
  le `service.py` de chaque projet), et faisait doublon avec le dépôt `morfDeploy`
  désormais canonique. Fin de l'ambiguïté « deux sources ».

## [0.10.0] - 2026-08-16

### Ajouté

- **`morf upgrade` met aussi à niveau la config partagée**, sans jamais écraser
  les choix locaux. En fin de passe, sur une machine qui consomme
  `morfsystem.json` (morfMonitor/morfDashboard), un **merge non destructif** ajoute
  les clés nouvelles du clone (ex. `beacon.archive_after_days`), conserve toutes
  les valeurs et les listes locales, signale les clés obsolètes sans les supprimer,
  et sauvegarde le fichier (backup horodaté systématique) avant toute écriture.
  C'est le pendant, pour le fichier partagé, du merge que `service.py update` fait
  déjà pour la config propre de chaque service : `upgrade` met la machine à niveau
  **complètement et de façon rétrocompatible** (code + contrat de config). Principe
  posé : *le clone fournit les valeurs par défaut, `/etc` reste la vérité locale.*
  `--only` saute cette étape (cible un projet précis).
- **`./config.py shared merge`** : la nouvelle action qui réalise ce merge, aussi
  invocable à la main. `install`/`apply` restent l'**écrasement** volontaire depuis
  le clone (réalignement explicite, jamais un effet de bord d'`upgrade`).

## [0.9.5] - 2026-08-16

### Modifié

- **`morf config deploy <projet>` unifié sur morfdeploy.** Il préférait déjà
  `service.py` au script bash, mais l'appelait sans action (il tombait sur `status`).
  Il invoque désormais `service.py config push --force` : le cœur de déploiement
  (vendoré dans chaque projet) remplace la config déployée depuis le dépôt, avec
  sauvegarde horodatée et redémarrage si changé, **sur toute plateforme** (Linux et
  Windows). Résultat : la capacité existe pour **tous** les services à config
  (morfCollector, morfNotify, morfSensor inclus) et le cas partagé de morfMonitor, sans
  script bash par projet. `-- <mode>` permet de nuancer (`merge` au lieu de `push`).
  Les `scripts/linux/deploy-config.sh` par projet deviennent redondants (à retirer au
  fil du dev).

## [0.9.4] - 2026-08-16

### Modifié

- **Émetteur de build : URL lue aussi depuis un fichier.** En plus de la variable
  `MORFANALYTICS_ACTIVITY_URL`, `lib/morfdeploy/activity.py` lit désormais l'URL
  d'ingestion depuis `/etc/morfsystem/monitor-activity-url` (une ligne) si la variable
  est absente. Nécessaire car `sudo service.py update` efface l'environnement : un
  fichier admin, posé une fois, est le moyen robuste d'activer l'émission.
- `activity.py` ajouté au registre des copies vendorées de `morfdeploy` dans
  `ecosystem.json` (contrôlé par `morf doctor`).

## [0.9.3] - 2026-08-16

### Ajouté

- **Émetteur d'événements de compilation (morfDeploy → morfAnalytics Monitor).** Le
  build (`build_as_user`, backends systemd et Windows) signale désormais chaque
  compilation au domaine Monitor de morfAnalytics : projet, machine, début/fin,
  résultat (succès/échec), preset. morfDeploy sait ce qu'il compile — c'est la source
  exacte des événements, sans rien faire deviner. **Best-effort et sans dépendance** :
  émis seulement si `MORFANALYTICS_ACTIVITY_URL` est défini (ex.
  `http://pi4fred:8799/api/monitor/activity`), jamais bloquant si morfAnalytics est
  injoignable — une télémétrie muette ne doit pas faire échouer un build. Nouveau
  module `lib/morfdeploy/activity.py`. À re-vendorer dans les projets (chantier suivant).

## [0.9.2] - 2026-08-15

### Ajouté

- **Port 8882 réservé à PhotoHub** dans `ecosystem.json` (bloc `appRange` des
  applications de bureau, 8880-8899). PhotoHub s'annonce désormais sur morfBeacon et
  expose `/status`, comme ComponentHub (8880) et SiteWatch (8881) ; le port vit dans
  son code (`src/main.cpp`, `beaconCfg.statusPort`), sans fichier de configuration.

## [0.9.1] - 2026-08-14

### Corrigé

- `install` (mode générique, sans `--services`) n'exécute plus `pip` pour un
  `requirements.txt` **vide ou réduit à des commentaires**. Sur un système Python
  « externally managed » (PEP 668, Raspberry Pi OS / Debian Bookworm+), pip
  échouait (`error: externally-managed-environment`) alors qu'il n'y avait rien à
  installer. Un tel fichier est désormais traité comme « no generic install
  definition », comme s'il était absent.

## [0.9.0] - 2026-08-14

### Ajouté

- **`activate-cli.sh` : exposition des commandes du parc dans `~/.local/bin`.**
  Les vraies commandes utilisateur (`morf`, `screenctl`, …) deviennent appelables
  depuis n'importe quel dossier, sans jamais déplacer ni copier les scripts hors
  de leur projet. Chaque projet déclare ses commandes dans un `cli.manifest` à sa
  racine, avec un mode explicite : `direct` (lien symbolique, pour un script
  indépendant du répertoire courant) ou `project` (petit lanceur qui entre dans
  le projet avant d'exécuter). Le mode est déclaré, jamais deviné.
- Propriétés garanties : activation **volontaire** (jamais déclenchée par
  `install`/`update` ; ne touche ni service, ni `/opt`, `/etc`, `/var/lib`),
  **cohérente** (un seul espace de travail à la fois, déterminé par le dossier
  parent de cette copie de morfTools - `01-Travail` ou `morfSystem`), et **sûre**
  (ne remplace jamais un fichier étranger de `~/.local/bin` ; un registre suit les
  commandes gérées pour les réorienter ou les retirer à la bascule d'espace).
  Options `--status`, `--dry-run`, `--deactivate`. morfTools déclare `morf`.
- Guide dédié [`docs/ACTIVATE-CLI.md`](docs/ACTIVATE-CLI.md) et section dans les
  README.

## [0.8.4] - 2026-08-11

### Ajouté

- **PhotoHub declare comme consommateur vendore** (`vendored.consumers`). Il embarque
  morfUpdate (verification des mises a jour) dans `third_party/morf/update` ; `morf
  doctor` verifie desormais que cette copie ne derive pas de la source.

## [0.8.3] - 2026-08-11

### Ajouté

- **PhotoHub inscrit au registre `ecosystem.json`** (`projects`). Application desktop
  du domaine photo, client pur de morfPhoto : pas de serveur, donc aucune allocation
  de port. Complète le trio du domaine photo (morfPhoto, PhotoHub, spécialisation
  Photo de morfAnalytics).

## [0.8.2] - 2026-08-11

### Ajouté

- **morfPhoto entre au registre `ecosystem.json`.** Nouveau service d'indexation
  d'une photothèque locale : ajouté à `projects`, à la table des consommateurs du
  socle vendoré `morf`, et doté de son allocation de port dans `ports.allocations`
  (**http 8793**, premier libre du bloc de service 8787-8799, `config/morfphoto.example.json`
  clé `http_port`). Le registre reste l'autorité unique sur les ports ; `morf doctor`
  vérifie que la configuration du service déclare bien 8793.
- **morfDeploy promu en dépôt autonome** et inscrit dans `projects`. Le cœur de
  déploiement quitte son statut de sous-dossier `lib/morfdeploy` de morfTools pour
  devenir une bibliothèque à part entière (dépôt, VERSION, README, CHANGELOG,
  LICENSE), sur le modèle de morfBeacon. `lib/morfdeploy` reste en place comme
  repli transitoire tant que tous les projets n'ont pas basculé leur `sync-morf`
  vers le nouveau dépôt (migration à venir).

## [0.8.1] - 2026-07-29

### Ajouté

- **`morf upgrade --force`** : transmet `--force` à chaque `service.py update`,
  pour redéployer et redémarrer les services **même quand rien n'a changé**.
  Jusqu'ici seul le `service.py update --force` d'un service pris isolément le
  permettait ; `upgrade` rejetait l'option (`unrecognized arguments`). Utile pour
  faire rebondir les services à la demande, le cas « binaire inchangé » étant
  sinon un no-op délibéré. `--force` ne s'applique qu'à `upgrade` (garde-fou).

### Corrigé

- **Badge de version de morfTools aligné sur `VERSION`** (0.8.1) dans les deux
  README : il était resté à 0.6.0 après les montées 0.7.0 et 0.8.0. `morf doctor`
  vérifie cette cohérence pour les projets du parc.

## [0.8.0] - 2026-07-29

### Ajouté

- **`service.py config` (morfdeploy) : mettre à jour la config d'un service
  installé sans réinstaller.** L'`update` n'ajoute que les clés de PREMIER NIVEAU
  (les listes restent entières, règle du parc : on n'ajoute jamais une entrée de
  liste). Un nouveau paramètre à l'INTÉRIEUR d'un module (ex. `morfsync_url` de
  morfAnalytics) ne se propageait donc pas tout seul. La nouvelle commande comble
  le trou, en deux modes, non destructifs (sauvegarde horodatée `.bak` avant toute
  écriture) :
  - `service.py config` (**merge**, défaut) : fusion PROFONDE. Ajoute les clés
    manquantes de l'exemple **y compris dans un module déjà présent** (apparié par
    `id`), préserve toutes les valeurs réglées, n'ajoute jamais d'entrée de liste.
    Redémarre le service seulement si quelque chose a changé.
  - `service.py config push --force` : remplace la config déployée par celle du
    dépôt (sauvegarde d'abord).
  - Rappels : éditer `/etc/morfsystem/<service>/<service>.json` puis
    `systemctl restart` marche aussi ; le binaire ne lit jamais le
    `.example.json`. Implémenté dans `morfdeploy` (`configmerge` gagne un mode
    `deep_lists`, `core` la commande `config`, `cli` l'action), donc **à
    re-vendorer dans chaque service** (`scripts/sync-morf.sh` ; `morf doctor`
    signale la dérive).

### Documentation

- **`docs/EXPLOITATION.md`** : référence d'exploitation du parc. Détaille chaque
  script (`morf.py`, `service.py`, `config.py shared`, `sync-morf.sh`,
  `reset-parc.sh`) avec ses options, son action et le moment où l'utiliser, plus
  les commandes système indispensables au suivi et à la maintenance sous Linux
  (`systemctl`, `journalctl`) et Windows (`schtasks`, `sc.exe`), une table des
  unités et ports, et des recettes courantes. Indexé dans les deux README.

## [0.7.0] - 2026-07-28

### Documentation

- **`install --services` documenté dans la table des commandes** (README.md et
  README.fr.md) : la commande qui déploie tout le parc en une fois n'y figurait
  pas (la ligne `install` ne mentionnait que `requirements.txt`). Ajout aussi de
  la ligne `uninstall` manquante dans le README français. Le guide de démarrage
  gagne morfCollector dans la table des services installables.

### Ajouté

- **Séparateur franc entre chaque projet** dans la sortie des commandes qui
  parcourent le parc (`install`, `update`, `upgrade`, `build`, `clone`, `pull`,
  `status`...). Chaque projet est introduit par une règle pleine largeur et son
  nom, au lieu d'une simple ligne `[nom]` : un déploiement complet se lit
  désormais comme des blocs distincts dans le terminal. ASCII uniquement (rendu
  identique sous Windows, Linux et Raspberry Pi). `doctor` conserve son rapport
  condensé.
- **Prise en charge de l'état persistant `/var/lib` dans le déploiement**
  (doctrine `morfTemplateService/docs/fr/FILESYSTEM.md`). Le manifeste
  `service.json` peut déclarer un bloc `state_dir` (par plateforme) ;
  `morfdeploy` expose `manifest.state_dir()`, substitue `__STATE_DIR__` dans les
  unités systemd et affiche le chemin d'état à l'installation. Se combine avec la
  directive `StateDirectory=` des unités, qui laisse systemd créer le dossier
  possédé par l'utilisateur du service.

## [0.6.0] - 2026-07-28

### Ajouté

- **`morf.py install --services` déploie tout le parc en une commande.** Chaque
  service est installé via son propre `service.py` (Linux, Raspberry Pi ou
  Windows) : compilation sous votre compte, puis élévation de la seule étape
  d'installation, comme `upgrade`. Le patron morfTemplateService est sauté
  (drapeau `"template": true` dans son `service.json`). Refuse de tourner sous
  sudo (un build possédé par root est un piège).

## [0.5.0] - 2026-07-28

### Modifié

- **morfdeploy : `uninstall --purge` retire tout le `config_dir` du service**
  (`/etc/morfsystem/<service>`), et non plus seulement le fichier de config
  déclaré. Les fichiers créés au runtime (coffre de secrets, état) ne survivent
  donc plus à un purge. Le parent partagé `/etc/morfsystem` est préservé.
- **`reset-parc.sh` : `/etc/morfsystem` est le point d'entrée unique** ; les
  anciens `/etc/<service>` passent en emplacements hérités (nettoyés). Ajout de
  morfcollector aux unités et dossiers `/opt`.


## [0.4.23] - 2026-07-26

### Modifié

- **Un service installé mais arrêté n'est plus un échec.** Il peut l'être
  volontairement : `doctor` le présente désormais comme un **avertissement**
  (« service installed but not running; may be intentional »), sans action
  alarmante, et ne fait plus échouer le diagnostic. Auparavant, un service
  simplement arrêté sortait en `[FAIL]` et donnait un code de retour 1.
- **Remède de mise à jour adapté à l'état du service.** Pour un service installé
  mais inactif et en retard, `--update` précise « service installé mais inactif »
  et donne la commande **en deux lignes** : `update` (tirer la source), puis, si
  souhaité, `upgrade` (reconstruire et redéployer). Un service actif reçoit
  directement `upgrade` ; un projet sans service (application de bureau) ou non
  installé ici reçoit `update`.
- **Plus de double affichage.** Quand un service inactif est aussi en retard,
  l'avertissement « installé mais inactif » est **replié dans l'entrée de mise à
  jour** (qui le mentionne déjà) au lieu d'apparaître en double dans deux
  sections. Le repli est conservé pour `--verbose`.

## [0.4.22] - 2026-07-26

### Modifié

- **La commande proposée pour une mise à jour dépend de l'état du service.** Si
  le service du projet est **actif** sur cette machine, le remède reste
  `upgrade` (reconstruire et redéployer en place). S'il n'est **pas actif** -
  non installé ici, application de bureau sans service, ou service arrêté - le
  remède devient `update` : tirer la source, sans rien redéployer. Proposer
  `upgrade` pour un service qui ne tourne pas reviendrait à reconstruire et
  relancer ce que la machine n'exécute pas. L'état est lu de la sonde que
  `doctor` vient de faire (le point d'état a-t-il répondu une version ?), sans
  second aller-retour réseau.

## [0.4.21] - 2026-07-26

### Corrigé

- **Le remède d'auto-mise-à-jour de morfTools ne contient plus de chemin
  absolu.** Il affichait `git -C /home/<user>/…/morfTools_travail pull
  --ff-only` : un chemin propre à une seule machine, qui casse sur une autre.
  C'est désormais un simple **`git pull --ff-only`**, conforme au reste de
  l'outil - toutes les commandes morf se lancent déjà depuis le dossier
  morfTools (c'est ainsi que `python3 morf.py …` se résout), donc
  l'auto-mise-à-jour part du même endroit. Aucune commande ne dépend plus d'un
  chemin en dur.

## [0.4.20] - 2026-07-26

### Modifié

- **Option `--updates` renommée `--update`** (alias court `-u` inchangé), pour
  suivre la convention habituelle des drapeaux booléens au singulier
  (`--verbose`, `--force`). Le pluriel n'aura vécu que la 0.4.19 ; l'entrée de
  cette version a été relue en conséquence. Règle générale retenue : nommer les
  options selon la norme des outils standard.

## [0.4.19] - 2026-07-26

### Modifié

- **Le contrôle des nouvelles versions passe sur option.** Introduit en 0.4.18
  comme systématique, il ajoutait un `git fetch` par dépôt - une trentaine de
  secondes sur le parc complet, trop pour un `doctor` de routine. Il ne s'exécute
  désormais qu'avec **`--update`**. Par défaut, `doctor` reste local et
  instantané, et se termine par `Tout est conforme (versions non vérifiées).` en
  rappelant la commande.
- **Distinction « non vérifié » / « à jour ».** Le résumé n'affiche le décompte
  des mises à jour que si le contrôle a réellement eu lieu : afficher « 0 mise à
  jour » sans avoir vérifié laisserait croire à une vérification qui n'a pas eu
  lieu.

### Ajouté

- **Indicateur de progression** pendant `--update` : une ligne réécrite en place
  sur `stderr` (`vérification des versions… 3/14 <projet>`), pour ne pas laisser
  l'utilisateur dans le flou le temps des `fetch`. Sur un terminal seulement ;
  redirigé ou journalisé, le contrôle reste silencieux plutôt que d'empiler des
  images d'animation. Comme elle vit sur `stderr`, elle ne pollue jamais le
  rapport, qui est sur `stdout`.

### Vérifié

Défaut sans réseau (indication « versions non vérifiées » + rappel de la
commande) ; `--update` effectue les `fetch`, ajoute la section « Mises à jour
disponibles » et l'auto-vérification de morfTools ; garde `--update` refusée
hors `doctor` ; progression rendue en place puis effacée sur un terminal,
muette une fois redirigée.

## [0.4.18] - 2026-07-26

### Ajouté

- **`doctor` signale les mises à jour disponibles.** À chaque exécution, il
  compare chaque clone à `origin/main` et, s'il est en retard, l'annonce dans
  une section **« Mises à jour disponibles »** avec les deux commandes à lancer :
  `morf pull --only <projet>` puis `morf upgrade --only <projet>`. Le signal est
  « le distant a des commits que je n'ai pas », et non « une release GitHub a été
  publiée » : la moitié des dépôts ne publient aucune release, alors que tous ont
  un distant. Il n'utilise que `git` - ni `gh`, ni jeton, rien qui puisse manquer
  sur le Pi.
- **morfTools s'auto-vérifie.** L'outil n'étant pas un projet du manifeste, rien
  ne signalait qu'il était lui-même en retard. Il apparaît désormais dans le
  rapport sous « Outil », avec pour remède un `git pull --ff-only` (depuis son dossier)
  en place (`morf pull` agit sur les autres projets, pas sur l'outil qui le
  lance).

### Notes

- Une mise à jour disponible n'est **pas un échec** : elle ne fait pas passer le
  code de retour à 1 et n'entre ni dans les avertissements ni dans les échecs.
  Être en retard est une information, pas une anomalie.
- Le contrôle est un pas réseau : un `git fetch` borné (20 s, invites
  d'identifiants désactivées) par dépôt. Hors-ligne ou distant injoignable, il se
  dégrade en `[SKIP]` sans alarme et sans bloquer. Compter quelques dizaines de
  secondes sur le parc complet ; il reste hors de `cmd_doctor`, qui demeure
  utilisable sans réseau.

### Vérifié

Parc réel : « conforme et à jour » en ~37 s. Détection en conditions réelles en
reculant un dépôt propre d'un commit - signalé avec les bonnes commandes, puis
restauré. morfTools inclus dans le rapport. Hors-ligne : `[SKIP]` propre.

## [0.4.17] - 2026-07-26

### Modifié

- **`doctor` rend un résumé lisible au lieu d'un flot de lignes.** Sain, le
  diagnostic imprimait une soixantaine de lignes vertes ; un vrai problème s'y
  noyait. Par défaut, les vérifications conformes sont désormais comptées et
  regroupées (Écosystème / Projets), seules les exceptions sont détaillées, et
  le rapport se termine par un **résumé chiffré** puis une section **« À
  corriger »** listant chaque échec avec l'action concrète à mener.
- **L'action réutilise le remède que la vérification imprime déjà** (commande de
  resynchronisation vendorée, commande de mise à niveau) quand il existe ; sinon
  elle est déduite du message. Une vérification qui améliore son propre conseil
  améliore ce résumé sans y toucher.
- **Les « impossible de vérifier » ne sont plus comptés comme des
  avertissements.** Sur un poste qui ne peut pas joindre les services (ils
  tournent sur le Pi), le contrôle de version active répondait « unavailable » :
  six faux avertissements par exécution. C'est une non-évaluation, traitée comme
  telle. Un service réellement installé qui ne répond pas reste, lui, un échec.
- **`doctor --verbose` rétablit la sortie ligne par ligne**, inchangée, pour qui
  veut le détail complet.
- **Sortie forcée en UTF-8** (avec remplacement) : le résumé emploie des accents
  et des marqueurs qu'une console Windows en cp1252 refusait, interrompant le
  rapport en cours par une `UnicodeEncodeError`.

### Vérifié

Parc sain : 61 lignes ramenées à 10. Cas en échec (collision de port, dérive
vendorée, version décalée, service en panne) : chaque problème rendu avec son
action, réutilisant le remède du producteur pour la resynchronisation et la
mise à niveau. `--verbose` conserve les 70 lignes détaillées.

## [0.4.16] - 2026-07-26

### Corrigé

- **Le contrôle des ports laissait passer un doublon entre projets.** La
  troisième passe de `check_ports` testait si un port déclaré *existait* dans le
  registre, pas s'il appartenait au projet qui le déclare : un service fraîchement
  cloné qui gardait le `8901` du gabarit passait, puisque `8901` est bien
  enregistré - au nom du gabarit. La passe compare désormais le **propriétaire**
  du port au projet déclarant, ce qui est la forme même d'un doublon. C'est la
  collision qui a mis morfAnalytics à terre (8799 pris par morfMonitor) et qu'un
  test par valeur seule ne pouvait pas voir. Reproduite sur un parc piège, puis
  corrigée et vérifiée.

### Ajouté

- **Discipline de la plage template appliquée dans les deux sens.** Un port de la
  plage `8900-8999` ne peut appartenir qu'à une allocation marquée
  `"template": true`, et une allocation template ne peut utiliser qu'un port de
  cette plage. En production, tout port de la plage template est refusé, même
  libre : c'est la barrière qui garantit qu'un gabarit ne livre jamais un numéro
  qu'un vrai service pourrait prendre. `morfTemplateService` est marqué
  `template` dans le registre.
- **Suggestion de port pour un nouveau projet** : `ecosystem-check.py … next-port`
  imprime le plus petit port libre du bloc service. `new-service.sh` l'exécute et
  affiche le numéro concret à réserver, au lieu de « choisis-en un ». Lire le
  registre à l'œil pour trouver un trou est précisément ce qui met deux projets
  sur le même port.

### Contexte

Le registre `ecosystem.json` était déjà l'autorité unique sur les ports, et
`morf doctor` en vérifiait la cohérence. Ces changements ferment le dernier trou
- un projet réutilisant en silence le port d'un autre - et rendent l'attribution
d'un port à un futur projet mécanique plutôt que manuelle.

## [0.4.15] - 2026-07-25

### Corrigé

- **Instruction de mise à niveau affichée par `doctor`.** Le diagnostic indique
  désormais la commande exécutable depuis morfTools :
  `python3 morf.py upgrade --only <projet>`.

## [0.4.14] - 2026-07-25

### Corrigé

- **`morf doctor` ne confond plus le dépôt à jour avec le service à jour.** Pour
  chaque service installé qui déclare un point `/status`, il compare désormais
  la version active à la version du fichier `VERSION` du projet. Un décalage,
  un service injoignable ou une réponse sans version font échouer le contrôle
  et indiquent la commande `python3 morf.py upgrade --only <projet>` à exécuter. Les
  services non installés sont explicitement ignorés ; si le point d'état ne
  répond pas et que le gestionnaire de services est protégé, l'absence de droits
  reste un avertissement, jamais un faux « non installé ».

## [0.4.13] - 2026-07-24

### Ajouté

- **Modèle d'issue GitHub « Premier test de morfSystem »**
  (`.github/ISSUE_TEMPLATE/premier-test.md`) : le retour demandé par
  `docs/FIRST-TEST.md` se dépose désormais en issue, avec les six questions
  prioritaires déjà en place. Le document pointe vers le formulaire et
  recommande d'ouvrir l'issue **avant** de commencer, pour la compléter au fil
  de l'eau plutôt que de tout écrire de mémoire à la fin - et d'ouvrir
  plusieurs issues courtes plutôt qu'un seul long compte rendu, un blocage
  précis se traitant et se clôturant, là où il se noierait dans un récit.

## [0.4.12] - 2026-07-24

### Ajouté

- **`docs/FIRST-TEST.md`** - demande de retour après une **première**
  installation, destinée à quelqu'un qui ne connaît pas morfSystem. C'est le
  seul test que le parc n'a jamais subi : tout a été éprouvé par son auteur, qui
  sait déjà ce qu'il faut faire et se trouve donc le moins capable de voir ce
  qui manque.

  Le document demande explicitement un retour **honnête plutôt qu'aimable**, et
  pose deux règles qui font sa valeur : ne demander d'aide à personne - chaque
  question qui surgit est notée au lieu d'être posée, car une question posée à
  l'auteur est une information perdue - et ne pas corriger le tir mentalement,
  ce réflexe effaçant justement le défaut.

  Six questions sont marquées comme prioritaires, dont le **point d'abandon**
  (« à quel moment auriez-vous arrêté si vous n'aviez pas accepté de rendre
  service ? ») et l'**écart entre l'attendu et l'obtenu même quand tout
  fonctionne** - ces moments-là ne produisent aucune erreur et n'apparaissent
  dans aucun journal. Référencé depuis le guide de démarrage et le README.

## [0.4.11] - 2026-07-24

### Corrigé

- **Un `update` sans changement ne redémarre plus le service.** La séquence
  était inconditionnelle : compiler, arrêter, recopier le binaire - fût-il
  identique octet pour octet - ré-enregistrer, redémarrer. Le premier `upgrade`
  réel du Pi a donc arrêté et relancé **cinq** services alors qu'aucun n'avait
  changé. Ce n'est pas neutre : c'est une coupure de supervision, un uptime
  remis à zéro et, pour un service au milieu d'une tâche, une interruption -
  payés au moment précis où l'on croyait ne rien toucher.

  `update` compare désormais **l'empreinte du contenu** du binaire construit et
  de l'installé (SHA-256 ; ni la taille ni la date, qu'un `git checkout` ou une
  recompilation réécrivent sur des octets identiques), vérifie que les
  configurations sont en place, et s'arrête là s'il n'y a rien à déployer - en
  le disant clairement, y compris que **le service n'a pas été redémarré**.
  `--force` redéploie et redémarre quand c'est justement l'intention.

- **Deux fonctionnalités annoncées mais jamais branchées le sont enfin.**
  `enrich_configs` (0.4.0, enrichissement des configurations à la mise à jour)
  et `verify_writable` (0.4.2, vérification que l'utilisateur du service peut
  écrire dans son dossier) existaient en code mort : `git log -S` ne trouve
  aucun commit ayant jamais contenu leur appel. Le changelog les décrivait
  comme livrées. Elles sont désormais appelées par `install` et `update`.

  L'enrichissement participe de surcroît à la décision ci-dessus : une clé
  ajoutée dans un fichier que le processus a lu au démarrage ne change rien
  tant qu'il ne l'a pas relu - un enrichissement effectif justifie donc le
  redémarrage, et lui seul.

## [0.4.10] - 2026-07-24

### Corrigé

- **`upgrade` ne laisse plus morfDashboard en arrière, en silence.** Le
  redéploiement ajouté en 0.4.7 ne reconnaissait que les projets dotés d'un
  `service.py` ; morfDashboard, seul service encore piloté par ses scripts
  shell, sortait sur « pas un service » sans rien afficher - son nouveau code
  était récupéré et le service continuait de tourner sur l'ancien. Exactement le
  piège que la fonctionnalité devait fermer, resté ouvert pour un projet, et de
  la pire manière : sans un mot. Constaté sur le premier `upgrade` réel du Pi.

### Modifié

- **La branche legacy de `uninstall` disparaît.** morfDashboard expose désormais
  la même interface que les autres (morfDashboard 1.10.0), si bien que morfTools
  s'en tient à une règle sans exception : un projet qui est un service porte un
  `service.py`. La connaissance d'un projet cesse de vivre dans l'outil qui
  l'administre.

## [0.4.9] - 2026-07-24

### Corrigé

- **« Pas installé » n'est plus conclu de « je n'avais pas le droit de
  demander ».** Lancé sans élévation sous Windows, `service.py update`
  répondait « morfMonitor n'est pas installé sur cette machine. Lancez d'abord
  install » - à propos d'un service en cours d'exécution, qui répondait sur son
  port à la seconde près. `schtasks` renvoie « accès refusé » pour une tâche
  enregistrée en SYSTEM, avec le code de retour de « cette tâche n'existe pas » ;
  le message envoyait donc vers `install`, exactement le mauvais geste.

  `update` et `status` interrogent désormais `can_query_installation()` avant de
  conclure, et nomment la vraie cause avec la manière d'y remédier. Le garde-fou
  existait depuis la 0.4.7 pour le balayage de `morf.py upgrade` ; il manquait
  là où une personne le lit directement.

  Constaté en testant sur une machine Windows réelle, service actif : aucun de
  ces deux défauts n'était visible à la lecture du code.

## [0.4.8] - 2026-07-24

### Corrigé

- **Sous Windows, un service est désactivé, arrêté, et son arrêt réel attendu
  avant que ses fichiers soient remplacés.** Windows refuse d'écraser un
  exécutable qu'un processus tient ouvert, et `schtasks /End` rend la main dès
  la demande émise, sans attendre la sortie effective : la copie qui suivait
  échouait sur une erreur de permission qui ne disait rien de sa cause - la
  précédente instance encore vivante. Trois gestes remplacent l'unique arrêt :

  - **désactivation d'abord** - un arrêt que quelque chose peut défaire n'en est
    pas un : un wrapper SCM (WinSW, NSSM) relance un service qu'il croit planté,
    et il reviendrait en tenant les fichiers qu'on s'apprête à remplacer. La
    désactivation est toujours défaite par l'appelant (install et update
    ré-enregistrent le service entièrement, uninstall le supprime) ;
  - **arrêt** ;
  - **attente de la libération réelle** du binaire, éprouvée en l'ouvrant en
    écriture - Windows accorde la poignée à l'instant où le processus disparaît.
    Un dépassement de délai avertit au lieu d'échouer, en nommant la cause et la
    commande pour s'en sortir.

  Linux n'a pas besoin de cette étape : `systemctl stop` ne rend la main
  qu'une fois l'unité réellement arrêtée. Le correctif vit dans le backend
  Windows, donc `install`, `update` et `uninstall` de **tous** les projets en
  héritent par leur `service.py` - copie vendorée resynchronisée dans les six
  services.

## [0.4.7] - 2026-07-24

### Ajouté

- **`morf.py upgrade` met désormais à jour les services installés.** Il
  s'arrêtait à la compilation : la machine continuait de faire tourner
  l'ancien binaire jusqu'à ce qu'on pense à visiter chaque projet pour y lancer
  son `service.py update` - un piège que le guide devait signaler plutôt que
  l'outil l'éviter. `upgrade` tient maintenant sa promesse : `git pull`,
  recompilation, puis remplacement des binaires **des seuls services
  réellement installés sur cette machine**. Un projet présent dans les dépôts
  sans y être installé est ignoré discrètement : le parc est un jeu de dépôts
  déployé différemment sur chaque machine, pas une anomalie.

  Le `git` reste exécuté en votre nom et **seul le déploiement est élevé** :
  `upgrade` refuse toujours de tourner sous `sudo` (la garde 0.4.3), et
  demande donc lui-même l'élévation au moment de remplacer le premier binaire.

- **`service.py is-installed`** - action muette dont le **code de retour est la
  réponse** : `0` installé, `1` absent, `2` impossible à déterminer. La
  troisième valeur n'est pas un luxe : sous Windows, `schtasks /Query` répond
  « accès refusé » pour une tâche enregistrée en SYSTEM, avec un code de retour
  indiscernable de « cette tâche n'existe pas ». Sans cette distinction, un
  balayage non élevé aurait conclu « rien n'est installé », sauté un service en
  cours d'exécution et annoncé un succès. `upgrade` avertit désormais au lieu
  de se taire. La sortie de `status` n'est toujours jamais analysée : une
  décision se demande au backend qui connaît la plateforme.

### Documentation

- **La découverte distribuée est consignée comme éprouvée** dans
  `docs/ECOSYSTEM-PRINCIPLES.md` : elle fonctionne sur un environnement
  hétérogène (Windows, Linux, Raspberry Pi, ESP32) sans aucune configuration
  manuelle, les instances de morfMonitor se découvrant mutuellement et les
  services du Raspberry Pi apparaissant automatiquement sur Windows comme
  l'inverse. La section « Portée : toutes les plateformes » ne décrit plus une
  intention. L'invariant « on ne promet que ce qu'on peut éprouver » note que
  Windows a franchi son seuil de support le 23 juillet 2026, et que les trois
  défauts révélés ce jour-là étaient tous invisibles à la lecture du code.

## [0.4.6] - 2026-07-23

### Corrigé

- **Les DLL tierces de Qt sont déployées sans dépendre d'un shell.** windeployqt
  place les bibliothèques Qt et le runtime du compilateur, mais **pas** les
  bibliothèques tierces contre lesquelles Qt6Core est lié (brotli,
  double-conversion, ICU, pcre2…) : le service s'arrêtait sur
  « libbrotlidec.dll introuvable », une par une. Le balayage de repli s'appuyait
  sur `ldd` d'un shell MSYS2 - absent depuis un PowerShell ordinaire, et c'est
  précisément là que ces DLL manquaient. Il est remplacé par `objdump` (livré
  dans le même `bin` MinGW que windeployqt, donc présent dès que windeployqt
  l'est, et sans shell) : la table d'imports de chaque binaire est lue, et toute
  DLL importée présente dans le `bin` du toolchain - une bibliothèque MinGW/Qt,
  pas une DLL système - est copiée, en suivant ses propres imports jusqu'à
  fermeture. Testé de bout en bout : 15 DLL au total, dont les quatre qui
  manquaient (libbrotlidec, libdouble-conversion, libicuin78, libicuuc78).
  No-op sous Linux inchangé. Copie vendorée resynchronisée dans les six services.

## [0.4.5] - 2026-07-23

### Corrigé

- **L'install Windows trouve `windeployqt` toute seule, depuis n'importe quel
  terminal.** La 0.4.4 exigeait de lancer l'install depuis le shell MSYS2 qui
  avait compilé, faute de quoi elle s'arrêtait sur « windeployqt introuvable » -
  y compris depuis un PowerShell ordinaire. morfdeploy lit désormais le
  `CMakeCache.txt` du build pour localiser Qt (`Qt6_DIR` → `<qt>/bin`, le même
  point d'ancrage que le CMake de ComponentHub) et préfixe le PATH du
  sous-processus avec le `bin` de Qt, pour qu'`objdump` et les DLL du runtime
  MinGW se résolvent sans dépendre du shell appelant. Testé de bout en bout :
  15 DLL (Qt6Core, Qt6Network, libgcc, libstdc++, pcre2, icu…) et les dossiers
  de plugins `networkinformation/` et `tls/` déployés à côté du binaire. Sous
  Linux, toujours un no-op. Copie vendorée resynchronisée dans les six services.

## [0.4.4] - 2026-07-23

### Corrigé

- **Un service Qt installé sous Windows embarque désormais ses DLL.** Installé
  seul, `morfmonitor.exe` démarrait sur une erreur « Qt6Core.dll introuvable »
  que le gestionnaire de services ne rapporte que comme un échec de démarrage,
  sans nommer un seul fichier manquant. Sous Linux, les bibliothèques
  partagées viennent du système ; Windows n'a pas d'équivalent. morfdeploy
  place maintenant, à l'installation comme à la mise à jour, les DLL Qt et
  MinGW à côté du binaire, via `windeployqt` (livré avec Qt) puis un balayage
  `ldd` de repli pour les dépendances tierces restantes. Le correctif vit dans
  le backend Windows - la seule couche qui interroge la plateforme - donc tout
  service du parc en bénéficie, sans toucher au CMake d'aucun projet. Sous
  Linux, l'appel est un no-op sans coût. Copie vendorée resynchronisée dans
  les six services concernés.

## [0.4.3] - 2026-07-22

### Corrigé

- **Les commandes git refusent de tourner sous sudo.** Élevé, git s'authentifie
  avec la clé SSH de root - inexistante : les treize dépôts répondent
  `Permission denied (publickey)` - et le fetch laisse des fichiers root dans
  chaque `.git` (`FETCH_HEAD`), si bien que les exécutions suivantes, en
  utilisateur, échouent sur leurs propres dépôts (`cannot open .git/FETCH_HEAD`).
  Les deux sont arrivés d'un seul `sudo` par habitude. Le refus nomme la cause
  et la commande correcte ; seul `uninstall` (et les `service.py`) exige
  l'élévation. Un vrai login root (sans `SUDO_USER`) n'est pas concerné.


## [0.4.2] - 2026-07-22

### Corrigé

- **Le dossier applicatif dédié appartient de nouveau à l'utilisateur du
  service.** Le rétrécissement du `chown` (protection de `/usr/local/bin`) avait
  emporté l'entrée du dossier lui-même : créé sous sudo lors d'une installation
  from-scratch, `/opt/<service>` restait à root, et un module y créant ses
  données d'exécution (cache, sqlite) échouait - silencieusement, avec un
  message d'interface pointant la configuration. Le `chown` couvre l'entrée du
  dossier, jamais récursif, et seulement quand son nom est celui du service.

- **`install` et `update` vérifient que l'utilisateur du service peut écrire
  dans son dossier** (`sudo -u <user> test -w`) et avertissent avec la commande
  de réparation. L'erreur devient bruyante au moment du geste, pour tous les
  services, au lieu d'un symptôme lointain.


## [0.4.1] - 2026-07-22

### Corrigé

- **Le conseil de réparation de `exec-bits` ne se sabote plus lui-même.** Sur un
  premier clone dont les scripts ont perdu le bit d'exécution, `doctor` invitait
  à lancer `./exec-bits.sh` - un wrapper qui a besoin du bit qu'il doit
  justement restaurer, donc `Permission denied` : le remède renvoyait à sa
  propre forme cassée. Le message donne désormais `python3 scripts/exec-bits.py ..`,
  qui s'exécute quel que soit le bit (même raison que `python3 morf.py`), et
  explique pourquoi. Le guide de démarrage documente la sortie, à l'étape
  `doctor` et en dépannage.

- **Le message post-réparation d'`exec-bits` explique comment rendre le
  correctif durable.** Le bit restauré n'est que *mis en scène* ; sans `commit`
  + `push`, le dépôt distant garde le fichier non-exécutable et le prochain
  `pull` retire à nouveau le bit sous Linux. Le message donne la séquence
  parc-wide (`morf.py commit` puis `morf.py push`) et distingue ce geste durable
  d'un simple déstage, qui laisserait le correctif aussi fragile.

- **La promotion vers la production restaure le bit d'exécution automatiquement.**
  `sync-to-morfsystem.ps1` lance `exec-bits.py` après le robocopy : la copie
  Windows perdait le bit à chaque report, obligeant chaque clone neuf du Pi à le
  réparer. Le correctif est désormais à l'unique endroit où le bit se perd. Il
  est mis en scène (fileMode-indépendant, survit au `git add -A` du commit de
  promotion, vérifié) ; le push le rend permanent.

## [0.4.0] - 2026-07-22
### Ajouté

- **`morf uninstall`** - désinstalle un service (`--only`) ou tout le parc, avec
  `--purge` (efface aussi config et binaire) et `--backup` (copie la config
  d'abord). Délègue au `service.py` de chaque projet.
- **`scripts/reset-parc.sh`** - remet une machine à blanc : arrête et désinstalle
  tous les services, retire `/opt`, `/etc` et les vestiges des migrations.
  Empreinte explicite auditable, `--dry-run`, confirmation, ne touche jamais aux
  dépôts.
- **morfdeploy enrichit la config à la mise à jour** : une clé introduite par une
  nouvelle version est ajoutée avec sa valeur par défaut, sans jamais toucher un
  réglage existant ni supprimer de clé. Remplace le `merge-config.py` dupliqué
  par service.
- **`morf build`/`upgrade` sautent les applications GUI sur une machine sans
  affichage** (Linux sans DISPLAY) ; `--gui` force. Reconnues par ce qu'elles
  lient (Qt Widgets), pas par une liste.

### Modifié

- **La configuration des services vit dans `/etc/<service>`**, séparée du binaire
  dans `/opt`. Conforme à la FHS ; migration déclarée, config adoptée jamais
  écrasée.
- **Les scripts shell remplacés par les entrées Python sont supprimés**
  (`morf.sh`/`.ps1`, `config.sh`/`.ps1`, `shared-config`, et les alias). `morf.py`
  et `config.py` sont l'interface unique, toutes plateformes.

### Corrigé

- **Une installation sans configuration à poser échoue désormais** au lieu
  d'enregistrer un service qui redémarre en boucle contre un fichier absent.

### Documentation

- **Guide de démarrage** (`docs/GUIDE-DEMARRAGE.md`) : cycle complet installer →
  configurer → consulter → désinstaller, applications du parc, et chapitre
  philosophie.
- **R5 (modèle de confiance / accès distant)** documenté comme décision ouverte
  dans `docs/ECOSYSTEM-PRINCIPLES.md`, avec les options à peser.

- **`morf.py` replaces `morf.sh` and `morf.ps1`**, which were the same algorithm
  written twice: iterate the projects, run git, read a JSON manifest. Nothing in
  either was platform-specific, so the duplication bought nothing and cost a
  second implementation free to disagree with the first.

  The shell version already called `python3 -c` five times to read the same
  manifest -- one process per project -- and every call site carried a
  `tr -d '
'` to undo the CRLF that Git Bash added on the way back. That
  workaround has no cause left and is gone rather than translated.

  Output is byte-identical to `morf.sh` for `doctor` and `status`, and the exit
  codes match. `--only <project>` is new: it restricts any command to a single
  project.

  Both shell versions stay in place until the Python one has been exercised on
  the Pi.

## [0.3.0] - 2026-07-21

- **`exec-bits` restores the executable bit across the parc**, and `doctor` now
  reports its absence. Forty-six tracked scripts were recorded as `100644`,
  including all five of morfMonitor - among them the `deploy-config.sh` the
  README tells people to run.

  The defect cannot be observed from the machine that creates it. Windows has no
  executable permission, so Git records new files as non-executable; the working
  copy runs fine because `bash script.sh` never consults the bit. The Pi clones
  the same repository, `./script.sh` answers `Permission denied`, and nothing in
  that message points back at Windows.

  So the fix targets the **index mode**, not the filesystem: `chmod` on Windows
  is a no-op Git ignores, while `git update-index --chmod=+x` records 100755 in
  the tree every other clone will see. What counts as runnable is the
  **shebang**, not the extension - that is the author's own statement of intent,
  and it covers `.sh` and `.py` alike without a list of extensions free to drift.

- **`morfTools` gains the `.gitattributes` every other project already had.** It
  was the only repository without one, and the only one whose scripts run on the
  Pi. Nothing had broken yet: its seventeen `.sh` were kept LF by the local
  Git configuration alone, which is not a property of the repository and does not
  travel with a clone. A `.sh` stored with CRLF fails there with
  `bad interpreter: /usr/bin/env bash^M` - the same class of defect as the
  missing bit, invisible from the machine that introduces it.

- **The three meanings of "update" are now documented.** `update` is a pure
  alias of `pull`; `upgrade` pulls **and rebuilds**; a project's own
  `update-service.sh` is the only one that touches an installed service. The
  first two act on sources, so a Pi keeps serving the previous binary after an
  `upgrade` until the project's own script runs.

## [0.2.1] - 2026-07-21

- **`doctor` compares the vendored `VERSION` file too.** It only compared `src`
  and `include`, so seven copies could announce 0.2.1 while carrying the code of
  0.4.1 and the check stayed green. The exclusion was too broad: the vendored
  `CMakeLists.txt` is legitimately adapted to its embedding context, `VERSION`
  is not - it is simply copied, and a copy that lies about its version is worse
  than no version at all, because it is trusted.

## [0.2.0] - 2026-07-21

- **`config` becomes the single entry point for configuration deployment**, on
  both platforms: `config shared <action>` for the parc file, `config deploy
  <project>` for a project's own file. `shared-config` still works and points at
  the new name.

  `deploy` **delegates** to the project's own script rather than learning its
  install directory and service name - the rule that keeps morfTools free of
  business knowledge, and that `morf build` already follows by delegating to
  each project's build system. A project cloned on its own therefore still
  deploys its configuration without morfTools.

  A project name is required rather than defaulting to "all": the command
  overwrites deployed configurations, and doing that to every project because an
  argument was forgotten is not a reasonable default.

- **Fixed a trap in `shared-config`: the source was hard-coded to
  `morfsystem.example.json`.** A clone carrying a real `config/morfsystem.json`
  beside it - which is the normal case - saw `install` silently deploy the
  sample OVER the parc description. Both platforms now prefer the real file and
  fall back to the example, the same rule `deploy-config` already applied.

- `install` shows a capped diff of what it changes. Overwriting a parc
  description without showing what moves is a poor way to be simple.

- Fixed a silent failure in the new dispatcher: under `set -e`, a helper
  returning non-zero inside `$(...)` killed the script **before** the error
  message explaining what was missing. The exit code was right and the user saw
  nothing.

- Added the standard ecosystem documents the project was missing: `VERSION` (first published version, 0.1.0), `LICENSE` (GPL-3.0-only, identical body to every sibling project), `CONTRIBUTING.md`, `ROADMAP.md` and a French `README.fr.md`. morfTools drives the whole parc yet was the only project without a version of its own, so no inventory could include the tool performing it.
- `CONTRIBUTING.md` records two rules that were previously only implicit and had each already been broken once: script output stays in English, and JSON logic stays in Python called by both dispatchers rather than reimplemented in Bash and PowerShell.

- `ecosystem.json` now owns the **port allocation registry** (`ports`), raised to `schemaVersion` 2. The parc plan previously existed only as a `_comment_port` string inside `morfMonitor/config/morfmonitor.example.json`: a component with no authority over the others, holding a partial copy of an ecosystem-wide fact. That copy was already incomplete - it omitted 8789 (morfNotify) and 8787 (the morfBeacon status default) - so a developer consulting it to pick a free port got wrong information with no way to know it.
- Fixed the resulting collision: `morfTemplateService` shipped `http_port: 8799`, the port allocated to morfAnalytics. Every service created through the documented procedure therefore started on an occupied port. The template now uses 8901, inside a `templateRange` (8900-8999) reserved for templates and examples and deliberately outside the 8787-8799 service block, so a clone that has not yet reserved its own port is visibly unfinished instead of silently conflicting.
- `ecosystem.json` also declares the **vendored copies** (`vendored`): the shared libraries copied into `third_party/morf/`, with their canonical source project. The copy strategy itself is unchanged - it is what keeps the build reproducible across Windows, Linux x64 and Raspberry Pi without an external repository.
- `doctor` now runs both ecosystem-wide checks before its per-project pass, through `scripts/ecosystem-check.py`. Ports: registry self-consistency, registry against each declared configuration, and each configuration against the registry so an unmanaged allocation cannot keep the registry green while making it incomplete. Vendored copies: content comparison of `src` and `include` against the canonical project, with line endings normalised so a CRLF-converted copy is not reported as drift.
- The check logic lives in one Python script called by both `morf.sh` and `morf.ps1`. Neither gains a dependency (`morf.sh` already parses the manifest with `python3`, `morf.ps1` already calls `python` for `install`), and a PowerShell reimplementation would let the two checkers disagree.
- Documented the registries, the reserved ranges, the allocation procedure for a new service, and how to resolve reported drift in `docs/ECOSYSTEM-CHECKS.md`.

- Fixed `morf.sh` skipping every project on Windows: python3 emits CRLF on stdout, so project names were read as `Name\r_travail`.
- A project failing no longer aborts the remaining projects silently; failures are collected and reported, and the command exits non-zero.
- `morf.ps1` now checks the exit code of `cmake`, `git` and `pio` instead of chaining with `;`, so a failed configure no longer runs a build against a stale directory.
- `clean` now removes every build directory (`build`, `build-arm64`, `build-mingw`, …) instead of only `build`.
- `build` and `upgrade` no longer fall back to a default `build/` directory when no preset is given: they list the presets declared by the cloned projects, with the number of projects declaring each, and ask which one to use. `commit` prompts for a missing message. Without a terminal, both list the valid values and exit with status 2.
- A preset that a given project does not declare (such as `linux-arm64-cross`) is now reported as `[SKIP]` instead of failing that project.
- All script output is English again: the prompts and failure summaries added with the preset selection were briefly written in French, while every pre-existing message (`[SKIP] … (not cloned)`, `Unknown command`) was in English.
- Documented the sandbox/production mechanism in `README.md`: the tools directory name (`morfTools` vs `morfTools_travail`) decides which projects are driven, which was previously implicit.
- `ecosystem.json` declared `GateWayLab` while the production repository is named `GatewayLab`. The manifest is meant to hold canonical production names, and `doctor` compared them case-sensitively, so the project reported `[WARN] unexpected origin` in production. The manifest now uses `GatewayLab`.
- `doctor` compares the origin URL case-insensitively in both scripts: GitHub resolves repository names case-insensitively, so a spelling difference alone never indicates a wrong remote.

- Corrected synchronization destination resolution: relative paths now resolve next to the sandbox workspace.
- Updated user-facing documentation to use canonical production project names.
- Added a manifest-driven Windows synchronization script that preserves destination Git repositories and never rewrites text globally.
- Made `ecosystem.json` canonical: it contains production component names.
- Renamed the standalone tools project to morfTools.
- Made PowerShell and Bash tools resolve component names consistently in production.
- Replaced the legacy project configuration with root-aware command launchers.
- Documented the portable workspace architecture and remote safety rules.
- Registered GateWayLab and created its GitHub repository.
