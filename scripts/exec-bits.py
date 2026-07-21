#!/usr/bin/env python3
"""Restore the executable bit on every runnable script of the ecosystem.

The problem this solves is invisible on Windows and fatal on the Raspberry Pi.
Windows has no executable permission, so Git records new files as 100644. The
working copy runs fine -- `bash deploy-config.sh` never consults the bit. The
Pi clones the same repository, `./deploy-config.sh` answers "Permission
denied", and nothing in the message points at the machine where the file was
created.

So the fix targets the GIT INDEX MODE, not the filesystem permission. `chmod`
on Windows is a no-op that Git ignores; `git update-index --chmod=+x` records
100755 in the tree itself, which is what every other clone will see. On Unix
the filesystem bit is set too, so the working copy matches what was recorded.

What counts as runnable is the SHEBANG, not the extension. A file starting
with `#!` was written to be executed -- that is the author's own statement of
intent, and it covers .sh and .py alike without maintaining a list of
extensions that would drift.

Usage:
    exec-bits.py <root> [--check] [--project NAME]

    --check    report only, change nothing, exit 1 if anything is missing.
               This is the form used by `morf doctor`.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    """Run a git command in `repo` and return stdout, or "" on failure."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def has_shebang(path: Path) -> bool:
    """True when the file starts with '#!'.

    Read as bytes: a script may carry any encoding, and a decoding error here
    would wrongly exclude a file that is perfectly executable.
    """
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


def find_repos(root: Path, only: str | None) -> list[Path]:
    repos = sorted(p for p in root.iterdir() if p.is_dir() and (p / ".git").exists())
    if only:
        # The sandbox suffixes directories with '_travail'; accept either form
        # so the same command works in the sandbox and in production.
        needle = only.lower().removesuffix("_travail")
        repos = [p for p in repos if p.name.lower().removesuffix("_travail") == needle]
    return repos


def scan(repo: Path) -> list[str]:
    """Tracked files carrying a shebang but recorded as non-executable."""
    listing = git(repo, "ls-files", "-s")
    missing = []
    for line in listing.splitlines():
        # Format: "<mode> <sha> <stage>\t<path>"
        meta, _, rel = line.partition("\t")
        if not rel or not meta.startswith("100644"):
            continue
        if has_shebang(repo / rel):
            missing.append(rel)
    return missing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="Directory holding the repositories")
    parser.add_argument("--check", action="store_true", help="Report only, change nothing")
    parser.add_argument("--project", help="Restrict to a single project")
    args = parser.parse_args()

    root: Path = args.root.resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    repos = find_repos(root, args.project)
    if not repos:
        target = args.project or root
        print(f"No repository found: {target}", file=sys.stderr)
        return 2

    total = 0
    touched: list[str] = []

    for repo in repos:
        missing = scan(repo)
        if not missing:
            continue
        total += len(missing)
        print(f"[{repo.name}]")
        for rel in missing:
            if args.check:
                print(f"  {rel}")
                continue
            # The index mode is what other clones will see; set it first.
            if git(repo, "update-index", "--chmod=+x", "--", rel) == "":
                # update-index prints nothing on success, so distinguish the
                # failure by re-reading the mode rather than trusting output.
                mode = git(repo, "ls-files", "-s", "--", rel)[:6]
                if mode != "100755":
                    print(f"  FAILED  {rel}", file=sys.stderr)
                    continue
            # On Unix, align the working copy with what was just recorded.
            if os.name != "nt":
                path = repo / rel
                try:
                    path.chmod(path.stat().st_mode | 0o111)
                except OSError:
                    pass
            print(f"  fixed   {rel}")
        touched.append(repo.name)

    print()
    if total == 0:
        print("All runnable scripts are executable.")
        return 0

    if args.check:
        print(f"{total} script(s) recorded as non-executable.")
        print("They will answer 'Permission denied' once cloned on Linux.")
        print("Fix with:  ./exec-bits.sh")
        return 1

    print(f"{total} script(s) fixed in {len(touched)} repository(ies).")
    print("The change is STAGED, not committed -- review it, then commit:")
    print("    git -C <project> status --short")
    print("    git -C <project> commit -m 'chore: restore executable bit on scripts'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
