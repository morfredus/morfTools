# morfSystem administration tools

*Read in another language: **English** (this document) · [Français](README.fr.md).*

`morfTools` is the administration project for morfSystem. The project can be moved or renamed: scripts derive the workspace root from their own location and never rely on an absolute path.

## Layout

- `ecosystem.json`: project manifest, clone URL template, port allocation registry, and vendored-copy registry.
- scripts at this project root: portable ecosystem administration commands.
- `scripts/ecosystem-check.py`: shared implementation of the ecosystem-wide checks run by `doctor`.
- sibling component directories: independent morfSystem projects.
- `docs/ECOSYSTEM-PRINCIPLES.md`: the founding principles and the architectural invariants that apply to the **whole parc**, including the boundaries no component may cross.
- `docs/`: workspace documentation.

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

Run PowerShell commands from any directory with `pwsh <workspace>/morfTools/morf.ps1 status`. On Linux or Raspberry Pi, use `bash <workspace>/morfTools/morf.sh status`.

### Script arguments

All commands operate only on projects declared in `ecosystem.json`.

| Script / command | Arguments | Action |
| --- | --- | --- |
| `clone` | none | Clone missing projects on the manifest branch. |
| `fetch` | none | Fetch remotes and prune deleted references. |
| `pull`, `update` | none | Fast-forward pull from the manifest branch. |
| `build` | CMake preset (asked when omitted) | Build PlatformIO projects, or configure and build CMake projects. |
| `install` | none | Install `requirements.txt` when present. |
| `upgrade` | CMake preset (asked when omitted) | Pull then rebuild CMake projects. |
| `doctor` | none | Check the port registry and the vendored copies, then verify Git repositories and their `origin`; run it before `push`. |
| `clean` | none | Remove every build directory (`build`, `build-arm64`, `build-mingw`, …). |
| `status` | none | Show the short Git status and branch. |
| `commit` | message (asked when omitted) | Stage all changes and commit when needed. |
| `push` | none | Push the manifest branch to `origin`. |
| `config shared` | `status`, `validate`, `edit`, `diff`, `install`, or `apply` | Manage the shared parc configuration read by morfMonitor and RaspberryDashboard. |
| `config deploy` | project name (lists them when omitted) | Deploy a project's own configuration by delegating to its script. |

For Linux and Raspberry Pi, use CMake's own vocabulary: `--preset <name>`
(or `-p <name>`) with `build` and `upgrade`:

```bash
./morfTools/build.sh --preset linux-arm64
./morfTools/upgrade.sh -p linux
```

The shortcut also accepts a single positional preset, for example `./morfTools/build.sh linux-arm64`. On PowerShell, use `-Preset <name>`:

```powershell
.\morfTools\build.ps1 -Preset mingw
pwsh .\morfTools\morf.ps1 upgrade -Preset linux-arm64
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
./morfTools/config.sh shared install     # the shared parc file
./morfTools/config.sh deploy morfMonitor # one project's own file
./morfTools/config.sh deploy             # list the projects that support it
```

```powershell
.\morfTools\config.ps1 shared Install
.\morfTools\config.ps1 deploy morfMonitor
```

**Shared** is `/etc/morfsystem/morfsystem.json` (`%ProgramData%\morfSystem\` on
Windows). It describes *what is supervised* and is read by morfMonitor **and**
RaspberryDashboard. No component owns it, so morfTools does — the same reasoning
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
morfMonitor and RaspberryDashboard both look there unless `MORFSYSTEM_CONFIG`
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

```text
[ecosystem]
--- addressing plan ---
[OK] morfSensor: 8788
--- vendored copies ---
[OK] morfSensor/third_party/morf/beacon matches morfBeacon
```

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
