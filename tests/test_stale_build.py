"""Dossier de build Windows perime : detection (0.39.1).

Cas d'origine : 2026-11-17, passage MINGW64 -> UCRT64. Les build-mingw gardaient le Qt6Core.dll
de MINGW64 deploye par windeployqt ; rcc, lance depuis ce dossier, le chargeait avant celui du
PATH et plantait (« rcc list process failed », 0xc0000409) sur PhotoHub et SiteWatch.

Run: python tests/test_stale_build.py   (also collected by pytest)
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))
import os  # noqa: E402
from morftools import commands  # noqa: E402
from morftools.commands import reset_stale_build_dir, stale_build_reason  # noqa: E402


def _toolchain(root: Path, env: str, qt_bytes: bytes):
    (root / env / "bin").mkdir(parents=True)
    (root / env / "bin" / "Qt6Core.dll").write_bytes(qt_bytes)
    return [f"-DCMAKE_CXX_COMPILER={root.as_posix()}/{env}/bin/g++.exe",
            f"-DCMAKE_PREFIX_PATH={root.as_posix()}/{env}"]


def test_cache_from_another_msys2_environment_is_stale():
    with tempfile.TemporaryDirectory() as d:
        root, build = Path(d) / "msys64", Path(d) / "proj" / "build-mingw"
        build.mkdir(parents=True)
        (build / "CMakeCache.txt").write_text(
            "CMAKE_CXX_COMPILER:STRING=C:/msys64/mingw64/bin/g++.EXE\n")
        assert "mingw64" in stale_build_reason(build, _toolchain(root, "ucrt64", b"u"))
        assert stale_build_reason(build, _toolchain(root, "mingw64", b"u")) == ""


def test_deployed_qt_dll_of_another_build_is_stale_even_with_a_fresh_cache():
    with tempfile.TemporaryDirectory() as d:
        root, build = Path(d) / "msys64", Path(d) / "proj" / "build-mingw"
        build.mkdir(parents=True)
        (build / "CMakeCache.txt").write_text(
            "CMAKE_CXX_COMPILER:STRING=C:/msys64/ucrt64/bin/g++.EXE\n")
        (build / "Qt6Core.dll").write_bytes(b"mingw64")
        overrides = _toolchain(root, "ucrt64", b"ucrt64")
        assert "Qt6Core.dll" in stale_build_reason(build, overrides)
        (build / "Qt6Core.dll").write_bytes(b"ucrt64")
        assert stale_build_reason(build, overrides) == ""


def test_reset_removes_only_a_stale_build_dir_inside_the_project():
    with tempfile.TemporaryDirectory() as d:
        root, proj = Path(d) / "msys64", Path(d) / "proj"
        build = proj / "build-mingw"
        build.mkdir(parents=True)
        (build / "Qt6Core.dll").write_bytes(b"old")
        overrides = _toolchain(root, "ucrt64", b"new")
        reset_stale_build_dir(proj, "build-mingw", overrides)
        assert not build.exists()
        reset_stale_build_dir(proj, "build-mingw", overrides)     # absent : sans effet


def test_package_dirs_of_another_environment_make_the_cache_stale():
    # Cache deja reconfigure avec le bon compilateur, mais Qt6_DIR / nlohmann_json_DIR restes
    # sur mingw64 (cas morfCollector et morfSync, 2026-11-17).
    with tempfile.TemporaryDirectory() as d:
        root, build = Path(d) / "msys64", Path(d) / "proj" / "build-mingw"
        build.mkdir(parents=True)
        (build / "CMakeCache.txt").write_text(
            "CMAKE_CXX_COMPILER:STRING=C:/msys64/ucrt64/bin/g++.EXE\n"
            "nlohmann_json_DIR:PATH=C:/msys64/mingw64/share/cmake/nlohmann_json\n")
        assert "mingw64" in stale_build_reason(build, _toolchain(root, "ucrt64", b"u"))


def test_msys2_qt_wins_over_cmake_prefix_path_of_the_environment():
    # Profil PowerShell qui vise le Qt officiel : ignore au profit du Qt du compilateur MSYS2.
    with tempfile.TemporaryDirectory() as d:
        root = Path(d) / "msys64"
        (root / "ucrt64" / "bin").mkdir(parents=True)
        (root / "ucrt64" / "lib" / "cmake" / "Qt6").mkdir(parents=True)
        fake = {"g++": str(root / "ucrt64" / "bin" / "g++.exe"),
                "ninja": str(root / "ucrt64" / "bin" / "ninja.exe")}
        real_which, real_env = commands.shutil.which, os.environ.get("CMAKE_PREFIX_PATH")
        commands.shutil.which = lambda name: fake.get(name)
        os.environ["CMAKE_PREFIX_PATH"] = "C:/Qt/6.11.1/mingw_64"
        commands.detect_windows_toolchain.cache_clear()
        try:
            overrides, _ = commands.detect_windows_toolchain()
            assert f"-DCMAKE_PREFIX_PATH={root / 'ucrt64'}" in overrides
            assert "CMAKE_PREFIX_PATH" not in os.environ
        finally:
            commands.shutil.which = real_which
            commands.detect_windows_toolchain.cache_clear()
            if real_env is not None:
                os.environ["CMAKE_PREFIX_PATH"] = real_env


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
    print("ok")
