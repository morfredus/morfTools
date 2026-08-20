# morfSystem administration tools

*Read in another language: **English** (this document) · [Français](README.fr.md).*

[![Version](https://img.shields.io/badge/version-0.34.0-blue)](CHANGELOG.md)

`morfTools` is the administration project for morfSystem. The project can be moved or renamed: scripts derive the workspace root from their own location and never rely on an absolute path.

## Layout

- `ecosystem.json`: project manifest, clone URL template, port allocation registry, and vendored-copy registry.
- scripts at this project root: portable ecosystem administration commands.
- `scripts/ecosystem-check.py`: shared implementation of the ecosystem-wide checks run by `doctor`.
- sibling component directories: independent morfSystem projects.
- [`docs/GUIDE-DEMARRAGE.md`](docs/GUIDE-DEMARRAGE.md) *(FR)*: installing and configuring
  morfSystem from nothing, and which command to run when. **Start here** if the parc is
  new to you.
- [`docs/ENVIRONNEMENT-DEV.md`](docs/ENVIRONNEMENT-DEV.md) *(FR)*: development environment
  and **compilation dependencies** (toolchain, Qt6 components, OpenSSL/libssh2/… per
  project, per-platform install). Read this to compile the parc without errors on a new
  machine.
- [`docs/EXPLOITATION.md`](docs/EXPLOITATION.md) *(FR)*: every script (options, action, when to
  use it) and the essential Linux/Windows commands for day-to-day monitoring and maintenance
  (`systemctl`, `journalctl`, `schtasks`, restart, logs). The operations reference.
- [`docs/SCRIPTS.md`](docs/SCRIPTS.md) *(FR)*: the **exhaustive** catalog of every parc
  script (global `morf` commands, `service.py`, and each project's local scripts, including
  packaging and build helpers), with actions and options.
- `docs/ECOSYSTEM-PRINCIPLES.md`: the founding principles and the architectural invariants that apply to the **whole parc**, including the boundaries no component may cross.
- [`docs/FIRST-TEST.md`](docs/FIRST-TEST.md) *(FR)*: what to report after a **first**
  installation. The parc has only ever been installed by the person who wrote it -
  the one least able to see what the guide leaves out. Honest feedback wanted,
  including "I gave up here".
- [`docs/ACTIVATE-CLI.md`](docs/ACTIVATE-CLI.md): expose the parc commands (`morf`, `screenctl`, …) in `~/.local/bin` via `activate-cli.sh`, without moving scripts out of their project.
- `docs/`: workspace documentation.

## CLI activation (`activate-cli.sh`)

To call the parc commands (`morf`, `screenctl`, …) from **any directory**,
`morfTools/activate-cli.sh` exposes them in `~/.local/bin` without moving or
copying the scripts out of their owning project:

```bash
cd ~/01-Travail/morfTools    # or ~/morfSystem/morfTools
./activate-cli.sh            # activate the workspace of THIS copy of morfTools
./activate-cli.sh --status   # active workspace + managed commands
./activate-cli.sh --dry-run  # preview without changing anything
```

The activated workspace is the **parent** directory of this copy of morfTools: an
activation never mixes two roots (`01-Travail` vs `morfSystem`). It is a
**deliberate** action, independent of `install`/`update`, touching only
`~/.local/bin` (no service, nothing under `/opt`, `/etc`, `/var/lib`). Each
project declares its real commands in a `cli.manifest` at its root: mode `direct`
(symlink, for a script independent of the current directory) or `project`
(launcher that enters the project first). The mode is declared, never guessed.
Full guide: [`docs/ACTIVATE-CLI.md`](docs/ACTIVATE-CLI.md).

## Sandbox and production workspaces

The tools decide which projects to drive from **their own directory name**, so
the same scripts serve both workspaces without any configuration:

| Tools directory | Projects driven | Usage |
| --- | --- | --- |
| `morfTools` | `ComponentHub`, `SiteWatch`, … | Production workspace. |
| `morfTools_travail` | `ComponentHub_travail`, `SiteWatch_travail`, … | Sandbox workspace. |

`ecosystem.json` only ever lists canonical names (`ComponentHub`); the
`_travail` suffix is added at runtime when the tools directory carries it.
Renaming the tools directory therefore switches the whole workspace, and a
project whose directory does not match the expected name is reported as
`[SKIP] <name> (not cloned)` rather than being touched.

## Commands

Run from any directory with `python3 <workspace>/morfTools/morf.py status` (or `./morf.py status`, it is executable). One implementation, every platform.

### Script arguments

All commands operate only on projects declared in `ecosystem.json`.

These are the 15 `morf` commands. Configuration and executable bits are handled
by **separate root scripts**, not `morf` subcommands: see the note below the
table.

**Two surfaces.** Administering a machine (`install`/`deploy`, `update`,
`upgrade`, `purge`, `uninstall`, `doctor`) is a different job from working on the
clones as source code (Git and build). The latter -- `clone`, `fetch`, `pull`,
`status`, `push`, `commit`, `build`, `clean` -- are also reachable under a
**`morf dev <subcommand>`** namespace, so the two surfaces read as two. The flat
forms keep working; `morf dev` with no subcommand lists them. (`morf update` as a
Git pull is deprecated in favour of `morf dev pull`.)

| `morf` command | Arguments | Action |
| --- | --- | --- |
| `clone` | `--protocol auto\|ssh\|https`, `--yes` | Clone missing projects on the manifest branch. Detects the machine's real Git access first (no assumed SSH setup): `auto` uses SSH when it truly authenticates to GitHub, else proposes HTTPS; `ssh` fails cleanly if SSH is not operational (saying what is missing); `https` clones over HTTPS. Never generates keys or edits `~/.ssh`. `--yes` authorises the HTTPS fallback non-interactively. |
| `fetch` | none | Fetch remotes and prune deleted references. |
| `pull` | `--dry-run` | Fast-forward pull from the manifest branch. `--dry-run` fetches and lists the incoming commits without merging. Prefer `morf dev pull`. |
| `update` | `--dry-run` | **Deprecated as a Git operation** -- prints a warning and behaves like `pull`. Use `morf dev pull` for Git. `morf update` is reserved to mean "update the installed components" in a later release. |
| `build` | CMake preset (auto-detected for the platform, else asked), `--gui` | Build PlatformIO projects, or configure and build CMake projects. On Windows the `mingw` preset's pinned toolchain paths are **overridden with what this machine actually has** (ninja, MinGW compiler and Qt prefix detected on the PATH / env), so a box with a different Qt/MinGW layout builds without editing presets; a missing piece is reported clearly (see `morf doctor`). PlatformIO firmware is skipped with a note when `pio` is absent. Desktop GUI apps are skipped on a headless machine (Linux, no display); `--gui` builds them anyway. |
| `install` | `[<project>…]`, `--all`, `--config keep\|merge\|replace`, `--preset`, `--dry-run`, `--yes`, `--services` | **The primo-install.** Builds the selected services and places their configuration, in one pass. Bare `morf install` offers a numbered choice; name services or `--all` to script it. `--config`: `keep` (default, never overwrite), `merge` (add the clone's new keys, keep local values), `replace` (overwrite from the repo, backup first). `--dry-run` prints the plan and touches nothing. Builds as you, elevates only the install. `install --services` = `--all` (kept for compatibility). Run it **without `sudo`**. |
| `deploy` | same as `install` | **Backward-compatible alias** of `install` (prints a note pointing to it). |
| `setup` | none | Generic per-language setup only (Python `requirements.txt` when present). Services are installed by `install`; here they are simply skipped. |
| `uninstall` | `[<project>…]`, `--all`, `--only NAME`, `--purge`, `--backup DIR`, `--dry-run`, `--yes` | Uninstall services: name them, `--all` (or bare) for every one, `--only` for one (compat). `--purge` also removes configuration and data; `--backup DIR` copies the configuration first. `--dry-run` lists what would go without touching anything. Removing services asks to confirm; `--purge` asks for a typed token (`PURGE`, or `PURGE ALL` machine-wide); non-interactive needs `--yes`. |
| `purge` | `[<project> [<id>…]]`, `--all`, `--dry-run`, `--yes`, `--force` | Erase declared data categories. Each project announces what it can erase (`service.py purge --list`); morfTools never reads a service.json. Bare `morf purge` lists what is purgeable here; `morf purge <project> <id>…` or `--all` targets it; `morf purge --all` sweeps every project on this machine. `--dry-run` previews without removing; a destructive real purge asks for a typed confirmation unless `--yes`. A real purge is refused while the service is running (it may be mid-write); `--force` overrides. |
| `upgrade` | CMake preset (auto-detected for the platform, else asked), `--gui`, `--force`, `--dry-run` | Pull, rebuild CMake projects, then update the services installed here **and merge the shared `morfsystem.json` contract** (add the clone's new keys, keep every local value; skipped with `--only`). `--force` redeploys and restarts each service even when nothing changed (passed to `service.py update`). `--dry-run` prints the per-project plan (incoming commits, rebuild, service update, shared-config merge) without doing any of it. |
| `doctor` | `--update`, `--verbose`, `--only` | Check the port registry, vendored copies, active version of installed services, and Git repositories; **`--update`** adds a comparison against `origin/main` (newer version available, morfTools included -- a network step). Run it before `push`. |
| `clean` | none | Remove every build directory (`build`, `build-arm64`, `build-mingw`, …). |
| `status` | none | Show the short Git status and branch. |
| `commit` | message (asked when omitted) | Stage all changes and commit when needed. |
| `push` | none | Push the manifest branch to `origin`. |

There is **no `morf config` and no `morf exec-bits`**. These live in separate
scripts at the morfTools root:

| Script | Usage | Action |
| --- | --- | --- |
| `./config.py shared <action>` | `status`, `validate`, `edit`, `diff`, `merge`, `install`, `apply` | Manage the shared `morfsystem.json` read by morfMonitor and morfDashboard. `merge` = non-destructive upgrade (what `morf upgrade` runs); `install`/`apply` = deliberate overwrite from the clone. |
| `./config.py deploy <project>` | project name (lists them when omitted) | Deploy a project's own configuration, delegating to its `service.py config push --force`. |
| `./exec-bits.sh` / `.ps1` | `--check`, `--project NAME` | Restore the executable bit on every script carrying a shebang. |

### `update`, `upgrade`, and `service.py update`

Three names, three different scopes. They are easy to confuse and the middle
one is the only one that touches a running machine:

| | Scope | What it does |
| --- | --- | --- |
| `update` | every repository | Nothing but `git pull --ff-only`. A pure alias of `pull`. |
| `upgrade` | every repository **and this machine** | The same pull, **rebuilds** the CMake projects, **then updates the services actually installed here**. |
| `<project>/service.py update` | one installed service | Pull, rebuild, replace the installed binary, complete the configurations, restart. |

`upgrade` only touches services this machine actually runs: a project present in
the clone and absent from the service manager is skipped quietly, because the
parc is one set of repositories deployed differently on each machine. Git runs as
you and only the deployment is elevated -- `upgrade` refuses to run under sudo,
so it asks for rights itself, once, when it reaches the first service. When a
service's binary is unchanged, `service.py update` deliberately deploys nothing
and does not restart it; `upgrade --force` passes `--force` through to redeploy
and restart every service anyway, for when bouncing them IS the intention.

An update now guarantees three things, not two: it installs the new binary,
**preserves your settings**, and **makes new options available** -- a key a new
version adds to the reference configuration is merged into an existing installed
file, with its default, without touching a value you set and without removing a
key. Lists are never merged element-wise: a supervised service or probe is never
switched on that you did not add yourself. This lives in morfdeploy, run by every
`service.py update` and `install`.

That last rule -- lists kept whole -- means a new option **inside** a module (a
module's own parameter, matched in the `modules` list) does not reach an existing
installation on its own. `<project>/service.py config` closes that gap without a
reinstall:

| | What it does |
| --- | --- |
| `service.py config` (merge, default) | Deep-enrich the deployed config: add this version's new keys **including inside a module you already have** (matched by `id`), keep every value you set, add no list entry. A timestamped `.bak` is written first. Restarts only if something changed. |
| `service.py config push --force` | Replace the deployed config with the repository's copy (backup first). The deliberate "start from the shipped config again". |

Editing `/etc/morfsystem/<service>/<service>.json` by hand and restarting works
too; `config` is the scripted, repeatable form, run from the repo like `update`.
(Not to be confused with `./config.py shared`, which manages the *shared* parc
file, not a single service's.)

`update` acts on **sources** only and leaves anything installed alone: it is the
command for looking at what changed before acting. `service.py update` remains
the way to take a **single** service without touching the rest, and it lives
inside each project because it knows that project's unit name and paths.

So a plain `update` rebuilds nothing and deploys nothing; `upgrade` carries the
new code all the way to the running services.

### Building on a headless machine

A Raspberry Pi reached over SSH has no display, so building the desktop GUI apps
(ComponentHub, SiteWatch, morfUpdate) there is effort spent on windows that
cannot open. `build` and `upgrade` skip them automatically when the machine is
headless -- Linux with neither `DISPLAY` nor `WAYLAND_DISPLAY`:

```
[ComponentHub_travail]
[SKIP] desktop GUI, no display on this machine (use --gui to build anyway)
```

A project is recognised as a GUI app by what it **links** -- Qt Widgets or Gui
-- read from its own `CMakeLists.txt`, so nothing has to be listed or kept in
sync. Headless services (morfMonitor, morfSync, …) build as before, because they
link neither.

`--gui` forces them: a headless build server that cross-distributes still wants
the binaries. On any machine with a display, everything builds, no flag needed.

### Uninstalling

`uninstall` is the mirror of installing a service, and it reads the same
manifests. By default it removes the service registration and **keeps the
configuration** -- the settings edited by hand on the machine outlive the
program.

```bash
./morfTools/morf.py uninstall --only morfSync        # one service, config kept
./morfTools/morf.py uninstall                         # every service, config kept
./morfTools/morf.py uninstall --purge                 # also remove config + binary
./morfTools/morf.py uninstall --purge --backup ~/save # copy every config there first
```

`--purge` removes each service's configuration **and every earlier location its
manifest declares** -- the `/opt` config left by the pre-`/etc` layout,
morfSync's `/etc/homeserverhub` and `/usr/local/bin/morfSync`. Nothing is
hard-coded: the teardown finds these exactly where the migration recorded them.
With `--backup DIR`, every file is copied there first, named after its full
source path so two configs sharing a basename cannot overwrite each other.

To wipe a machine whose clones are already gone, use the standalone
`scripts/reset-parc.sh` instead: hard-coded and dependency-free, for when no
manifest is available to read.

For Linux and Raspberry Pi, use CMake's own vocabulary: `--preset <name>`
(or `-p <name>`) with `build` and `upgrade`:

```bash
python3 morfTools/morf.py build --preset linux-arm64
python3 morfTools/morf.py upgrade -p linux
```

One implementation on every platform (`python3 morf.py ...`, or `morf ...` once
the CLI is activated); there is no per-platform wrapper. On Windows, the same
call runs under PowerShell:

```powershell
python3 .\morfTools\morf.py build --preset mingw
```

The preset selects the project's CMake configure and build preset. Typical presets are `mingw` (Windows/MSYS2), `linux` (native x86_64 Linux or WSL2), `linux-arm64` (native 64-bit Raspberry Pi / ARM64), and, where defined, `linux-arm64-cross` (cross-compilation). It is ignored for PlatformIO projects. `--profile` and `-Profile` remain accepted as compatibility aliases.

When no preset is given, `build` and `upgrade` list the presets declared across
the cloned projects and ask which one to use, rather than falling back to a
default build directory:

```text
No preset given for 'build'. Available presets:
  1) linux                (10/10 projects)
  2) linux-arm64          (10/10 projects)
  3) linux-arm64-cross    (3/10 projects)
  4) mingw                (10/10 projects)
Choice [1-4]:
```

The count shows how many projects declare each preset. A project that does not
declare the selected preset is reported as `[SKIP]` and does not fail the run.
`commit` prompts for its message the same way. Without a terminal (cron, CI,
redirected input) both commands list the valid values and exit with status 2
instead of guessing.

`ecosystem.json` always contains canonical production names, including `GateWayLab`; production tools use these names without modification.

## Configuration

Two kinds of configuration exist, and they do not belong in the same place.

```bash
python3 ./morfTools/config.py shared install     # the shared parc file
./morfTools/config.sh deploy morfMonitor # one project's own file
./morfTools/config.sh deploy             # list the projects that support it
```

```powershell
.\morfTools\config.ps1 shared Install
.\morfTools\config.ps1 deploy morfMonitor
```

**Shared** is `/etc/morfsystem/morfsystem.json` (`%ProgramData%\morfSystem\` on
Windows). It describes *what is supervised* and is read by morfMonitor **and**
morfDashboard. No component owns it, so morfTools does - the same reasoning
that moved the port registry into `ecosystem.json`.

**Deploy** handles a project's own configuration, and **delegates** to that
project's `deploy-config` script rather than knowing its install directory or
service name. `morf build` delegates to each project's build system instead of
learning CMake and PlatformIO; this is the same rule. The consequence is worth
keeping: a project cloned on its own still deploys its configuration without
morfTools.

A project name is required rather than defaulting to "all": the command
overwrites deployed configurations, and doing that to every project because an
argument was forgotten is not a reasonable default.

Both read the **real** configuration when the clone carries one
(`config/morfsystem.json`, `config/morfmonitor.json`) and the `.example` file
otherwise. Every write is preceded by a dated backup and shows a capped diff of
what changes.

`shared-config.sh` still works and points at the current entry point.

### Details

`config shared edit` opens `$EDITOR` (or `nano`) and validates the JSON.
`install` creates a dated backup before copying to `/etc`; `apply` additionally
restarts `morfmonitor` and `morfdashboard`. Only the system writes request sudo.

On Windows the installed location is `%ProgramData%\morfSystem\morfsystem.json`;
morfMonitor and morfDashboard both look there unless `MORFSYSTEM_CONFIG`
is set. Use `-ConfigPath` to install elsewhere.


## Ecosystem checks

`doctor` starts with two checks that no single project can perform, because
they describe a resource shared by the whole parc:

- **Port registry.** `ecosystem.json` owns the addressing plan under `ports`.
  Each allocation names the configuration file and JSON key expected to declare
  it, and the check reports collisions, mismatches, and ports declared in a
  configuration but absent from the registry.
- **Vendored copies.** Libraries copied into `third_party/morf/` are compared
  against their canonical project. Drift is reported with the offending files
  and the resynchronisation command.

The output is **a summary**, not a transcript of everything checked: healthy,
sixty green lines would bury the one failure that matters. Passing checks are
counted, exceptions detailed, and the run ends with what to do:

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

By default `doctor` stays **local and instant**: it does not touch the network,
and ends with `Tout est conforme (versions non vérifiées).`

**`doctor --update`** adds a network step -- one `git fetch` per clone --
comparing each against `origin/main` and reporting any newer version with the
commands to fetch and apply it. The signal is "the remote has commits I do not",
which holds for the whole parc (GitHub Releases are cut for only some projects)
and needs nothing but `git`. **morfTools checks itself.** An available update is
not a failure and does not affect the exit code; a progress line on `stderr`
keeps the fetches from being a silent wait, and offline the check degrades to
`[SKIP]`.

The proposed command depends on what runs here: if the project's service is
active on this machine the remedy is `upgrade` (rebuild and redeploy in place);
if it is not -- not installed here, a desktop app with no service, or a stopped
service -- the remedy is `update` (pull the source, nothing to redeploy).

Each action reuses the remediation the check itself prints (a resync command, an
upgrade command) when there is one, and is derived from the message otherwise.
`doctor --verbose` restores the line-by-line output.

Allocate a port in `ecosystem.json` **before** writing it into a service
configuration; `doctor` fails while the two disagree. See
[`docs/ECOSYSTEM-CHECKS.md`](docs/ECOSYSTEM-CHECKS.md) for the registry format,
the reserved ranges, and how to resolve reported drift.

## Deployment synchronization

`scripts/windows/sync-to-morfsystem.ps1` is a Windows-specific deployment helper. It reads `ecosystem.json` and copies component content to a production root without copying or deleting destination `.git` directories. It never performs a global text replacement.

Use a dry run first:

```powershell
.\scripts\windows\sync-to-morfsystem.ps1 -DestinationRoot ..\..\morfSystem -DryRun
```

When run from the sandbox workspace, the destination defaults to the sibling `morfSystem` directory. An explicit relative `-DestinationRoot morfSystem` is resolved from the parent of the sandbox workspace. Then run the same command without `-DryRun`. `-SkipToolProject` omits deployment of morfTools itself.
