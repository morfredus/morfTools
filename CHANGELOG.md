# Changelog

## Unreleased

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
