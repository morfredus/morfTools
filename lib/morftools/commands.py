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
import re
import shutil
import subprocess
import sys
import json
from functools import lru_cache
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import morfproject
from .gitretry import run_git
from .workspace import Project, Workspace


def run(args: list, cwd: Path | None = None, check: bool = True) -> int:
    """Run a command, letting its output through to the terminal."""
    result = subprocess.run(args, cwd=cwd, check=False)
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:2])} failed ({result.returncode})")
    return result.returncode


# Signatures d'un ECHEC D'AUTHENTIFICATION (pas de transport : l'accès lui-même
# est refusé). Sert uniquement à afficher une aide ciblée -- jamais à convertir un
# remote ni à décider qu'un protocole est « faux » : HTTPS et SSH sont tous deux
# légitimes, seul l'accès manque dans cet environnement.
_AUTH_SSH = re.compile(r"permission denied \(publickey\)|"
                       r"host key verification failed", re.IGNORECASE)
_AUTH_HTTPS = re.compile(r"authentication failed|could not read username|"
                         r"could not read password|username for 'https|"
                         r"password for 'https|terminal prompts disabled|"
                         r"invalid username or (password|token)|"
                         r"remote: (support for password authentication|invalid credentials)",
                         re.IGNORECASE)


def _auth_hint(blob: str) -> None:
    """Aide protocole-consciente après un échec d'ACCES au remote.

    Distingue clairement « accès refusé » de « protocole invalide » : le message
    ne présente jamais HTTPS comme une erreur ni ne propose de convertir un dépôt
    automatiquement. Il rappelle seulement quoi préparer (identifiants HTTPS ou
    clé SSH), et signale que l'uniformisation, si elle est voulue, est une
    décision explicite via `morf remotes`.
    """
    text = blob or ""
    if _AUTH_HTTPS.search(text):
        print("  [aide] accès HTTPS refusé : identifiants indisponibles dans cet "
              "environnement.", file=sys.stderr)
        print("         WSL/CI n'ont souvent aucun credential helper (Windows en a "
              "un via Git Credential Manager).", file=sys.stderr)
        print("         Choix, sans rien réécrire : configurer un credential helper "
              "HTTPS (ou un jeton PAT),", file=sys.stderr)
        print("         ou basculer VOLONTAIREMENT ce dépôt en SSH : "
              "morf remotes --to ssh --only <projet>.", file=sys.stderr)
        print("         HTTPS reste un protocole valide : c'est l'accès qui manque, "
              "pas le protocole.", file=sys.stderr)
    elif _AUTH_SSH.search(text):
        print("  [aide] accès SSH refusé : aucune clé acceptée par le remote.",
              file=sys.stderr)
        print("         Vérifier la clé dans ~/.ssh puis : ssh -T git@github.com.",
              file=sys.stderr)
        print("         Ne pas convertir en HTTPS pour contourner : corriger l'accès "
              "SSH, ou choisir HTTPS volontairement", file=sys.stderr)
        print("         via morf remotes --to https --only <projet>.", file=sys.stderr)


def run_net(args: list, cwd: Path | None = None, check: bool = True) -> int:
    """Comme run(), mais pour les opérations git DISTANTES (clone/fetch/pull/push).

    Une coupure SSH transitoire (« Connection closed by ... port 22 »...) ne doit
    pas faire échouer tout un `morf dev pull`/`push` : run_git réessaie ces seuls
    hoquets de transport. La sortie est capturée pour lire le signal, puis
    ré-émise pour garder l'affichage habituel.
    """
    result = run_git(args, cwd=cwd, echo=lambda m: print(f"  [git] {m}", file=sys.stderr))
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    if result.returncode != 0:
        # Un échec d'accès n'est pas un hoquet réseau : on ajoute une aide ciblée
        # (identifiants HTTPS ou clé SSH) SANS jamais toucher au remote.
        _auth_hint((result.stderr or "") + (result.stdout or ""))
    if check and result.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:2])} failed ({result.returncode})")
    return result.returncode


def capture(args: list, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=False)
    return result.stdout.strip()


# -- Git ------------------------------------------------------------------

def cmd_clone(workspace: Workspace, project: Project, protocol: str = "ssh") -> bool:
    if project.exists:
        print(f"[SKIP] {project.local_name} (already present)")
        return True
    url = workspace.clone_url(project.local_name, protocol)
    run_net(["git", "clone", "--branch", workspace.branch, url, str(project.path)])
    return True


def cmd_fetch(workspace: Workspace, project: Project) -> bool:
    run_net(["git", "fetch", "--prune"], cwd=project.path)
    return True


def cmd_pull(workspace: Workspace, project: Project, dry_run: bool = False) -> bool:
    if dry_run:
        # Show what a fast-forward would bring, without merging. The fetch only
        # updates remote-tracking refs (never the working tree or a service), so
        # the preview is honest about what `update` would apply.
        run_net(["git", "fetch", "--quiet", "origin", workspace.branch],
                cwd=project.path, check=False)
        incoming = capture(
            ["git", "log", "--oneline", f"HEAD..origin/{workspace.branch}"],
            cwd=project.path)
        if incoming:
            print(f"[dry-run] would fast-forward {workspace.branch}; incoming:")
            print(incoming)
        else:
            print(f"[dry-run] already up to date with origin/{workspace.branch}")
        return True
    run_net(["git", "pull", "--ff-only", "origin", workspace.branch], cwd=project.path)
    return True


def cmd_status(workspace: Workspace, project: Project) -> bool:
    run(["git", "status", "--short", "--branch"], cwd=project.path)
    return True


def cmd_push(workspace: Workspace, project: Project) -> bool:
    run_net(["git", "push", "origin", workspace.branch], cwd=project.path)
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


@lru_cache(maxsize=1)
def detect_windows_toolchain() -> tuple:
    """Detect the MinGW/Qt build toolchain actually present, for -D overrides.

    The parc's `mingw` preset pins one machine's MSYS2 paths -- ninja, g++, the
    Qt prefix -- as absolute cache variables. Those paths do not exist on another
    Windows box (the official Qt toolchain lives under C:/Qt/..., MSYS2 may be
    absent entirely), so the pinned `ninja.exe` fails with "no such file". Rather
    than assume a layout, morfTools detects what is on THIS machine and overrides
    the pins: the same "the machine announces, morfTools adapts" rule as the rest
    of the chantier.

    Returns (overrides, problems): CMake -D flags to add, and human-readable gaps.
    Cached: the toolchain is the same for every project in one run.
    """
    overrides, problems = [], []
    ninja = shutil.which("ninja")
    if ninja:
        overrides.append(f"-DCMAKE_MAKE_PROGRAM={ninja}")
    else:
        problems.append("ninja introuvable sur le PATH")

    cxx = shutil.which("g++") or shutil.which("c++")
    if cxx:
        overrides.append(f"-DCMAKE_CXX_COMPILER={cxx}")
        cc = shutil.which("gcc") or shutil.which("cc")
        if cc:
            overrides.append(f"-DCMAKE_C_COMPILER={cc}")
    else:
        problems.append("compilateur MinGW (g++/c++) introuvable sur le PATH")

    # Qt: an explicit CMAKE_PREFIX_PATH wins; Qt6_DIR lets CMake resolve on its
    # own (no override, no problem); otherwise derive the prefix from qmake on
    # the PATH (.../<qtver>/mingw_64/bin/qmake.exe -> .../<qtver>/mingw_64).
    prefix = os.environ.get("CMAKE_PREFIX_PATH", "")
    qt_via_env = bool(prefix or os.environ.get("Qt6_DIR"))
    if not qt_via_env:
        qmake = shutil.which("qmake6") or shutil.which("qmake")
        if qmake:
            prefix = str(Path(qmake).resolve().parent.parent)
    if prefix:
        overrides.append(f"-DCMAKE_PREFIX_PATH={prefix}")
    elif not qt_via_env:
        problems.append("préfixe Qt introuvable "
                        "(ni CMAKE_PREFIX_PATH/Qt6_DIR, ni qmake sur le PATH)")
    return tuple(overrides), tuple(problems)


#: Print the toolchain diagnostic only once per run, not once per project.
_TOOLCHAIN_REPORTED = [False]


def cmake_build(project: Project, preset: str = "") -> None:
    """Build, skipping a preset this project does not declare.

    A preset missing here is a normal absence rather than a failure: it means
    the project does not target that configuration, not that the build broke.

    On Windows, the `mingw` preset's pinned toolchain paths are overridden with
    what this machine actually has (see detect_windows_toolchain), so a fresh box
    with a different Qt/MinGW layout builds without editing thirteen presets.
    """
    if not preset:
        run(["cmake", "-S", ".", "-B", "build"], cwd=project.path)
        run(["cmake", "--build", "build"], cwd=project.path)
        return
    if preset not in project.presets():
        print(f"[SKIP] preset '{preset}' not defined in this project")
        return

    overrides = ()
    if platform.system() == "Windows" and preset in ("mingw", "windows"):
        overrides, problems = detect_windows_toolchain()
        if problems:
            if not _TOOLCHAIN_REPORTED[0]:
                print("[FAIL] toolchain de build incomplète sur cette machine :")
                for gap in problems:
                    print(f"       - {gap}")
                print("       installer / mettre sur le PATH : ninja, un compilateur "
                      "MinGW, et Qt")
                print("       (ou définir CMAKE_PREFIX_PATH vers votre Qt). "
                      "Voir 'morf doctor'.")
                _TOOLCHAIN_REPORTED[0] = True
            raise RuntimeError("toolchain de build incomplète")
        if not _TOOLCHAIN_REPORTED[0]:
            shown = ", ".join(o.split("=", 1)[1] for o in overrides)
            print(f"[INFO] toolchain détectée sur cette machine : {shown}")
            _TOOLCHAIN_REPORTED[0] = True

    run(["cmake", "--preset", preset, *overrides], cwd=project.path)
    run(["cmake", "--build", "--preset", preset], cwd=project.path)


def cmd_build(workspace: Workspace, project: Project, preset: str = "",
              force_gui: bool = False) -> bool:
    if skip_gui(project, force_gui):
        return True
    if project.is_platformio:
        if preset:
            print(f"[INFO] preset ignored for PlatformIO: {preset}")
        # PlatformIO is a separate toolchain, often absent on a machine that only
        # builds the Qt services. Its absence is not a failure of the parc: skip
        # the firmware with a clear note rather than crashing on a missing 'pio'.
        pio = shutil.which("pio") or shutil.which("platformio")
        if not pio:
            print("[SKIP] PlatformIO (pio) introuvable sur le PATH : build firmware sauté.")
            print("       Installer PlatformIO (pip install platformio) pour compiler "
                  "les projets ESP32.")
            return True
        run([pio, "run"], cwd=project.path)
    elif project.is_cmake:
        # Resolve declared build libraries first (a no-op for a non-service
        # project, which has no service.py to declare them yet).
        if service_build_deps(project) != 0:
            raise RuntimeError("build dependencies not satisfied")
        cmake_build(project, preset)
        _stamp_provenance(project)
    else:
        print("[SKIP] no known build definition")
    return True


def _stamp_provenance(project: Project) -> None:
    """After a successful build, record this binary's provenance for a service.

    Delegated to morfdeploy, and ONLY for a standardised service (its
    `morfproject.json` declares packaging provider "morfdeploy"): morfdeploy owns
    the artifact location (locate_binary) and the build-info.json format, so
    morfTools carries no artifact heuristic of its own -- the single source of
    truth stays where the build layout is already defined. Projects that own their
    packaging (provider "project") write their own conformant provenance in their
    scripts.

    Never a build failure: provenance is what lets the later packaging chain trust
    a binary, not a build requirement. A missing morfproject.json is a project not
    yet onboarded, silently skipped.
    """
    try:
        declared = morfproject.load(project.path)
    except morfproject.MorfProjectError as exc:
        print(f"[WARN] {exc}")
        return
    if declared is None or not declared.is_morfdeploy_service:
        return
    entry = project.path / "service.py"
    if not entry.is_file():
        return
    run([sys.executable, str(entry), "build-info"], cwd=project.path, check=False)


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
        run(elevated([sys.executable, str(entry), "install"]), cwd=project.path)
        return True

    # Default (no --services): generic per-language setup only, no service.
    # An EMPTY (or comment-only) requirements.txt must not trigger pip: on an
    # externally-managed system (PEP 668, Raspberry Pi OS / Debian Bookworm+),
    # pip refuses to touch the system Python and fails -- even with nothing to
    # install. Such a file is treated as "no generic install definition".
    req = project.path / "requirements.txt"
    if req.is_file() and _requirements_has_packages(req):
        run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=project.path)
    elif (project.path / "service.py").is_file() and not is_template(project):
        # Reached only through `morf setup` (the generic per-language step): a
        # service has nothing to do here (no requirements.txt). It is installed by
        # `morf install`, which builds it and places its configuration in one pass.
        print("[SKIP] service — installed by 'morf install' (this is 'setup': "
              "generic dependencies only)")
    else:
        print("[SKIP] no generic install definition")
    return True


def _requirements_has_packages(path: Path) -> bool:
    """True when requirements.txt lists at least one real package.

    A blank or comment-only file lists nothing to install; running pip on it
    only produces a spurious externally-managed failure (see cmd_install).
    """
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return True
    except OSError:
        return False
    return False


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
    # Python lance en root ecrit son cache bytecode (__pycache__/*.pyc) a cote
    # des modules importes -- ici la copie vendoree morfdeploy, dans l'arbre
    # source de l'utilisateur. Ces .pyc root:root ne sont ensuite ni supprimables
    # ni reconstruisibles sans sudo : un « rm -rf ~/Codage » lance en simple
    # utilisateur (comme le script de remise a blanc) echoue en « Permission
    # denied ». -B desactive l'ecriture du cache pour cette execution privilegiee
    # sans rien changer d'autre (les imports fonctionnent, juste sans cache).
    if args and args[0] == sys.executable:
        args = [args[0], "-B", *args[1:]]
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

    probe = subprocess.run([sys.executable, str(entry), "is-installed"],
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
    cmd = [sys.executable, str(entry), "update"] + (["--force"] if force else [])
    run(elevated(cmd), cwd=project.path)


def cmd_upgrade(workspace: Workspace, project: Project, preset: str = "",
                force_gui: bool = False, force: bool = False,
                dry_run: bool = False) -> bool:
    if dry_run:
        # The plan, without doing any of it: what would be pulled, whether a
        # rebuild would run, and whether the installed service would be updated.
        print("[dry-run] plan:")
        cmd_pull(workspace, project, dry_run=True)
        if project.is_cmake and not skip_gui(project, force_gui):
            print(f"  would rebuild (CMake, preset {preset or 'default'})")
        entry = project.path / "service.py"
        if entry.is_file():
            probe = subprocess.run(
                [sys.executable, str(entry), "is-installed"],
                cwd=project.path, capture_output=True, check=False)
            if probe.returncode == 0:
                print("  would update the installed service (service.py update)")
            elif probe.returncode == 2:
                print("  would try to update the service (cannot tell without rights)")
            else:
                print("  service not installed here: would skip redeploy")
        return True
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
    run([sys.executable, *args], cwd=project.path)
    return True


def cmd_clean(workspace: Workspace, project: Project) -> bool:
    for directory in sorted(project.path.glob("build*")):
        if directory.is_dir():
            print(f"[RM] {directory.name}")
            shutil.rmtree(directory, ignore_errors=True)
    return True


# -- Purge ----------------------------------------------------------------
#
# morfTools does not read service.json and does not know where any service
# keeps its data. It asks each project what it can erase (`purge --list`) and
# forwards the chosen categories back to that project's service.py. The
# knowledge stays in the project; morfTools only orchestrates.

def purge_catalog(project: Project) -> list:
    """The purge categories a project declares, via its own `service.py purge --list`.

    Returns a list of {id, label, destructive, type}. An empty list covers every
    "nothing to purge" case identically -- not a service, no purge block,
    service.py failing -- because for an orchestrator the answer is the same:
    this clone offers no category to erase.
    """
    entry = project.path / "service.py"
    if not entry.is_file():
        return []
    result = subprocess.run(
        [sys.executable, str(entry), "purge", "--list"],
        cwd=project.path, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
    except (ValueError, TypeError):
        return []
    categories = data.get("categories")
    return categories if isinstance(categories, list) else []


def service_uninstall(project: Project, purge: bool, backup: str,
                      dry_run: bool) -> int:
    """Uninstall one service through its own service.py; return the exit code.

    Mirrors service_purge: elevated for the real removal, never for a dry-run.
    Delegates the actual teardown (deregister, remove config/binary) to the
    project, which knows its own paths -- morfTools only decides which services
    and forwards the intent.
    """
    entry = project.path / "service.py"
    cmd = [sys.executable, str(entry), "uninstall"]
    if purge:
        cmd.append("--purge")
        if backup:
            cmd += ["--backup", backup]
    if dry_run:
        cmd.append("--dry-run")
    else:
        cmd = elevated(cmd)
    return subprocess.run(cmd, cwd=project.path).returncode


def service_build_deps(project: Project, dry_run: bool = False,
                       assume_yes: bool = False) -> int:
    """Resolve a project's declared build libraries before compiling it.

    Delegates to the project's own `service.py build-deps` (morfDeploy), which
    knows the packages per platform. A non-service project has no service.py and
    no such contract yet, so it is a no-op (returns 0). The real install of a
    build library needs root, so it is elevated like the service install; a
    dry-run only reports and is never elevated.
    """
    entry = project.path / "service.py"
    if not entry.is_file():
        return 0
    cmd = [sys.executable, str(entry), "build-deps"]
    if dry_run:
        cmd.append("--dry-run")
    if assume_yes:
        cmd.append("--yes")
    if not dry_run:
        cmd = elevated(cmd)
    return subprocess.run(cmd, cwd=project.path).returncode


def is_service_project(project: Project) -> bool:
    """A project morfTools can deploy as a service on this machine.

    It carries a service.py and is not the template pattern -- the same rule
    install --services already uses, named once so deploy and the discovery of
    deployable components agree.
    """
    return (project.path / "service.py").is_file() and not is_template(project)


#: The three configuration behaviours the façade offers, mapped onto what
#: service.py already does. `keep` is the safe default: install never overwrites
#: an existing config, so keeping it is simply not running a config step.
CONFIG_MODES = ("keep", "merge", "replace")


def deploy_one(project: Project, preset: str, config_mode: str,
               dry_run: bool, assume_yes: bool = False) -> tuple:
    """Build and install one service, then apply the chosen config behaviour.

    Returns (returncode, steps) where steps names what ran (or would run under a
    dry-run), for the summary. Mirrors `install --services`: build as the user,
    elevate only the install and the config write. `keep` runs no config step at
    all; `merge` adds the clone's new keys without touching local values;
    `replace` overwrites the deployed config from the repo (a timestamped backup
    is written by service.py first).
    """
    entry = project.path / "service.py"
    steps = []
    builds = project.is_cmake and not skip_gui(project, False)
    if builds:
        steps.append(f"build (preset {preset or 'default'})")
    steps.append("install")
    if config_mode != "keep":
        steps.append(f"config {config_mode}")

    if builds:
        steps.insert(0, "build-deps")

    if dry_run:
        return 0, steps

    if builds:
        # Build libraries BEFORE compiling: a missing OpenSSL stops here with a
        # clear message rather than a find_package failure mid-build. On a
        # toolchain with no package manager it only announces and proceeds.
        if service_build_deps(project, dry_run=False, assume_yes=assume_yes) != 0:
            raise RuntimeError("build dependencies not satisfied")
        cmake_build(project, preset)
    rc = subprocess.run(elevated([sys.executable, str(entry), "install"]),
                        cwd=project.path).returncode
    if rc != 0:
        return rc, steps
    if config_mode == "merge":
        rc = subprocess.run(elevated([sys.executable, str(entry), "config", "merge"]),
                            cwd=project.path).returncode
    elif config_mode == "replace":
        rc = subprocess.run(
            elevated([sys.executable, str(entry), "config", "push", "--force"]),
            cwd=project.path).returncode
    return rc, steps


def service_purge(project: Project, ids, all_flag: bool, dry_run: bool,
                  force: bool = False) -> int:
    """Run the project's own purge for the chosen categories; return its exit code.

    The real erasure reaches under /etc, /var/lib or /opt and is elevated exactly
    as the service install is. A dry-run touches nothing, so it is never elevated
    -- the safe preview must never be harder to run than the destructive act.

    `force` is passed through to override the running-service guard: service.py
    refuses to erase data a live service may be writing unless told to proceed.
    """
    entry = project.path / "service.py"
    cmd = [sys.executable, str(entry), "purge"]
    if all_flag:
        cmd.append("--all")
    else:
        cmd += list(ids)
    if force:
        cmd.append("--force")
    if dry_run:
        cmd.append("--dry-run")
    else:
        cmd = elevated(cmd)
    return subprocess.run(cmd, cwd=project.path).returncode


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
    # Le protocole est une propriété du dépôt, pas un défaut : information (visible
    # sous --verbose), jamais un avertissement. HTTPS et SSH sont tous deux valides.
    proto = remote_protocol(remote)
    if proto in ("ssh", "https"):
        print(f"[INFO] origin protocol: {proto}")
    elif proto:
        print(f"[INFO] origin protocol: {proto} (non reconnu)")
    return healthy


# -- Remotes : lecture, protocole, conversion volontaire -------------------
# morfSystem ne choisit JAMAIS le protocole à la place de l'utilisateur. Ces
# helpers ne font que LIRE le remote existant et, sur demande explicite,
# proposer/appliquer une conversion qui PRESERVE le nom distant réel (lu dans
# l'URL, jamais dérivé du nom de dossier -- c'est ce qui protège un dépôt renommé
# comme morfSync dont l'origin pointe encore vers HomeServerHub).

def remote_url(path: Path) -> str:
    """URL du remote 'origin' du dépôt, ou chaîne vide s'il n'y en a pas."""
    return capture(["git", "remote", "get-url", "origin"], cwd=path)


def remote_protocol(url: str) -> str:
    """'ssh', 'https', 'other' selon l'URL ; '' si l'URL est vide."""
    if not url:
        return ""
    if url.startswith("git@") or url.startswith("ssh://"):
        return "ssh"
    if url.startswith(("https://", "http://")):
        return "https"
    return "other"


def _split_remote(url: str):
    """(host, 'owner/repo(.git)') depuis une URL git, ou None si non reconnue.

    Le chemin distant est repris tel quel : c'est LUI le nom du dépôt distant,
    qu'on ne reconstruit jamais à partir du dossier local.
    """
    if url.startswith("git@") and ":" in url:
        host, path = url[len("git@"):].split(":", 1)
        return host, path
    if url.startswith("ssh://"):
        rest = url[len("ssh://"):]
        if rest.startswith("git@"):
            rest = rest[len("git@"):]
        host, _, path = rest.partition("/")
        return host, path
    if url.startswith(("https://", "http://")):
        rest = url.split("://", 1)[1]
        host, _, path = rest.partition("/")
        if "@" in host:                      # d'éventuels identifiants dans l'URL
            host = host.split("@", 1)[1]
        return host, path
    return None


def convert_remote_url(url: str, to: str) -> str | None:
    """Réécrit l'URL vers 'ssh' ou 'https' en conservant host + owner/repo.

    Retourne None si l'URL n'est pas reconnue (elle est alors laissée intacte par
    l'appelant, jamais devinée).
    """
    parsed = _split_remote(url)
    if parsed is None:
        return None
    host, path = parsed
    host = host.strip("/")
    path = path.strip("/")
    if not host or not path:
        return None
    if to == "ssh":
        return f"git@{host}:{path}"
    if to == "https":
        return f"https://{host}/{path}"
    return None


def set_remote_url(path: Path, url: str) -> int:
    """Applique `git remote set-url origin <url>` ; retourne le code de sortie."""
    return subprocess.run(["git", "remote", "set-url", "origin", url],
                          cwd=path, check=False).returncode


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
    "install": cmd_install,   # intercepted in the CLI: install IS the deploy engine
    "setup": cmd_install,     # the generic per-language setup (Python deps only)
    "uninstall": cmd_uninstall,
    "upgrade": cmd_upgrade,
    "clean": cmd_clean,
    "doctor": cmd_doctor,
}

#: Commands that accept --preset. Passing it elsewhere is refused rather than
#: ignored: silently dropping an option the person typed is how they end up
#: believing a build used a configuration it never saw.
PRESET_COMMANDS = {"build", "upgrade", "install", "deploy"}
