# Changelog

## Unreleased

- Corrected synchronization destination resolution: relative paths now resolve next to the sandbox workspace.
- Updated user-facing documentation to use canonical production project names.
- Added a manifest-driven Windows synchronization script that preserves destination Git repositories and never rewrites text globally.
- Made `ecosystem.json` canonical: it contains production component names.
- Renamed the standalone tools project to morfTools.
- Made PowerShell and Bash tools resolve component names consistently in production.
- Replaced the legacy project configuration with root-aware command launchers.
- Documented the portable workspace architecture and remote safety rules.
- Registered GateWayLab and created its GitHub repository.
