"""The project contract morfTools reads: `morfproject.json` at a repo's root.

morfTools knows only this SCHEMA, never a hard-coded list of projects. It
discovers the clones and aggregates what each one declares. The declaration
lives WITH the project, separate from `service.json` because a UI or an ESP32
firmware is not a service, and not every project has a service manifest.

Four states, distinguished on purpose:

  - no file at all         -> unknown / not yet onboarded;
  - packaging.provider none -> recognised, deliberately not packaged;
  - packaging.provider morfdeploy -> standard packaging by morfdeploy;
  - packaging.provider project    -> build/packaging by the project's own scripts.

`packaging.provider` is the project's DEFAULT provider; the project's
classification is carried by `project.type`. A single target may override the
default with its own `package.provider`, so a mixed project (Windows by its own
script, Linux by morfdeploy) needs no duplication.

Shape (schema_version 1):

    {
      "schema_version": 1,
      "project": { "id": "morfCollector", "type": "service" },
      "packaging": {
        "provider": "morfdeploy",
        "targets": {
          "linux-amd64-deb": {
            "platform": { "os": "linux", "arch": "x86_64" },
            "build":   { "preset": "linux" },            # or { "script": ... } / { "tool": "platformio", "env": ... }
            "package": { "format": "deb", "architecture": "amd64" }
          },
          ...
        }
      }
    }

One target per DELIVERABLE (a .deb and an AppImage for the same platform are two
targets). Targets that share a build recipe (same preset) must not be compiled
twice in one run -- the packaging steps stay separate, the compilation is shared.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_FILE = "morfproject.json"

TYPES = ("service", "application", "firmware",
         "library", "tool", "documentation", "meta", "template")
PROVIDERS = ("none", "morfdeploy", "project")


class MorfProjectError(ValueError):
    """A `morfproject.json` that is present but does not fit the schema."""


@dataclass
class Target:
    name: str
    platform: dict           # {"os": ..., "arch": ...}
    build: dict              # {"preset": ...} | {"script": ...} | {"tool": ..., "env": ...}
    package: dict            # {"format": ..., "provider"?: ..., "script"?: ..., "architecture"?: ...}
    default_provider: str

    @property
    def provider(self) -> str:
        """This deliverable's provider: its own override, or the project default."""
        return self.package.get("provider") or self.default_provider

    @property
    def build_preset(self) -> str | None:
        return self.build.get("preset")

    @property
    def os(self) -> str | None:
        return self.platform.get("os")

    @property
    def arch(self) -> str | None:
        return self.platform.get("arch")


@dataclass
class MorfProject:
    id: str
    type: str
    provider: str                     # default provider
    targets: dict = field(default_factory=dict)   # name -> Target
    path: Path | None = None
    schema_version: int = 1

    @property
    def is_morfdeploy_service(self) -> bool:
        """A standard service morfdeploy builds and stamps with provenance."""
        return self.type == "service" and self.provider == "morfdeploy"

    def target_names(self) -> list:
        return list(self.targets.keys())


def _norm_arch(arch: str | None) -> str | None:
    """Internal architecture names: x86_64 and arm64, whatever the input spelling."""
    if arch is None:
        return None
    a = arch.lower()
    if a in ("x86_64", "amd64"):
        return "x86_64"
    if a in ("arm64", "aarch64"):
        return "arm64"
    return a


def load(project_path: Path) -> MorfProject | None:
    """Read `morfproject.json` from a project root, or None when it has none.

    A missing file is not an error: the contract is rolled out project by project.
    A malformed file IS an error -- a declaration that cannot be trusted is worse
    than none, because it would be acted upon.
    """
    file = project_path / PROJECT_FILE
    if not file.is_file():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise MorfProjectError(f"{file}: cannot read ({exc})")

    project = data.get("project") or {}
    ptype = project.get("type")
    if ptype not in TYPES:
        raise MorfProjectError(
            f"{file}: project.type must be one of {', '.join(TYPES)} (got {ptype!r})")

    pack = data.get("packaging") or {}
    provider = pack.get("provider")
    if provider not in PROVIDERS:
        raise MorfProjectError(
            f"{file}: packaging.provider must be one of {', '.join(PROVIDERS)} "
            f"(got {provider!r})")

    raw_targets = pack.get("targets") or {}
    if not isinstance(raw_targets, dict):
        raise MorfProjectError(f"{file}: packaging.targets must be an object "
                               "(one entry per deliverable)")

    targets = {}
    for name, spec in raw_targets.items():
        spec = spec or {}
        platform = dict(spec.get("platform") or {})
        if "arch" in platform:
            platform["arch"] = _norm_arch(platform["arch"])
        tpkg = spec.get("package") or {}
        tprov = tpkg.get("provider")
        if tprov is not None and tprov not in PROVIDERS:
            raise MorfProjectError(
                f"{file}: target '{name}' package.provider must be one of "
                f"{', '.join(PROVIDERS)} (got {tprov!r})")
        targets[name] = Target(
            name=name,
            platform=platform,
            build=dict(spec.get("build") or {}),
            package=dict(tpkg),
            default_provider=provider,
        )

    return MorfProject(
        id=project.get("id") or project_path.name,
        type=ptype,
        provider=provider,
        targets=targets,
        path=project_path,
        schema_version=int(data.get("schema_version") or 1),
    )
