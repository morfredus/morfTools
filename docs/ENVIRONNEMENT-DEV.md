# Environnement de développement et dépendances de compilation

Ce document décrit ce qu'il faut installer sur une machine pour **compiler le parc
morfSystem sans erreur**. Il complète `docs/GUIDE-DEMARRAGE.md` (utilisation) en se
concentrant sur la préparation de l'environnement de build.

Principe : le parc ne suppose plus l'environnement du poste principal. `morf build`
détecte la toolchain réellement présente (Qt, MinGW, Ninja) et s'y adapte. Restent
à fournir, une fois par machine, la **toolchain** et les **bibliothèques de
compilation** listées ici. Sur Debian/Ubuntu/Mint, `morf install`/`build` sait même
proposer d'installer les dépendances de build déclarées ; sous Windows, MSYS2 UCRT64
est reconnu (les bibliothèques sont vérifiées avec `pacman`, jamais installées par le
build) ; sur une toolchain sans gestionnaire de paquets (Qt officielle), elles doivent
être présentes au préalable.

---

## 1. Toolchain commune (tous les projets C++/Qt)

| Outil | Rôle | Vérifier |
| --- | --- | --- |
| **Git** | cloner, mettre à jour | `git --version` |
| **Python 3.10+** | exécuter `morf` et les `service.py` | `python --version` |
| **CMake 3.21+** | configuration de build | `cmake --version` |
| **Ninja** | générateur de build | `ninja --version` |
| **Compilateur C++17** | MinGW (Windows) / gcc (Linux) | `g++ --version` |
| **Qt 6** | framework de tous les services et apps | `qmake --version` |

Composants Qt 6 utilisés dans le parc : **Core**, **Network** (partout), **Sql**
(morfAnalytics, morfPhoto), **Concurrent** (morfCollector, morfPhoto), **Widgets**
(ComponentHub, PhotoHub, SiteWatch), **Charts** (SiteWatch), **SerialPort**
(morfSensor, pour le driver LD2410C).

> **Version Qt minimale : 6.4.** Le plancher du parc est le Qt du système Linux
> (Debian / Ubuntu 24.04 : `qt6-base-dev` = Qt 6.4), PAS le Qt plus récent de
> MSYS2 sous Windows (6.9). Tout code C++/Qt doit donc compiler avec Qt 6.4. Une
> API arrivée plus tard - par ex. `QStyleHints::colorScheme()` /
> `Qt::ColorScheme`, introduites en 6.5 - doit être gardée derrière
> `#if QT_VERSION >= QT_VERSION_CHECK(6, 5, 0)` avec un repli portable. Compiler
> seulement sous Windows (MSYS2, Qt récent) ne prouve pas la portabilité : c'est
> le build Linux/Pi de la chaîne de publication qui la révèle.

> `morf doctor` (section « Toolchain build (Windows) ») indique si Ninja, le
> compilateur MinGW et Qt sont trouvés sur la machine.

---

## 2. Bibliothèques de compilation non-Qt

Certains projets référencent des bibliothèques externes via `find_package`. Leur
absence fait échouer la configuration CMake (`Could NOT find …`).

| Bibliothèque | Projets qui en ont besoin | Paquet Debian/Ubuntu/Mint | Paquet MSYS2 (ucrt64) |
| --- | --- | --- | --- |
| **OpenSSL** | morfCollector (coffre), SiteWatch (via libssh2) | `libssl-dev` | `mingw-w64-ucrt-x86_64-openssl` |
| **libssh2** | morfCollector (SFTP), SiteWatch | `libssh2-1-dev` | `mingw-w64-ucrt-x86_64-libssh2` |
| **nlohmann_json** | ComponentHub, SiteWatch, morfSync | `nlohmann-json3-dev` | `mingw-w64-ucrt-x86_64-nlohmann-json` |
| **zlib** | SiteWatch | `zlib1g-dev` | `mingw-w64-ucrt-x86_64-zlib` |
| **pkg-config** | morfCollector, SiteWatch (recherche de libssh2) | `pkg-config` | `mingw-w64-ucrt-x86_64-pkgconf` |
| **Threads** | morfSync | (fourni par le compilateur) | (fourni par le compilateur) |

Les **services** morfCollector et morfSync déclarent leurs besoins dans
`service.json` (`build_dependencies`) : sur une plateforme avec gestionnaire de
paquets, morfDeploy propose de les installer avant le build. Les **applications**
ComponentHub et SiteWatch n'ont pas de `service.json` : leurs bibliothèques doivent
être installées à la main (colonnes ci-dessus) jusqu'à l'arrivée d'un contrat de
projet dédié.

---

## 3. Installation par plateforme

### 3.1 Linux Debian / Ubuntu / Linux Mint (x86_64) et Raspberry Pi (ARM64)

```bash
sudo apt update
sudo apt install -y \
    git python3 python3-pip \
    cmake ninja-build build-essential pkg-config \
    qt6-base-dev qt6-base-dev-tools \
    qt6-charts-dev qt6-serialport-dev \
    libssl-dev libssh2-1-dev nlohmann-json3-dev zlib1g-dev \
    libimage-exiftool-perl
```

- `qt6-base-dev` fournit Core / Network / Sql / Widgets / Concurrent.
- `qt6-charts-dev` : requis seulement pour SiteWatch.
- `qt6-serialport-dev` : requis pour le driver radar LD2410C de morfSensor
  (sans lui, morfSensor compile sans ce driver - voir sa doc).
- `libimage-exiftool-perl` : dépendance **runtime** de morfPhoto (métadonnées
  EXIF), pas de compilation.

Sur Debian/Ubuntu/Mint, `morf install` et `morf build` peuvent aussi installer les
dépendances de build **déclarées** (morfCollector, morfSync) avant de compiler :
elles sont proposées, jamais installées en silence (`--yes` pour un run non
interactif).

### 3.2 Windows

Deux approches, selon la toolchain choisie.

#### Option A - MSYS2 / UCRT64 (recommandée : cohérente, tout au même endroit)

Installer [MSYS2](https://www.msys2.org/), puis dans un shell **UCRT64** (le runtime UCRT remplace MINGW64, déprécié) :

```bash
pacman -Syu
pacman -S --needed \
    git python \
    mingw-w64-ucrt-x86_64-toolchain mingw-w64-ucrt-x86_64-cmake mingw-w64-ucrt-x86_64-ninja \
    mingw-w64-ucrt-x86_64-pkgconf \
    mingw-w64-ucrt-x86_64-qt6-base mingw-w64-ucrt-x86_64-qt6-charts \
    mingw-w64-ucrt-x86_64-qt6-serialport \
    mingw-w64-ucrt-x86_64-openssl mingw-w64-ucrt-x86_64-libssh2 \
    mingw-w64-ucrt-x86_64-nlohmann-json mingw-w64-ucrt-x86_64-zlib
```

Compilateur, Qt et toutes les bibliothèques proviennent de la même source : c'est
la configuration la plus simple pour compiler l'intégralité du parc.

`morf build` prend le compilateur et Qt dans l'ordre du `PATH` : mettre
`C:\msys64\ucrt64\bin` en tête. `morf doctor` signale un `PATH` qui pointe encore
vers `mingw64` ou qui mélange un Qt officiel et le compilateur de MSYS2.

#### Option B - toolchain officielle de Qt (non retenue pour le parc)

L'installeur Qt officiel (Qt + MinGW 13 + Ninja + CMake sous `C:\Qt\...`) forme une
toolchain **complète et fermée** : Qt, compilateur et runtime y sont compilés ensemble. Elle
n'est plus la référence du parc, pour deux raisons :

- elle ne fournit ni OpenSSL, libssh2, nlohmann_json ni zlib : morfCollector, morfSync et
  SiteWatch ne compilent pas sans bibliothèques ajoutées, compatibles avec ce MinGW ;
- elle **ne se combine pas avec MSYS2** : un compilateur UCRT64 avec le Qt officiel (ou
  l'inverse) mélange deux runtimes C et deux `libstdc++`. Résultat : `rcc` qui plante
  (`The rcc list process failed`, code `0xc0000409`), ou un exécutable qui ne démarre pas
  (« point d'entrée introuvable »).

Sur une machine qui n'a que cette toolchain, `morf build` la détecte et compile les services
Qt-only. Ne jamais la laisser sur le `PATH` ni dans `CMAKE_PREFIX_PATH` à côté d'UCRT64 :
`morf build` ignore alors `CMAKE_PREFIX_PATH` au profit du Qt de MSYS2 et le signale.

---

## 4. Firmware ESP32 (GatewayLab, MeteoHub)

Ces deux projets se compilent avec **PlatformIO**, pas CMake :

```bash
python -m pip install --user platformio
```

`morf build` les compile via `pio` s'il est présent ; sinon il les **saute** avec
un avis (le reste du parc se compile quand même).

---

## 5. Dépendances runtime (hors compilation)

| Projet | Dépendance runtime | Paquet | Effet si absente |
| --- | --- | --- | --- |
| morfPhoto | `exiftool` | `libimage-exiftool-perl` (Debian) | indexe sans EXIF (boîtiers/objectifs/années vides) |
| morfSensor | Qt SerialPort | (voir §2, build) | driver LD2410C désactivé, capteurs simulés seulement |

---

## 6. Vérifier et compiler

```bash
# état de la toolchain de build (Windows)
python morf.py doctor

# compiler tout le parc (toolchain détectée automatiquement)
python morf.py build
```

Un projet dont une bibliothèque manque est signalé **FAILED** avec la cause, sans
interrompre les autres. Corriger l'environnement (sections ci-dessus) puis
relancer.

---

## 7. Récapitulatif par projet

| Projet | Type | Qt6 | Libs de build non-Qt | Runtime |
| --- | --- | --- | --- | --- |
| morfBeacon | lib | Core, Network | - | - |
| morfAnalytics | service | Core, Network, Sql | - | - |
| morfMonitor | service | Core, Network | - | - |
| morfNotify | service | Core, Network | - | - |
| morfPhoto | service | Core, Network, Sql, Concurrent | - | exiftool |
| morfSensor | service | Core, Network, (SerialPort) | - | (SerialPort) |
| morfCollector | service | Core, Network, Concurrent | **OpenSSL, libssh2**, pkg-config | - |
| morfSync | service | - (C++ pur, sans Qt) | **nlohmann_json**, Threads | - |
| morfTemplateService | patron | Core, Network | - | - |
| morfUpdate | lib | Core, Network | - | - |
| ComponentHub | app | Widgets | **nlohmann_json** | - |
| PhotoHub | app | Widgets, Network | - | - |
| SiteWatch | app | Widgets, Charts, Network | **libssh2, zlib, nlohmann_json**, pkg-config | - |
| GatewayLab | firmware | (PlatformIO) | - | - |
| MeteoHub | firmware | (PlatformIO) | - | - |

morfDeploy, morfSystem, morfDashboard n'ont pas d'étape de compilation C++ (socle
Python, documentation, application Python).
