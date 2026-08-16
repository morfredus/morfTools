#!/usr/bin/env python3
"""Parc configuration: the shared file, and each project's own.

    ./config.py shared status|validate|edit|diff|merge|install|apply
    ./config.py deploy [<project>] [-- <args passed through>]

Replaces config.sh, config.ps1, shared-config.sh and shared-config.ps1.

`shared merge` is the non-destructive upgrade of the deployed file: it adds the
clone's new keys and keeps every local value (what `morf upgrade` runs). `install`
and `apply` still OVERWRITE from the clone -- a deliberate re-alignment, never an
upgrade side effect.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from morftools.config import deploy, shared
from morftools.workspace import Workspace, WorkspaceError

SHARED_ACTIONS = ("status", "validate", "edit", "diff", "merge", "install", "apply")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__.strip())
        print(f"\nshared actions: {', '.join(SHARED_ACTIONS)}")
        return 0
    try:
        workspace = Workspace(Path(__file__).resolve().parent)
    except WorkspaceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    command, rest = argv[0], argv[1:]
    if command == "shared":
        return shared(workspace, rest[0] if rest else "status")
    if command == "deploy":
        extra = rest[1:] if len(rest) > 1 else []
        return deploy(workspace, rest[0] if rest else "", extra)
    print(f"Unknown command: {command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
