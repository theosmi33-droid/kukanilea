from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_time_mobile_workspace_contract_present_in_web_template_string():
    source = _read("app/web.py")

    assert "Zeiterfassung mobil" in source
    assert "time-clock" in source
    assert "timePause" in source
    assert "timeTravel" in source
    assert "timePhoto" in source
    assert "Schnellaktionen" in source
    assert "time-mobile-shell" in source
