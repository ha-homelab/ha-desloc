"""Keep Home Assistant brand images valid and present in release packages."""

import importlib
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
COMPONENT = Path("custom_components/desloc")
ICONS = {"icon.png": (256, 256), "icon@2x.png": (512, 512)}


@pytest.mark.parametrize("filename,dimensions", ICONS.items())
def test_bundled_brand_icons_are_valid_pngs(filename, dimensions):
    """HA's standard and high-resolution icons must be readable RGBA PNGs."""
    with Image.open(ROOT / COMPONENT / "brand" / filename) as icon:
        assert icon.format == "PNG"
        assert icon.size == dimensions
        assert icon.mode == "RGBA"
        icon.verify()


def test_release_package_preserves_bundled_brand_icons(tmp_path, monkeypatch):
    """Exercise the real packager against an isolated, minimal Git index."""
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    packager = importlib.import_module("package_release")
    # Release-plan validation is covered by the release contract suite. This
    # fixture only isolates its inputs; file selection and ZIP writing are real.
    monkeypatch.setattr(packager, "checked_version", Mock(return_value="0.0.1-beta.1"))

    component = tmp_path / COMPONENT
    (component / "brand").mkdir(parents=True)
    (component / "__init__.py").write_text('"""Synthetic integration fixture."""\n')
    (component / "manifest.json").write_text(json.dumps({
        "domain": "desloc", "name": "DESLOC", "version": "0.0.1b1",
    }))
    expected_icons = {}
    for filename in ICONS:
        contents = (ROOT / COMPONENT / "brand" / filename).read_bytes()
        (component / "brand" / filename).write_bytes(contents)
        expected_icons[(COMPONENT / "brand" / filename).as_posix()] = contents

    subprocess.run(
        ["git", "init", "--quiet", "--template="],
        cwd=tmp_path, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "add", "--", COMPONENT.as_posix()],
        cwd=tmp_path, check=True, capture_output=True,
    )

    output = tmp_path / "release-dist"
    packager.build(tmp_path, "0.0.1", "beta", output)

    with ZipFile(output / "ha-desloc.zip") as archive:
        for member, contents in expected_icons.items():
            assert archive.read(member) == contents
