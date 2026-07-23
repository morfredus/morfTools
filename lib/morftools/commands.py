"""What each morf command does to one project.

Every command here receives a project and returns True on success. The loop
that drives them lives in cli.py and knows nothing about what any of them mean.

The rule that shaped this file: a failure in one project must never stop the
others. The shell version wrapped its case block in `if ! ( ... )` precisely to
defeat `set -e`, because one project failing to build used to leave the
remaining twelve untouched with nothing saying so.
"""

from __future__ import annotations

import os
import platform
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

def is_headless() -> bool:
    """True on a Linux machine with no display server.

    A Raspberry Pi reached over SSH has neither DISPLAY nor WAYLAND_DISPLAY,
    which is exactly the case where a desktop GUI cannot run and need not be
    built. Windows and macOS always have a display in this sense, so they never
    skip.
    """
    if platform.system() != "Linux":
        return False
    return not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def skip_gui(project: Project, force_gui: bool) -> bool:
    """Whether to skip building this project, reporting why if so.

    A desktop GUI on a headless machine is effort spent on something that
    cannot run there. `--gui` forces it -- a headless build server that
    cross-distributes still wants the binaries.
    """
    if project.is_gui and is_headless() and not force_gui:
        print("[SKIP] desktop GUI, no display on this machine (use --gui to build anyway)")
        return True
    return False


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


def cmd_build(workspace: Workspace, project: Project, preset: str = "",
              force_gui: bool = False) -> bool:
    if skip_gui(project, force_gui):
        return True
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


def elevated(args: list) -> list:
    """The same command, with elevation when the platform needs it.

    Only the service deployment is elevated, never git. That separation is the
    whole point: run as root, git authenticates with root's missing SSH key and
    leaves root-owned files in every .git -- which is why `upgrade` itself
    refuses to run under sudo (see cli.py). So the pull happens as you, and only
    this last step asks for rights.

    Windows has no sudo: an administrator shell is how it grants rights there,
    and the service backend already refuses clearly when it lacks them.
    """
    if platform.system() == "Windows":
        return args
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return args                       # a genuine root login: nothing to add
    if shutil.which("sudo"):
        return ["sudo", *args]
    return args


def redeploy_service(project: Project) -> None:
    """Push the freshly built code into this project's service, if it runs here.

    Only services actually registered on THIS machine are touched: the parc is
    one set of repositories deployed differently on each machine, so a project
    present in the clone and absent from the service manager is the normal case,
    not a failure. It is skipped quietly.

    `is-installed` answers by exit status rather than by printing something to
    parse -- the decision belongs to the backend that knows the platform.
    """
    entry = project.path / "service.py"
    if not entry.is_file():
        return                            # not a service at all

    probe = subprocess.run(["python3", str(entry), "is-installed"],
                           cwd=project.path, capture_output=True, check=False)
    if probe.returncode == 2:
        # Not the same as "no": we were not allowed to ask. Staying quiet here
        # would report a successful upgrade while leaving the service on its
        # old binary -- the exact silence this parc keeps being bitten by.
        print("[WARN] cannot tell whether this service is installed "
              "(insufficient rights to ask)")
        print("       re-run from an elevated shell to update it")
        return
    if probe.returncode != 0:
        print("[SKIP] service not installed on this machine")
        return

    print("  updating the installed service...")
    run(elevated(["python3", str(entry), "update"]), cwd=project.path)


def cmd_upgrade(workspace: Workspace, project: Project, preset: str = "",
                force_gui: bool = False) -> bool:
    cmd_pull(workspace, project)
    # The sources are pulled regardless; only the build is skipped on a headless
    # machine, so an upgrade still refreshes a GUI app's code without compiling
    # what cannot run there.
    if project.is_cmake and not skip_gui(project, force_gui):
        cmake_build(project, preset)
    # ...and the machine actually runs the new code. Building alone left every
    # service serving its previous binary until someone remembered to visit each
    # project and run its own service.py -- the trap the guide had to warn about.
    # `upgrade` now means what its name promises.
    redeploy_service(project)
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
    # One rule, no exception: a project that is a service carries a service.py.
    # There used to be a fallback here for morfDashboard, whose deployment is an
    # rsync of a Python tree rather than a copied binary and which therefore
    # kept its shell scripts. That exception cost more than it saved -- `upgrade`
    # had no such fallback, so it pulled morfDashboard's new code and left the
    # service running the old one, silently. morfDashboard now exposes the same
    # interface as everything else, delegating to those very scripts.
    entry = project.path / "service.py"
    if not entry.is_file():
        print("[SKIP] not a service")
        return True

    args = [str(entry), "uninstall"]
    if purge:
        args.append("--purge")
        if backup:
            # One directory for the whole run; each service prefixes its own
            # files, so a single --backup collects the entire parc.
            args += ["--backup", backup]
    run(["python3", *args], cwd=project.path)
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
