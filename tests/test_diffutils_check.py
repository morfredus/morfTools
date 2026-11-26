"""The Windows toolchain check warns when MSYS2's cmp (diffutils) is missing."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
from morftools.commands import windows_toolchain_warnings  # noqa: E402


class DiffutilsCheck(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp()) / "msys64"
        (self.root / "usr" / "bin").mkdir(parents=True)
        gxx = (self.root / "ucrt64" / "bin" / "g++.exe").as_posix()
        self.overrides = (f"-DCMAKE_CXX_COMPILER={gxx}",)

    def test_missing_cmp_is_reported(self):
        warnings = windows_toolchain_warnings(self.overrides)
        self.assertTrue(any("diffutils" in w for w in warnings))

    def test_present_cmp_is_silent(self):
        (self.root / "usr" / "bin" / "cmp.exe").write_bytes(b"")
        self.assertFalse(any("diffutils" in w
                             for w in windows_toolchain_warnings(self.overrides)))


if __name__ == "__main__":
    unittest.main()
