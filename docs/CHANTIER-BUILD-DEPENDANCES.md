# Chantier morfDeploy - Dépendances de build déclaratives

Prolongement direct du chantier « machine neuve » : après l'accès Git, la
toolchain, `python3` et PlatformIO, l'Asus (Windows, toolchain Qt officielle,
sans MSYS2) a révélé une dernière hypothèse implicite : **certaines
bibliothèques nécessaires à la COMPILATION** (OpenSSL, libssh2, nlohmann_json,
zlib) sont présentes sur le Legion via MSYS2 mais absentes ailleurs.

Règle : *le projet déclare son besoin, la machine annonce ce qu'elle a, morfDeploy
résout l'écart avant le build, l'utilisateur reste maître de toute installation.*

## `build_dependencies` ≠ `system_dependencies`

- **`system_dependencies`** (0.7.0) : ce qu'un service a besoin pour **tourner**
  (Qt SerialPort, exiftool). Le projet déclare le(s) paquet(s) par famille.
- **`build_dependencies`** (0.9.0) : ce qu'un projet a besoin pour **compiler**.
  Le projet déclare un **id logique** ; morfDeploy le mappe au paquet via un
  **registre central** (`builddeps.py`).

## Fait (morfDeploy 0.9.0, morfTools 0.21.0)

- **Contrat** `build_dependencies: [{id, required}]` dans `service.json` + registre
  central (openssl, libssh2, nlohmann-json, zlib → paquets debian/fedora/arch).
- **`service.py build-deps`** (`--list` JSON, `--dry-run`, `--yes`) ; résolution
  intégrée à `install` avant `ensure_binary`, et à **`morf build`/`morf deploy`
  avant `cmake_build`**.
- **Gestionnaire présent (Debian)** : détecte, présente, installe (validation /
  `--yes`), vérifie. **Sans gestionnaire (Qt Windows)** : annonce le besoin,
  laisse le `find_package` du build comme dernier mot (filet), ne bloque pas.
- Une obligatoire non satisfaite → projet **FAILED** (rattrapé, pas de cascade).
- **Déclarés** : morfCollector (`openssl`, `libssh2`), morfSync (`nlohmann-json`).

## Reste

- **Section `doctor`** « Dépendances de build » (par service) - à ajouter.
- **Projets non-services** (SiteWatch → openssl, apps/libs) : pas de `service.json`
  donc pas de contrat `build_dependencies` pour l'instant. Relève du futur
  « contrat de projet » (build/package pour non-services), déféré dans l'audit.
- **Détection sur toolchain sans gestionnaire** : aujourd'hui on annonce (CMake
  filet). Une sonde `find_package` réelle par toolchain pourrait vérifier la
  présence — à **concevoir et éprouver sur l'Asus** (banc d'essai voulu par Fred),
  sans y installer les libs à la main pour préserver le cas de test.
- Étendre le registre (autres libs, familles) au fil des besoins réels.
