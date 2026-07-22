"""What each morf command does to one project.

Every command here receives a project and returns True on success. The loop
that drives them lives in cli.py and knows nothing about what any of them mean.

The rule that shaped this file: a failure in one project must never stop the
others. The shell version wrapped its case block in `if ! ( ... )` precisely to
defeat `set -e`, because one project failing to build used to leave the
remaining twelve untouched with nothing saying so.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .workspace import Project, Workspace


def run(args: list, cwd: Path | None = None, check: bool = True) -> int:
    """Run a command, letting its output through to the terminal."""
    result = subprocess.run(args, cwd=cwd, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:2])} failed ({result.returncode})")
    return result.returncode


def capture(args: list, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


# -- Git ------------------------------------------------------------------

def cmd_clone(workspace: Workspace, project: Project) -> bool:
    if project.exists:
        print(f"[SKIP] {project.local_name} (already present)")
        return True
    url = workspace.clone_url(project.local_name)
    run(["git", "clone", "--branch", workspace.branch, url, str(project.path)])
    return True


def cmd_fetch(workspace: Workspace, project: Project) -> bool:
    run(["git", "fetch", "--prune"], cwd=project.path)
    return True


def cmd_pull(workspace: Workspace, project: Project) -> bool:
    run(["git", "pull", "--ff-only", "origin", workspace.branch], cwd=project.path)
    return True


def cmd_status(workspace: Workspace, project: Project) -> bool:
    run(["git", "status", "--short", "--branch"], cwd=project.path)
    return True


def cmd_push(workspace: Workspace, project: Project) -> bool:
    run(["git", "push", "origin", workspace.branch], cwd=project.path)
    return True


def cmd_commit(workspace: Workspace, project: Project, message: str = "") -> bool:
    if not message:
        raise RuntimeError("A commit message is required.")
    run(["git", "add", "-A"], cwd=project.path)
    if not capture(["git", "status", "--porcelain"], cwd=project.path):
        return True
    run(["git", "commit", "-m", message], cwd=project.path)
    return True


# -- Build ----------------------------------------------------------------

def cmake_build(project: Project, preset: str = "") -> None:
    """Build, skipping a preset this project does not declare.

    A preset missing here is a normal absence rather than a failure: it means
    the project does not target that configuration, not that the build broke.
    """
    if not preset:
        run(["cmake", "-S", ".", "-B", "build"], cwd=project.path)
        run(["cmake", "--build", "build"], cwd=project.path)
        return
    if preset not in project.presets():
        print(f"[SKIP] preset '{preset}' not defined in this project")
        return
    run(["cmake", "--preset", preset], cwd=project.path)
    run(["cmake", "--build", "--preset", preset], cwd=project.path)


def cmd_build(workspace: Workspace, project: Project, preset: str = "") -> bool:
    if project.is_platformio:
        if preset:
            print(f"[INFO] preset ignored for PlatformIO: {preset}")
        run(["pio", "run"], cwd=project.path)
    elif project.is_cmake:
        cmake_build(project, preset)
    else:
        print("[SKIP] no known build definition")
    return True


def cmd_install(workspace: Workspace, project: Project) -> bool:
    if (project.path / "requirements.txt").is_file():
        run(["python3", "-m", "pip", "install", "-r", "requirements.txt"], cwd=project.path)
    else:
        print("[SKIP] no generic install definition")
    return True


def cmd_upgrade(workspace: Workspace, project: Project, preset: str = "") -> bool:
    cmd_pull(workspace, project)
    if project.is_cmake:
        cmake_build(project, preset)
    return True


def cmd_uninstall(workspace: Workspace, project: Project,
                  purge: bool = False, backup: str = "") -> bool:
    """Uninstall a project's service, if it is one.

    Delegates to the project's own entry point rather than reimplementing the
    teardown here: the morfdeploy services know their config locations from
    their manifest, and a project that keeps an old script knows its own paths.
    A project that is not a service is skipped, not failed -- `uninstall` sweeps
    the whole parc and most of it has nothing to remove.
    """
    entry = project.path / "service.py"
    if entry.is_file():
        args = [str(entry), "uninstall"]
        if purge:
            args.append("--purge")
            if backup:
                # One directory for the whole run; each service prefixes its
                # own files, so a single --backup collects the entire parc.
                args += ["--backup", backup]
        run(["python3", *args], cwd=project.path)
        return True

    # Not yet converted to morfdeploy (RaspberryDashboard): its install script
    # carries an --uninstall. --purge is not honoured there; say so rather than
    # pretend it was.
    legacy = project.path / "scripts" / "linux" / "install-service.sh"
    if legacy.is_file():
        if purge:
            print("[note] --purge not supported by this project's script; "
                  "the service is removed, its configuration is left in place")
        run(["bash", str(legacy), "--uninstall"], cwd=project.path)
        return True

    print("[SKIP] not a service")
    return True


def cmd_clean(workspace: Workspace, project: Project) -> bool:
    for directory in sorted(project.path.glob("build*")):
        if directory.is_dir():
            print(f"[RM] {directory.name}")
            shutil.rmtree(directory, ignore_errors=True)
    return True


# -- Doctor ---------------------------------------------------------------

def cmd_doctor(workspace: Workspace, project: Project) -> bool:
    if not (project.path / ".git").exists():
        print("[FAIL] not a git repository")
        return False

    remote = capture(["git", "remote", "get-url", "origin"], cwd=project.path)
    if not remote:
        print("[WARN] no origin remote")
        return True

    # GitHub resolves repository names case-insensitively, so a spelling
    # difference alone (GatewayLab vs GateWayLab) is not a wrong origin.
    if project.local_name.lower() in remote.lower():
        print("[OK] remote name matches")
    else:
        print(f"[WARN] unexpected origin: {remote}")
    return True


#: Dispatch table. Commands taking extra arguments receive them by keyword from
#: the driver, which is why the signatures differ.
COMMANDS = {
    "clone": cmd_clone,
    "fetch": cmd_fetch,
    "pull": cmd_pull,
    "update": cmd_pull,      # an alias, and documented as one
    "status": cmd_status,
    "push": cmd_push,
    "commit": cmd_commit,
    "build": cmd_build,
    "install": cmd_install,
    "uninstall": cmd_uninstall,
    "upgrade": cmd_upgrade,
    "clean": cmd_clean,
    "doctor": cmd_doctor,
}

#: Commands that accept --preset. Passing it elsewhere is refused rather than
#: ignored: silently dropping an option the person typed is how they end up
#: believing a build used a configuration it never saw.
PRESET_COMMANDS = {"build", "upgrade"}
