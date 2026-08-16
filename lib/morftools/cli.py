"""The driver: parse, ask what is missing, run over every project.

One implementation for Windows, Linux and the Raspberry Pi. It replaces
morf.sh and morf.ps1, which were the same algorithm written twice -- iterate
the projects, run git, read a JSON manifest -- with no platform-specific
mechanism anywhere in them.
"""

from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

from .commands import COMMANDS, PRESET_COMMANDS, cmd_doctor, elevated, update_status
from .config import SHARED_CONSUMERS, shared_config_path
from .report import Reporter
from .workspace import Workspace, WorkspaceError


def prompt(question: str) -> str | None:
    """Ask on the terminal, or give up honestly.

    Returns None when there is no terminal -- cron, CI, a pipe. A required
    answer is never guessed: a default preset silently chosen in CI produces
    artefacts nobody can account for.
    """
    if not sys.stdin or not sys.stdin.isatty():
        return None
    try:
        return input(question)
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return None


def choose_preset(workspace: Workspace) -> str:
    presets = workspace.all_presets()
    if not presets:
        return ""    # no CMake project cloned: nothing to ask

    print("No preset given. Available presets:", file=sys.stderr)
    for index, (name, count, total) in enumerate(presets, start=1):
        print(f"  {index}) {name:<20} ({count}/{total} projects)", file=sys.stderr)

    while True:
        reply = prompt(f"Choice [1-{len(presets)}]: ")
        if reply is None:
            print("Not a terminal: rerun with --preset <name>.", file=sys.stderr)
            raise SystemExit(2)
        if reply.isdigit() and 1 <= int(reply) <= len(presets):
            chosen = presets[int(reply) - 1][0]
            print(f"[INFO] selected preset: {chosen}", file=sys.stderr)
            return chosen
        print("Invalid answer.", file=sys.stderr)


def ask_message() -> str:
    while True:
        reply = prompt("Commit message: ")
        if reply is None:
            print(
                "A commit message is required (not a terminal: use --message).",
                file=sys.stderr,
            )
            raise SystemExit(2)
        if reply.strip():
            return reply.strip()


#: Ecosystem passes, each a named area in the report. Running them separately
#: (rather than the script's default "all") lets the summary name which one
#: failed instead of a single opaque "ecosystem".
ECOSYSTEM_PASSES = [
    ("ports", "Plan d'adressage"),
    ("versions", "Versions"),
    ("vendor", "Copies vendorées"),
    ("manifests", "Manifestes de déploiement"),
]


def _progress(active: bool, done: int, total: int, name: str):
    """Live one-line progress on stderr, so the update check is never a silent wait.

    On a terminal it rewrites a single line with a carriage return; piped or
    logged, it stays quiet rather than littering the output with spinner frames.
    stderr is used so it never contaminates the report, which is stdout.
    """
    if active:
        print(f"\r  vérification des versions… {done}/{total} {name:<24}",
              end="", file=sys.stderr, flush=True)


def _project_banner(name: str) -> None:
    """A hard separator before each project processed.

    A run over the whole parc (install, update, upgrade, build...) is otherwise
    one continuous wall of output where the boundary between two services is a
    single faint `[name]` line. A full-width rule turns it into distinct blocks
    the eye can scan in the terminal. ASCII only, so it renders the same on the
    Windows console, Linux and the Raspberry Pi.
    """
    bar = "=" * 72
    print()
    print(bar)
    print(f"  {name}")
    print(bar)


def _progress_clear(active: bool):
    if active:
        print("\r" + " " * 56 + "\r", end="", file=sys.stderr, flush=True)


def _shared_config_relevant() -> bool:
    """Cette machine consomme-t-elle le fichier partage morfsystem.json ?

    Vrai si le fichier est deja deploye, ou si morfMonitor / morfDashboard tourne
    ici. Sur une machine de build pur (aucun consommateur, aucun /etc), on ne va
    pas semer un fichier de configuration partagee dont rien ne se sert.
    """
    if shared_config_path().exists():
        return True
    import platform
    for name in SHARED_CONSUMERS:
        if platform.system() == "Windows":
            probe = subprocess.run(["sc.exe", "query", name],
                                   capture_output=True, check=False)
            if probe.returncode == 0:
                return True
        else:
            probe = subprocess.run(
                ["systemctl", "list-unit-files", f"{name}.service"],
                capture_output=True, text=True, check=False)
            if probe.returncode == 0 and name in probe.stdout:
                return True
    return False


def _merge_shared_config() -> None:
    """Mise a niveau NON destructive du fichier partage, pendant `upgrade`.

    Le pendant, pour /etc/morfsystem/morfsystem.json, du merge que service.py
    update fait deja pour la config propre de chaque service : ajoute les cles
    nouvelles du clone, garde tous les choix locaux. Delegue a `config.py shared
    merge`, ELEVE car il ecrit sous /etc -- comme le deploiement d'un service,
    c'est la seule etape qui demande les droits, jamais le git.
    """
    config_py = Path(__file__).resolve().parents[2] / "config.py"
    _project_banner("configuration partagee (morfsystem.json)")
    rc = subprocess.run(
        elevated([sys.executable, str(config_py), "shared", "merge"]),
        check=False).returncode
    if rc != 0:
        print("[WARN] la mise a niveau de la config partagee n'a pas abouti "
              "(relancer depuis un shell eleve si elle a demande des droits)",
              file=sys.stderr)


def run_doctor(workspace: Workspace, projects: list, verbose: bool,
               check_updates: bool) -> int:
    """Doctor with a readable report: capture every check, summarise, advise.

    Nothing is lost -- `--verbose` still prints each line. What changes by
    default is that the sixty green lines collapse to a count, and the run ends
    with the failures and what to do about each.

    The check for newer versions is a NETWORK step (a git fetch per clone), so it
    is off by default: a routine `doctor` stays local and instant. `--update`
    turns it on, with a live progress line so the wait is never a silent one.
    """
    reporter = Reporter(verbose, updates_checked=check_updates)
    scripts = workspace.tool_dir / "scripts"

    def capture(cmd):
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return result.stdout + result.stderr

    for which, label in ECOSYSTEM_PASSES:
        text = capture([sys.executable, str(scripts / "ecosystem-check.py"),
                        str(workspace.root), str(workspace.manifest_path), which])
        reporter.feed(text, group="Écosystème", name=label)

    text = capture([sys.executable, str(scripts / "exec-bits.py"),
                    str(workspace.root), "--check"])
    reporter.feed(text, group="Écosystème", name="Bits exécutables")

    branch = workspace.branch
    live = check_updates and sys.stderr.isatty()
    total = len(projects) + 1        # the projects, plus morfTools itself

    for index, project in enumerate(projects, start=1):
        if not project.exists:
            reporter.feed("[SKIP] not cloned", group="Projets",
                          name=project.local_name)
            continue
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            ok = cmd_doctor(workspace, project)
        captured = buffer.getvalue()
        text = captured
        if check_updates:
            _progress(live, index, total, project.name)
            name = project.name
            # The remedy follows what runs here, read from the probe cmd_doctor
            # just did -- no second round trip:
            #   - service answering (version reported)     -> upgrade
            #   - installed but stopped (maybe on purpose) -> update, and only if
            #     wanted, upgrade -- shown on two lines, with the state noted
            #   - not installed / GUI / cannot tell        -> update
            # Upgrading a service that is not running would rebuild and restart
            # what this machine does not, or was deliberately stopped.
            answering = ("matches project" in captured
                         or "differs from project" in captured)
            note = ""
            if answering:
                remedy = f"-> python3 morf.py upgrade --only {name}"
            elif "installed but not running" in captured:
                note = "service installé mais inactif"
                remedy = (f"-> python3 morf.py update --only {name}\n"
                          f"   puis, si vous le souhaitez : "
                          f"python3 morf.py upgrade --only {name}")
            else:
                remedy = f"-> python3 morf.py update --only {name}"
            text += update_status(project.path, branch, remedy, note)
        reporter.feed(text, group="Projets",
                      name=project.local_name, forced_fail=(ok is False))

    # morfTools checks ITSELF, but only when the network step is on: it is not a
    # project in the manifest, so nothing else would ever tell you the tool is
    # out of date. The remedy is a plain 'git pull --ff-only', with no path:
    # every morf command is already run from this directory (that is how
    # 'python3 morf.py ...' resolves at all), so the self-update runs from the
    # same place. An absolute path baked into the message would be specific to
    # one machine and break on the next, which is exactly what the rest of the
    # tool avoids by deriving everything from its own location.
    if check_updates:
        _progress(live, total, total, "morfTools")
        reporter.feed(update_status(workspace.tool_dir, branch, "-> git pull --ff-only"),
                      group="Outil", name="morfTools")
        _progress_clear(live)

    return reporter.render()



def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="morf",
        description="Operate on every project declared in ecosystem.json.",
    )
    parser.add_argument("command", choices=sorted(COMMANDS), help="What to do")
    parser.add_argument("--preset", "-p", default="",
                        help=f"CMake preset ({', '.join(sorted(PRESET_COMMANDS))} only)")
    parser.add_argument("--message", "-m", default="", help="Commit message")
    parser.add_argument("--only", default="",
                        help="Restrict to one project, by canonical name")
    parser.add_argument("--gui", action="store_true",
                        help="build/upgrade: build desktop GUI apps even on a headless machine")
    parser.add_argument("--force", action="store_true",
                        help="upgrade: redeploy and restart each service even when "
                             "nothing changed (passed to service.py update)")
    parser.add_argument("--purge", action="store_true",
                        help="uninstall: also remove the configuration and binary")
    parser.add_argument("--backup", default="", metavar="DIR",
                        help="uninstall --purge: copy every config into DIR first")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="doctor: print every check line instead of the summary")
    parser.add_argument("--update", "-u", action="store_true", dest="update",
                        help="doctor: also check each clone against origin/main for a "
                             "newer version (a network step; adds a few seconds)")
    parser.add_argument("--services", action="store_true",
                        help="install: deploy every service too, via each project's "
                             "service.py (Linux, Raspberry Pi or Windows)")
    return parser


def main(argv: list | None = None) -> int:
    # Line buffering, set once. This driver interleaves its own prints with the
    # output of git and of the check scripts, which write straight to the
    # descriptor. Buffered, our lines surface after the subprocess output they
    # introduce -- and on stderr summaries, before lines that came first.
    # Fixing it here covers every command, including ones not yet written.
    for stream in (sys.stdout, sys.stderr):
        try:
            # UTF-8 with replacement: the report uses accented French and box
            # markers. A Windows console defaults to cp1252, where an unmapped
            # character raises UnicodeEncodeError and aborts the run mid-report.
            stream.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)

    # Git must run as YOU, never under sudo. Elevated, it authenticates with
    # root's SSH key -- which does not exist, so every repository answers
    # 'Permission denied (publickey)' -- and the fetch it attempts first leaves
    # root-owned files (FETCH_HEAD, objects) inside your .git, so later runs as
    # yourself fail on your own repositories with 'cannot open .git/FETCH_HEAD'.
    # Both happened, across thirteen repositories at once, from one sudo out of
    # habit. Only 'uninstall' needs elevation, and it delegates to service.py.
    # A genuine root login (no SUDO_USER) owns its clones and is left alone.
    GIT_COMMANDS = {"clone", "fetch", "pull", "update", "push", "commit",
                    "upgrade", "build"}
    if (args.command in GIT_COMMANDS and hasattr(os, "geteuid")
            and os.geteuid() == 0 and os.environ.get("SUDO_USER")):
        print(f"Refusing to run '{args.command}' under sudo.", file=sys.stderr)
        print("Git operations must run as your user: elevated, they use root's",
              file=sys.stderr)
        print("missing SSH key and leave root-owned files inside your .git.",
              file=sys.stderr)
        print(f"Run instead:  python3 morf.py {args.command}", file=sys.stderr)
        print("(only 'uninstall' and each project's service.py need sudo)",
              file=sys.stderr)
        return 2

    # `install --services` builds as YOU, then elevates each service.py itself.
    # Run wholesale under sudo it would build as root -- the same trap. Refuse it
    # the same way, pointing at the form that works.
    if (args.command == "install" and args.services and hasattr(os, "geteuid")
            and os.geteuid() == 0 and os.environ.get("SUDO_USER")):
        print("Refusing to run 'install --services' under sudo.", file=sys.stderr)
        print("It builds as your user, then elevates each service.py on its own.",
              file=sys.stderr)
        print("Run instead:  python3 morf.py install --services", file=sys.stderr)
        return 2

    if args.services and args.command != "install":
        print("--services only applies to install.", file=sys.stderr)
        return 2

    if args.preset and args.command not in PRESET_COMMANDS:
        print(f"--preset is only supported by {', '.join(sorted(PRESET_COMMANDS))}.",
              file=sys.stderr)
        return 2

    if (args.purge or args.backup) and args.command != "uninstall":
        print("--purge and --backup only apply to uninstall.", file=sys.stderr)
        return 2
    if args.verbose and args.command != "doctor":
        print("--verbose only applies to doctor.", file=sys.stderr)
        return 2
    if args.update and args.command != "doctor":
        print("--update only applies to doctor.", file=sys.stderr)
        return 2
    if args.gui and args.command not in ("build", "upgrade"):
        print("--gui only applies to build and upgrade.", file=sys.stderr)
        return 2
    if args.force and args.command != "upgrade":
        print("--force only applies to upgrade "
              "(a single service: <project>/service.py update --force).",
              file=sys.stderr)
        return 2
    if args.backup and not args.purge:
        print("--backup only applies with --purge.", file=sys.stderr)
        return 2

    try:
        workspace = Workspace(Path(__file__).resolve().parents[2])
    except WorkspaceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    preset = args.preset
    # A plain `install` (Python deps only) never builds, so it must not ask for a
    # preset; `install --services` does build, and needs one like build/upgrade.
    needs_preset = args.command in ("build", "upgrade") or (
        args.command == "install" and args.services)
    if needs_preset and not preset:
        preset = choose_preset(workspace)

    message = args.message
    if args.command == "commit" and not message:
        message = ask_message()

    handler = COMMANDS[args.command]
    projects = workspace.projects()
    if args.only:
        wanted = args.only.lower()
        projects = [p for p in projects if p.name.lower() == wanted]
        if not projects:
            print(f"No project named '{args.only}' in the manifest.", file=sys.stderr)
            return 2

    # Doctor is read-only and produces a lot of output: it gets its own path,
    # which captures every check and renders a summary instead of the flood.
    if args.command == "doctor":
        return run_doctor(workspace, projects, args.verbose, args.update)

    failed = []

    for project in projects:
        # Banner first, so every project reads as its own block -- including the
        # ones skipped below, which otherwise blur into the previous project's
        # output.
        _project_banner(project.local_name)
        if args.command != "clone" and not project.exists:
            print(f"[SKIP] {project.local_name} (not cloned)")
            continue

        try:
            # Extra arguments go only to the handlers that take them, so a
            # command's signature states what it actually depends on.
            if handler.__name__ == "cmd_upgrade":
                ok = handler(workspace, project, preset, args.gui, args.force)
            elif handler.__name__ == "cmd_build":
                ok = handler(workspace, project, preset, args.gui)
            elif handler.__name__ == "cmd_install":
                ok = handler(workspace, project, args.services, preset)
            elif handler.__name__ == "cmd_commit":
                ok = handler(workspace, project, message)
            elif handler.__name__ == "cmd_uninstall":
                ok = handler(workspace, project, args.purge, args.backup)
            else:
                ok = handler(workspace, project)
            if ok is False:
                failed.append(project.local_name)
        except (RuntimeError, OSError) as exc:
            # One project failing must never stop the others: the remaining
            # ones would stay stale with nothing saying so.
            print(f"[FAIL] {project.local_name}: {exc}", file=sys.stderr)
            failed.append(project.local_name)

    # Apres avoir mis a niveau le CODE (binaires + config propre de chaque service
    # via service.py update), `upgrade` met aussi a niveau le CONTRAT de config
    # PARTAGEE : les cles nouvelles de morfsystem.json arrivent sans qu'aucun choix
    # local ne soit ecrase. Une seule fois, apres les projets, sur une machine qui
    # consomme ce fichier. Sautee avec --only, qui cible un projet precis plutot
    # qu'une mise a niveau complete de la machine (utiliser alors `./config.py
    # shared merge` a la main).
    if args.command == "upgrade" and not args.only and _shared_config_relevant():
        _merge_shared_config()

    if failed:
        sys.stdout.flush()
        print(file=sys.stderr)
        print(f"[FAILED] {args.command} failed on: {' '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
