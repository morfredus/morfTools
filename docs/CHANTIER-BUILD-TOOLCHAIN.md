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

## Reste

- Le vrai test sur l'Asus : `morf build` avec la toolchain Qt officielle sur le
  PATH doit compiler (détection → surcharge → build).
- Éventuel nettoyage des presets `mingw` figés (pour que `cmake --preset mingw`
  direct, hors morfTools, soit aussi portable) — chantier distinct, non urgent.
- Risque de toolchains mélangées sur le PATH (msys64 + Qt officielle) : la
  détection suit l'ordre du PATH ; sur une machine bien configurée, cohérent.
