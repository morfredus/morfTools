"""What a project must declare to be installable.

Every install-service.sh in the parc carried the same four steps and differed
only by a service name and a directory. Those two values, plus the handful of
paths around them, are what this manifest holds -- so the algorithm can live in
one place and the project keeps stating its own facts.

The manifest is JSON for the same reason the shared parc configuration is:
neither C++ nor Python is privileged, and a project written in either declares
itself the same way.
"""

from __future__ import annotations

import json
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path

MANIFEST_NAME = "service.json"

#: Single environment override for the install directory, across the whole
#: parc. The per-project prefixes it replaces (MT_, MN_, MS_) had already
#: drifted -- morfAnalytics carried morfMonitor's MT_APP_DIR verbatim, and
#: morfSync had none at all, so its documented override silently did nothing.
APP_DIR_ENV = "MORF_APP_DIR"


class ManifestError(RuntimeError):
    """The manifest is missing, malformed, or incomplete."""


@dataclass(frozen=True)
class ConfigFile:
    """A configuration to place at install time.

    `overwrite` is false by default, and that default matters: these files hold
    settings edited by hand on the machine. An install that overwrites them
    destroys local state to deliver a default nobody asked for.
    """

    source: str
    dest: str
    overwrite: bool = False

    def resolved_dest(self, app_dir: Path) -> Path:
        """Absolute destinations are honoured as-is.

        The shared parc configuration lives in /etc/morfsystem and is read by
        two different programs, so it cannot be relative to any one
        application's directory.
        """
        dest = Path(os.path.expandvars(self.dest))
        return dest if dest.is_absolute() else app_dir / dest


@dataclass(frozen=True)
class Manifest:
    """A project's deployment facts."""

    repo_root: Path
    service_name: str
    display_name: str
    binary: str
    app_dirs: dict = field(default_factory=dict)
    configs: tuple = ()
    description: str = ""
    status_url: str = ""

    # -- Derived paths ----------------------------------------------------

    def app_dir(self) -> Path:
        """Where the binary and configurations are installed.

        The environment override wins over the manifest, which wins over a
        conventional default. Resolution order is fixed here rather than in
        each backend so that the answer cannot depend on the platform for any
        reason other than the path itself.
        """
        override = os.environ.get(APP_DIR_ENV)
        if override:
            return Path(override)

        key = {"Windows": "windows", "Darwin": "darwin"}.get(platform.system(), "linux")
        declared = self.app_dirs.get(key)
        if declared:
            return Path(os.path.expandvars(declared))

        if key == "windows":
            base = os.environ.get("ProgramData", r"C:\ProgramData")
            return Path(base) / self.service_name
        return Path("/opt") / self.service_name

    def binary_name(self) -> str:
        """The executable's file name, with the platform's extension."""
        if platform.system() == "Windows" and not self.binary.endswith(".exe"):
            return self.binary + ".exe"
        return self.binary

    def installed_binary(self) -> Path:
        return self.app_dir() / self.binary_name()

    # -- Loading ----------------------------------------------------------

    @classmethod
    def load(cls, repo_root: Path) -> "Manifest":
        path = repo_root / MANIFEST_NAME
        if not path.is_file():
            raise ManifestError(
                f"No {MANIFEST_NAME} in {repo_root}.\n"
                f"A project states its own deployment facts there; see "
                f"morfTemplateService/{MANIFEST_NAME} for the reference."
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            raise ManifestError(f"{path} is not valid JSON: {exc}") from exc

        missing = [k for k in ("service_name", "binary") if not raw.get(k)]
        if missing:
            raise ManifestError(f"{path} declares no {' and no '.join(missing)}.")

        configs = tuple(
            ConfigFile(
                source=entry["source"],
                dest=entry["dest"],
                overwrite=bool(entry.get("overwrite", False)),
            )
            for entry in raw.get("configs", [])
            if entry.get("source") and entry.get("dest")
        )

        return cls(
            repo_root=repo_root,
            service_name=raw["service_name"],
            display_name=raw.get("display_name") or raw["service_name"],
            binary=raw["binary"],
            app_dirs=raw.get("app_dir") or {},
            configs=configs,
            description=raw.get("description", ""),
            status_url=raw.get("status_url", ""),
        )
