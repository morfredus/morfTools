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


#: Only these are judged on their shebang. A tracked binary or a .bat has every
#: right to be executable without one, so the question is never asked of it.
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".zsh"}


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


def scan_spurious(repo: Path) -> list:
    """Tracked files recorded as executable while carrying no shebang.

    The mirror image of the defect above, and it bites differently: nothing
    fails, but the file is checked out executable everywhere, so anyone who
    sets the bit locally -- on a module that never needed it -- produces a mode
    difference that git refuses to merge, and `git pull` stops on a file whose
    content is identical. The message talks about local changes and shows none.

    Reported, not fixed: a tracked file may legitimately be executable without
    a shebang -- a helper binary, a .bat, a wrapper invoked by name. Demoting
    those silently would break them to tidy up a listing.
    """
    listing = git(repo, "ls-files", "-s")
    spurious = []
    for line in listing.splitlines():
        meta, _, rel = line.partition("\t")
        if not rel or not meta.startswith("100755"):
            continue
        path = repo / rel
        if path.suffix.lower() in SCRIPT_SUFFIXES and not has_shebang(path):
            spurious.append(rel)
    return spurious


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
    spurious_total = 0
    touched: list[str] = []

    for repo in repos:
        spurious = scan_spurious(repo)
        if spurious:
            spurious_total += len(spurious)
            print(f"[{repo.name}]")
            for rel in spurious:
                print(f"  executable without a shebang: {rel}")

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
    if spurious_total:
        # A warning, not a failure: nothing is broken, but this is what makes a
        # later `git pull` stop on a file nobody edited.
        print(f"{spurious_total} file(s) executable without a shebang.")
        print("Harmless to run, but a local chmod on one of them will block a pull")
        print("with 'local changes' on a file whose content is identical.")
        print()

    if total == 0:
        print("All runnable scripts are executable.")
        return 0

    if args.check:
        print(f"{total} script(s) recorded as non-executable.")
        print("They answer 'Permission denied' once cloned on Linux.")
        print()
        print("Fix, from the morfTools directory:")
        print("    python3 scripts/exec-bits.py ..")
        print()
        # Deliberately NOT './exec-bits.sh': that wrapper needs the very bit this
        # restores, so on a fresh clone it cannot start ("Permission denied") --
        # the fix advising its own broken form. `python3 <script>` runs whatever
        # the bit says, the same reason `python3 morf.py` always works. Once the
        # command above has run, ./exec-bits.sh and ./service.py work too.
        print("Run it with python3, not ./exec-bits.sh: the wrapper would need")
        print("the bit it is about to restore, so it cannot start on a fresh clone.")
        return 1

    print(f"{total} script(s) fixed in {len(touched)} repository(ies).")
    print()
    print("The working copy is runnable now, but the change is only STAGED. To make")
    print("it LAST, commit and push it -- otherwise the remote still records the")
    print("files non-executable, and the next `pull` that touches them takes the bit")
    print("away again on Linux. From the morfTools directory:")
    print()
    print("    python3 morf.py commit -m 'chore: restore executable bit on scripts'")
    print("    python3 morf.py push")
    print()
    print("Only stopping here (no push) leaves the fix local and fragile. Unstaging")
    print("it (git restore --staged) would clean the status but keep it just as")
    print("fragile -- the durable fix is on the remote, so it has to be pushed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
