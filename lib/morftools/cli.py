"""The driver: parse, ask what is missing, run over every project.

One implementation for Windows, Linux and the Raspberry Pi. It replaces
morf.sh and morf.ps1, which were the same algorithm written twice -- iterate
the projects, run git, read a JSON manifest -- with no platform-specific
mechanism anywhere in them.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from .commands import COMMANDS, PRESET_COMMANDS
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


def ecosystem_checks(workspace: Workspace) -> list:
    """The checks no single project can perform on itself.

    The addressing plan, the vendored copies and the executable bits describe a
    SHARED resource: each project stays individually valid while the parc as a
    whole is wrong, so they run once, before the per-project loop.
    """
    failed = []
    scripts = workspace.tool_dir / "scripts"

    print("[ecosystem]")
    result = subprocess.run(
        [sys.executable, str(scripts / "ecosystem-check.py"),
         str(workspace.root), str(workspace.manifest_path)],
        check=False,
    )
    if result.returncode != 0:
        failed.append("ecosystem")
    print()

    result = subprocess.run(
        [sys.executable, str(scripts / "exec-bits.py"), str(workspace.root), "--check"],
        check=False,
    )
    if result.returncode != 0:
        failed.append("exec-bits")
    print()
    return failed


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
    parser.add_argument("--purge", action="store_true",
                        help="uninstall: also remove the configuration and binary")
    parser.add_argument("--backup", default="", metavar="DIR",
                        help="uninstall --purge: copy every config into DIR first")
    return parser


def main(argv: list | None = None) -> int:
    # Line buffering, set once. This driver interleaves its own prints with the
    # output of git and of the check scripts, which write straight to the
    # descriptor. Buffered, our lines surface after the subprocess output they
    # introduce -- and on stderr summaries, before lines that came first.
    # Fixing it here covers every command, including ones not yet written.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(line_buffering=True)
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

    if args.preset and args.command not in PRESET_COMMANDS:
        print(f"--preset is only supported by {', '.join(sorted(PRESET_COMMANDS))}.",
              file=sys.stderr)
        return 2

    if (args.purge or args.backup) and args.command != "uninstall":
        print("--purge and --backup only apply to uninstall.", file=sys.stderr)
        return 2
    if args.gui and args.command not in ("build", "upgrade"):
        print("--gui only applies to build and upgrade.", file=sys.stderr)
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
    if args.command in PRESET_COMMANDS and not preset:
        preset = choose_preset(workspace)

    message = args.message
    if args.command == "commit" and not message:
        message = ask_message()

    failed = ecosystem_checks(workspace) if args.command == "doctor" else []

    handler = COMMANDS[args.command]
    projects = workspace.projects()
    if args.only:
        wanted = args.only.lower()
        projects = [p for p in projects if p.name.lower() == wanted]
        if not projects:
            print(f"No project named '{args.only}' in the manifest.", file=sys.stderr)
            return 2

    for project in projects:
        if args.command != "clone" and not project.exists:
            print(f"[SKIP] {project.local_name} (not cloned)")
            continue

        print(f"[{project.local_name}]")
        try:
            # Extra arguments go only to the handlers that take them, so a
            # command's signature states what it actually depends on.
            if handler.__name__ in ("cmd_build", "cmd_upgrade"):
                ok = handler(workspace, project, preset, args.gui)
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

    if failed:
        sys.stdout.flush()
        print(file=sys.stderr)
        print(f"[FAILED] {args.command} failed on: {' '.join(failed)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
