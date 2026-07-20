# morfSystem administration tools

`morfTools` is the administration project for morfSystem. The project can be moved or renamed: scripts derive the workspace root from their own location and never rely on an absolute path.

## Layout

- `ecosystem.json`: project manifest and clone URL template.
- scripts at this project root: portable ecosystem administration commands.
- sibling component directories: independent morfSystem projects.
- `docs/`: workspace documentation.

## Commands

Run PowerShell commands from any directory with `pwsh <workspace>/morfTools/morf.ps1 status`. On Linux or Raspberry Pi, use `bash <workspace>/morfTools/morf.sh status`.

### Script arguments

All commands operate only on projects declared in `ecosystem.json`.

| Script / command | Arguments | Action |
| --- | --- | --- |
| `clone` | none | Clone missing projects on the manifest branch. |
| `fetch` | none | Fetch remotes and prune deleted references. |
| `pull`, `update` | none | Fast-forward pull from the manifest branch. |
| `build` | optional CMake profile | Build PlatformIO projects, or configure and build CMake projects. |
| `install` | none | Install `requirements.txt` when present. |
| `upgrade` | optional CMake profile | Pull then rebuild CMake projects. |
| `doctor` | none | Verify Git repositories and their `origin`; run it before `push`. |
| `clean` | none | Remove the default `build/` directory only. |
| `status` | none | Show the short Git status and branch. |
| `commit` | message required | Stage all changes and commit when needed. |
| `push` | none | Push the manifest branch to `origin`. |
| `shared-config` (Linux) | `status`, `validate`, `edit`, `diff`, `install`, or `apply` | Manage the shared configuration read by morfMonitor and RaspberryDashboard. |
| `shared-config.ps1` (Windows) | `-Action Status|Validate|Edit|Diff|Install` | Manage the local shared configuration used by Windows morfSystem applications. |

For Linux and Raspberry Pi, use `--profile <name>` (or `-p <name>`) with `build` and `upgrade`:

```bash
./morfTools/build.sh --profile linux-arm64
./morfTools/upgrade.sh -p linux
```

The shortcut also accepts a single positional profile, for example `./morfTools/build.sh linux-arm64`. On PowerShell, use `-Profile <name>`:

```powershell
.\morfTools\build.ps1 -Profile mingw
pwsh .\morfTools\morf.ps1 upgrade -Profile linux-arm64
```

The profile selects the project's CMake configure and build preset. Typical profiles are `mingw` (Windows/MSYS2), `linux` (native x86_64 Linux or WSL2), `linux-arm64` (native 64-bit Raspberry Pi / ARM64), and, where defined, `linux-arm64-cross` (cross-compilation). A profile must be listed in the target project's `CMakePresets.json`. It is ignored for PlatformIO projects.

### Shared Linux configuration

`morfMonitor` and `RaspberryDashboard` both read
`/etc/morfsystem/morfsystem.json`. The editable, versioned source is
`morfMonitor/config/morfsystem.example.json`; it is deliberately kept in the
repository so changes can be reviewed and committed.

```bash
./morfTools/shared-config.sh status
./morfTools/shared-config.sh edit
./morfTools/shared-config.sh diff
./morfTools/shared-config.sh install
./morfTools/shared-config.sh apply
```

`edit` opens `$EDITOR` (or `nano`) and validates the JSON. `install`
creates a dated backup before copying to `/etc`; `apply` additionally
restarts both services. These two commands request sudo only for system writes.

On Windows, the equivalent installed location is
`%ProgramData%\morfSystem\morfsystem.json`. Both morfMonitor and
RaspberryDashboard now look there by default (unless `MORFSYSTEM_CONFIG` is
set). The PowerShell tool stays entirely local:

```powershell
.\morfTools\shared-config.ps1 -Action Edit
.\morfTools\shared-config.ps1 -Action Diff
.\morfTools\shared-config.ps1 -Action Install
```

`Install` validates first, creates a dated backup when needed, then copies
the file locally. Use `-ConfigPath` to choose a different installation path.

`ecosystem.json` always contains canonical production names. Production tools use these names without modification.

Supported commands are `clone`, `fetch`, `pull`, `build`, `install`, `update`, `upgrade`, `doctor`, `clean`, `status`, `commit`, and `push`. `commit` requires `-Message` in PowerShell or a second argument in Bash. Commands only operate on projects declared by `ecosystem.json`.

`doctor` verifies that each present project is a Git repository and reports its `origin`; it is the safety check to run before `push`.

`GateWayLab` is declared in the manifest and is managed like every other component.

## Deployment synchronization

`scripts/windows/sync-to-morfsystem.ps1` is a Windows-specific deployment helper. It reads `ecosystem.json` and copies component content to a production root without copying or deleting destination `.git` directories. It never performs a global text replacement.

Use a dry run first:

```powershell
.\scripts\windows\sync-to-morfsystem.ps1 -DestinationRoot ..\..\morfSystem -DryRun
```

When run from the sandbox workspace, the destination defaults to the sibling `morfSystem` directory. An explicit relative `-DestinationRoot morfSystem` is resolved from the parent of the sandbox workspace. Then run the same command without `-DryRun`. `-SkipToolProject` omits deployment of morfTools itself.
