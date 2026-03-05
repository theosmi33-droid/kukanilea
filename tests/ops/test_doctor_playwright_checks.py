import os
import stat
import subprocess
from pathlib import Path

DOCTOR = Path("scripts/dev/doctor.sh")


def _write_fake_python(tmp_path: Path, *, module_playwright: bool, playwright_module_cli: bool, browser_present: bool) -> Path:
    fake = tmp_path / "fake_python.py"
    fake.write_text(
        """#!/usr/bin/env python3
import sys

MODULES = {
    'pytest': True,
    'flask': True,
    'ruff': True,
    'playwright': __MODULE_PLAYWRIGHT__,
}
PLAYWRIGHT_MODULE_CLI = __PLAYWRIGHT_MODULE_CLI__
BROWSER_PRESENT = __BROWSER_PRESENT__

args = sys.argv[1:]

if args == ['--version']:
    print('Python 3.12.0')
    raise SystemExit(0)

if args[:2] == ['-m', 'pip'] and '--version' in args:
    print('pip 24.0')
    raise SystemExit(0)

if args and args[0] == '-c':
    snippet = args[1] if len(args) > 1 else ''
    if snippet.startswith('import '):
        mod = snippet.split('import ', 1)[1].strip()
        if MODULES.get(mod, False):
            raise SystemExit(0)
        raise SystemExit(1)
    raise SystemExit(0)

if args[:2] == ['-m', 'playwright']:
    if args[2:] == ['--version']:
        if MODULES['playwright'] and PLAYWRIGHT_MODULE_CLI:
            print('Version 1.52.0')
            raise SystemExit(0)
        raise SystemExit(1)
    if args[2:] == ['install', '--list']:
        if not MODULES['playwright'] or not PLAYWRIGHT_MODULE_CLI:
            raise SystemExit(1)
        if BROWSER_PRESENT:
            print('  chromium 1234')
        else:
            print('  firefox 5678')
        raise SystemExit(0)

raise SystemExit(1)
""".replace("__MODULE_PLAYWRIGHT__", "True" if module_playwright else "False")
        .replace("__PLAYWRIGHT_MODULE_CLI__", "True" if playwright_module_cli else "False")
        .replace("__BROWSER_PRESENT__", "True" if browser_present else "False"),
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _write_fake_node_playwright(tmp_path: Path) -> Path:
    fake = tmp_path / "playwright"
    fake.write_text(
        "#!/usr/bin/env bash\nif [[ \"$1\" == \"--version\" ]]; then echo 'Version 9.9.9'; exit 0; fi\nexit 0\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _run_doctor(tmp_path: Path, fake_python: Path, extra_args: list[str] | None = None, prepend_path: Path | None = None):
    args = ["bash", str(DOCTOR), "--strict"]
    if extra_args:
        args.extend(extra_args)

    env = os.environ.copy()
    env["PYTHON"] = str(fake_python)
    # Force deterministic local-mode behavior in CI runners unless --ci is passed explicitly.
    env["CI"] = "0"
    if prepend_path is not None:
        env["PATH"] = f"{prepend_path}:{env['PATH']}"

    return subprocess.run(args, capture_output=True, text=True, env=env, check=False)


def test_doctor_local_mode_missing_playwright_module_fails_strict(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=False,
        playwright_module_cli=False,
        browser_present=False,
    )

    result = _run_doctor(tmp_path, fake_python)

    assert result.returncode == 4
    assert "Local mode enabled" in result.stdout
    assert "python module 'playwright' missing" in result.stdout
    assert "Skipping Playwright runtime checks" in result.stdout


def test_doctor_local_mode_playwright_module_cli_failure_fails_strict(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=False,
        browser_present=False,
    )

    result = _run_doctor(tmp_path, fake_python)

    assert result.returncode == 4
    assert "Playwright Python module found, but" in result.stdout
    assert "Node Playwright CLI" in result.stdout


def test_doctor_local_mode_browser_missing_is_warning_only(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=True,
        browser_present=False,
    )

    result = _run_doctor(tmp_path, fake_python)

    assert result.returncode == 0
    assert "Playwright Python CLI available" in result.stdout
    assert "optional local warning" in result.stdout
    assert "All checks passed" in result.stdout


def test_doctor_ci_mode_browser_missing_fails_strict(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=True,
        browser_present=False,
    )

    result = _run_doctor(tmp_path, fake_python, extra_args=["--ci"])

    assert result.returncode == 4
    assert "CI mode enabled" in result.stdout
    assert "chromium browser binary missing in CI mode" in result.stdout


def test_doctor_ci_mode_browser_present_passes(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=True,
        browser_present=True,
    )

    result = _run_doctor(tmp_path, fake_python, extra_args=["--ci"])

    assert result.returncode == 0
    assert "chromium browser binary present" in result.stdout
    assert "All checks passed" in result.stdout


def test_doctor_node_cli_optional_when_missing(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=True,
        browser_present=True,
    )

    result = _run_doctor(tmp_path, fake_python)

    assert result.returncode == 0
    assert "Node Playwright CLI" in result.stdout
    assert "optional" in result.stdout


def test_doctor_node_cli_optional_when_present(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=True,
        browser_present=True,
    )
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_fake_node_playwright(bin_dir)

    result = _run_doctor(tmp_path, fake_python, prepend_path=bin_dir)

    assert result.returncode == 0
    assert "Node Playwright CLI available" in result.stdout




def test_doctor_local_flag_overrides_ci_env(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=True,
        playwright_module_cli=True,
        browser_present=False,
    )

    env = os.environ.copy()
    env["PYTHON"] = str(fake_python)
    env["CI"] = "1"

    result = subprocess.run(
        ["bash", str(DOCTOR), "--strict", "--local"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0
    assert "Local mode enabled" in result.stdout
    assert "source=flag:--local" in result.stdout

def test_doctor_non_strict_returns_zero_with_warning_summary(tmp_path: Path):
    fake_python = _write_fake_python(
        tmp_path,
        module_playwright=False,
        playwright_module_cli=False,
        browser_present=False,
    )

    env = os.environ.copy()
    env["PYTHON"] = str(fake_python)
    result = subprocess.run(
        ["bash", str(DOCTOR)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0
    assert "Completed with warnings" in result.stdout
