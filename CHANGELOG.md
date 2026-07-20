# Changelog

## Unreleased

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
