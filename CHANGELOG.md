# Changelog

## Unreleased

## [0.4.1] — 2026-07-22

### Corrigé

- **Le conseil de réparation de `exec-bits` ne se sabote plus lui-même.** Sur un
  premier clone dont les scripts ont perdu le bit d'exécution, `doctor` invitait
  à lancer `./exec-bits.sh` — un wrapper qui a besoin du bit qu'il doit
  justement restaurer, donc `Permission denied` : le remède renvoyait à sa
  propre forme cassée. Le message donne désormais `python3 scripts/exec-bits.py ..`,
  qui s'exécute quel que soit le bit (même raison que `python3 morf.py`), et
  explique pourquoi. Le guide de démarrage documente la sortie, à l'étape
  `doctor` et en dépannage.

## [0.4.0] — 2026-07-22
### Ajouté

- **`morf uninstall`** — désinstalle un service (`--only`) ou tout le parc, avec
  `--purge` (efface aussi config et binaire) et `--backup` (copie la config
  d'abord). Délègue au `service.py` de chaque projet.
- **`scripts/reset-parc.sh`** — remet une machine à blanc : arrête et désinstalle
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

## [0.3.0] — 2026-07-21

- **`exec-bits` restores the executable bit across the parc**, and `doctor` now
  reports its absence. Forty-six tracked scripts were recorded as `100644`,
  including all five of morfMonitor — among them the `deploy-config.sh` the
  README tells people to run.

  The defect cannot be observed from the machine that creates it. Windows has no
  executable permission, so Git records new files as non-executable; the working
  copy runs fine because `bash script.sh` never consults the bit. The Pi clones
  the same repository, `./script.sh` answers `Permission denied`, and nothing in
  that message points back at Windows.

  So the fix targets the **index mode**, not the filesystem: `chmod` on Windows
  is a no-op Git ignores, while `git update-index --chmod=+x` records 100755 in
  the tree every other clone will see. What counts as runnable is the
  **shebang**, not the extension — that is the author's own statement of intent,
  and it covers `.sh` and `.py` alike without a list of extensions free to drift.

- **`morfTools` gains the `.gitattributes` every other project already had.** It
  was the only repository without one, and the only one whose scripts run on the
  Pi. Nothing had broken yet: its seventeen `.sh` were kept LF by the local
  Git configuration alone, which is not a property of the repository and does not
  travel with a clone. A `.sh` stored with CRLF fails there with
  `bad interpreter: /usr/bin/env bash^M` — the same class of defect as the
  missing bit, invisible from the machine that introduces it.

- **The three meanings of "update" are now documented.** `update` is a pure
  alias of `pull`; `upgrade` pulls **and rebuilds**; a project's own
  `update-service.sh` is the only one that touches an installed service. The
  first two act on sources, so a Pi keeps serving the previous binary after an
  `upgrade` until the project's own script runs.

## [0.2.1] — 2026-07-21

- **`doctor` compares the vendored `VERSION` file too.** It only compared `src`
  and `include`, so seven copies could announce 0.2.1 while carrying the code of
  0.4.1 and the check stayed green. The exclusion was too broad: the vendored
  `CMakeLists.txt` is legitimately adapted to its embedding context, `VERSION`
  is not — it is simply copied, and a copy that lies about its version is worse
  than no version at all, because it is trusted.

## [0.2.0] — 2026-07-21

- **`config` becomes the single entry point for configuration deployment**, on
  both platforms: `config shared <action>` for the parc file, `config deploy
  <project>` for a project's own file. `shared-config` still works and points at
  the new name.

  `deploy` **delegates** to the project's own script rather than learning its
  install directory and service name — the rule that keeps morfTools free of
  business knowledge, and that `morf build` already follows by delegating to
  each project's build system. A project cloned on its own therefore still
  deploys its configuration without morfTools.

  A project name is required rather than defaulting to "all": the command
  overwrites deployed configurations, and doing that to every project because an
  argument was forgotten is not a reasonable default.

- **Fixed a trap in `shared-config`: the source was hard-coded to
  `morfsystem.example.json`.** A clone carrying a real `config/morfsystem.json`
  beside it — which is the normal case — saw `install` silently deploy the
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

- `ecosystem.json` now owns the **port allocation registry** (`ports`), raised to `schemaVersion` 2. The parc plan previously existed only as a `_comment_port` string inside `morfMonitor/config/morfmonitor.example.json`: a component with no authority over the others, holding a partial copy of an ecosystem-wide fact. That copy was already incomplete — it omitted 8789 (morfNotify) and 8787 (the morfBeacon status default) — so a developer consulting it to pick a free port got wrong information with no way to know it.
- Fixed the resulting collision: `morfTemplateService` shipped `http_port: 8799`, the port allocated to morfAnalytics. Every service created through the documented procedure therefore started on an occupied port. The template now uses 8901, inside a `templateRange` (8900-8999) reserved for templates and examples and deliberately outside the 8787-8799 service block, so a clone that has not yet reserved its own port is visibly unfinished instead of silently conflicting.
- `ecosystem.json` also declares the **vendored copies** (`vendored`): the shared libraries copied into `third_party/morf/`, with their canonical source project. The copy strategy itself is unchanged — it is what keeps the build reproducible across Windows, Linux x64 and Raspberry Pi without an external repository.
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
