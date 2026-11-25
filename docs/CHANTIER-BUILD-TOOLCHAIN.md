# Chantier morfTools - `morf build` sur un autre environnement de dev

Même leçon que `morf clone` : le build supposait l'environnement du poste
principal. Le preset CMake `mingw` (13 projets) **fige** les chemins d'une
machine dans ses `cacheVariables` :

```
CMAKE_CXX_COMPILER = C:/msys64/mingw64/bin/c++.exe
CMAKE_MAKE_PROGRAM = C:/msys64/mingw64/bin/ninja.exe
CMAKE_PREFIX_PATH  = C:/msys64/mingw64
```

Sur l'Asus (toolchain Qt officielle : `C:\Qt\Tools\Ninja`, `C:\Qt\Tools\
mingw1310_64`, `C:\Qt\6.11.1\mingw_64`), ces chemins n'existent pas →
`'…/ninja.exe' failed with: no such file or directory` sur les 15 projets.

## Principe

La machine annonce ce qu'elle possède ; morfTools détecte la toolchain **réelle**
et s'y adapte, plutôt que d'imposer la disposition du poste principal.

## Fait (morfTools 0.19.0)

- **`detect_windows_toolchain()`** (dans `commands.py`, mise en cache) : trouve
  `ninja`, le compilateur MinGW (`g++`/`gcc`) et le préfixe Qt (via
  `CMAKE_PREFIX_PATH`/`Qt6_DIR`, sinon `qmake` sur le PATH → `.../mingw_64`).
- **`cmake_build`** surcharge les valeurs figées du preset `mingw` par des `-D`
  détectés (la ligne de commande l'emporte sur les `cacheVariables` du preset).
  Aucune édition des 13 presets ; marche partout où la toolchain est sur le PATH.
- Un **élément manquant** (ninja/compilateur/Qt) est signalé clairement **une
  fois** (pas 13 échecs), avec la marche à suivre.
- **PlatformIO absent** → firmware ESP32 sauté avec un avis, pas de crash `pio`.
- **`morf doctor`** : section « Toolchain build (Windows) » (ninja/compilateur/Qt).

## Frontière

morfTools **détecte et surcharge**, il n'installe pas la toolchain (ninja/MinGW/Qt
restent à la charge de l'utilisateur, comme le documente `doctor`). Détecter ≠
configurer, comme pour le reste du chantier.

## Validé

- **Compilation confirmée sur l'Asus (2026-08-18)** : machine Windows fraîche,
  toolchain Qt officielle (`C:\Qt\Tools\Ninja`, `mingw1310_64`, `C:\Qt\6.11.1\
  mingw_64`) sur le PATH. `morf build` détecte cette toolchain, surcharge les
  chemins MSYS2 figés du preset, et compile - sans édition des presets. L'objectif
  du chantier est atteint : morfTools est indépendant de l'environnement du poste
  principal.

## Reste (non urgent)

- Éventuel nettoyage des presets `mingw` figés (pour que `cmake --preset mingw`
  direct, hors morfTools, soit aussi portable) - chantier distinct.
- Risque de toolchains mélangées sur le PATH (msys64 + Qt officielle) : la
  détection suit l'ordre du PATH ; sur une machine bien configurée, cohérent (le
  cas Asus l'a confirmé).

## Mise à jour : MSYS2 UCRT64 (2026-11-17)

L'environnement MSYS2 du parc passe de `MINGW64` (déprécié) à `UCRT64`, comme Ant
Renamer Qt. La détection reste pilotée par le `PATH` : mettre `C:\msys64\ucrt64\bin`
en tête suffit. Deux garde-fous s'ajoutent :

- le préfixe Qt est pris **au même endroit que le compilateur** quand celui-ci est un
  préfixe MSYS2 qui contient Qt (plus de Qt officiel associé au g++ de MSYS2) ;
- `morf build` et `morf doctor` signalent (`[WARN]`) un compilateur `mingw64` ou un
  compilateur et un Qt de préfixes différents.

Les chemins figés ci-dessus (`C:/msys64/mingw64/...`) sont historiques.

Suites (0.39.1 et 0.39.2) : le Qt du préfixe MSYS2 du compilateur l'emporte aussi sur
`CMAKE_PREFIX_PATH` et `Qt6_DIR` de l'environnement (avertissement), et un `build-mingw` dont
le cache référence un autre environnement, ou dont la `Qt6Core.dll` diffère, est supprimé avant
la configuration. Voir `ENVIRONNEMENT-DEV` (environnement Windows de référence).
