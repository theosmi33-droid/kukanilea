from __future__ import annotations

import os
from pathlib import Path

import pytest

BUILD_SCRIPTS = [
    Path("scripts/build/obfuscate.sh"),
    Path("scripts/build/bundle_macos.sh"),
    Path("scripts/build/dmg_macos.sh"),
    Path("scripts/build/sign_macos.sh"),
]


def test_packaging_scripts_exist_and_executable() -> None:
    for script in BUILD_SCRIPTS:
        assert script.exists(), f"missing script: {script}"
        assert os.access(script, os.X_OK), f"script not executable: {script}"


def test_packaging_docs_exist() -> None:
    assert Path("docs/packaging/BUILD.md").exists()
    assert Path("docs/packaging/SIGNING.md").exists()


@pytest.mark.packaging
def test_app_bundle_structure_if_present() -> None:
    app_bundle = Path("dist/KUKANILEA.app")
    if not app_bundle.exists():
        pytest.skip("Bundle not built in this environment")

    assert (app_bundle / "Contents").exists()
    assert (app_bundle / "Contents/Info.plist").exists()
