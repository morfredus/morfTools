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
import sys
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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


def is_template(project: Project) -> bool:
    """A template service (the pattern new services are cloned from) carries a
    service.py like any other, yet must never be deployed in production. It says
    so declaratively in its manifest (`"template": true`), not by name, so the
    rule survives a rename."""
    manifest = project.path / "service.json"
    if not manifest.is_file():
        return False
    try:
        data = json.loads(manifest.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return False
    return bool(data.get("template"))


def cmd_install(workspace: Workspace, project: Project,
                deploy_service: bool = False, preset: str = "") -> bool:
    # `--services`: bring the actual service up, through the project's own
    # cross-platform service.py -- the same entry point `upgrade` and `uninstall`
    # use. One command then installs the whole parc, identically on Linux, a Pi
    # or Windows; only service.py's backend differs, and it hides that.
    if deploy_service:
        entry = project.path / "service.py"
        if not entry.is_file():
            print("[SKIP] not a service")
            return True
        if is_template(project):
            print("[SKIP] template service, never installed in production")
            return True
        # Build as the user first -- a build tree owned by root is the very trap
        # the git steps go to such lengths to avoid -- then elevate ONLY the
        # deployment, exactly as `upgrade` does. service.py finds the fresh
        # binary and installs it without rebuilding as root.
        if project.is_cmake and not skip_gui(project, False):
            cmake_build(project, preset)
        run(elevated(["python3", str(entry), "install"]), cwd=project.path)
        return True

    # Default (no --services): generic per-language setup only, no service.
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


def redeploy_service(project: Project, force: bool = False) -> None:
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
    # `--force` is passed through to service.py update: redeploy and restart even
    # when nothing changed. Useful to bounce a service on demand, since the
    # unchanged-binary case is otherwise a deliberate no-op.
    cmd = ["python3", str(entry), "update"] + (["--force"] if force else [])
    run(elevated(cmd), cwd=project.path)


def cmd_upgrade(workspace: Workspace, project: Project, preset: str = "",
                force_gui: bool = False, force: bool = False) -> bool:
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
    redeploy_service(project, force=force)
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

def installed_service_state(project: Project) -> int:
    """Return the service.py is-installed exit code without parsing prose."""
    result = subprocess.run(
        [sys.executable, str(project.path / "service.py"), "is-installed"],
        cwd=project.path, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode


def active_service_version(url: str) -> tuple[str, str]:
    """Read a running service's version from its declared status endpoint."""
    try:
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=3) as response:
            status = json.load(response)
    except (HTTPError, URLError, OSError, ValueError) as exc:
        return "", str(exc)

    if not isinstance(status, dict):
        return "", "response is not a JSON object"
    version = status.get("version")
    if not isinstance(version, str) or not version.strip():
        return "", "response has no version"
    return version.strip(), ""


def cmd_active_version(project: Project) -> bool:
    """Check the installed service, when any, against the project's VERSION."""
    service = project.path / "service.py"
    manifest_path = project.path / "service.json"
    if not service.is_file() or not manifest_path.is_file():
        return True

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
        status_url = manifest.get("status_url", "")
        expected = (project.path / "VERSION").read_text(encoding="utf-8-sig").strip()
    except (OSError, ValueError) as exc:
        print(f"[WARN] active version check unavailable: {exc}")
        return True

    if not status_url:
        print("[SKIP] active version check (no status_url declared)")
        return True
    if not expected:
        print("[FAIL] active version check (empty VERSION file)")
        return False

    active, error = active_service_version(status_url)
    if error:
        # Reaching the endpoint is enough to prove a service is active, even
        # when the system service manager is protected from this user.
        installed = installed_service_state(project)
        if installed == 1:
            print("[SKIP] active version check (service not installed on this machine)")
            return True
        if installed == 2:
            print(f"[WARN] active version check unavailable: {status_url} does not answer "
                  "and the service manager cannot be queried")
            return True
        if installed != 0:
            print(f"[WARN] active version check unavailable: {status_url} does not answer "
                  f"and service probe failed ({installed})")
            return True
        # Installed here, but the endpoint does not answer: the service is
        # stopped. That is not necessarily wrong -- it may be stopped on purpose
        # -- so it is a notice, not a failure, and does not fail doctor. The
        # phrase "installed but not running" is the stable token the update
        # remedy reads to offer 'update' (and only optionally 'upgrade').
        print(f"[WARN] service installed but not running ({status_url} does not "
              "answer); may be intentional")
        return True

    # A leading v is a presentation convention, not a different release.
    if active.removeprefix("v") == expected.removeprefix("v"):
        print(f"[OK] active version {active} matches project {expected}")
        return True

    print(f"[FAIL] active version {active} differs from project {expected}")
    print(f"       update with: python3 morf.py upgrade --only {project.name}")
    return False


def update_status(path: Path, branch: str, remedy: str, note: str = "") -> str:
    """Is the clone at `path` behind its remote? Returns tagged text for the report.

    `remedy` may span several lines (an inactive service is offered `update` and,
    only if wanted, `upgrade`); each becomes an indented continuation the report
    prints as-is. `note` qualifies the message -- "service installé mais inactif"
    -- so the reader sees why the remedy is what it is.

    The signal is "origin/<branch> has commits I do not", not "a GitHub Release
    was published": every repository has a remote, whereas releases are cut for
    only some of them, so this is the check that works across the whole parc and
    for morfTools itself. It needs nothing but git -- no gh, no token, nothing
    that might be absent on the Pi.

    A fetch that cannot reach the remote is not a defect: offline is a normal
    state for a laptop, so it degrades to a skip rather than an alarm. Credential
    prompts are disabled and the fetch is bounded, so doctor never hangs waiting
    on the network.
    """
    if not (path / ".git").is_dir():
        return ""

    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        fetched = subprocess.run(
            ["git", "fetch", "--quiet", "origin", branch],
            cwd=path, env=env, capture_output=True, text=True, timeout=20,
        )
    except (subprocess.TimeoutExpired, OSError):
        return f"[SKIP] update check (origin/{branch} unreachable)\n"
    if fetched.returncode != 0:
        return f"[SKIP] update check (origin/{branch} unreachable)\n"

    behind = capture(["git", "rev-list", "--count", f"HEAD..origin/{branch}"], cwd=path)
    if not behind.isdigit():
        return f"[SKIP] update check (cannot compare to origin/{branch})\n"
    count = int(behind)
    if count == 0:
        return f"[OK] up to date with origin/{branch}\n"

    plural = "s" if count > 1 else ""
    message = (f"nouvelle version disponible : {count} commit{plural} "
               f"en retard sur origin/{branch}")
    if note:
        message += f" — {note}"
    lines = [f"[UPDATE] {message}"]
    lines += [f"       {line}" for line in remedy.splitlines()]
    return "\n".join(lines) + "\n"


def cmd_doctor(workspace: Workspace, project: Project) -> bool:
    healthy = cmd_active_version(project)

    if not (project.path / ".git").exists():
        print("[FAIL] not a git repository")
        return False

    remote = capture(["git", "remote", "get-url", "origin"], cwd=project.path)
    if not remote:
        print("[WARN] no origin remote")
        return healthy

    # GitHub resolves repository names case-insensitively, so a spelling
    # difference alone (GatewayLab vs GateWayLab) is not a wrong origin.
    if project.local_name.lower() in remote.lower():
        print("[OK] remote name matches")
    else:
        print(f"[WARN] unexpected origin: {remote}")
    return healthy


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
PRESET_COMMANDS = {"build", "upgrade", "install"}
