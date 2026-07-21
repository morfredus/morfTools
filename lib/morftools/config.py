"""The parc configuration: the shared file, and each project's own.

Two things live here because the shell kept them in two scripts that only ever
called each other -- config.sh dispatched, shared-config.sh worked.

  shared    /etc/morfsystem/morfsystem.json, read by morfMonitor (which
            collects) AND RaspberryDashboard (which displays). It describes
            WHAT IS SUPERVISED, and it is the one file to edit to add a
            service, a probe or an application.

  deploy    a project's own configuration, delegated to that project's script,
            because only the project knows where its own file goes.

Platform-specific knowledge is confined to three answers -- where the shared
file lives, which editor to open, how to restart a service -- and nothing else
in this module asks.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .workspace import Workspace

#: Services that read the shared configuration, and therefore need restarting
#: when it changes. Both are optional: a machine may run either, or neither.
SHARED_CONSUMERS = ("morfmonitor", "morfdashboard")


# -- The three platform answers -------------------------------------------

def shared_config_path() -> Path:
    if platform.system() == "Windows":
        base = os.environ.get("ProgramData", r"C:\ProgramData")
        return Path(base) / "morfsystem" / "morfsystem.json"
    return Path("/etc/morfsystem/morfsystem.json")


def default_editor() -> str:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        return editor
    return "notepad" if platform.system() == "Windows" else "nano"


def restart_service(name: str) -> str:
    """Restart a service if it exists. Returns a line describing what happened.

    Absence is not a failure: a Pi runs the dashboard, a workstation does not,
    and neither is wrong.
    """
    if platform.system() == "Windows":
        probe = subprocess.run(["sc.exe", "query", name],
                               capture_output=True, check=False)
        if probe.returncode != 0:
            return f"  {name}: not installed here"
        subprocess.run(["sc.exe", "stop", name], capture_output=True, check=False)
        subprocess.run(["sc.exe", "start", name], capture_output=True, check=False)
        return f"  {name}: restarted"

    probe = subprocess.run(["systemctl", "list-unit-files", f"{name}.service"],
                           capture_output=True, text=True, check=False)
    if name not in probe.stdout:
        return f"  {name}: not installed here"
    result = subprocess.run(["systemctl", "restart", name],
                            capture_output=True, check=False)
    return f"  {name}: {'restarted' if result.returncode == 0 else 'restart FAILED'}"


# -- Source selection ------------------------------------------------------

def source_config(workspace: Workspace) -> Path | None:
    """The editable source: the real file when the clone has one, else the example.

    The example used to be hard-coded here, which closed a trap the hard way:
    `install` deployed the sample OVER a real morfsystem.json kept beside it,
    replacing the parc description with a specimen.
    """
    monitor = workspace.root / workspace.local_name("morfMonitor")
    if not monitor.is_dir():
        monitor = workspace.root / "morfMonitor"
    for candidate in ("morfsystem.json", "morfsystem.example.json"):
        path = monitor / "config" / candidate
        if path.is_file():
            return path
    return None


def validate(path: Path) -> bool:
    try:
        json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        print(f"[FAIL] {path}: {exc}", file=sys.stderr)
        return False
    print(f"[OK] valid JSON: {path}")
    return True


# -- shared ----------------------------------------------------------------

def shared(workspace: Workspace, action: str) -> int:
    source = source_config(workspace)
    target = shared_config_path()

    if source is None:
        print("No morfsystem.json or morfsystem.example.json found in morfMonitor.",
              file=sys.stderr)
        print("Clone morfMonitor beside morfTools first.", file=sys.stderr)
        return 2

    if action == "status":
        # Wording kept from shared-config.sh. The path differs by platform --
        # the shell version printed /etc/morfsystem even on Windows, where it
        # does not exist -- but the shape of the report should not, or someone
        # comparing the two starts doubting both.
        print(f"Editable source: {source}")
        print(f"Installed file:  {target}")
        print("[OK] source present")
        if target.is_file():
            stamp = datetime.fromtimestamp(target.stat().st_mtime)
            print(f"[OK] installed file present (installed {stamp:%Y-%m-%d %H:%M})")
        else:
            print("[WARN] installed file missing")
        return 0

    if action == "validate":
        return 0 if validate(source) else 1

    if action == "edit":
        subprocess.run([*default_editor().split(), str(source)], check=False)
        return 0 if validate(source) else 1

    if action == "diff":
        if not target.is_file():
            print(f"{target} does not exist yet: nothing to compare.")
            return 0
        left = source.read_text(encoding="utf-8-sig").splitlines()
        right = target.read_text(encoding="utf-8-sig").splitlines()
        import difflib
        lines = list(difflib.unified_diff(
            right, left, fromfile=str(target), tofile=str(source), lineterm=""))
        if not lines:
            print("Identical.")
            return 0
        print("\n".join(lines))
        return 0

    if action in ("install", "apply"):
        if not validate(source):
            print("Refusing to install invalid JSON.", file=sys.stderr)
            return 1

        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file():
            backup = target.with_name(
                f"{target.name}.bak-{datetime.now():%Y%m%d-%H%M%S}")
            shutil.copy2(target, backup)
            print(f"backup: {backup}")
        shutil.copy2(source, target)
        print(f"installed: {target}")

        if action == "apply":
            print("Restarting the services that read it:")
            for name in SHARED_CONSUMERS:
                print(restart_service(name))
        return 0

    print(f"Unknown shared action: {action}", file=sys.stderr)
    return 2


# -- deploy ----------------------------------------------------------------

def deploy_entry_point(workspace, project) -> Path | None:
    """A project's own configuration deployment, whatever form it takes.

    service.py is preferred where a project has been converted; the shell
    script is still honoured for those that have not. Both are listed rather
    than one being assumed, because the parc is mid-migration and a tool that
    only knows the new shape would report perfectly working projects as
    missing.
    """
    for candidate in (
        project.path / "service.py",
        project.path / "scripts" / "linux" / "deploy-config.sh",
    ):
        if candidate.is_file():
            return candidate
    return None


def deploy(workspace: Workspace, target: str, extra: list) -> int:
    if not target:
        print("Projects providing a configuration deployment:")
        found = False
        for project in workspace.projects():
            if project.exists and deploy_entry_point(workspace, project):
                print(f"    {project.name}")
                found = True
        if not found:
            print("    (none — clone a project first)")
        print()
        # A project name is required rather than defaulting to "all": this
        # overwrites deployed configurations, and doing that everywhere because
        # an argument was forgotten is not a reasonable default.
        print("Name one:  morf-config deploy <project>")
        return 0

    wanted = target.lower()
    for project in workspace.projects():
        if project.name.lower() != wanted:
            continue
        if not project.exists:
            print(f"{project.name} is not cloned.", file=sys.stderr)
            return 1
        script = deploy_entry_point(workspace, project)
        if script is None:
            print(f"No deployment entry point for '{target}'.", file=sys.stderr)
            print(f"Expected {project.local_name}/service.py or "
                  f"scripts/linux/deploy-config.sh", file=sys.stderr)
            return 1
        print(f"[{project.name}] {script}")
        if script.suffix == ".py":
            return subprocess.run([sys.executable, str(script), *extra],
                                  check=False).returncode
        return subprocess.run(["bash", str(script), *extra], check=False).returncode

    print(f"No project named '{target}' in the manifest.", file=sys.stderr)
    return 2
