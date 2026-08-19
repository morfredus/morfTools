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

The deliverables land in one shared distribution directory. Feeding them to the
morfPackages GitHub Releases is a separate step (Phase 5), kept out of here on
purpose: this script only PRODUCES, it does not publish.

    python3 package-all.py [--dry-run] [--force] [--out DIR] [--only NAME ...]
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
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


def _run(cmd: list, cwd: Path | None = None) -> int:
    print(f"    $ {' '.join(str(c) for c in cmd)}")
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False).returncode


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


def _package_project_script(project, target, out: Path, dry: bool) -> str:
    """Run the project's own package script declared on the target."""
    script = target.package.get("script")
    if not script:
        return "no package script declared"
    script_path = project.path / script
    if not script_path.is_file():
        return f"declared script missing: {script}"
    if script.endswith(".ps1"):
        launcher = ["pwsh", "-File", str(script_path)]
    else:
        launcher = ["bash", str(script_path)]
    if dry:
        print(f"    would run: {' '.join(launcher)}  (output owned by the project)")
        return "planned"
    # The script owns its output location; a project is expected to write beside
    # its build. Collecting it into `out` is left to the script's own convention
    # or to a later standardisation -- Phase 4 runs it, honestly reporting where
    # ownership lies.
    return "ran (project-owned output)" if _run(launcher, project.path) == 0 else "FAILED"


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
    parser.add_argument("--out", type=Path, default=HERE.parent / "dist",
                        help="shared distribution directory (default: <workspace>/dist)")
    parser.add_argument("--only", nargs="*", default=None, metavar="NAME",
                        help="restrict to these project names")
    args = parser.parse_args(argv)

    try:
        ws = Workspace(HERE)
    except WorkspaceError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    cur_os, cur_arch = current_platform()
    out = args.out.resolve()
    print(f"Platform: {cur_os}-{cur_arch}   Output: {out}"
          + ("   [dry-run]" if args.dry_run else ""))

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

        for target in native:
            expected = _expected_name(project, target, svc, version)
            if expected and (out / expected).exists() and not args.force:
                print(f"  {target.name}: already present ({expected}), skipped "
                      "(--force to rebuild)")
                skipped += 1
                continue

            print(f"  {target.name} -> provider {target.provider}, "
                  f"format {target.package.get('format')}")
            if target.provider == "morfdeploy":
                result = _package_service(project, target, out, args.dry_run)
            elif declared.type == "firmware":
                result = _package_firmware(project, target, out, version, args.dry_run)
            elif target.provider == "project":
                result = _package_project_script(project, target, out, args.dry_run)
            else:
                result = f"no producer for provider '{target.provider}'"
            print(f"    -> {result}")
            if result in ("built",):
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
