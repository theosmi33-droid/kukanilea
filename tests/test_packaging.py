from __future__ import annotations

import os
from pathlib import Path

import pytest

BUILD_SCRIPTS = [
    Path("scripts/build/obfuscate.sh"),
    Path("scripts/build/bundle_macos.sh"),
    Path("scripts/build/dmg_macos.sh"),
    Path("scripts/build/sign_macos.sh"),
    Path("scripts/build/obfuscate.ps1"),
    Path("scripts/build/bundle_windows.ps1"),
    Path("scripts/build/installer_windows.ps1"),
]


def test_packaging_scripts_exist_and_executable() -> None:
    for script in BUILD_SCRIPTS:
        assert script.exists(), f"missing script: {script}"
        assert os.access(script, os.X_OK), f"script not executable: {script}"


def test_packaging_docs_exist() -> None:
    assert Path("docs/packaging/BUILD.md").exists()
    assert Path("docs/packaging/SIGNING.md").exists()


def test_packaging_ci_workflows_exist() -> None:
    assert Path(".github/workflows/build-macos.yml").exists()
    assert Path(".github/workflows/build-windows.yml").exists()


def test_packaging_uses_native_desktop_entrypoint() -> None:
    mac_script = Path("scripts/build/bundle_macos.sh").read_text(encoding="utf-8")
    win_script = Path("scripts/build/bundle_windows.ps1").read_text(encoding="utf-8")

    assert "from app.desktop import main" in mac_script
    assert "raise SystemExit(main())" in mac_script
    assert "import webview" in mac_script
    assert (
        'serve(app, host="127.0.0.1", port=int(os.environ.get("PORT", "5051")))'
        not in mac_script
    )

    assert "from app.desktop import main" in win_script
    assert "raise SystemExit(main())" in win_script
    assert "import webview" in win_script
    assert (
        'serve(app, host="127.0.0.1", port=int(os.environ.get("PORT", "5051")))'
        not in win_script
    )


@pytest.mark.packaging
def test_app_bundle_structure_if_present() -> None:
    app_bundle = Path("dist/KUKANILEA.app")
    if not app_bundle.exists():
        pytest.skip("Bundle not built in this environment")

    assert (app_bundle / "Contents").exists()
    assert (app_bundle / "Contents/Info.plist").exists()
