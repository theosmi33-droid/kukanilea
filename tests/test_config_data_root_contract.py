from __future__ import annotations

from pathlib import Path

CONFIG = Path("app/config.py")


def test_config_uses_platformdirs_and_env_override_for_user_data_root() -> None:
    text = CONFIG.read_text(encoding="utf-8")
    assert "user_data_dir(\"KUKANILEA\"" in text
    assert "KUKANILEA_USER_DATA_ROOT" in text
