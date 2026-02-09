import subprocess


def test_no_conflict_markers() -> None:
    result = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "-E",
            r"<<<<<<<|=======|>>>>>>>",
            "--",
            ".",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise AssertionError(
            "Conflict markers found:\n" + (result.stdout or result.stderr)
        )
    if result.returncode not in (0, 1):
        raise AssertionError(
            "git grep failed:\n" + (result.stdout or result.stderr)
        )
