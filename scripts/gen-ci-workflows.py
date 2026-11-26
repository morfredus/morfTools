#!/usr/bin/env python3
"""gen-ci-workflows: write the GitHub Actions workflows of every morfSystem project.

One generator instead of one hand-written workflow per repository: the projects share
the same build (CMake presets, Qt, Debian/Ubuntu and MSYS2 packages) and the same
packaging chain, so a fix made here reaches all of them with one more run.

For each project that declares packaging targets in morfproject.json, it writes:

  .github/workflows/ci.yml        build + ctest on Linux x86_64 (Ubuntu 24.04 = Qt 6.4,
                                  the parc floor), Linux arm64 and Windows (MSYS2 UCRT64)
  .github/workflows/packages.yml  the deliverables as artifacts (push to main + manual)
  scripts/ci/build-deb-container.sh   .deb built in a Debian Trixie container (Linux)

and adds a `package.ci` block to every target a CI run can supply, so that
package-all.py takes the packages of the run of the released commit instead of
compiling them (see docs/WORKFLOW-PACKAGING.md). Three kinds of project:

  cmake-app   provider project, presets + scripts/linux/package-deb.sh + package-win.ps1
  service     provider morfdeploy: `service.py package --target ...`
  firmware    PlatformIO (pio run -e <env>)

Build dependencies are read from the project's CMakeLists.txt (find_package), never
listed by hand. Nothing is written without --write.

    python3 scripts/gen-ci-workflows.py [--only NAME ...] [--write] [--bump] [--root DIR]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "lib"))
from morftools import morfproject  # noqa: E402

TODAY = date.today().isoformat()

# --- build dependency maps (from find_package / Qt components) ----------------------
QT_APT = {"Charts": "qt6-charts-dev", "SerialPort": "qt6-serialport-dev",
          "Svg": "qt6-svg-dev", "WebSockets": "qt6-websockets-dev"}
QT_PACMAN = {"Charts": "qt6-charts", "SerialPort": "qt6-serialport",
             "Svg": "qt6-svg", "WebSockets": "qt6-websockets"}
LIB_APT = {"openssl": "libssl-dev", "libssh2": "libssh2-1-dev",
           "nlohmann_json": "nlohmann-json3-dev", "sqlite3": "libsqlite3-dev",
           "zlib": "zlib1g-dev", "pkgconfig": "pkg-config"}
LIB_PACMAN = {"openssl": "openssl", "libssh2": "libssh2",
              "nlohmann_json": "nlohmann-json", "sqlite3": "sqlite3",
              "zlib": "zlib", "pkgconfig": "pkgconf"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.is_file() else ""


def cmake_needs(root: Path) -> tuple[set, set]:
    """(Qt components, third-party libraries) the project's CMakeLists.txt asks for."""
    text = read(root / "CMakeLists.txt")
    qt, libs = set(), set()
    for match in re.finditer(r"find_package\(\s*Qt6\b([^)]*)\)", text, re.I):
        qt.update(re.findall(r"\b[A-Z][A-Za-z]+\b", match.group(1).replace("REQUIRED", "")
                             .replace("QUIET", "").replace("COMPONENTS", "")
                             .replace("CONFIG", "")))
    for match in re.finditer(r"find_package\(\s*([A-Za-z0-9_]+)", text, re.I):
        name = match.group(1).lower()
        if name in ("openssl", "libssh2", "nlohmann_json", "sqlite3", "zlib", "pkgconfig"):
            libs.add(name)
    if re.search(r"pkg_check_modules\([^)]*libssh2", text, re.I):
        libs.add("libssh2")
    if "pkg_check_modules" in text:
        libs.add("pkgconfig")
    return qt, libs


def apt_packages(root: Path) -> list:
    qt, libs = cmake_needs(root)
    pkgs = ["cmake", "ninja-build", "g++", "pkg-config", "git", "python3",
            "qt6-base-dev", "qt6-tools-dev", "qt6-tools-dev-tools", "qt6-l10n-tools",
            "libgl1-mesa-dev", "libxkbcommon-dev"]
    pkgs += [QT_APT[c] for c in sorted(qt) if c in QT_APT]
    pkgs += [LIB_APT[x] for x in sorted(libs)]
    if "Sql" in qt:
        pkgs.append("libqt6sql6-sqlite")        # the SQLite driver, needed by the tests
    return sorted(set(pkgs), key=lambda p: (pkgs.index(p)))


def pacman_packages(root: Path, service: bool) -> list:
    qt, libs = cmake_needs(root)
    pre = "mingw-w64-ucrt-x86_64-"
    pkgs = [pre + n for n in ("gcc", "cmake", "ninja", "qt6-base", "qt6-tools")]
    pkgs += [pre + QT_PACMAN[c] for c in sorted(qt) if c in QT_PACMAN]
    pkgs += [pre + LIB_PACMAN[x] for x in sorted(libs)]
    if service:
        # git: the packaging refuses to build without proof of the sources' state (provenance).
        pkgs += [pre + "python", "git"]
    return pkgs + ["diffutils"]


# --- project description ------------------------------------------------------------
class Project:
    def __init__(self, root: Path):
        self.root = root
        self.name = root.name[:-len("_travail")] if root.name.endswith("_travail") else root.name
        self.declared = morfproject.load(root)
        self.kind = self._kind()
        self.version = read(root / "VERSION").splitlines()[0].strip() if (root / "VERSION").is_file() else ""

    @property
    def has_packages(self) -> bool:
        """False for a firmware that compiles private values in (include/secrets.h).

        Such a binary built in CI would carry the example's Wi-Fi credentials, API key or no
        admin token: unusable (or unsafe) as a release. The CI then only checks that the
        firmware compiles and its tests pass; the release binaries stay built locally.
        """
        if self.kind != "firmware":
            return True
        for folder in ("src", "include"):
            for path in (self.root / folder).rglob("*"):
                if path.is_file() and path.suffix in (".h", ".hpp", ".cpp", ".c", ".ino") \
                        and not path.name.startswith("secrets") \
                        and "secrets.h" in read(path):
                    return False
        return True

    def _kind(self):
        d = self.declared
        if d is None or not d.targets:
            return None
        if d.type == "firmware":
            return "firmware"
        if d.provider == "morfdeploy" and (self.root / "service.py").is_file():
            return "service"
        if d.provider == "project" and any(t.build.get("preset") for t in d.targets.values()):
            return "cmake-app"
        return None

    def targets(self, os_: str, arch: str | None = None) -> list:
        return [t for t in self.declared.targets.values()
                if t.os == os_ and (arch is None or t.arch == arch)]

    @property
    def service_name(self) -> str:
        try:
            return json.loads(read(self.root / "service.json")).get("service_name") or self.name.lower()
        except ValueError:
            return self.name.lower()

    @property
    def slug(self) -> str:
        return self.name.lower()

    def preset_dirs(self) -> dict:
        try:
            data = json.loads(read(self.root / "CMakePresets.json"))
        except ValueError:
            return {}
        return {c["name"]: c.get("binaryDir", "").replace("${sourceDir}/", "")
                for c in data.get("configurePresets", [])}

    def deb_command(self) -> str:
        """Package name of the .deb (the CMD variable of package-deb.sh)."""
        match = re.search(r'^CMD="([^"]+)"', read(self.root / "scripts/linux/package-deb.sh"), re.M)
        return match.group(1) if match else self.slug

    def win_name(self) -> str:
        """Prefix of the Windows deliverables (<Name>-<version>-win64...)."""
        match = re.search(r'\$name\s*=\s*"([A-Za-z0-9]+)-\$Version-win64"',
                          read(self.root / "scripts/windows/package-win.ps1"))
        return match.group(1) if match else self.name


# --- workflow text --------------------------------------------------------------------
def _yaml_list(items: list, indent: int) -> str:
    pad = " " * indent
    return (" \\\n" + pad).join(items)


def ci_yml(p: Project) -> str:
    d = p.declared
    dirs = p.preset_dirs()
    linux_x64 = [t for t in p.targets("linux", "x86_64")]
    linux_arm = [t for t in p.targets("linux", "arm64")]
    windows = p.targets("windows")
    out = [f"""# Pull-request check: compile and run the ctest suite of {p.name}.
#
# Linux x86_64 runs on Ubuntu 24.04, which ships Qt 6.4.2: the parc's minimum Qt. A green
# run there proves the code does not use a newer Qt API. Linux arm64 and Windows (MSYS2
# UCRT64) run in parallel. The result shows as a check on the PR; the ctest output is also
# written to the run summary.
#
# The repository is public, so runner minutes are not a constraint. A newer commit cancels
# the run of the same ref, and documentation-only changes do not trigger it. Packages are
# NOT built here (see packages.yml).
# Generated by morfTools scripts/gen-ci-workflows.py: change the generator, not this file.
name: CI

on:
  pull_request:
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/FUNDING.yml"
      - ".github/ISSUE_TEMPLATE/**"
  push:
    branches: [main, dev]
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/FUNDING.yml"
      - ".github/ISSUE_TEMPLATE/**"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:"""]
    if p.kind == "firmware":
        return ci_firmware_yml(p)
    rows = []
    if linux_x64:
        rows.append(("Linux x86_64, Qt 6.4", "ubuntu-24.04", "linux", dirs.get("linux", "build")))
    if linux_arm:
        rows.append(("Linux arm64", "ubuntu-24.04-arm", "linux-arm64", dirs.get("linux-arm64", "build-arm64")))
    if rows:
        apt = _yaml_list(apt_packages(p.root), 12)
        out.append(f"""  build-test:
    name: Build and test (${{{{ matrix.name }}}})
    runs-on: ${{{{ matrix.os }}}}
    timeout-minutes: 25
    strategy:
      fail-fast: false
      matrix:
        include:""")
        for name, os_, preset, bdir in rows:
            out.append(f"""          - name: {name}
            os: {os_}
            preset: {preset}
            build_dir: {bdir}""")
        out.append(f"""    steps:
      - uses: actions/checkout@v4

      - name: Install build dependencies
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y -qq --no-install-recommends \\
            {apt}

      - name: Show the Qt version in use
        run: dpkg-query -W qt6-base-dev

      - name: Configure
        run: cmake --preset ${{{{ matrix.preset }}}}

      - name: Build
        run: cmake --build --preset ${{{{ matrix.preset }}}} --parallel

      - name: Test
        env:
          QT_QPA_PLATFORM: offscreen
        run: |
          set -o pipefail
          ctest --test-dir ${{{{ matrix.build_dir }}}} --output-on-failure --timeout 120 | tee ctest.log

      - name: Summarise tests in the run summary
        if: always()
        run: |
          {{
            echo '### ctest (${{{{ matrix.name }}}})'
            echo '```'
            tail -n 40 ctest.log 2>/dev/null || echo 'no ctest output (build failed?)'
            echo '```'
          }} >> "$GITHUB_STEP_SUMMARY"

      - name: Keep the test log on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: ctest-log-${{{{ matrix.preset }}}}
          path: |
            ctest.log
            ${{{{ matrix.build_dir }}}}/Testing/Temporary/LastTest.log
          if-no-files-found: ignore
          retention-days: 7
""")
    if windows:
        out.append(windows_job("build-test-windows", "Build and test (Windows, MSYS2 UCRT64)", p,
                               dirs.get("mingw", "build-mingw"), package=False))
    return "\n".join(out).rstrip() + "\n"


def windows_job(job: str, title: str, p: Project, bdir: str, package: bool) -> str:
    service = p.kind == "service"
    pac = (chr(10) + " " * 12).join(pacman_packages(p.root, service))
    steps = f"""  {job}:
    name: {title}
    runs-on: windows-latest
    timeout-minutes: 40
    steps:
      - uses: actions/checkout@v4

      - name: MSYS2 UCRT64 toolchain
        uses: msys2/setup-msys2@v2
        with:
          msystem: UCRT64
          update: true
          install: >-
            {pac}

      - name: Build and test (preset mingw)
        shell: msys2 {{0}}
        run: |
          export QT_ROOT="$(cygpath -m /ucrt64)"
          export QT_QPA_PLATFORM=offscreen
          cmake --preset mingw
          cmake --build --preset mingw --parallel
          # windeployqt only deploys the "windows" platform plugin. Tests that force
          # QT_QPA_PLATFORM=offscreen would otherwise raise a modal "no Qt platform plugin"
          # dialog that nobody closes and hang the job. A timeout turns any hang into a failure.
          if [ -d {bdir}/platforms ]; then
            install -D "$MSYSTEM_PREFIX/share/qt6/plugins/platforms/qoffscreen.dll" \\
              {bdir}/platforms/qoffscreen.dll
          fi
          ctest --test-dir {bdir} --output-on-failure --timeout 120
"""
    if package and service:
        steps += """
      - name: Package (ZIP)
        shell: msys2 {0}
        run: |
          export QT_ROOT="$(cygpath -m /ucrt64)"
          # The checkout belongs to another user for MSYS2's git: allow it, or the provenance
          # (git status) cannot be read and the packaging refuses to build.
          git config --global --add safe.directory '*'
          python3 service.py package --target windows-x86_64-zip --out dist

      - uses: actions/upload-artifact@v4
        with:
          name: """ + f"{p.slug}-windows" + """
          path: dist/*.zip
          if-no-files-found: error
          retention-days: 14
"""
    elif package:
        steps += f"""
      - name: Package (ZIP, and installer when Inno Setup is present)
        shell: pwsh
        run: |
          if (-not (Get-Command ISCC.exe -ErrorAction SilentlyContinue) -and
              -not (Test-Path "${{env:ProgramFiles(x86)}}\\Inno Setup 6\\ISCC.exe")) {{
            choco install innosetup --no-progress -y
          }}
          ./scripts/windows/package-win.ps1

      - uses: actions/upload-artifact@v4
        with:
          name: {p.slug}-windows
          path: |
            dist/{p.win_name()}-*-win64.zip
            dist/{p.win_name()}-*-win64-setup.exe
          if-no-files-found: error
          retention-days: 14
"""
    return steps


def packages_yml(p: Project) -> str:
    if p.kind == "firmware":
        return packages_firmware_yml(p)
    d = p.declared
    dirs = p.preset_dirs()
    has_x64 = bool(p.targets("linux", "x86_64"))
    has_arm = bool(p.targets("linux", "arm64"))
    has_win = bool(p.targets("windows"))
    inputs = []
    if has_arm:
        inputs.append('      arm64:\n        description: "Build the arm64 .deb"\n'
                      '        type: boolean\n        default: true')
    if has_win:
        inputs.append('      windows:\n        description: "Build the Windows packages"\n'
                      '        type: boolean\n        default: true')
    dispatch = "  workflow_dispatch:" + (("\n    inputs:\n" + "\n".join(inputs)) if inputs else "")
    head = f"""# Builds the distributable packages of {p.name} as workflow artifacts.
#
# Triggers: every push to main (like ci.yml, so the run of the commit that a release tags
# already exists and is finished when the release is prepared) and a manual run. There is
# no tag trigger on purpose: the tag points at a commit already built by its push to main,
# and a tag run would only repeat it. Pull requests are covered by ci.yml, not here.
#
# The GitHub release itself is published by the morfSystem tooling (publish-releases): its
# package-all step looks for the successful run of this workflow for the released commit and
# takes the packages from it, building locally only what is missing. Artifacts are kept 14
# days. The arm64 .deb is built natively on GitHub's arm64 runner (no cross-compilation).
# Generated by morfTools scripts/gen-ci-workflows.py: change the generator, not this file.
name: Packages

on:
  push:
    branches: [main]
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/FUNDING.yml"
      - ".github/ISSUE_TEMPLATE/**"
{dispatch}

permissions:
  contents: read

concurrency:
  group: packages-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:"""
    jobs = []
    if has_x64:
        jobs.append(f"""  deb-amd64:
    name: .deb amd64
    runs-on: ubuntu-24.04
    timeout-minutes: 30
    steps:
      - uses: actions/checkout@v4
      - name: Build, test and package in Debian Trixie
        run: |
          docker run --rm -v "$PWD:/src" -w /src debian:trixie \\
            bash scripts/ci/build-deb-container.sh linux
      - uses: actions/upload-artifact@v4
        with:
          name: {p.slug}-deb-amd64
          path: dist/*.deb
          if-no-files-found: error
          retention-days: 14
""")
    if has_arm:
        jobs.append(f"""  deb-arm64:
    name: .deb arm64
    if: github.event_name != 'workflow_dispatch' || inputs.arm64
    runs-on: ubuntu-24.04-arm
    timeout-minutes: 40
    steps:
      - uses: actions/checkout@v4
      - name: Build, test and package in Debian Trixie arm64
        run: |
          docker run --rm -v "$PWD:/src" -w /src debian:trixie \\
            bash scripts/ci/build-deb-container.sh linux-arm64
      - uses: actions/upload-artifact@v4
        with:
          name: {p.slug}-deb-arm64
          path: dist/*.deb
          if-no-files-found: error
          retention-days: 14
""")
    if has_win:
        w = windows_job("windows", "Windows packages", p, dirs.get("mingw", "build-mingw"), package=True)
        w = w.replace("    runs-on: windows-latest",
                      "    if: github.event_name != 'workflow_dispatch' || inputs.windows\n"
                      "    runs-on: windows-latest", 1)
        jobs.append(w)
    return head + "\n" + "\n".join(jobs).rstrip() + "\n"


def container_script(p: Project) -> str:
    apt = _yaml_list(apt_packages(p.root), 4).replace("\\\n", "\\\n")
    apt = apt.replace("\\\n    ", "\\\n    ")
    if p.kind == "service":
        package = ('case "$PRESET" in\n'
                   '    linux)       TARGET=linux-amd64-deb ;;\n'
                   '    linux-arm64) TARGET=linux-arm64-deb ;;\n'
                   'esac\n'
                   '# service.py package builds (preset of the target), then writes the .deb.\n'
                   'python3 service.py package --target "$TARGET" --out dist')
        extra = "dpkg-dev"
    else:
        package = 'scripts/linux/package-deb.sh --build "$BUILD_DIR"'
        extra = "dpkg-dev imagemagick"
    return f"""#!/usr/bin/env bash
#
# {p.name} - build, test and package a .deb INSIDE a Debian Trixie container.
#
# Used by .github/workflows/packages.yml (amd64 and arm64, each on a runner of its own
# architecture). Trixie is the target of the Raspberry Pi packages: same glibc and same Qt 6.8
# as the Pi, so the Depends detected while packaging match what the Pi installs.
# Generated by morfTools scripts/gen-ci-workflows.py: change the generator, not this file.
#
# Usage (as root, in the container, from the repository root):
#   scripts/ci/build-deb-container.sh <linux|linux-arm64>
# The argument is the CMake preset: it picks the NATIVE build of the container's
# architecture (no cross-compilation, no sysroot to maintain).
set -euo pipefail

PRESET="${{1:?usage: build-deb-container.sh <linux|linux-arm64>}}"
case "$PRESET" in
    linux)       BUILD_DIR={p.preset_dirs().get('linux', 'build')} ;;
    linux-arm64) BUILD_DIR={p.preset_dirs().get('linux-arm64', 'build-arm64')} ;;
    *) echo "unknown preset: $PRESET" >&2; exit 1 ;;
esac

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends \\
    build-essential ca-certificates file {extra} \\
    {apt.replace(chr(10), chr(10))}
# The sources belong to the runner's user, not to root: git refuses them otherwise.
git config --global --add safe.directory "$PWD"

cmake --preset "$PRESET"
cmake --build --preset "$PRESET" --parallel "$(nproc)"
QT_QPA_PLATFORM=offscreen ctest --test-dir "$BUILD_DIR" --output-on-failure --timeout 120
{package}
ls -l dist/*.deb
"""


def firmware_envs(p: Project) -> list:
    return [(t.name, t.build.get("env")) for t in p.declared.targets.values()
            if t.build.get("tool") == "platformio" and t.build.get("env")]


def firmware_steps(p: Project, package: bool) -> str:
    ini = read(p.root / "platformio.ini")
    has_native = "[env:native]" in ini
    envs = firmware_envs(p)
    secret = ""
    if (p.root / "include/secrets_example.h").is_file():
        secret = ("      # secrets.h is never versioned: the example is enough to compile.\n"
                  "      - name: Placeholder secrets\n"
                  "        run: cp include/secrets_example.h include/secrets.h\n\n")
    steps = f"""    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - uses: actions/cache@v4
        with:
          path: ~/.platformio
          key: pio-${{{{ runner.os }}}}-${{{{ hashFiles('platformio.ini') }}}}

      - name: Install PlatformIO
        run: pip install platformio

{secret}"""
    if has_native and not package:
        steps += "      - name: Unit tests (native)\n        run: pio test -e native\n\n"
    for tname, env in envs:
        steps += f"      - name: Build {env}\n        run: pio run -e {env}\n\n"
    if package:
        copy = "\n".join(
            f"          cp .pio/build/{env}/firmware.bin dist/{p.slug}-\"$VERSION\"-{tname}.bin"
            for tname, env in envs)
        steps += f"""      - name: Collect the firmware
        run: |
          VERSION="$(head -n1 VERSION | tr -d '[:space:]')"
          mkdir -p dist
{copy}

      - uses: actions/upload-artifact@v4
        with:
          name: {p.slug}-firmware
          path: dist/*.bin
          if-no-files-found: error
          retention-days: 14
"""
    return steps.rstrip() + "\n"


def ci_firmware_yml(p: Project) -> str:
    return f"""# Pull-request check: compile the firmware of {p.name} with PlatformIO (and run the native
# unit tests when the project has them). Nothing is flashed.
# Generated by morfTools scripts/gen-ci-workflows.py: change the generator, not this file.
name: CI

on:
  pull_request:
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/FUNDING.yml"
      - ".github/ISSUE_TEMPLATE/**"
  push:
    branches: [main, dev]
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/FUNDING.yml"
      - ".github/ISSUE_TEMPLATE/**"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: ci-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  build:
    name: Build firmware
    runs-on: ubuntu-24.04
    timeout-minutes: 30
{firmware_steps(p, package=False)}"""


def packages_firmware_yml(p: Project) -> str:
    return f"""# Builds the firmware binaries of {p.name} as workflow artifacts (push to main + manual run).
# package-all takes them from the run of the released commit instead of compiling them.
# Generated by morfTools scripts/gen-ci-workflows.py: change the generator, not this file.
name: Packages

on:
  push:
    branches: [main]
    paths-ignore:
      - "**.md"
      - "docs/**"
      - ".github/FUNDING.yml"
      - ".github/ISSUE_TEMPLATE/**"
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: packages-${{{{ github.ref }}}}
  cancel-in-progress: true

jobs:
  firmware:
    name: Firmware binaries
    runs-on: ubuntu-24.04
    timeout-minutes: 30
{firmware_steps(p, package=True)}"""


# --- morfproject.json: the package.ci blocks -------------------------------------------
def ci_block_for(p: Project, t) -> dict | None:
    fmt = t.package.get("format")
    arch = t.package.get("architecture") or t.arch
    if p.kind == "service":
        if fmt == "deb":
            return {"workflow": "packages.yml", "artifact": f"{p.slug}-deb-{arch}",
                    "file": f"{p.service_name}-{{version}}-linux-{arch}.deb"}
        if fmt == "zip":
            return {"workflow": "packages.yml", "artifact": f"{p.slug}-windows",
                    "file": f"{p.service_name}-{{version}}-windows-x86_64.zip"}
    elif p.kind == "cmake-app":
        if fmt == "deb":
            return {"workflow": "packages.yml", "artifact": f"{p.slug}-deb-{arch}",
                    "file": f"{p.deb_command()}_{{version}}_{arch}.deb"}
        if fmt == "zip":
            return {"workflow": "packages.yml", "artifact": f"{p.slug}-windows",
                    "file": f"{p.win_name()}-{{version}}-win64.zip"}
        if fmt == "exe":
            return {"workflow": "packages.yml", "artifact": f"{p.slug}-windows",
                    "file": f"{p.win_name()}-{{version}}-win64-setup.exe"}
    elif p.kind == "firmware" and fmt == "bin" and p.has_packages:
        return {"workflow": "packages.yml", "artifact": f"{p.slug}-firmware",
                "file": f"{p.slug}-{{version}}-{t.name}.bin"}
    return None


# A JSON string is one token, so a brace inside it ("{version}") never counts as structure.
_TOKEN = r'(?:[^{}"]|"[^"]*")'


def update_morfproject(p: Project) -> bool:
    """Insert (or refresh) `ci` in each target's package object, keeping the file's layout."""
    path = p.root / "morfproject.json"
    text = path.read_text(encoding="utf-8")
    original = text
    # Start from a file without any ci block, so a refresh never meets a nested object.
    text = re.sub(r',\s*"ci"\s*:\s*\{%s*\}' % _TOKEN, "", text)
    for name, t in p.declared.targets.items():
        block = ci_block_for(p, t)
        if block is None:
            continue
        compact = ('"ci": { "workflow": "%s", "artifact": "%s", "file": "%s" }'
                   % (block["workflow"], block["artifact"], block["file"]))
        # This target's package object: the first "package" after the target's own key.
        key = text.find('"%s"' % name)
        pkg = text.find('"package"', key) if key >= 0 else -1
        pattern = re.compile(r'("package"\s*:\s*\{)(%s*?)(\s*\})' % _TOKEN)
        match = pattern.match(text, pkg) if pkg >= 0 else None
        if not match:
            print(f"  [WARN] {p.name}: cannot place ci in target {name}")
            continue
        text = (text[:match.start()] + match.group(1) + match.group(2) + ", " + compact
                + match.group(3) + text[match.end():])
    if text != original:
        json.loads(text)
        path.write_text(text, encoding="utf-8", newline="\n")
        return True
    return False



# --- docs, version -------------------------------------------------------------------
README_EN = """## Continuous integration

GitHub Actions workflows live in `.github/workflows/` (generated by the morfTools script
`gen-ci-workflows.py`):

- **`ci.yml`**: on every pull request (and push to `main`/`dev`), builds and runs the tests on
  {platforms}. Documentation-only changes skip it and an outdated run is cancelled by a
  newer commit.
- **`packages.yml`**: on every push to `main` or a manual run (*Actions > Packages > Run
  workflow*), builds {deliverables}. Packages are workflow artifacts kept 14 days; releases are
  published by the morfSystem tooling, which takes the packages of the run of the released
  commit and builds locally only what is missing.

"""
README_FR = """## Intégration continue

Des workflows GitHub Actions vivent dans `.github/workflows/` (générés par le script morfTools
`gen-ci-workflows.py`) :

- **`ci.yml`** : à chaque pull request (et push sur `main`/`dev`), compile et lance les tests sous
  {platforms}. Les changements de documentation seule l'ignorent et un run périmé est annulé
  par un commit plus récent.
- **`packages.yml`** : à chaque push sur `main` ou en lancement manuel (*Actions > Packages >
  Run workflow*), construit {deliverables}. Les paquets sont des artefacts du workflow conservés
  14 jours ; les releases sont publiées par l'outillage morfSystem, qui prend les paquets du run
  du commit publié et ne compile en local que ce qui manque.

"""


def describe(p: Project) -> tuple[str, str, str, str]:
    if p.kind == "firmware":
        return ("PlatformIO (the firmware, plus the native tests when present)",
                "PlatformIO (le firmware, plus les tests natifs s'il y en a)",
                "the firmware binaries", "les binaires du firmware")
    en, fr, den, dfr = [], [], [], []
    if p.targets("linux", "x86_64"):
        en.append("Ubuntu 24.04 (Qt 6.4)"); fr.append("Ubuntu 24.04 (Qt 6.4)")
        den.append("the `.deb` amd64"); dfr.append("le `.deb` amd64")
    if p.targets("linux", "arm64"):
        en.append("Linux arm64"); fr.append("Linux arm64")
        den.append("the `.deb` arm64"); dfr.append("le `.deb` arm64")
    if p.targets("windows"):
        en.append("Windows (MSYS2 UCRT64)"); fr.append("Windows (MSYS2 UCRT64)")
        den.append("the Windows packages"); dfr.append("les paquets Windows")
    j = lambda xs, w: ", ".join(xs[:-1]) + f" {w} " + xs[-1] if len(xs) > 1 else xs[0]
    return j(en, "and"), j(fr, "et"), j(den, "and"), j(dfr, "et")


def bump(version: str) -> str:
    major, minor, _patch = version.split(".")
    return f"{major}.{int(minor) + 1}.0"


def apply_fix(p: Project, text: str) -> list:
    """Patch bump, badges and a `Fixed` CHANGELOG entry (the workflows were corrected)."""
    nl = chr(10)
    major, minor, patch = p.version.split(".")
    new = f"{major}.{minor}.{int(patch) + 1}"
    old = p.version
    (p.root / "VERSION").write_text(new + nl, encoding="utf-8", newline=nl)
    for name in ("README.md", "README.fr.md"):
        path = p.root / name
        content = path.read_text(encoding="utf-8")
        path.write_text(content.replace(f"version-{old}", f"version-{new}", 1),
                        encoding="utf-8", newline=nl)
    cl = p.root / "CHANGELOG.md"
    content = cl.read_text(encoding="utf-8")
    first = content.index("## [")
    entry = f"## [{new}] - {TODAY}" + nl*2 + "### Fixed" + nl*2 + f"- {text}" + nl*2
    cl.write_text(content[:first] + entry + content[first:], encoding="utf-8", newline=nl)
    return [f"version {old} -> {new}"]


def apply_docs(p: Project) -> list:
    """Version bump, badges, CHANGELOG entry and README sections. Returns what was done."""
    done = []
    new = bump(p.version)
    old = p.version
    (p.root / "VERSION").write_text(new + "\n", encoding="utf-8", newline="\n")
    for name in ("README.md", "README.fr.md"):
        path = p.root / name
        text = path.read_text(encoding="utf-8")
        if f"version-{old}" not in text:
            done.append(f"[WARN] {name}: badge version-{old} not found")
            continue
        text = text.replace(f"version-{old}", f"version-{new}", 1)
        pen, pfr, den, dfr = describe(p)
        section = (README_EN if name == "README.md" else README_FR).format(
            platforms=pen if name == "README.md" else pfr,
            deliverables=den if name == "README.md" else dfr)
        if not p.has_packages:
            # Only the ci.yml bullet: drop the packages.yml one (a paragraph ending at a blank line).
            section = re.sub(r"- \*\*`packages\.yml`\*\*.*?\n\n", "\n", section, flags=re.S)
        if "Continuous integration" not in text and "Intégration continue" not in text:
            heading = re.search(r"^## (License|Licence|Licen[cs]e)\b.*$", text, re.M)
            text = (text[:heading.start()] + section + text[heading.start():]) if heading \
                else text.rstrip() + "\n\n" + section.rstrip() + "\n"
        path.write_text(text, encoding="utf-8", newline="\n")
    cl = p.root / "CHANGELOG.md"
    text = cl.read_text(encoding="utf-8")
    pen, pfr, den, dfr = describe(p)
    if not p.has_packages:
        entry = (f"## [{new}] - {TODAY}\n\n### Added\n\n"
                 f"- GitHub Actions CI (`.github/workflows/ci.yml`): compiles the firmware with PlatformIO "
                 f"(and runs the native tests) on every pull request and push to `main`/`dev`. No package "
                 f"workflow: the binaries embed values from `include/secrets.h`, so they stay built locally. "
                 f"The workflow is generated by morfTools `scripts/gen-ci-workflows.py`.\n\n")
    else:
      entry = (f"## [{new}] - {TODAY}\n\n### Added\n\n"
             f"- GitHub Actions CI (`.github/workflows/ci.yml`): build and `ctest` on {pen} for every "
             f"pull request and push to `main`/`dev`. `packages.yml` builds {den} as workflow artifacts "
             f"on every push to `main`; `package-all.py` (morfTools) takes them for the released commit "
             f"and builds locally only what is missing. Each target declares its artifact in "
             f"`morfproject.json` (`package.ci`). Workflows are generated by morfTools "
             f"`scripts/gen-ci-workflows.py`.\n\n")
    first = re.search(r"^## \[", text, re.M)
    text = text[:first.start()] + entry + text[first.start():] if first else text.rstrip() + "\n\n" + entry
    cl.write_text(text, encoding="utf-8", newline="\n")
    return done + [f"version {old} -> {new}"]


def write_file(path: Path, content: str, executable: bool = False) -> bool:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    return True


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--only", nargs="*", default=None, metavar="NAME")
    parser.add_argument("--write", action="store_true", help="write the files (default: plan only)")
    parser.add_argument("--bump", action="store_true",
                        help="also bump the minor version, badges, CHANGELOG and README sections")
    parser.add_argument("--fix", metavar="TEXT", default="",
                        help="patch bump + a Fixed CHANGELOG entry with this text (workflow correction)")
    parser.add_argument("--root", type=Path, default=HERE.parent,
                        help="folder holding the *_travail clones (default: the workspace)")
    args = parser.parse_args(argv)

    eco = json.loads((HERE / "ecosystem.json").read_text(encoding="utf-8-sig"))
    names = [*eco.get("projects", []), *eco.get("extras", [])]
    for name in names:
        if args.only and name not in args.only:
            continue
        root = args.root / f"{name}_travail"
        if not root.is_dir():
            continue
        p = Project(root)
        if p.kind is None:
            print(f"{name}: no CI (no packaging target to build)")
            continue
        print(f"{name}: {p.kind}")
        files = {".github/workflows/ci.yml": ci_yml(p)}
        if p.has_packages:
            files[".github/workflows/packages.yml"] = packages_yml(p)
        else:
            print("  (no packages.yml: the binaries embed private values from secrets.h)")
        if p.kind in ("cmake-app", "service") and (p.targets("linux", "x86_64") or p.targets("linux", "arm64")):
            files["scripts/ci/build-deb-container.sh"] = container_script(p)
        for rel, content in files.items():
            print(f"  {rel}")
            if args.write:
                write_file(root / rel, content)
        if args.write:
            if p.kind in ("cmake-app", "service"):
                (root / "scripts/ci/build-deb-container.sh").chmod(0o755) \
                    if (root / "scripts/ci/build-deb-container.sh").exists() else None
            update_morfproject(p)
            if args.bump:
                for line in apply_docs(p):
                    print(f"  {line}")
            elif args.fix:
                for line in apply_fix(p, args.fix):
                    print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
