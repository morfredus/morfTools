"""Tests of the CI-artifact path of package-all.py (no network, no real gh).

`_gh` and `_git_head` are replaced by fakes: the point is the DECISIONS (which run is
accepted, what is skipped, what provenance is written), not GitHub itself.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("package_all", HERE / "package-all.py")
package_all = importlib.util.module_from_spec(SPEC)
sys.modules["package_all"] = package_all
SPEC.loader.exec_module(package_all)

SHA = "a" * 40
VERSION = "1.2.3"


class FakeProject:
    name = "ComponentHub"

    def __init__(self, path: Path):
        self.path = path


class FakeTarget:
    name = "linux-arm64-deb"
    os = "linux"
    arch = "arm64"
    build = {}
    provider = "project"

    def __init__(self, ci=None):
        self.package = {"format": "deb", "architecture": "arm64", "script": "x.sh"}
        if ci is not None:
            self.package["ci"] = ci


CI = {"workflow": "packages.yml", "artifact": "art-arm64",
      "file": "componenthub_{version}_arm64.deb"}


class CiPackageTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.project = FakeProject(self.tmp)
        self.calls = []
        self.runs = [{"databaseId": 42, "status": "completed", "conclusion": "success"}]
        self.files = {f"componenthub_{VERSION}_arm64.deb": b"deb-bytes"}
        self.download_ok = True
        package_all._CI_DOWNLOADS.clear()
        self._gh, self._head = package_all._gh, package_all._git_head
        package_all._git_head = lambda path: SHA
        package_all._gh = self.fake_gh

    def tearDown(self):
        package_all._gh, package_all._git_head = self._gh, self._head

    def fake_gh(self, args, cwd):
        self.calls.append(args)
        if args[:2] == ["repo", "view"]:
            return "owner/repo"
        if args[:2] == ["run", "list"]:
            assert SHA in args, "the run must be looked up by the released commit"
            return json.dumps(self.runs)
        if args[:2] == ["run", "download"]:
            if not self.download_ok:
                return None
            dest = Path(args[args.index("-D") + 1])
            for name, data in self.files.items():
                (dest / name).write_bytes(data)
            return ""
        return None

    def fetch(self, target=None):
        out = self.tmp / "dist"
        return package_all._fetch_ci_package(self.project, target or FakeTarget(CI), out,
                                             VERSION, False, False), out

    def test_successful_run_is_downloaded_under_public_name(self):
        (status, artifact), out = self.fetch()
        self.assertEqual(status, "built")
        self.assertEqual(artifact, out / f"componenthub-{VERSION}-linux-arm64.deb")
        self.assertEqual(artifact.read_bytes(), b"deb-bytes")

    def test_run_id_is_recorded_for_provenance(self):
        target = FakeTarget(CI)
        self.fetch(target)
        self.assertEqual(target.package["_ci_run"]["run_id"], 42)

    def test_no_run_for_the_commit_is_unavailable(self):
        self.runs = []
        (status, artifact), _ = self.fetch()
        self.assertTrue(status.startswith("unavailable"))
        self.assertIsNone(artifact)

    def test_failed_run_is_never_used(self):
        self.runs = [{"databaseId": 7, "status": "completed", "conclusion": "failure"}]
        (status, _), _ = self.fetch()
        self.assertTrue(status.startswith("unavailable"))

    def test_run_in_progress_is_reported_not_built(self):
        self.runs = [{"databaseId": 8, "status": "in_progress", "conclusion": None}]
        (status, _), _ = self.fetch()
        self.assertIn("--wait-ci", status)

    def test_finished_success_wins_over_a_run_in_progress(self):
        # e.g. the run of the branch push is done while the run of the tag is still going
        self.runs = [{"databaseId": 9, "status": "in_progress", "conclusion": None},
                     {"databaseId": 42, "status": "completed", "conclusion": "success"}]
        waited = []
        original = package_all.subprocess.run
        package_all.subprocess.run = lambda *a, **k: waited.append(a) or original(*a, **k)
        try:
            out = self.tmp / "dist"
            status, _ = package_all._fetch_ci_package(self.project, FakeTarget(CI), out,
                                                      VERSION, False, True)
        finally:
            package_all.subprocess.run = original
        self.assertEqual(status, "built")
        self.assertEqual(waited, [], "must not wait when a successful run exists")

    def test_public_name_follows_the_provider(self):
        project = FakeProject(self.tmp)
        (self.tmp / "service.json").write_text('{"service_name": "morfmonitor"}', encoding="utf-8")

        class Svc(FakeTarget):
            provider = "morfdeploy"
        deb = Svc(CI)
        self.assertEqual(package_all._public_name(project, deb, "1.2.3"),
                         "morfmonitor-1.2.3-linux-arm64.deb")

        class Fw(FakeTarget):
            provider = "project"
            name = "esp32s3-ota"
            build = {"tool": "platformio", "env": "hub"}
        self.assertEqual(package_all._public_name(project, Fw(CI), "1.2.3"),
                         "componenthub-1.2.3-esp32s3-ota.bin")

    def test_expired_artifact_is_unavailable(self):
        self.download_ok = False
        (status, _), _ = self.fetch()
        self.assertIn("missing or expired", status)

    def test_ambiguous_artifact_is_refused(self):
        self.files[f"componenthub_{VERSION}_arm64.deb"] = b"x"
        # a second file matching the same pattern in a sub folder would be ambiguous
        original = self.fake_gh

        def twice(args, cwd):
            result = original(args, cwd)
            if args[:2] == ["run", "download"]:
                sub = Path(args[args.index("-D") + 1]) / "sub"
                sub.mkdir()
                (sub / f"componenthub_{VERSION}_arm64.deb").write_bytes(b"y")
            return result
        package_all._gh = twice
        (status, _), _ = self.fetch()
        self.assertIn("found 2", status)

    def test_incomplete_ci_block_is_unavailable(self):
        (status, _), _ = self.fetch(FakeTarget({"workflow": "packages.yml"}))
        self.assertIn("incomplete", status)

    def test_target_without_ci_block_is_not_touched(self):
        self.assertIsNone(FakeTarget().package.get("ci"))

    def test_provenance_carries_the_ci_run(self):
        # _release_metadata needs a clean git tree: stub the git calls it makes.
        target = FakeTarget(CI)
        (_, artifact), _ = self.fetch(target)
        real_run = package_all.subprocess.run

        class Done:
            def __init__(self, out):
                self.returncode, self.stdout = 0, out

        def fake_run(cmd, **kw):
            return Done(SHA + "\n" if cmd[:2] == ["git", "rev-parse"] else "")
        package_all.subprocess.run = fake_run
        try:
            error = package_all._release_metadata(self.project, target, artifact, VERSION)
        finally:
            package_all.subprocess.run = real_run
        self.assertIsNone(error)
        meta = json.loads(artifact.with_name(artifact.name + ".metadata.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual(meta["commit"], SHA)
        self.assertEqual(meta["ci"]["run_id"], 42)
        self.assertFalse(meta["dirty"])


if __name__ == "__main__":
    unittest.main()
