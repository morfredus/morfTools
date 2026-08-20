#!/usr/bin/env python3
"""Publish already-built packages from dist, without rebuilding any project.

Every sidecar is still validated by morfPackages before GitHub receives an
asset.  A successful publication updates both the distribution release and the
matching source-project release, which is the release an end user normally
opens first.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

from morftools.workspace import Workspace, WorkspaceError  # noqa: E402


def version(project: Path) -> str:
    try:
        return project.joinpath("VERSION").read_text(encoding="utf-8-sig").splitlines()[0].strip()
    except (OSError, IndexError) as exc:
        raise RuntimeError("VERSION is missing or empty") from exc


def changelog_summary(project: Path, current: str) -> str | None:
    """Keep the GitHub release short while retaining useful change highlights."""
    try:
        lines = project.joinpath("CHANGELOG.md").read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None
    heading = re.compile(rf"^##\s+\[?{re.escape(current)}\]?(?:\s|$)")
    start = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return None
    bullets = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        value = line.strip()
        if value.startswith(("- ", "* ")):
            bullets.append(value)
    return "\n".join(bullets[:3]) or None


def release_notes(project, current: str, override: str | None) -> str:
    if override:
        return override.replace("{project}", project.name).replace("{version}", current)
    summary = changelog_summary(project.path, current)
    default = (f"## {project.name} {current}\n\n{summary}" if summary
               else f"## {project.name} {current}\n\nRelease package for this version.")
    path = project.path / "RELEASE-NOTES.md"
    if not path.is_file():
        return default
    try:
        text = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return default
    text = text.replace("{project}", project.name).replace("{version}", current)
    if "{{changelog_summary}}" in text:
        return text.replace("{{changelog_summary}}", summary or "No changelog summary is available.")
    return f"{text}\n\n{summary}" if text and summary else (text or default)


def metadata_for(out: Path, project: str, current: str) -> list[Path]:
    """Select only sidecars that explicitly describe this exact release."""
    paths = []
    for path in sorted(out.glob("*.metadata.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("project") == project and data.get("version") == current:
            paths.append(path)
    return paths


def run(command: list[str], cwd: Path) -> None:
    print("$ " + " ".join(str(item) for item in command))
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode})")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Publish validated dist assets without rebuilding.")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--all", action="store_true", help="publish every current project found in dist")
    choice.add_argument("--only", nargs="+", metavar="PROJECT", help="publish these projects")
    parser.add_argument("--out", type=Path, default=HERE.parent / "dist",
                        help="shared distribution directory")
    parser.add_argument("--notes", help="temporary text for every selected release")
    parser.add_argument("--dry-run", action="store_true", help="show what would be published")
    args = parser.parse_args(argv)

    try:
        workspace = Workspace(HERE)
    except WorkspaceError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    output = args.out.resolve()
    packages = HERE.parent / HERE.name.replace("Tools", "Packages")
    script = packages / "scripts" / "release.py"
    if not script.is_file():
        print(f"REFUSED: morfPackages script missing: {script}", file=sys.stderr)
        return 2
    requested = set(args.only or [])
    available = {project.name: project for project in workspace.projects()}
    unknown = requested - set(available)
    if unknown:
        print(f"REFUSED: unknown project(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    failures = 0
    published = 0
    for project in workspace.projects():
        if not args.all and project.name not in requested:
            continue
        if not project.exists:
            print(f"[SKIP] {project.name}: project is not cloned")
            continue
        try:
            current = version(project.path)
            sidecars = metadata_for(output, project.name, current)
            if not sidecars:
                print(f"[SKIP] {project.name} {current}: no matching sidecar in {output}")
                continue
            notes = release_notes(project, current, args.notes)
            command = [sys.executable, str(script), "publish", "--project", project.name,
                       "--version", current]
            for sidecar in sidecars:
                command += ["--metadata", str(sidecar)]
            command += ["--notes", notes]
            print(f"\n== {project.name} {current} ==")
            if args.dry_run:
                print("would publish: " + " ".join(command))
            else:
                run(command, packages)
            published += 1
        except RuntimeError as exc:
            failures += 1
            print(f"[REFUSED] {project.name}: {exc}", file=sys.stderr)
    print(f"\n{published} project(s) published, {failures} failed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
