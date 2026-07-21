"""The four steps every install-service script performed.

Find or build the binary, stop whatever runs, copy the binary and the
configurations into a fixed directory, hand the result to the service manager.
Six projects each carried their own copy of this, differing by a service name
and a directory.

There is no `platform.system()` in this file, and that is the design rule
rather than a coincidence: the moment orchestration starts asking which system
it runs on, the platform boundary has leaked and the single core becomes a
label on top of the old duplication.
"""

from __future__ import annotations

import getpass
import os
import platform
import shutil
from pathlib import Path

from .backends import ServiceBackend, select
from .manifest import Manifest


class DeployError(RuntimeError):
    """A deployment step failed for a reason worth reporting as-is."""


def invoking_user() -> str:
    """Who asked for this, not who is running it.

    Under sudo the process is root, but the build must not be: a build tree
    owned by root inside the clone breaks the next ordinary build, in a place
    that says nothing about the install that caused it.
    """
    return os.environ.get("SUDO_USER") or getpass.getuser()


def detect_preset() -> tuple:
    """CMake preset and build directory for this machine.

    Architecture, not operating system: an ARM64 Raspberry Pi and an x64 Linux
    box run the same backend and need different presets, so this belongs to the
    build step rather than to any platform module.
    """
    if platform.system() == "Windows":
        return "mingw", "build-mingw"
    machine = platform.machine().lower()
    if machine in ("aarch64", "arm64"):
        return "linux-arm64", "build-arm64"
    return "linux", "build"


def locate_binary(manifest: Manifest, build_dir: str) -> Path | None:
    """The freshly built binary, if it is there.

    Several layouts are tried because the parc has more than one: a service
    subdirectory for the C++ services, the build root for the simpler ones.
    """
    name = manifest.binary_name()
    for candidate in (
        manifest.repo_root / build_dir / "service" / name,
        manifest.repo_root / build_dir / name,
    ):
        if candidate.is_file():
            return candidate
    return None


class Deployer:
    """Runs the four steps against a backend."""

    def __init__(self, manifest: Manifest, backend: ServiceBackend | None = None):
        self.manifest = manifest
        self.backend = backend or select()

        if not self.backend.supported:
            raise DeployError(self.backend.supported_note)

    # -- Preconditions ----------------------------------------------------

    def check_privileges(self) -> None:
        if self.backend.requires_privileges() and not self.backend.has_privileges():
            raise DeployError(
                f"Installing a {self.backend.name} service requires administrator rights.\n"
                + self.backend.privilege_hint()
            )

    # -- Step 1 -----------------------------------------------------------

    def ensure_binary(self, rebuild: bool = False) -> Path:
        preset, build_dir = detect_preset()
        binary = locate_binary(self.manifest, build_dir)

        if binary is not None and not rebuild:
            print(f"  binary found: {binary}")
            return binary

        print(f"  building (preset {preset})...")
        self.backend.build_as_user(self.manifest.repo_root, preset, invoking_user())

        binary = locate_binary(self.manifest, build_dir)
        if binary is None:
            raise DeployError(
                f"No binary named '{self.manifest.binary_name()}' under "
                f"{self.manifest.repo_root / build_dir} after building."
            )
        print(f"  built: {binary}")
        return binary

    # -- Step 2 -----------------------------------------------------------

    def stop_existing(self) -> None:
        self.backend.stop(self.manifest)

    # -- Step 3 -----------------------------------------------------------

    def install_files(self, binary: Path, app_dir: Path) -> None:
        app_dir.mkdir(parents=True, exist_ok=True)
        target = app_dir / self.manifest.binary_name()
        shutil.copy2(binary, target)
        target.chmod(0o755)
        print(f"  binary installed: {target}")

        for config in self.manifest.configs:
            source = self.manifest.repo_root / config.source
            if not source.is_file():
                print(f"  MISSING source, skipped: {config.source}")
                continue

            dest = config.resolved_dest(app_dir)
            dest.parent.mkdir(parents=True, exist_ok=True)

            # Never overwrite by default: these hold settings edited by hand on
            # this machine. Delivering a default over them destroys local state
            # nobody asked to lose.
            if dest.exists() and not config.overwrite:
                print(f"  config kept:      {dest}")
                continue

            shutil.copy2(source, dest)
            dest.chmod(0o644)
            print(f"  config installed: {dest}")

    def chown_to_user(self, app_dir: Path) -> None:
        """Give the directory back to the invoking user, where that means
        something. A no-op on Windows, whose ownership model is different and
        whose ProgramData ACLs already grant what is needed."""
        if platform.system() == "Windows":
            return
        user = invoking_user()
        if user == "root":
            return
        shutil.chown(app_dir, user=user, group=user)
        for path in app_dir.rglob("*"):
            shutil.chown(path, user=user, group=user)

    # -- Step 4 -----------------------------------------------------------

    def register(self, app_dir: Path) -> None:
        self.backend.install(self.manifest, app_dir, invoking_user())

    # -- Whole operations -------------------------------------------------

    def install(self, rebuild: bool = False) -> None:
        app_dir = self.manifest.app_dir()
        print(f"Installing {self.manifest.display_name} ({self.backend.name})")
        print(f"  user:   {invoking_user()}")
        print(f"  source: {self.manifest.repo_root}")
        print(f"  target: {app_dir}")
        print()

        self.check_privileges()
        binary = self.ensure_binary(rebuild=rebuild)
        self.stop_existing()
        self.install_files(binary, app_dir)
        self.chown_to_user(app_dir)
        self.register(app_dir)

        print()
        print(f"{self.manifest.display_name} installed and started.")
        if self.manifest.status_url:
            print(f"Check with:  curl {self.manifest.status_url}")

    def update(self) -> None:
        """Rebuild and replace, keeping the service registered.

        Distinct from install because it always rebuilds -- an update whose
        whole purpose is to ship new code must not silently reuse the binary
        that happens to be lying in the build directory.
        """
        if not self.backend.is_installed(self.manifest):
            raise DeployError(
                f"{self.manifest.display_name} is not installed on this machine.\n"
                "Run the install action first."
            )
        print(f"Updating {self.manifest.display_name} ({self.backend.name})")
        print()
        self.check_privileges()
        binary = self.ensure_binary(rebuild=True)
        self.stop_existing()
        app_dir = self.manifest.app_dir()
        self.install_files(binary, app_dir)
        self.chown_to_user(app_dir)
        self.register(app_dir)
        print()
        print(f"{self.manifest.display_name} updated.")

    def uninstall(self) -> None:
        print(f"Uninstalling {self.manifest.display_name} ({self.backend.name})")
        self.check_privileges()
        self.backend.uninstall(self.manifest)
        app_dir = self.manifest.app_dir()
        print()
        print("Service removed.")
        print(f"{app_dir} was kept -- it holds your configurations.")
        print(f"Remove it by hand if you mean to: {app_dir}")

    def status(self) -> None:
        if not self.backend.is_installed(self.manifest):
            print(f"{self.manifest.display_name}: not installed ({self.backend.name})")
            return
        print(self.backend.status(self.manifest))
