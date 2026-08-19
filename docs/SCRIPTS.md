# Référence des scripts du parc morfSystem

Recensement **exhaustif** de tous les scripts du parc : les commandes globales
`morf`, le `service.py` de chaque service, et les scripts locaux propres à chaque
projet, avec leurs actions et leurs options.

Complément de [`EXPLOITATION.md`](EXPLOITATION.md), qui est l'aide-mémoire du
quotidien (quand utiliser quoi, plus les commandes système). Ce document-ci vise
la **couverture complète** : chaque fichier de script, y compris les outils de
packaging et de build propres à un projet.

Deux niveaux d'outils :

- **`morf` / `morf.py`** (morfTools) agit sur **tout le parc** ou un sous-ensemble.
  C'est la dépendance d'administration : pratique, jamais requise à l'exécution.
  Un service déjà installé tourne sans morfTools.
- **`service.py`** (dans chaque projet) agit sur **un seul service**. C'est le CLI
  de morfdeploy, vendoré et identique partout : un service se déploie donc sans
  morfTools.

> Convention : lancer `morf` **sans `sudo`** (il élève lui-même la seule étape qui
> en a besoin). Les actions `service.py` qui touchent le gestionnaire de services
> demandent les droits administrateur (`sudo` sous Linux).

---

## 1. Commandes globales - `morf <commande>`

Le pilote du parc (`morfTools/morf.py`, exposé en `morf` via `activate-cli.sh`).
Chaque commande n'opère que sur les projets déclarés dans `ecosystem.json`. Le
preset accepte `-p/--preset <nom>` ou une valeur en position simple (`mingw`,
`linux`, `linux-arm64`...).

### Dépôts et Git

| Commande | Action | Options |
|---|---|---|
| `clone` | Clone les projets manquants (branche du manifeste). | - |
| `fetch` | Récupère les dépôts distants et purge les références supprimées. | - |
| `pull` / `update` | Tire en avance rapide (`git pull --ff-only`) tous les dépôts. Alias. | - |
| `push` | Pousse la branche du manifeste vers `origin`. | - |
| `commit` | Indexe toutes les modifications et valide si nécessaire. | `-m/--message` |
| `status` | Affiche l'état Git court et la branche de chaque projet. | - |

### Compilation et déploiement

| Commande | Action | Options |
|---|---|---|
| `build` | Compile les projets (PlatformIO, ou configure+compile CMake). Les GUI de bureau sont sautées sur machine sans écran. | `-p/--preset`, `--gui` |
| `install` | Sans `--services` : installe `requirements.txt`. **`--services` déploie TOUS les services** (compile sous vous, élève la seule install). À lancer **sans sudo**. | `--services`, `--only NAME`, `--preset` |
| `uninstall` | Désinstalle un service (`--only`) ou tous. Conserve la config par défaut. | `--only NAME`, `--purge`, `--backup DIR` |
| `upgrade` | Pull + recompile les projets CMake + met à jour les services installés ici. Refuse sudo (élève au premier service). | `-p/--preset`, `--gui`, `--force` |

### Maintenance et configuration

| Commande | Action | Options |
|---|---|---|
| `doctor` | Vérifie le registre des ports, les copies vendorées, la version active des services installés et les dépôts Git. À lancer avant `push`. | `-u/--update`, `-v/--verbose`, `--only` |
| `clean` | Supprime tous les dossiers de compilation (`build`, `build-arm64`, `build-mingw`...). | - |

Les 13 commandes de `morf` sont exactement : `clone`, `fetch`, `pull`, `update`
(alias de `pull`), `push`, `commit`, `status`, `build`, `install`, `uninstall`,
`upgrade`, `clean`, `doctor`. **Il n'y a pas de commande `morf config` ni
`morf exec-bits`** : la configuration passe par le script `./config.py`, les bits
exécutables par `./exec-bits.sh` / `.ps1` (voir §2).

Options globales du CLI : `-p/--preset`, `-m/--message`, `--only`, `--gui`,
`--force`, `--purge`, `--backup DIR`, `-v/--verbose`, `-u/--update`, `--services`
(chacune n'a d'effet que sur les commandes qui l'acceptent).

> **Mettre à jour tout le parc en une passe.** `morf upgrade` enchaîne, pour chaque
> projet installé sur cette machine : `pull` → recompilation → `service.py update`
> du projet (les services absents de la machine sont sautés proprement). Chaque
> projet garde son `service.py` ; `morf` ne fait que l'orchestrer. À lancer **sans
> `sudo`** (il élève lui-même la seule étape de déploiement). `--force` redéploie
> même sans changement ; `morf install` fait la première installation
> complète d'une machine neuve.
>
> En fin de passe, sur une machine qui consomme la config partagée
> (morfMonitor/morfDashboard), `upgrade` met aussi à niveau **le contrat de config
> partagée** `morfsystem.json` : un **merge non destructif** (backup horodaté
> systématique, ajoute les clés nouvelles du clone, ne touche jamais une valeur ni
> une liste locale, signale les clés obsolètes sans les supprimer). C'est le
> pendant, pour le fichier partagé, du merge que `service.py update` fait déjà pour
> la config propre de chaque service. `--only` saute cette étape (cible un projet
> précis) : utiliser alors `./config.py shared merge` à la main.

---

## 2. Outils à la racine de morfTools

| Script | Action | Options / arguments |
|---|---|---|
| `morf.py` | Le pilote du parc (toutes les commandes du §1). Une implémentation, toute plateforme. | cf. §1 |
| `config.py` | Gestion de la config du parc, **script séparé** (pas une commande `morf`). `shared` agit sur le fichier partagé `/etc/morfsystem/morfsystem.json` (lu par morfMonitor et morfDashboard) : `merge` = mise à niveau non destructive (ajoute les clés du clone, garde les valeurs locales ; ce que lance `morf upgrade`), `install`/`apply` = **écrasement** depuis le clone (réalignement volontaire). `deploy <projet>` déploie la config d'un projet en déléguant à son `service.py config push --force`. | `shared status\|validate\|edit\|diff\|merge\|install\|apply`, `deploy [<projet>] [-- <args>]` |
| `activate-cli.sh` | Expose les commandes du parc (`morf`, `screenctl`...) dans `~/.local/bin`, sans déplacer les scripts. Action volontaire, ne touche que `~/.local/bin`. | `--status`, `-n/--dry-run`, `--help` |
| `exec-bits.sh` / `exec-bits.ps1` | Restaure le bit exécutable des scripts à shebang (racine du parc). Enveloppes de `scripts/exec-bits.py`. | `--check`, `--project NAME` |
| `scripts/ecosystem-check.py` | Implémentation partagée des vérifications à l'échelle du parc, appelée par `doctor`. | (interne) |
| `scripts/exec-bits.py` | Implémentation de la restauration des bits exécutables. | `<root> [--check] [--project NAME]` |
| `scripts/reset-parc.sh` | Efface l'état morfSystem installé de cette machine (remise à zéro). | - |

---

## 3. `service.py` - un par service (cœur morfdeploy)

Présent à la racine de chaque service. C'est le CLI de **morfdeploy** (vendoré,
identique partout) : `sudo ./service.py <action>`. Un seul point d'entrée sur
toute plateforme (systemd / Planificateur Windows).

| Action | Ce qu'elle fait | Options |
|---|---|---|
| `install` | Compile si besoin, installe le binaire + la config, enregistre et démarre le service. | `--rebuild`, `--repo DIR` |
| `update` | Recompile, remplace le binaire, **complète** la config (ajoute les nouvelles clés, garde les valeurs), redémarre. Ne redémarre pas si rien n'a changé. | `--force`, `--repo DIR` |
| `uninstall` | Désinscrit le service. Conserve la config par défaut. | `--purge`, `--backup DIR`, `--repo DIR` |
| `status` | Ce que le gestionnaire de services dit du service. | `--repo DIR` |
| `is-installed` | Silencieux ; le **code retour EST la réponse** : `0` installé, `1` non, `2` droits insuffisants pour répondre. | `--repo DIR` |
| `config [merge\|push]` | Déploie la config depuis le dépôt vers `/etc/morfsystem/<service>/`. **merge** (défaut) : ajoute les nouvelles clés, garde les valeurs. **push** (avec `--force`) : **remplace** la config déployée (sauvegarde `.bak` horodatée + redémarrage si changé). | `merge` \| `push` (positionnel), `--force`, `--repo DIR` |

> **Déployer une config modifiée** (une source, une racine, un réglage...) sans
> recompiler : `sudo ./service.py config push --force`, ou depuis la racine du parc
> `./config.py deploy <projet>` (qui délègue à ce même `service.py config push
> --force`). C'est la voie unifiée qui a remplacé les anciens `deploy-config.sh`
> par projet (§7).

---

## 4. Scripts communs à (presque) tous les projets

| Script | Action | Options / arguments |
|---|---|---|
| `scripts/sync-morf.sh` / `.ps1` | Resynchronise les **copies vendorées** (`third_party/morf/` : beacon, update, morfdeploy) depuis leurs dépôts sources. À lancer après une évolution d'un socle partagé. | - |
| `scripts/new-service.sh` / `.ps1` | Clone le patron (`morfTemplateService`) en un nouveau service : copie l'arbre (sans `.git`/build), remplace les jetons de nom, renomme les fichiers. | `<nom-minuscule> <NomCamel> [dossier_dest]` |

`sync-morf` et `new-service` sont présents dans les services dérivés du patron
(morfPhoto, morfAnalytics, morfMonitor, morfCollector, morfNotify, morfSensor,
morfSync, morfTemplateService). `service.py` est, lui, dans **tous** les services.

---

## 5. Spécifiques morfMonitor - config partagée

morfMonitor porte l'outillage de la **config partagée** `morfsystem.json` (ce qui
est supervisé, lu par morfMonitor *et* morfDashboard). Distinct du déploiement de
config d'un service, donc **à conserver**.

| Script | Action | Sous-commandes / rôle |
|---|---|---|
| `scripts/linux/config-tool.sh` | Outil de la config partagée déployée. | `status`, `check`, `diff`, `merge` |
| `scripts/windows/config-tool.ps1` | Équivalent Windows de `config-tool`. | idem |
| `scripts/linux/check-config.py` | Diagnostic détaillé de la config (types de modules, clés manquantes, exposition). Appelé par `config-tool check`. | (interne) |
| `scripts/linux/merge-config.py` | Ajoute les clés apparues depuis l'installation, sans modifier une valeur existante. Appelé par `config-tool merge`. | (interne) |
| `scripts/linux/morfmonitor.service` | Modèle d'unité systemd (jetons remplacés par morfdeploy). Présent dans chaque service. | (gabarit) |

---

## 6. Applications de bureau, dashboard et firmware

### morfDashboard

| Script | Action |
|---|---|
| `scripts/linux/install-service.sh` | Installe morfDashboard en service systemd (variante dédiée, antérieure au `service.py` générique). |
| `scripts/linux/update-service.sh` | Met à jour le service morfDashboard installé. |

### ComponentHub et SiteWatch (applications de bureau Qt)

| Script | Action |
|---|---|
| `scripts/linux/install.sh` | Intégration au bureau Linux (raccourci `.desktop`, icône). |
| `scripts/linux/package-appimage.sh` | Construit une AppImage autonome. |
| `scripts/linux/package-deb.sh` | Construit un paquet Debian (`.deb`). |
| `scripts/windows/package-win.ps1` | Assemble une distribution Windows autonome (exe + DLL + plugins Qt). |
| `scripts/windows/deploy-mingw.sh` | Copie à côté de l'exe les DLL non-Qt de `/mingw64/bin` nécessaires. |
| `scripts/windows/vscode-mingw.ps1` | Configure l'environnement MinGW pour VS Code. |

### MeteoHub (firmware ESP32)

| Script | Action |
|---|---|
| `scripts/embed_web_files.py` | Convertit les fichiers de l'interface web en tableau C (embarqué dans le firmware). |
| `scripts/version.py` | Injecte `PROJECT_VERSION` depuis le fichier `VERSION` à la racine. |

---

## 7. Scripts redondants (déploiement de config)

Depuis l'unification du déploiement de config dans morfdeploy
(`service.py config push --force`, §3), les `deploy-config` par projet font
doublon.

| Fichier | Statut | Remplacé par |
|---|---|---|
| `morfPhoto/scripts/linux/deploy-config.sh` | retiré | `service.py config push --force` |
| `morfAnalytics/scripts/linux/deploy-config.sh` | retiré | `service.py config push --force` |
| `morfMonitor/scripts/linux/deploy-config.sh` | à retirer | `service.py config push --force` |
| `morfMonitor/scripts/windows/deploy-config.ps1` | à retirer | `service.py config push --force` (Windows) |

> **Avant de retirer ceux de morfMonitor** : son `README` (FR + EN) et son
> `CHANGELOG` renvoient vers `deploy-config.sh` (table de dépannage), à repointer
> vers `service.py config push --force`. Ses `config-tool` / `merge-config` /
> `check-config` (§5) sont d'un autre rôle et **restent**.
