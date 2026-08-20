#!/usr/bin/env python3
"""package-all: build every project's deliverable for THIS machine, in one command.

Deliberately OUTSIDE morf.py: packaging is its own job, and morfTools stays the
conductor -- it holds no packaging recipe. Each project declares, in
morfproject.json, its type and its targets; this script reads those declarations,
keeps only the targets NATIVE to the current OS+architecture (no cross-compilation
is assumed), and hands each to the right producer:

  - packaging.provider morfdeploy -> the project's `service.py package`, which
    builds a provenance-checked binary and produces the .deb / .zip;
  - packaging.provider project    -> the project's own package script, declared on
    the target (a .deb, an AppImage, a Windows .zip...);
  - a firmware target (build.tool platformio) -> a PlatformIO build, its
    firmware.bin renamed with project and version, when the toolchain is present;
  - packaging.provider none, or no native target -> reported and skipped.

The deliverables land in one shared distribution directory, then the verified
ones are uploaded to the matching private morfPackages GitHub Release. Git only
holds the durable scripts and contract: package files are release assets.

    python3 package-all.py [--sync] [--dry-run] [--force] [--out DIR] [--only NAME ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import re
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

from morftools import morfproject  # noqa: E402
from morftools.workspace import Workspace, WorkspaceError  # noqa: E402


def current_platform() -> tuple:
    """(os, arch) of THIS machine, in the same names a target's platform uses."""
    system = platform.system()
    if system == "Windows":
        return "windows", "x86_64"
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine in ("x86_64", "amd64"):
        arch = "x86_64"
    else:
        arch = machine or "unknown"
    plat = "linux" if system == "Linux" else system.lower()
    return plat, arch


def _read_first_line(path: Path) -> str | None:
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        return lines[0].strip() if lines else None
    except OSError:
        return None


def _service_name(project_path: Path) -> str | None:
    """The service_name declared in service.json (a .deb/.zip is named after it)."""
    import json
    try:
        data = json.loads((project_path / "service.json").read_text(encoding="utf-8-sig"))
        return data.get("service_name")
    except (OSError, ValueError):
        return None


def _expected_name(project, target, svc: str | None, version: str) -> str | None:
    """The deliverable morfdeploy would produce, for the idempotency check.

    Only predictable for morfdeploy services (a stable naming); project scripts
    own their output name, so their idempotency is left to the script (and, later,
    to morfPackages' checksum/provenance check).
    """
    if target.provider != "morfdeploy" or not svc:
        return None
    fmt = target.package.get("format")
    if fmt == "deb":
        arch = target.package.get("architecture") or target.arch
        return f"{svc}-{version}-linux-{arch}.deb"
    if fmt == "zip":
        return f"{svc}-{version}-windows-x86_64.zip"
    return None


def _script_artifact_name(project, target, version: str) -> str:
    """Canonical shared-dist name for an artifact made by a project script."""
    fmt = target.package.get("format")
    arch = target.package.get("architecture") or target.arch
    return f"{project.name.lower()}-{version}-{target.os}-{arch}.{fmt}"


def _run(cmd: list, cwd: Path | None = None) -> int:
    print(f"    $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False).returncode


def _sync_published(project, version: str, out: Path, dry: bool) -> str:
    """Retrieve this release's existing assets before adding local output.

    The sibling's name is derived from this tools directory, so the same source
    works in both workspaces without embedding a workspace-specific suffix.
    """
    packages = HERE.parent / HERE.name.replace("Tools", "Packages")
    script = packages / "scripts" / "release.py"
    if not script.is_file():
        return f"morfPackages script missing: {script}"
    cmd = [sys.executable, str(script), "sync", "--project", project.name,
           "--version", version, "--out", str(out)]
    if dry:
        print(f"    would sync: {' '.join(str(c) for c in cmd)}")
        return "planned"
    return "synced" if _run(cmd, packages) == 0 else "FAILED (sync)"


def _packages_script() -> Path:
    """Resolve the sibling through the tools name, never a fixed workspace path."""
    return HERE.parent / HERE.name.replace("Tools", "Packages") / "scripts" / "release.py"


def _release_preflight(dry: bool) -> str:
    """Fetch and fast-forward morfPackages before producing any new asset."""
    script = _packages_script()
    if not script.is_file():
        return f"morfPackages script missing: {script}"
    cmd = [sys.executable, str(script), "preflight"]
    if dry:
        print(f"  would preflight: {' '.join(str(c) for c in cmd)}")
        return "planned"
    return "ready" if _run(cmd, script.parent.parent) == 0 else "FAILED (preflight)"


def _publish_release(project, version: str, artifact: Path, notes: str | None, dry: bool) -> str:
    """Upload an artifact only through its checked morfPackages release."""
    script = _packages_script()
    sidecar = artifact.with_name(f"{artifact.name}.metadata.json")
    cmd = [sys.executable, str(script), "publish", "--project", project.name,
           "--version", version, "--metadata", str(sidecar)]
    if notes:
        cmd += ["--notes", notes]
    if dry:
        print(f"    would publish: {' '.join(str(c) for c in cmd)}")
        return "planned"
    return "published" if _run(cmd, script.parent.parent) == 0 else "FAILED (publish)"


def _latest_changelog_summary(project_path: Path, version: str) -> str | None:
    """Return at most three useful items from this version's changelog section.

    A GitHub release should point to the changes without becoming a second copy
    of CHANGELOG.md.  The parser deliberately understands only the common
    Markdown structure used by the projects: a level-two version heading and
    bullet items under it.  If a project writes prose instead, its first two
    meaningful lines remain a concise fallback.
    """
    changelog = project_path / "CHANGELOG.md"
    try:
        lines = changelog.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return None

    heading = re.compile(rf"^##\s+\[?{re.escape(version)}\]?(?:\s|$)")
    start = next((index for index, line in enumerate(lines) if heading.match(line)), None)
    if start is None:
        return None
    section = []
    for line in lines[start + 1:]:
        if line.startswith("## "):
            break
        section.append(line.rstrip())

    bullets = []
    current = None
    for line in section:
        stripped = line.strip()
        if stripped.startswith(("- ", "* ")):
            if current:
                bullets.append(current)
            current = stripped[2:].strip()
        elif current and stripped and not stripped.startswith("#"):
            current = f"{current} {stripped}"
    if current:
        bullets.append(current)
    if bullets:
        return "\n".join(f"- {item}" for item in bullets[:3])

    prose = [line.strip() for line in section
             if line.strip() and not line.lstrip().startswith("#")]
    return "\n".join(prose[:2]) or None


def _project_release_notes(project, version: str, global_notes: str | None) -> str:
    """Build the first-release text, with a project note taking priority.

    RELEASE-NOTES.md is intentionally tiny and human-owned.  Its optional
    {{changelog_summary}} marker places the generated highlights exactly where
    the author wants them.  Without the marker they are appended, so every
    automatic release still points at the current changelog rather than copying
    it in full.  The existing command-line option remains an explicit global
    override for a one-off release campaign.
    """
    if global_notes:
        return global_notes.replace("{project}", project.name).replace("{version}", version)

    summary = _latest_changelog_summary(project.path, version)
    default = (f"## {project.name} {version}\n\n{summary}" if summary
               else f"## {project.name} {version}\n\nRelease package for this version.")
    notes_file = project.path / "RELEASE-NOTES.md"
    if not notes_file.is_file():
        return default
    try:
        custom = notes_file.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return default
    custom = custom.replace("{project}", project.name).replace("{version}", version)
    marker = "{{changelog_summary}}"
    if marker in custom:
        return custom.replace(marker, summary or "No changelog summary is available.")
    return f"{custom}\n\n{summary}" if custom and summary else (custom or default)


def _release_metadata(project, target, artifact: Path, version: str) -> str | None:
    """Write the immutable provenance sidecar consumed by morfPackages.

    This is deliberately a read-only Git check. Packaging must never turn a
    dirty or unprovable source tree into something publishable later.
    """
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project.path,
                            text=True, capture_output=True, check=False)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=project.path,
                           text=True, capture_output=True, check=False)
    if commit.returncode or dirty.returncode:
        return "Git provenance cannot be read"
    if dirty.stdout.strip():
        return "source tree is dirty; provenance sidecar refused"

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    metadata = {
        "project": project.name,
        "version": version,
        "name": artifact.name,
        "sha256": digest,
        "commit": commit.stdout.strip(),
        "dirty": False,
        "target": target.name,
        # Firmware targets describe their MCU with the OS field only.  It is
        # still a complete platform identity: use that value for the missing
        # architecture rather than emitting metadata which publishing rejects.
        "platform": {"os": target.os, "arch": target.arch or target.os},
        "format": target.package.get("format"),
        "built_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    sidecar = artifact.with_name(f"{artifact.name}.metadata.json")
    sidecar.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"    provenance: {sidecar.name}")
    return None


def _sidecar_matches_target(path: Path, target) -> bool:
    """Whether an existing sidecar can safely be reused for this target.

    Earlier firmware runs wrote an empty architecture. Treat such a sidecar as
    stale locally: the artifact is rebuilt and given fresh provenance before it
    reaches the publisher, rather than repeatedly sending known-invalid JSON.
    """
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    platform_data = metadata.get("platform")
    expected_arch = target.arch or target.os
    return (isinstance(platform_data, dict)
            and platform_data.get("os") == target.os
            and platform_data.get("arch") == expected_arch)


def _new_artifact(out: Path, target, before: set[Path], expected: str | None) -> Path | None:
    """Find exactly the deliverable created for this target, never guess."""
    if expected:
        candidate = out / expected
        return candidate if candidate.is_file() else None
    extension = target.package.get("format")
    candidates = [path for path in out.glob(f"*.{extension}")
                  if path.is_file() and path not in before]
    return candidates[0] if len(candidates) == 1 else None


def _package_service(project, target, out: Path, dry: bool) -> str:
    """Delegate to the project's service.py package (morfdeploy does the work)."""
    entry = project.path / "service.py"
    if not entry.is_file():
        return "no service.py"
    cmd = [sys.executable, str(entry), "package", "--target", target.name,
           "--out", str(out)]
    if dry:
        print(f"    would run: {' '.join(str(c) for c in cmd)}")
        return "planned"
    return "built" if _run(cmd, project.path) == 0 else "FAILED"


def _package_project_script(project, target, out: Path, version: str, dry: bool) -> str:
    """Run a project-owned script and collect its one current deliverable.

    Older project scripts deliberately own their local ``dist`` directory.
    Keeping that convention is useful for direct use, while this conductor
    copies the matching, current-version artifact into its shared directory.
    The copy is renamed to the public packaging contract before provenance is
    written, so both paths remain useful without releasing an ambiguous file.
    """
    script = target.package.get("script")
    if not script:
        return "no package script declared"
    script_path = project.path / script
    if not script_path.is_file():
        return f"declared script missing: {script}"
    preset = target.build.get("preset")
    if not preset:
        return "no CMake preset declared for project packaging"
    cmake = shutil.which("cmake")
    if cmake is None:
        return "CMake not on this machine"
    if script.endswith(".ps1"):
        launcher = ["pwsh", "-File", str(script_path)]
    else:
        launcher = ["bash", str(script_path)]
    if dry:
        print(f"    would run: {cmake} --preset {preset}; {cmake} --build --preset {preset}; "
              f"{' '.join(launcher)} then collect its deliverable")
        return "planned"
    if _run([cmake, "--preset", preset], project.path) != 0:
        return "FAILED (configure)"
    if _run([cmake, "--build", "--preset", preset], project.path) != 0:
        return "FAILED (build)"
    if _run(launcher, project.path) != 0:
        return "FAILED"

    fmt = target.package.get("format")
    local_dist = project.path / "dist"
    candidates = sorted(
        (path for path in local_dist.iterdir()
         if path.is_file() and path.suffix.lstrip(".").lower() == fmt.lower()
         and version in path.name),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if local_dist.is_dir() else []
    if len(candidates) != 1:
        return "FAILED (project script did not produce one current deliverable)"
    out.mkdir(parents=True, exist_ok=True)
    artifact = out / _script_artifact_name(project, target, version)
    shutil.copy2(candidates[0], artifact)
    print(f"    collected: {artifact.name}")
    return "built"


def _package_firmware(project, target, out: Path, version: str, dry: bool) -> str:
    """Build the firmware and rename its .bin, when PlatformIO is available."""
    if shutil.which("pio") is None and shutil.which("platformio") is None:
        return "skipped (PlatformIO not on this machine)"
    env = target.build.get("env")
    if not env:
        return "no platformio env declared"
    pio = shutil.which("pio") or shutil.which("platformio")
    if dry:
        print(f"    would run: {pio} run -e {env}  then rename firmware.bin")
        return "planned"
    if _run([pio, "run", "-e", env], project.path) != 0:
        return "FAILED (build)"
    src = project.path / ".pio" / "build" / env / "firmware.bin"
    if not src.is_file():
        return "FAILED (firmware.bin not found)"
    out.mkdir(parents=True, exist_ok=True)
    dest = out / f"{project.name.lower()}-{version}-{target.name}.bin"
    shutil.copy2(src, dest)
    print(f"    built: {dest}")
    return "built"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build this machine's deliverables "
                                     "for every declared project.")
    parser.add_argument("--dry-run", action="store_true",
                        help="show the plan without building anything")
    parser.add_argument("--force", action="store_true",
                        help="build even a deliverable already present in --out")
    parser.add_argument("--sync", action="store_true",
                        help="download already published assets before local packaging")
    parser.add_argument("--no-publish", action="store_true",
                        help="build locally and write metadata without publishing assets")
    parser.add_argument("--release-notes",
                        help="text for a newly created morfPackages release")
    parser.add_argument("--out", type=Path, default=HERE.parent / "dist",
                        help="shared distribution directory (default: <workspace>/dist)")
    parser.add_argument("--only", nargs="*", default=None, metavar="NAME",
                        help="restrict to these project names")
    args = parser.parse_args(argv)

    if args.sync and args.no_publish:
        parser.error("--sync cannot be combined with --no-publish")

    try:
        ws = Workspace(HERE)
    except WorkspaceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    cur_os, cur_arch = current_platform()
    out = args.out.resolve()
    print(f"Platform: {cur_os}-{cur_arch}   Output: {out}"
          + ("   [dry-run]" if args.dry_run else ""))

    if args.no_publish:
        print("morfPackages preflight -> deferred (build-only mode)")
    else:
        preflight = _release_preflight(args.dry_run)
        print(f"morfPackages preflight -> {preflight}")
        if preflight.startswith("FAILED") or preflight.startswith("morfPackages script missing"):
            return 2

    produced, skipped, failed = 0, 0, 0
    for project in ws.projects():
        if args.only and project.name not in args.only:
            continue
        if not project.exists:
            continue
        try:
            declared = morfproject.load(project.path)
        except morfproject.MorfProjectError as exc:
            print(f"\n== {project.name} ==\n  [WARN] {exc}")
            continue
        if declared is None:
            continue   # not onboarded onto the contract yet

        print(f"\n== {project.name} ({declared.type}, provider {declared.provider}) ==")
        if declared.provider == "none":
            print("  not packaged (provider none).")
            continue

        # A native binary target is selected when its os+arch is this machine's;
        # a firmware target (built by PlatformIO, which cross-builds to the MCU)
        # is selected on any host that has the toolchain, regardless of os/arch.
        def buildable_here(t) -> bool:
            if t.build.get("tool") == "platformio":
                return bool(shutil.which("pio") or shutil.which("platformio"))
            return t.os == cur_os and t.arch == cur_arch

        native = [t for t in declared.targets.values() if buildable_here(t)]
        if not native:
            others = ", ".join(sorted(declared.target_names())) or "(none)"
            if declared.type == "firmware":
                print(f"  firmware targets need PlatformIO (absent here). "
                      f"Declared: {others}")
            else:
                print(f"  no target native to {cur_os}-{cur_arch}. Declared: {others}")
            continue

        svc = _service_name(project.path)
        version = _read_first_line(project.path / "VERSION") or "0.0.0"
        notes = _project_release_notes(project, version, args.release_notes)

        if args.sync:
            result = _sync_published(project, version, out, args.dry_run)
            print(f"  release sync -> {result}")
            if result.startswith("FAILED") or result.startswith("morfPackages script missing"):
                failed += 1
                continue

        for target in native:
            expected = _expected_name(project, target, svc, version)
            if declared.type == "firmware":
                # Firmware names are fully deterministic as well. Keeping an
                # expected path lets a second run recover a binary produced
                # before provenance support without treating it as ambiguous.
                expected = f"{project.name.lower()}-{version}-{target.name}.bin"
            elif target.provider == "project":
                # Project-owned scripts are collected under this canonical name.
                # It remains the authoritative candidate even when --sync just
                # downloaded an existing asset with the same name.
                expected = _script_artifact_name(project, target, version)
            if expected and (out / expected).exists() and not args.force:
                artifact = out / expected
                sidecar = artifact.with_name(f"{artifact.name}.metadata.json")
                if sidecar.is_file() and _sidecar_matches_target(sidecar, target):
                    if args.no_publish:
                        print(f"  {target.name}: already present ({expected}), "
                              "kept for final publication")
                        skipped += 1
                        continue
                    print(f"  {target.name}: already present ({expected}), publishing "
                          "its verified metadata")
                    result = _publish_release(project, version, artifact,
                                              notes, args.dry_run)
                    print(f"    -> {result}")
                    if result == "published":
                        produced += 1
                    elif result.startswith("FAILED"):
                        failed += 1
                    continue
                if sidecar.is_file():
                    print(f"  {target.name}: existing provenance is stale or incomplete; "
                          "rebuilding it")
                else:
                    print(f"  {target.name}: already present ({expected}) without provenance; "
                          "rebuilding it")

            print(f"  {target.name} -> provider {target.provider}, "
                  f"format {target.package.get('format')}")
            before = set(out.glob(f"*.{target.package.get('format')}")) if out.exists() else set()
            if target.provider == "morfdeploy":
                result = _package_service(project, target, out, args.dry_run)
            elif declared.type == "firmware":
                result = _package_firmware(project, target, out, version, args.dry_run)
            elif target.provider == "project":
                result = _package_project_script(project, target, out, version, args.dry_run)
            else:
                result = f"no producer for provider '{target.provider}'"
            if result == "built":
                artifact = _new_artifact(out, target, before, expected)
                if artifact is None:
                    result = "FAILED (deliverable ambiguous; provenance not written)"
                else:
                    error = _release_metadata(project, target, artifact, version)
                    if error:
                        result = f"FAILED ({error})"
                    else:
                        result = ("built locally (publication deferred)"
                                  if args.no_publish else
                                  _publish_release(project, version, artifact,
                                                   notes, args.dry_run))
            print(f"    -> {result}")
            if result in ("published", "built locally (publication deferred)"):
                produced += 1
            elif result.startswith("FAILED"):
                failed += 1
            elif result in ("planned",):
                pass

    print(f"\n{produced} built, {skipped} already present, {failed} failed"
          + ("  (dry-run: nothing was built)" if args.dry_run else "")
          + f".\nDeliverables in {out}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
