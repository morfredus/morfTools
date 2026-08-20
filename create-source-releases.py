#!/usr/bin/env python3
"""Create the authoritative source releases from the current workspace.

This script never copies work files to production. It runs only from the
workspace the operator selected, where the sources have already been reviewed.
Its job is limited to: preflight each selected repository and create the
matching GitHub source release when it does not yet exist.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

from morftools.workspace import Project, Workspace, WorkspaceError  # noqa: E402


def run(command: list[str], cwd: Path, *, capture: bool = False) -> str:
    print("$ " + " ".join(command))
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=capture)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(detail or f"command failed ({result.returncode})")
    return result.stdout if capture else ""


def preflight(project: Path) -> None:
    """Require a clean branch that can only fast-forward before a release."""
    run(["git", "fetch", "--prune"], project)
    if run(["git", "status", "--porcelain"], project, capture=True).strip():
        raise RuntimeError("working tree is dirty")
    counts = run(["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"],
                 project, capture=True).split()
    if len(counts) != 2 or counts[1] != "0":
        raise RuntimeError("branch is ahead of or diverges from its upstream")
    run(["git", "pull", "--ff-only"], project)


def version(project: Path) -> str:
    try:
        value = (project / "VERSION").read_text(encoding="utf-8-sig").splitlines()[0].strip()
    except (OSError, IndexError) as exc:
        raise RuntimeError("VERSION is missing or empty") from exc
    if not value:
        raise RuntimeError("VERSION is missing or empty")
    return value


def release_repository(project: Path, fallback_owner: str) -> str:
    """Use this clone's own remote, so sandbox and production stay separate."""
    url = run(["git", "remote", "get-url", "origin"], project, capture=True).strip()
    match = re.search(r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$", url)
    if match:
        return match.group(1)
    return f"{fallback_owner}/{project.name}"


def require_github_auth() -> None:
    """Fail before touching any project when this machine cannot create releases."""
    result = subprocess.run(["gh", "api", "user"], text=True,
                            capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(
            "GitHub CLI cannot authenticate to the API. Run: "
            "gh auth login --hostname github.com --git-protocol ssh --web --scopes repo")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Create source releases from current workspace clones.")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--all", action="store_true", help="release every declared project with VERSION")
    choice.add_argument("--only", nargs="+", metavar="PROJECT", help="release these canonical projects")
    parser.add_argument("--notes", default="Source release for {project} {version}.",
                        help="release text; {project} and {version} are expanded")
    parser.add_argument("--owner", default="morfredus", help="GitHub repository owner")
    parser.add_argument("--dry-run", action="store_true", help="show the release plan without GitHub writes")
    args = parser.parse_args(argv)

    try:
        workspace = Workspace(HERE)
    except WorkspaceError as exc:
        print(exc, file=sys.stderr)
        return 2
    try:
        require_github_auth()
    except RuntimeError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    # The conductor is deliberately absent from ecosystem.json: it is not a
    # runtime component. It nevertheless has a VERSION and must therefore be
    # included in the all-project source release workflow.
    tool_project = Project(name=HERE.name.split("_", 1)[0], path=HERE)
    projects = [*workspace.projects(), tool_project]
    requested = set(args.only or [])
    available = {project.name: project for project in projects}
    unknown = requested - set(available)
    if unknown:
        print(f"Unknown project(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    failures = 0
    for project in projects:
        if not args.all and project.name not in requested:
            continue
        if not project.exists or not (project.path / ".git").is_dir():
            print(f"[SKIP] {project.name}: not cloned")
            continue
        print(f"\n== {project.name} ==")
        try:
            current = version(project.path)
            preflight(project.path)
            tag = f"v{current}"
            repo = release_repository(project.path, args.owner)
            seen = subprocess.run(["gh", "release", "view", tag, "--repo", repo],
                                  cwd=project.path, text=True, capture_output=True)
            if seen.returncode == 0:
                print(f"already released: {repo} {tag}")
                continue
            notes = args.notes.format(project=project.name, version=current)
            command = ["gh", "release", "create", tag, "--repo", repo,
                       "--title", f"{project.name} - v{current}", "--notes", notes]
            if args.dry_run:
                print("would create: " + " ".join(command))
            else:
                run(command, project.path)
        except (RuntimeError, ValueError) as exc:
            failures += 1
            print(f"[REFUSED] {exc}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
