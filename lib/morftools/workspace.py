"""The workspace: the manifest, the projects, and where they live on disk.

Split out from the commands because every command needs these answers and none
of them should re-derive them. The shell version asked python3 for each one, in
a separate process, once per project -- and each answer came back through a
pipe that Git Bash on Windows terminated with \\r, which is why every call site
carried a `tr -d '\\r'`. That workaround has no cause left here, so it is gone
rather than translated.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

MANIFEST_NAME = "ecosystem.json"

#: A project that links Qt Widgets or Gui builds a desktop window.
_GUI_LINK = re.compile(r"Qt6::(Widgets|Gui)|find_package\s*\(\s*Qt6[^)]*(Widgets|Gui)", re.I)


class WorkspaceError(RuntimeError):
    """The workspace cannot be described: no manifest, or an unusable one."""


@dataclass(frozen=True)
class Project:
    """A project as the manifest names it, and as the disk holds it."""

    name: str          # canonical name, e.g. morfMonitor
    path: Path         # actual directory, possibly morfMonitor_travail

    @property
    def local_name(self) -> str:
        return self.path.name

    @property
    def exists(self) -> bool:
        return self.path.is_dir()

    @property
    def is_cmake(self) -> bool:
        return (self.path / "CMakeLists.txt").is_file()

    @property
    def is_platformio(self) -> bool:
        return (self.path / "platformio.ini").is_file()

    @property
    def is_gui(self) -> bool:
        """True when the project builds a desktop GUI (links Qt Widgets or Gui).

        Read from the project's own build definition, not a maintained list: a
        project that links Qt Widgets is declaring it needs a display. Adding a
        GUI app needs nothing kept in sync -- it is recognised by what it links.
        """
        cmake = self.path / "CMakeLists.txt"
        try:
            text = cmake.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        return _GUI_LINK.search(text) is not None

    def presets(self) -> list:
        """Configure presets this project declares, hidden ones excluded.

        A preset absent from a project is a normal absence: linux-arm64-cross is
        declared by three repositories out of fourteen, and building the others
        must not be reported as a failure.
        """
        path = self.path / "CMakePresets.json"
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            return []
        return [
            entry["name"]
            for entry in data.get("configurePresets", [])
            if entry.get("name") and not entry.get("hidden")
        ]


class Workspace:
    """The directory holding every project, plus the manifest describing them."""

    def __init__(self, tool_dir: Path):
        self.tool_dir = tool_dir.resolve()
        self.root = self.tool_dir.parent
        self.manifest_path = self.tool_dir / MANIFEST_NAME

        if not self.manifest_path.is_file():
            raise WorkspaceError(f"No {MANIFEST_NAME} beside {self.tool_dir}.")
        try:
            self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8-sig"))
        except ValueError as exc:
            raise WorkspaceError(f"{self.manifest_path} is not valid JSON: {exc}") from exc

        # The sandbox suffixes every directory with '_travail'; production does
        # not. The tool's own directory says which one we are in, so a single
        # checkout never has to be told.
        self.sandbox = self.tool_dir.name.endswith("_travail")

    # -- Manifest ---------------------------------------------------------

    @property
    def branch(self) -> str:
        return self.manifest.get("branch", "main")

    def clone_url(self, local_name: str, protocol: str = "ssh") -> str:
        """The clone URL for a repository, over SSH or HTTPS.

        SSH is the manifest's `cloneUrlTemplate` (the developer default). HTTPS is
        an equally valid access mode for a fresh machine that has no SSH identity:
        it is derived from the SSH template (git@host:owner/... -> https://host/
        owner/...), or read from an explicit `httpsUrlTemplate` when the manifest
        provides one.
        """
        if protocol == "https":
            template = self.manifest.get("httpsUrlTemplate") or self._derive_https_template()
        else:
            template = self.manifest.get("cloneUrlTemplate", "")
        return template.replace("{name}", local_name)

    def _derive_https_template(self) -> str:
        """Turn the SSH template into an HTTPS one, or "" if it cannot be parsed.

        Handles the common forms `git@host:owner/{name}.git` and
        `ssh://git@host/owner/{name}.git`. Anything else returns empty, and the
        caller reports HTTPS as unavailable rather than building a wrong URL.
        """
        ssh = self.manifest.get("cloneUrlTemplate", "")
        if ssh.startswith("git@") and ":" in ssh:
            host, path = ssh[len("git@"):].split(":", 1)
            return f"https://{host}/{path}"
        if ssh.startswith("ssh://"):
            rest = ssh[len("ssh://"):]
            if rest.startswith("git@"):
                rest = rest[len("git@"):]
            host, _, path = rest.partition("/")
            return f"https://{host}/{path}"
        return ""

    def local_name(self, canonical: str) -> str:
        return f"{canonical}_travail" if self.sandbox else canonical

    # -- Projects ---------------------------------------------------------

    def projects(self) -> list:
        """Every declared project, cloned or not.

        Absence is reported by the caller rather than filtered here: "not
        cloned" is information, and silently skipping it is how a project drops
        out of the parc without anyone noticing.
        """
        out = []
        for canonical in self.manifest.get("projects", []):
            local = self.local_name(canonical)
            path = self.root / local
            # Accept the other naming too: a workspace may be partially cloned,
            # or a production checkout may sit next to a sandbox one.
            if not path.is_dir():
                alternative = self.root / canonical
                if alternative.is_dir():
                    path = alternative
            out.append(Project(name=canonical, path=path))
        return out

    def all_presets(self) -> list:
        """Presets declared anywhere, with how many projects declare each.

        Used to offer a real choice instead of guessing one.
        """
        counts: dict = {}
        total = 0
        for project in self.projects():
            if not (project.path / "CMakePresets.json").is_file():
                continue
            total += 1
            for name in project.presets():
                counts[name] = counts.get(name, 0) + 1
        return [(name, counts[name], total) for name in sorted(counts)]
