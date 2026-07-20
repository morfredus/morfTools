# morfSystem administration tools

`morfTools` is the administration project for morfSystem. The project can be moved or renamed: scripts derive the workspace root from their own location and never rely on an absolute path.

## Layout

- `ecosystem.json`: project manifest and clone URL template.
- scripts at this project root: portable ecosystem administration commands.
- sibling component directories: independent morfSystem projects.
- `docs/`: workspace documentation.

## Commands

Run PowerShell commands from any directory with `pwsh <workspace>/morfTools/morf.ps1 status`. On Linux or Raspberry Pi, use `bash <workspace>/morfTools/morf.sh status`.

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
