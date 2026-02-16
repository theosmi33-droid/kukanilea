from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_PREFERRED_LANGS = ["eng"]
TEST_MARKERS = ("pilot+test@example.com", "+49 151 12345678")
ABS_PATH_RE = re.compile(r"/[^\s\"']+")


def _sanitize_text(raw: str | None) -> str | None:
    if raw is None:
        return None
    text = str(raw)
    for marker in TEST_MARKERS:
        text = text.replace(marker, "<redacted>")
    text = ABS_PATH_RE.sub("<path>", text)
    text = text.replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > 400:
        text = text[-400:]
    return text or None


def _resolve_bin(bin_path: str | None) -> Path | None:
    if bin_path:
        p = Path(str(bin_path)).expanduser()
        if p.exists() and p.is_file():
            return p
        return None
    try:
        from app.autonomy.ocr import resolve_tesseract_bin

        resolved = resolve_tesseract_bin()
        if resolved is not None:
            return Path(str(resolved))
    except Exception:
        pass
    fallback = shutil.which("tesseract")
    if not fallback:
        return None
    candidate = Path(fallback)
    if candidate.exists() and candidate.is_file():
        return candidate
    return None


def _candidate_tessdata_dirs(
    *,
    bin_resolved: Path | None,
    tessdata_dir: str | None,
    env: dict[str, str],
) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []

    def _add(source: str, raw_path: Path | str | None) -> None:
        if raw_path is None:
            return
        p = Path(str(raw_path)).expanduser()
        key = str(p.resolve() if p.exists() else p)
        if any(str(existing[1]) == key for existing in candidates):
            return
        candidates.append((source, Path(key)))

    if tessdata_dir:
        _add("cli", tessdata_dir)

    env_prefix = str(env.get("TESSDATA_PREFIX") or "").strip()
    if env_prefix:
        prefix_path = Path(env_prefix).expanduser()
        _add("env", prefix_path / "tessdata")
        _add("env", prefix_path)

    if bin_resolved is not None:
        bin_parent = bin_resolved.parent
        _add("heuristic", bin_parent / "../share/tessdata")
        _add("heuristic", bin_parent / "../../share/tessdata")

    for raw in (
        "/opt/homebrew/share/tessdata",
        "/usr/local/share/tessdata",
        "/usr/share/tesseract-ocr/5/tessdata",
        "/usr/share/tesseract-ocr/4.00/tessdata",
        "/usr/share/tessdata",
    ):
        _add("heuristic", raw)
    return candidates


def _parse_langs(stdout: str) -> list[str]:
    lines = [line.strip() for line in str(stdout or "").splitlines()]
    langs: list[str] = []
    for line in lines:
        if not line:
            continue
        if "list of available languages" in line.casefold():
            continue
        token = line.split()[0].strip()
        if token and token not in langs:
            langs.append(token)
    return langs


def _pick_lang(
    langs: list[str],
    preferred_langs: list[str] | None,
) -> tuple[str | None, bool]:
    preferred = [
        str(v).strip().lower() for v in (preferred_langs or []) if str(v).strip()
    ]
    explicit_preferred = preferred_langs is not None
    if not preferred:
        preferred = list(DEFAULT_PREFERRED_LANGS)

    normalized = {item.lower(): item for item in langs}
    for want in preferred:
        if want in normalized:
            return normalized[want], True

    for lang in langs:
        if str(lang).lower() != "osd":
            return lang, not explicit_preferred

    if langs and str(langs[0]).lower() == "osd":
        if explicit_preferred and preferred == ["osd"]:
            return "osd", True
        return "osd", False
    return None, False


def _next_actions(
    reason: str | None, *, preferred_langs: list[str] | None
) -> list[str]:
    if reason == "tesseract_missing":
        return [
            "Install tesseract and ensure it is on PATH.",
            "Verify with: tesseract --version",
        ]
    if reason == "tessdata_missing":
        return [
            "Set an explicit tessdata directory with --tessdata-dir.",
            "Verify traineddata files are present for the selected language.",
        ]
    if reason == "language_missing":
        wanted = ", ".join(preferred_langs or DEFAULT_PREFERRED_LANGS)
        return [
            f"Requested language not available ({wanted}).",
            "Install the missing language traineddata or choose an available language.",
        ]
    if reason == "tesseract_failed":
        return [
            "Check tesseract execution and permissions.",
            "Re-run with --show-tesseract to inspect sanitized diagnostics.",
        ]
    return []


def probe_tesseract(
    *,
    bin_path: str | None = None,
    tessdata_dir: str | None = None,
    preferred_langs: list[str] | None = None,
    env: dict[str, str] | None = None,
    timeout_s: int = 5,
) -> dict[str, Any]:
    runtime_env = dict(os.environ)
    runtime_env.update(dict(env or {}))

    result: dict[str, Any] = {
        "ok": False,
        "reason": None,
        "bin_path": None,
        "tessdata_dir": None,
        "tessdata_source": None,
        "langs": [],
        "lang_used": None,
        "stderr_tail": None,
        "next_actions": [],
    }

    binary = _resolve_bin(bin_path)
    if binary is None:
        result["reason"] = "tesseract_missing"
        result["next_actions"] = _next_actions(
            "tesseract_missing", preferred_langs=preferred_langs
        )
        return result

    result["bin_path"] = str(binary)
    attempts: list[tuple[str, Path | None]] = [("unknown", None)]
    attempts.extend(
        _candidate_tessdata_dirs(
            bin_resolved=binary, tessdata_dir=tessdata_dir, env=runtime_env
        )
    )

    last_error: str | None = None
    last_stderr: str | None = None
    selected_langs: list[str] = []
    used_source: str | None = None
    used_tessdata: Path | None = None

    for source, candidate in attempts:
        cmd = [str(binary), "--list-langs"]
        if candidate is not None:
            cmd.extend(["--tessdata-dir", str(candidate)])
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_s)),
                check=False,
                shell=False,
                stdin=subprocess.DEVNULL,
                env=runtime_env,
            )
        except subprocess.TimeoutExpired:
            last_error = "tesseract_failed"
            last_stderr = "timeout"
            continue
        except Exception as exc:
            last_error = "tesseract_failed"
            last_stderr = type(exc).__name__
            continue

        if int(proc.returncode or 0) != 0:
            last_error = "tesseract_failed"
            last_stderr = str(proc.stderr or proc.stdout or "")
            continue

        langs = _parse_langs(str(proc.stdout or ""))
        if langs:
            selected_langs = langs
            used_source = source
            used_tessdata = candidate
            break
        last_error = "tessdata_missing"
        last_stderr = str(proc.stderr or proc.stdout or "")

    result["langs"] = selected_langs
    if not selected_langs:
        result["reason"] = (
            "tessdata_missing"
            if last_error in (None, "tessdata_missing")
            else "tesseract_failed"
        )
        result["stderr_tail"] = _sanitize_text(last_stderr)
        result["next_actions"] = _next_actions(
            result["reason"], preferred_langs=preferred_langs
        )
        return result

    result["tessdata_source"] = used_source or "unknown"
    if used_tessdata is not None:
        result["tessdata_dir"] = str(used_tessdata)

    lang_used, allowed = _pick_lang(selected_langs, preferred_langs)
    result["lang_used"] = lang_used
    if not lang_used:
        result["reason"] = "language_missing"
        result["next_actions"] = _next_actions(
            "language_missing", preferred_langs=preferred_langs
        )
        return result
    if not allowed:
        result["reason"] = "language_missing"
        result["next_actions"] = _next_actions(
            "language_missing", preferred_langs=preferred_langs
        )
        return result

    if preferred_langs is None and str(lang_used).lower() != "eng":
        result["next_actions"] = [
            "Preferred language 'eng' is unavailable; using fallback language.",
        ]
    result["ok"] = True
    return result
