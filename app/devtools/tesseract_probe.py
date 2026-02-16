from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

DEFAULT_PREFERRED_LANGS = ["eng"]
TEST_MARKERS = (
    "pilot+test@example.com",
    "+49 151 12345678",
    "OCR_Test_2026-02-16_KD-9999",
)
LANG_CODE_RE = re.compile(r"^[a-z]{3}(?:_[a-z0-9]{2,8})*$")
MISSING_DATA_RE = re.compile(
    r"(error opening data file|couldn.?t load any languages|read_params_file)",
    re.IGNORECASE,
)
MISSING_LANG_RE = re.compile(r"(failed loading language)", re.IGNORECASE)
HEADER_RE = re.compile(r"^\s*list of available languages", re.IGNORECASE)
SUSPICIOUS_PATH_RE = re.compile(
    r"/[^\n]*(?:\.traineddata|/tessdata(?:/[^\n]*)?|/Tesseract[^\n]*)",
    re.IGNORECASE,
)
HOME_DIR_RE = re.compile(r"/(?:Users|home)/[^\s\"']+")
ABS_PATH_SPACE_RE = re.compile(r"/[^\n]+")
WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")
WINDOWS_UNC_RE = re.compile(r"\\\\[A-Za-z0-9_.-]+\\(?:[^\\\r\n]+\\)*[^\\\r\n]*")


def _sanitize_text(
    raw: str | None,
    *,
    known_paths: list[str] | None = None,
    max_lines: int = 20,
    max_chars: int = 1200,
) -> str | None:
    if raw is None:
        return None
    text = str(raw).replace("\x00", "")
    for marker in TEST_MARKERS:
        text = text.replace(marker, "<redacted>")
    home = str(Path.home())
    if home:
        text = text.replace(home, "<path>")
    for known in sorted([p for p in (known_paths or []) if p], key=len, reverse=True):
        text = text.replace(str(known), "<path>")
    text = SUSPICIOUS_PATH_RE.sub("<path>", text)
    text = HOME_DIR_RE.sub("<path>", text)
    text = WINDOWS_DRIVE_RE.sub("<path>", text)
    text = WINDOWS_UNC_RE.sub("<path>", text)
    text = ABS_PATH_SPACE_RE.sub(
        lambda m: (
            "<path>"
            if (
                "/tessdata" in m.group(0).casefold()
                or ".traineddata" in m.group(0).casefold()
                or "/tesseract" in m.group(0).casefold()
            )
            else m.group(0)
        ),
        text,
    )
    lines = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if cleaned:
            lines.append(cleaned)
    if not lines:
        return None
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    out = "\n".join(lines)
    if len(out) > max_chars:
        out = out[-max_chars:]
    return out or None


def _resolve_bin(bin_path: str | None) -> Path | None:
    if bin_path:
        p = Path(str(bin_path)).expanduser()
        if p.exists() and p.is_file() and os.access(p, os.X_OK):
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
    if candidate.exists() and candidate.is_file() and os.access(candidate, os.X_OK):
        return candidate
    return None


def _classify_tesseract_path(
    path: str | None,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    if not str(path or "").strip():
        return {
            "exists": False,
            "executable": False,
            "allowlisted": False,
            "reason": "tesseract_missing",
            "allowlist_reason": "path_missing_or_not_executable",
            "allowed_prefixes": [],
        }
    try:
        from app.autonomy.ocr import classify_tesseract_path

        return classify_tesseract_path(str(path), env=env)
    except Exception:
        p = Path(str(path)).expanduser()
        exists = p.exists() and p.is_file()
        executable = bool(exists and os.access(p, os.X_OK))
        return {
            "exists": bool(exists),
            "executable": bool(executable),
            "allowlisted": bool(executable),
            "reason": "ok" if executable else "tesseract_missing",
            "allowlist_reason": (
                "fallback_unverified"
                if executable
                else "path_missing_or_not_executable"
            ),
            "allowed_prefixes": [],
        }


def _is_lang_code(line: str) -> bool:
    token = str(line or "").strip().casefold()
    return bool(LANG_CODE_RE.match(token))


def supports_flag(bin_path: str, flag: str, timeout_s: int = 3) -> bool:
    cmd = [str(bin_path), "--help"]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_s)),
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return False
    stdout = str(proc.stdout or "")
    return flag in stdout


def _normalize_prefix(raw_path: Path) -> Path:
    candidate = raw_path.expanduser()
    if candidate.name.casefold() == "tessdata":
        return candidate.parent
    return candidate


def _traineddata_count(tessdata_dir: Path) -> int:
    try:
        return sum(1 for _ in tessdata_dir.glob("*.traineddata"))
    except Exception:
        return 0


def _prefix_has_tessdata(prefix: Path) -> bool:
    td = prefix / "tessdata"
    return td.is_dir() and _traineddata_count(td) > 0


def _prefix_direct_tessdata(prefix: Path) -> bool:
    return prefix.is_dir() and _traineddata_count(prefix) > 0


def _candidate_tessdata_dirs(
    *,
    bin_resolved: Path | None,
    tessdata_dir: str | None,
    print_tessdata_dir: str | None,
    env: dict[str, str],
) -> list[tuple[str, Path]]:
    candidates: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def _add(source: str, raw: str | Path | None) -> None:
        if raw is None:
            return
        normalized = _normalize_prefix(Path(str(raw)))
        key = str(normalized.resolve() if normalized.exists() else normalized)
        if key in seen:
            return
        seen.add(key)
        candidates.append((source, Path(key)))

    if print_tessdata_dir:
        _add("print", print_tessdata_dir)

    if tessdata_dir:
        _add("cli", tessdata_dir)

    env_prefix = str(env.get("TESSDATA_PREFIX") or "").strip()
    if env_prefix:
        _add("env", env_prefix)

    if bin_resolved is not None:
        bin_parent = bin_resolved.parent
        _add("heuristic", bin_parent / "../share")
        _add("heuristic", bin_parent / "../../share")

    for raw in (
        "/opt/homebrew/share",
        "/usr/local/share",
        "/usr/share",
        "/usr/share/tesseract-ocr/5",
        "/usr/share/tesseract-ocr/4.00",
    ):
        _add("heuristic", raw)
    return candidates


def _run_print_tessdata_dir(
    *,
    binary: Path,
    env: dict[str, str],
    timeout_s: int,
) -> str | None:
    cmd = [str(binary), "--print-tessdata-dir"]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_s)),
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
            env=dict(env),
        )
    except Exception:
        return None
    if int(proc.returncode or 0) != 0:
        return None
    line = str(proc.stdout or "").strip().splitlines()
    if not line:
        return None
    path = str(line[-1]).strip()
    if not path:
        return None
    return path


def _validate_print_tessdata_dir(raw: str | None) -> str | None:
    if not raw:
        return None
    path = Path(str(raw).strip()).expanduser()
    if not path.exists() or not path.is_dir():
        return None
    if path.name.casefold() == "tessdata":
        return str(path)
    if _traineddata_count(path) > 0:
        return str(path)
    nested = path / "tessdata"
    if nested.is_dir() and _traineddata_count(nested) > 0:
        return str(path)
    return None


def _run_tesseract_version(
    *,
    binary: Path,
    timeout_s: int = 3,
) -> str | None:
    cmd = [str(binary), "--version"]
    try:
        proc = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=max(1, int(timeout_s)),
            check=False,
            shell=False,
            stdin=subprocess.DEVNULL,
        )
    except Exception:
        return None
    if int(proc.returncode or 0) != 0:
        return None
    lines = [
        line.strip() for line in str(proc.stdout or "").splitlines() if line.strip()
    ]
    return lines[0] if lines else None


def parse_list_langs_output(stdout: str, stderr: str) -> dict[str, Any]:
    langs: list[str] = []
    for raw_line in str(stdout or "").splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        folded = line.casefold()
        if HEADER_RE.match(line):
            continue
        if ":" in line and "languages" in folded:
            continue
        token = line.strip().casefold()
        if _is_lang_code(token):
            langs.append(token)

    warning_lines: list[str] = []
    for raw_line in str(stderr or "").splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        folded = line.casefold()
        if (
            "error opening data file" in folded
            or "failed loading language" in folded
            or "read_params_file" in folded
        ):
            warning_lines.append(line)
        elif line:
            warning_lines.append(line)

    langs_unique = list(dict.fromkeys(langs))
    sanitized_warnings = []
    for line in warning_lines:
        safe = _sanitize_text(line, max_lines=1, max_chars=240)
        if safe:
            sanitized_warnings.append(safe)
    sanitized_warnings = sanitized_warnings[:20]
    stderr_tail = _sanitize_text(stderr, max_lines=20, max_chars=1200) or ""
    has_warning = bool(sanitized_warnings or stderr_tail)
    return {
        "langs": langs_unique,
        "warnings": sanitized_warnings,
        "stderr_tail": stderr_tail,
        "has_warning": has_warning,
    }


def _pick_lang(
    *,
    langs: list[str],
    preferred_langs: list[str] | None,
) -> tuple[str | None, bool]:
    if not langs:
        return None, False

    normalized = list(dict.fromkeys([str(v).strip().casefold() for v in langs if v]))
    preferred = [
        str(v).strip().casefold() for v in (preferred_langs or []) if str(v).strip()
    ]
    if preferred:
        for want in preferred:
            if want in normalized:
                return want, True
        return None, False

    if "eng" in normalized:
        return "eng", True
    for lang in normalized:
        if lang != "osd":
            return lang, True
    return None, False


def _next_actions(
    reason: str | None,
    *,
    preferred_langs: list[str] | None,
) -> list[str]:
    if reason == "tesseract_missing":
        return [
            "Install tesseract and ensure it is on PATH.",
            "Verify with: tesseract --version",
        ]
    if reason == "tessdata_missing":
        return [
            "Set TESSDATA_PREFIX to a prefix containing tessdata/.",
            "Verify with: tesseract --list-langs --tessdata-dir <dir>",
        ]
    if reason == "tesseract_not_allowlisted":
        return [
            "Use an allowlisted tesseract location (e.g. /opt/homebrew, /usr/local/bin, /usr/bin).",
            "Or add a safe prefix via KUKANILEA_TESSERACT_ALLOWED_PREFIXES (never filesystem root).",
        ]
    if reason == "language_missing":
        wanted = ", ".join(preferred_langs or DEFAULT_PREFERRED_LANGS)
        return [
            f"Requested language is unavailable ({wanted}).",
            "Install the language traineddata or use --lang with an available entry.",
        ]
    if reason == "ok_with_warnings":
        return [
            "Tesseract reported warnings; verify tessdata path and language packs.",
            "Use --strict to treat warnings as failure in smoke runs.",
        ]
    if reason == "tesseract_failed":
        return [
            "Run with --show-tesseract and inspect sanitized stderr_tail.",
            "Verify local tesseract invocation with explicit --tessdata-dir.",
        ]
    return []


def _classify_no_langs(stderr_tail: str) -> str:
    lower = str(stderr_tail or "").casefold()
    if MISSING_DATA_RE.search(lower):
        return "tessdata_missing"
    if MISSING_LANG_RE.search(lower):
        return "language_missing"
    return "tesseract_failed"


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
        "tesseract_found": False,
        "tesseract_allowlisted": False,
        "tesseract_allowlist_reason": None,
        "tesseract_allowed_prefixes": [],
        "bin_path": None,
        "tesseract_bin": None,
        "tesseract_bin_used": None,
        "tesseract_version": None,
        "supports_print_tessdata_dir": False,
        "print_tessdata_dir": None,
        "tessdata_prefix": None,
        "tessdata_dir": None,
        "tessdata_dir_used": None,
        "tessdata_source": None,
        "tessdata_candidates": [],
        "langs": [],
        "lang_selected": None,
        "lang_used": None,
        "warnings": [],
        "stderr_tail": "",
        "next_actions": [],
    }

    resolved_candidate = (
        str(bin_path).strip()
        if str(bin_path or "").strip()
        else (shutil.which("tesseract") or None)
    )
    classification = _classify_tesseract_path(resolved_candidate, env=runtime_env)
    result["tesseract_allowlisted"] = bool(classification.get("allowlisted"))
    result["tesseract_allowlist_reason"] = (
        str(classification.get("allowlist_reason") or "") or None
    )
    result["tesseract_allowed_prefixes"] = [
        str(item) for item in list(classification.get("allowed_prefixes") or [])
    ]
    result["tesseract_found"] = bool(
        classification.get("exists") and classification.get("executable")
    )

    binary = _resolve_bin(bin_path)
    if binary is None:
        result["reason"] = str(classification.get("reason") or "tesseract_missing")
        result["next_actions"] = _next_actions(
            str(result["reason"]), preferred_langs=preferred_langs
        )
        return result

    binary_classification = _classify_tesseract_path(str(binary), env=runtime_env)
    result["tesseract_allowlisted"] = bool(binary_classification.get("allowlisted"))
    result["tesseract_allowlist_reason"] = (
        str(binary_classification.get("allowlist_reason") or "") or None
    )
    result["tesseract_allowed_prefixes"] = [
        str(item) for item in list(binary_classification.get("allowed_prefixes") or [])
    ]
    result["tesseract_found"] = bool(
        binary_classification.get("exists") and binary_classification.get("executable")
    )
    if str(binary_classification.get("reason") or "") == "tesseract_not_allowlisted":
        result["reason"] = "tesseract_not_allowlisted"
        result["next_actions"] = _next_actions(
            "tesseract_not_allowlisted", preferred_langs=preferred_langs
        )
        result["bin_path"] = str(binary)
        result["tesseract_bin"] = str(binary)
        result["tesseract_bin_used"] = str(binary)
        return result

    result["tesseract_found"] = True
    result["bin_path"] = str(binary)
    result["tesseract_bin"] = str(binary)
    result["tesseract_bin_used"] = str(binary)
    result["tesseract_version"] = _run_tesseract_version(binary=binary)
    preferred = preferred_langs if preferred_langs else list(DEFAULT_PREFERRED_LANGS)

    supports_print = supports_flag(str(binary), "--print-tessdata-dir", timeout_s=3)
    result["supports_print_tessdata_dir"] = bool(supports_print)
    print_tessdata_dir: str | None = None
    if supports_print:
        raw_print_dir = _run_print_tessdata_dir(
            binary=binary,
            env=runtime_env,
            timeout_s=min(max(1, int(timeout_s)), 5),
        )
        print_tessdata_dir = _validate_print_tessdata_dir(raw_print_dir)
        if raw_print_dir and not print_tessdata_dir:
            result["warnings"].append("print_tessdata_dir_invalid")

    result["print_tessdata_dir"] = (
        _sanitize_text(
            print_tessdata_dir,
            known_paths=[str(binary), str(Path.home())],
            max_lines=1,
            max_chars=256,
        )
        or None
    )

    candidate_prefixes = _candidate_tessdata_dirs(
        bin_resolved=binary,
        tessdata_dir=tessdata_dir,
        print_tessdata_dir=print_tessdata_dir,
        env=runtime_env,
    )
    valid_candidates: list[tuple[str, Path, Path]] = []
    for source, prefix in candidate_prefixes:
        cli_dir: Path | None = None
        if _prefix_has_tessdata(prefix):
            cli_dir = prefix / "tessdata"
        elif _prefix_direct_tessdata(prefix):
            cli_dir = prefix
        if cli_dir is not None:
            valid_candidates.append((source, prefix, cli_dir))
    result["tessdata_candidates"] = [
        str(prefix) for _src, prefix, _dir in valid_candidates
    ]

    attempts: list[tuple[str, Path | None, Path | None]] = [("auto", None, None)]
    attempts.extend(valid_candidates)

    known_paths = [str(binary)] + [
        str(prefix) for _src, prefix, _dir in valid_candidates
    ]
    success: dict[str, Any] | None = None
    fallback_success: dict[str, Any] | None = None
    last_stderr: str = ""
    for source, prefix, cli_dir in attempts:
        cmd = [str(binary), "--list-langs"]
        if cli_dir is not None:
            cmd.extend(["--tessdata-dir", str(cli_dir)])
        env_copy = dict(runtime_env)
        if prefix is not None:
            env_copy["TESSDATA_PREFIX"] = str(prefix)
        try:
            proc = subprocess.run(  # noqa: S603
                cmd,
                capture_output=True,
                text=True,
                timeout=max(1, int(timeout_s)),
                check=False,
                shell=False,
                stdin=subprocess.DEVNULL,
                env=env_copy,
            )
        except subprocess.TimeoutExpired:
            last_stderr = "timeout"
            continue
        except Exception as exc:
            last_stderr = type(exc).__name__
            continue

        parsed = parse_list_langs_output(str(proc.stdout or ""), str(proc.stderr or ""))
        parsed["stderr_tail"] = (
            _sanitize_text(
                parsed.get("stderr_tail"),
                known_paths=known_paths + [str(cli_dir)]
                if cli_dir is not None
                else known_paths,
            )
            or ""
        )
        parsed["warnings"] = [
            _sanitize_text(item, known_paths=known_paths, max_lines=1, max_chars=240)
            or ""
            for item in list(parsed.get("warnings") or [])
        ]
        parsed["warnings"] = [item for item in parsed["warnings"] if item][:20]
        parsed["source"] = source
        parsed["prefix"] = str(prefix) if prefix is not None else None
        parsed["dir"] = str(cli_dir) if cli_dir is not None else None
        parsed["returncode"] = int(proc.returncode or 0)

        langs = list(parsed.get("langs") or [])
        if langs:
            if fallback_success is None:
                fallback_success = parsed
            requested = [item.casefold() for item in preferred if item]
            if requested and any(item in langs for item in requested):
                success = parsed
                break
            if requested:
                continue
            success = parsed
            break

        last_stderr = str(parsed.get("stderr_tail") or "")
        if int(proc.returncode or 0) == 0:
            continue

    if success is None:
        success = fallback_success

    if success is None:
        reason = _classify_no_langs(last_stderr)
        if reason == "tessdata_missing" and not valid_candidates:
            reason = "tessdata_missing"
        result["reason"] = reason
        result["stderr_tail"] = (
            _sanitize_text(last_stderr, known_paths=known_paths) or ""
        )
        result["tessdata_candidates"] = [
            _sanitize_text(item, known_paths=known_paths, max_lines=1, max_chars=256)
            or ""
            for item in list(result.get("tessdata_candidates") or [])
        ]
        result["tessdata_candidates"] = [
            item for item in result["tessdata_candidates"] if item
        ]
        result["tesseract_bin_used"] = (
            _sanitize_text(
                str(binary), known_paths=[str(Path.home())], max_lines=1, max_chars=256
            )
            or None
        )
        result["next_actions"] = _next_actions(reason, preferred_langs=preferred_langs)
        return result

    langs = list(
        dict.fromkeys(
            [str(v).strip().casefold() for v in success["langs"] if str(v).strip()]
        )
    )
    result["langs"] = langs
    result["warnings"] = list(result.get("warnings") or []) + list(
        success.get("warnings") or []
    )
    result["stderr_tail"] = str(success.get("stderr_tail") or "")
    result["tessdata_source"] = str(success.get("source") or "auto")
    result["tessdata_prefix"] = str(success.get("prefix") or "") or None
    result["tessdata_dir"] = str(success.get("prefix") or "") or None
    result["tessdata_dir_used"] = str(success.get("prefix") or "") or None
    result["tessdata_candidates"] = [
        _sanitize_text(item, known_paths=known_paths, max_lines=1, max_chars=256) or ""
        for item in list(result.get("tessdata_candidates") or [])
    ]
    result["tessdata_candidates"] = [
        item for item in result["tessdata_candidates"] if item
    ]
    result["tesseract_bin_used"] = (
        _sanitize_text(
            str(binary), known_paths=[str(Path.home())], max_lines=1, max_chars=256
        )
        or None
    )

    selected_lang, allowed = _pick_lang(langs=langs, preferred_langs=preferred_langs)
    result["lang_selected"] = selected_lang
    result["lang_used"] = selected_lang
    if not selected_lang or not allowed:
        result["reason"] = "language_missing"
        result["next_actions"] = _next_actions(
            "language_missing",
            preferred_langs=preferred_langs,
        )
        return result

    if success.get("has_warning"):
        result["reason"] = "ok_with_warnings"
        result["ok"] = True
        result["next_actions"] = _next_actions(
            "ok_with_warnings",
            preferred_langs=preferred_langs,
        )
    else:
        result["reason"] = "ok"
        result["ok"] = True
        result["next_actions"] = []

    if preferred_langs is None and selected_lang != "eng":
        result["next_actions"].append(
            "Preferred language 'eng' is unavailable; fallback language is used."
        )
    result["warnings"] = [
        _sanitize_text(item, known_paths=known_paths, max_lines=1, max_chars=240) or ""
        for item in list(result.get("warnings") or [])
    ]
    result["warnings"] = [item for item in result["warnings"] if item]
    return result
