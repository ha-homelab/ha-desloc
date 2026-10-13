"""Verify the shipped integration ZIP through real plans and receipt checking."""

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import package_release
import stage_release_assets
import version_plan
import version_receipt


class IntegrationPackagingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        names = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=ROOT, text=True
        ).split("\0")
        for name in filter(None, names):
            source = ROOT / name
            if source.is_file():
                target = self.root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
        for command in (
            ["git", "init", "-q"],
            ["git", "add", "."],
            [
                "git",
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-qm",
                "Fixture",
            ],
        ):
            subprocess.run(command, cwd=self.root, check=True, capture_output=True)
        self.policy = json.loads((self.root / ".release-policy.json").read_text())
        self.sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=self.root, text=True
        ).strip()
        self.base = version_plan.read_base_version(self.root, self.policy)
        self.originals = {
            item["path"]: (self.root / item["path"]).read_bytes()
            for item in self.policy["versioning"]["files"]
        }

    def test_all_channels_preserve_installable_layout_and_metadata(self):
        for channel in ("beta", "rc", "nightly"):
            with self.subTest(channel=channel):
                for name, contents in self.originals.items():
                    (self.root / name).write_bytes(contents)
                sequence = "20261013120000.42.1" if channel == "nightly" else 7
                plan = version_plan.create_plan(
                    self.base, channel, sequence, self.sha, self.policy, 7
                )
                (self.root / ".release-plan.json").write_text(json.dumps(plan))
                subprocess.run(
                    [
                        sys.executable,
                        str(self.root / "scripts/version_plan.py"),
                        "sync",
                        "--root",
                        str(self.root),
                        "--plan",
                        ".release-plan.json",
                    ],
                    check=True,
                    capture_output=True,
                )
                output = self.root / ("dist-" + channel)
                package_release.build(self.root, self.base, channel, output)
                with ZipFile(output / "ha-desloc.zip") as archive:
                    expected = {
                        name
                        for name in subprocess.check_output(
                            [
                                "git",
                                "ls-files",
                                "-z",
                                "--",
                                "custom_components/desloc/",
                            ],
                            cwd=self.root,
                            text=True,
                        ).split("\0")
                        if name
                    }
                    self.assertEqual(set(archive.namelist()), expected)
                    for name in expected:
                        self.assertEqual(
                            archive.read(name), (self.root / name).read_bytes()
                        )
                    manifest = json.loads(
                        archive.read("custom_components/desloc/manifest.json")
                    )
                    self.assertEqual(manifest["domain"], "desloc")
                    self.assertEqual(
                        manifest["version"],
                        version_plan.projections(plan, "pep440")["package"],
                    )
                # ZIP can be installed directly into a fresh HA configuration directory.
                with tempfile.TemporaryDirectory() as install:
                    with ZipFile(output / "ha-desloc.zip") as archive:
                        archive.extractall(install)
                    self.assertTrue(
                        (
                            Path(install) / "custom_components/desloc/__init__.py"
                        ).is_file()
                    )
                    self.assertTrue(
                        (
                            Path(install)
                            / "custom_components/desloc/translations/en.json"
                        ).is_file()
                    )
                staged = stage_release_assets.stage(
                    self.root, channel, [output.name + "/*"]
                )
                assets = [
                    {
                        "name": path.name,
                        "size": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    }
                    for path in staged.iterdir()
                ]
                self.assertTrue(
                    version_receipt.verify_receipts(staged, plan, assets, self.policy)
                )
                self.assertTrue(
                    version_receipt.verify_declared_artifacts(staged, self.policy, plan)
                )

    def test_existing_hacs_source_installation_mode_is_preserved(self):
        self.assertEqual(
            json.loads((self.root / "hacs.json").read_text()),
            {"name": "DESLOC", "homeassistant": "2026.9.1"},
        )


if __name__ == "__main__":
    unittest.main()
