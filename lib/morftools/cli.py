"""The driver: parse, ask what is missing, run over every project.

One implementation for Windows, Linux and the Raspberry Pi. It replaces
morf.sh and morf.ps1, which were the same algorithm written twice -- iterate
the projects, run git, read a JSON manifest -- with no platform-specific
mechanism anywhere in them.
"""

from __future__ import annotations

import argparse
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

    if args.preset and args.command not in PRESET_COMMANDS:
        print(f"--preset is only supported by {', '.join(sorted(PRESET_COMMANDS))}.",
              file=sys.stderr)
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
                handler(workspace, project, preset)
            elif handler.__name__ == "cmd_commit":
                handler(workspace, project, message)
            else:
                handler(workspace, project)
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
