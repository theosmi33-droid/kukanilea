#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tophandwerk Core (FINAL)
- Pending/Done JSON store
- Background analysis (text extract + OCR fallback)
- Suggestions: kdnr, name, addr, plz/ort, doctype, doc-date (Excel-like input)
- RBAC (simple sqlite)
- Audit log (sqlite)
- Assistant search:
    - FTS5 if available (fast)
    - fallback LIKE (slow, MVP ok)
- Dedupe: doc_id = SHA256(file bytes)
- Versioning:
    - logical group_key exists -> new version if bytes differ
    - exact same bytes -> treated as duplicate (no new version)
- Object-folder duplicate detection (similar names like ö vs oe)
- IMPORTANT FIX:
    - FTS5 virtual tables DO NOT support UPSERT (ON CONFLICT DO UPDATE)
    - we use DELETE + INSERT for docs_fts
"""

import os
import re
import io
import json
import time
import base64
import hashlib
import sqlite3
import threading
import unicodedata
from pathlib import Path
from datetime import datetime, date
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

# Optional libs
try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None

try:
    import fitz  # PyMuPDF  # type: ignore
except Exception:
    fitz = None

try:
    from PIL import Image  # type: ignore
except Exception:
    Image = None

try:
    import pytesseract  # type: ignore
except Exception:
    pytesseract = None


# ============================================================
# CONFIG / PATHS
# ============================================================
EINGANG = Path.home() / "Tophandwerk_Eingang"
BASE_PATH = Path.home() / "Tophandwerk_Kundenablage"
PENDING_DIR = Path.home() / "Tophandwerk_Pending"
DONE_DIR = Path.home() / "Tophandwerk_Done"

DB_PATH = Path.home() / "Tophandwerk_DB.sqlite3"

SUPPORTED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# OCR / Extraction limits
OCR_MAX_PAGES = 2
MIN_TEXT_LEN_BEFORE_OCR = 200

# Duplicate-detection for object folders (name/addr/plzort variations)
DEFAULT_DUP_SIM_THRESHOLD = 0.93

# Assistant search result size
ASSISTANT_DEFAULT_LIMIT = 50


# ============================================================
# UTIL
# ============================================================
def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()


def _read_bytes(fp: Path) -> bytes:
    with open(fp, "rb") as f:
        return f.read()


def _token() -> str:
    raw = f"{time.time_ns()}:{os.getpid()}:{os.urandom(8).hex()}".encode("utf-8")
    return base64.urlsafe_b64encode(hashlib.sha256(raw).digest())[:22].decode("ascii")


def normalize_component(s: str) -> str:
    """
    Strong, filesystem-friendly normalization:
    - normalize unicode
    - collapse whitespace
    """
    if s is None:
        return ""
    s = str(s).strip()
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _norm_for_match(s: str) -> str:
    """
    Aggressive matching normalization:
    - lower
    - replace umlauts with ascii expansions
    - drop non-alnum
    """
    s = normalize_component(s).lower()
    s = (
        s.replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s


_DATE_PATTERNS = [
    # pure dates
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y.%m.%d",
    "%d.%m.%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%y",
    "%d/%m/%y",
    "%d-%m-%y",
    # date-time variants (Excel-ish)
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
    "%d.%m.%Y %H:%M:%S",
    "%d.%m.%Y %H:%M",
    "%d/%m/%Y %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%d-%m-%Y %H:%M:%S",
    "%d-%m-%Y %H:%M",
]


def parse_excel_like_date(s: str) -> str:
    """
    Accept common Excel-like date strings -> normalized YYYY-MM-DD or "" if invalid.

    Examples accepted:
      24.10.2025
      24/10/2025
      24-10-2025
      2025-10-24
      2025/10/24
      2025.10.24
      24.10.2025 12:30
      2025-10-24 12:30:00
    """
    if not s:
        return ""
    s = str(s).strip()
    if not s:
        return ""

    # normalize separators a bit, keep time if any
    s = re.sub(r"\s+", " ", s).replace("T", " ")

    for pat in _DATE_PATTERNS:
        try:
            dt = datetime.strptime(s, pat)
            d = dt.date()
            if d.year < 1900 or d.year > 2099:
                return ""
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    # ISO-ish anywhere
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        try:
            y = int(m.group(1))
            mo = int(m.group(2))
            da = int(m.group(3))
            d = date(y, mo, da)
            if d.year < 1900 or d.year > 2099:
                return ""
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    # DMY anywhere
    m = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", s)
    if m:
        try:
            da = int(m.group(1))
            mo = int(m.group(2))
            y = int(m.group(3))
            if y < 100:
                # 2-digit year heuristic like Excel (00-68 => 2000-2068, else 1900-1999)
                y = 2000 + y if y <= 68 else 1900 + y
            d = date(y, mo, da)
            if d.year < 1900 or d.year > 2099:
                return ""
            return d.strftime("%Y-%m-%d")
        except Exception:
            pass

    return ""


# ============================================================
# PENDING / DONE store (JSON files)
# ============================================================
def _pending_path(token: str) -> Path:
    return PENDING_DIR / f"{token}.json"


def _done_path(token: str) -> Path:
    return DONE_DIR / f"{token}.json"


def read_pending(token: str) -> Optional[Dict[str, Any]]:
    fp = _pending_path(token)
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_pending(token: str, payload: Dict[str, Any]) -> None:
    fp = _pending_path(token)
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_pending(token: str) -> None:
    fp = _pending_path(token)
    try:
        fp.unlink()
    except Exception:
        pass


def list_pending() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for fp in sorted(PENDING_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            j = json.loads(fp.read_text(encoding="utf-8"))
            j["_token"] = fp.stem
            out.append(j)
        except Exception:
            continue
    return out


def write_done(token: str, payload: Dict[str, Any]) -> None:
    fp = _done_path(token)
    fp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_done(token: str) -> Optional[Dict[str, Any]]:
    fp = _done_path(token)
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


# ============================================================
# SQLITE DB
# ============================================================
_DB_LOCK = threading.Lock()
_FTS5_AVAILABLE: Optional[bool] = None


def _db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA foreign_keys=ON;")
    return con


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    row = con.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view') AND name=?",
        (name,),
    ).fetchone()
    return bool(row)


def _has_fts5(con: sqlite3.Connection) -> bool:
    global _FTS5_AVAILABLE
    if _FTS5_AVAILABLE is not None:
        return _FTS5_AVAILABLE
    try:
        con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_test USING fts5(x);")
        con.execute("DROP TABLE IF EXISTS __fts5_test;")
        _FTS5_AVAILABLE = True
    except Exception:
        _FTS5_AVAILABLE = False
    return bool(_FTS5_AVAILABLE)


def db_init() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _DB_LOCK:
        con = _db()
        try:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS users(
                  username TEXT PRIMARY KEY,
                  pass_sha256 TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS roles(
                  username TEXT NOT NULL,
                  role TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  PRIMARY KEY(username, role),
                  FOREIGN KEY(username) REFERENCES users(username) ON DELETE CASCADE
                );
                """
            )
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS audit(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  ts TEXT NOT NULL,
                  user TEXT NOT NULL,
                  role TEXT NOT NULL,
                  action TEXT NOT NULL,
                  target TEXT,
                  meta_json TEXT
                );
                """
            )

            # docs = EXACT BYTES identity (dedupe)
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS docs(
                  doc_id TEXT PRIMARY KEY,                  -- sha256(file bytes)
                  group_key TEXT NOT NULL,                  -- logical group for versioning
                  kdnr TEXT,
                  object_folder TEXT,
                  doctype TEXT,
                  doc_date TEXT,                            -- YYYY-MM-DD
                  created_at TEXT NOT NULL
                );
                """
            )

            # versions = versions for ONE doc_id (same bytes) is pointless,
            # but we keep it for your UI. For real “edited version” you’ll get a NEW doc_id.
            # We therefore treat “versions” as “snapshots we stored for this doc_id”,
            # and we also detect same group_key for “new_version_same_group_key”.
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS versions(
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  doc_id TEXT NOT NULL,
                  version_no INTEGER NOT NULL,
                  bytes_sha256 TEXT NOT NULL,
                  file_name TEXT NOT NULL,
                  file_path TEXT NOT NULL,
                  extracted_text TEXT,
                  used_ocr INTEGER NOT NULL DEFAULT 0,
                  note TEXT,
                  created_at TEXT NOT NULL,
                  FOREIGN KEY(doc_id) REFERENCES docs(doc_id) ON DELETE CASCADE
                );
                """
            )

            con.execute("CREATE INDEX IF NOT EXISTS idx_docs_group ON docs(group_key);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_docs_kdnr ON docs(kdnr);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_versions_doc ON versions(doc_id);")
            con.execute("CREATE INDEX IF NOT EXISTS idx_versions_path ON versions(file_path);")

            # FTS5 (optional)
            if _has_fts5(con):
                # IMPORTANT:
                # - FTS5 does NOT support UPSERT
                # - We store doc_id as UNINDEXED key; content is indexed
                con.execute(
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts
                    USING fts5(
                        doc_id UNINDEXED,
                        kdnr UNINDEXED,
                        doctype UNINDEXED,
                        doc_date UNINDEXED,
                        file_name UNINDEXED,
                        file_path UNINDEXED,
                        content,
                        tokenize='unicode61'
                    );
                    """
                )
            con.commit()
        finally:
            con.close()


# ============================================================
# RBAC
# ============================================================
def _pw_hash(pw: str) -> str:
    return _sha256_bytes((pw or "").encode("utf-8"))


def rbac_create_user(username: str, password: str) -> str:
    username = normalize_component(username).lower()
    if not username:
        raise ValueError("username required")
    if not password:
        raise ValueError("password required")

    with _DB_LOCK:
        con = _db()
        try:
            con.execute(
                "INSERT OR REPLACE INTO users(username, pass_sha256, created_at) VALUES (?,?,?)",
                (username, _pw_hash(password), _now_iso()),
            )
            con.commit()
            return username
        finally:
            con.close()


def rbac_verify_user(username: str, password: str) -> bool:
    username = normalize_component(username).lower()
    if not username or not password:
        return False
    with _DB_LOCK:
        con = _db()
        try:
            row = con.execute("SELECT pass_sha256 FROM users WHERE username=?", (username,)).fetchone()
            if not row:
                return False
            return str(row["pass_sha256"]) == _pw_hash(password)
        finally:
            con.close()


def rbac_assign_role(username: str, role: str) -> None:
    username = normalize_component(username).lower()
    role = normalize_component(role).upper()
    if not username or not role:
        return
    with _DB_LOCK:
        con = _db()
        try:
            con.execute(
                "INSERT OR IGNORE INTO roles(username, role, created_at) VALUES (?,?,?)",
                (username, role, _now_iso()),
            )
            con.commit()
        finally:
            con.close()


def rbac_get_user_roles(username: str) -> List[str]:
    username = normalize_component(username).lower()
    if not username:
        return []
    with _DB_LOCK:
        con = _db()
        try:
            rows = con.execute("SELECT role FROM roles WHERE username=? ORDER BY role", (username,)).fetchall()
            return [str(r["role"]) for r in rows]
        finally:
            con.close()


# ============================================================
# AUDIT
# ============================================================
def audit_log(user: str, role: str, action: str, target: str = "", meta: Optional[dict] = None) -> None:
    user = normalize_component(user).lower()
    role = normalize_component(role).upper()
    action = normalize_component(action)
    target = normalize_component(target)
    meta_json = json.dumps(meta or {}, ensure_ascii=False)

    with _DB_LOCK:
        con = _db()
        try:
            con.execute(
                "INSERT INTO audit(ts, user, role, action, target, meta_json) VALUES (?,?,?,?,?,?)",
                (_now_iso(), user, role, action, target, meta_json),
            )
            con.commit()
        finally:
            con.close()


# ============================================================
# FOLDER HELPERS
# ============================================================
def _safe_fs(s: str) -> str:
    s = normalize_component(s)
    if not s:
        return ""
    s = re.sub(r"[^\wäöüÄÖÜß\-\.\, ]+", "", s)
    s = s.replace(" ", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60]


def parse_folder_fields(folder_name: str) -> Dict[str, str]:
    folder_name = folder_name.strip()
    parts = folder_name.split("_")
    out = {"kdnr": "", "name": "", "addr": "", "plzort": ""}

    if not parts:
        return out

    if re.match(r"^\d{3,}$", parts[0]):
        out["kdnr"] = parts[0]
        rest = parts[1:]
    else:
        rest = parts

    plz_idx = None
    for i, t in enumerate(rest):
        if re.match(r"^\d{5}$", t):
            plz_idx = i
            break

    if plz_idx is not None:
        plz = rest[plz_idx]
        ort = "_".join(rest[plz_idx + 1 :]) if plz_idx + 1 < len(rest) else ""
        out["plzort"] = normalize_component(f"{plz} {ort.replace('_',' ')}").strip()
        before = rest[:plz_idx]
    else:
        before = rest

    addr_start = None
    for i, t in enumerate(before):
        low = t.lower()
        if any(x in low for x in ["str", "straße", "strasse", "weg", "allee", "platz", "ring", "damm", "ufer", "gasse"]):
            addr_start = i
            break

    if addr_start is not None:
        out["name"] = normalize_component(" ".join(before[:addr_start]).replace("_", " "))
        out["addr"] = normalize_component(" ".join(before[addr_start:]).replace("_", " "))
    else:
        out["name"] = normalize_component(" ".join(before).replace("_", " "))

    return out


def find_existing_customer_folders(base_path: Path, kdnr: str) -> List[Path]:
    kdnr = normalize_component(kdnr)
    if not kdnr:
        return []
    base_path = Path(base_path)
    if not base_path.exists():
        return []
    out: List[Path] = []
    prefix = f"{kdnr}_"
    for p in base_path.iterdir():
        if p.is_dir() and p.name.startswith(prefix):
            out.append(p)
    return sorted(out)


def best_match_object_folder(existing: List[Path], addr: str, plzort: str) -> Tuple[Optional[Path], float]:
    addr_n = _norm_for_match(addr)
    plz_n = _norm_for_match(plzort)

    best: Optional[Path] = None
    best_score = 0.0

    for f in existing:
        fields = parse_folder_fields(f.name)
        a2 = _norm_for_match(fields.get("addr", ""))
        p2 = _norm_for_match(fields.get("plzort", ""))

        s1 = SequenceMatcher(None, addr_n, a2).ratio() if addr_n or a2 else 0.0
        s2 = SequenceMatcher(None, plz_n, p2).ratio() if plz_n or p2 else 0.0
        score = (0.6 * s2) + (0.4 * s1)

        if score > best_score:
            best_score = score
            best = f

    return best, best_score


def detect_object_duplicates_for_kdnr(kdnr: str, threshold: float = DEFAULT_DUP_SIM_THRESHOLD) -> List[Dict[str, Any]]:
    kdnr = normalize_component(kdnr)
    folders = find_existing_customer_folders(BASE_PATH, kdnr)
    names = [(f, _norm_for_match(f.name)) for f in folders]
    out: List[Dict[str, Any]] = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            f1, n1 = names[i]
            f2, n2 = names[j]
            if not n1 or not n2:
                continue
            sim = SequenceMatcher(None, n1, n2).ratio()
            if sim >= float(threshold):
                out.append(
                    {
                        "a": str(f1),
                        "b": str(f2),
                        "name_a": f1.name,
                        "name_b": f2.name,
                        "similarity": round(sim, 4),
                        "hint": "Mögliche Dublette (Admin: mergen/repair ohne Datenverlust).",
                    }
                )
    out.sort(key=lambda x: x["similarity"], reverse=True)
    return out


# ============================================================
# EXTRACTION / OCR
# ============================================================
def _extract_pdf_text(fp: Path) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(str(fp))
        texts = []
        for page in reader.pages[: max(1, OCR_MAX_PAGES)]:
            try:
                t = page.extract_text() or ""
                if t:
                    texts.append(t)
            except Exception:
                continue
        return "\n".join(texts).strip()
    except Exception:
        return ""


def _ocr_pdf(fp: Path) -> str:
    if fitz is None or pytesseract is None or Image is None:
        return ""
    try:
        doc = fitz.open(str(fp))
        texts = []
        for i in range(min(len(doc), OCR_MAX_PAGES)):
            page = doc.load_page(i)
            pix = page.get_pixmap(dpi=250)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            txt = pytesseract.image_to_string(img, lang="deu+eng")
            if txt:
                texts.append(txt)
        return "\n".join(texts).strip()
    except Exception:
        return ""


def _ocr_image(fp: Path) -> str:
    if pytesseract is None or Image is None:
        return ""
    try:
        img = Image.open(str(fp))
        txt = pytesseract.image_to_string(img, lang="deu+eng")
        return (txt or "").strip()
    except Exception:
        return ""


def _extract_text(fp: Path) -> Tuple[str, bool]:
    ext = fp.suffix.lower()
    if ext == ".pdf":
        t = _extract_pdf_text(fp)
        if len(t) >= MIN_TEXT_LEN_BEFORE_OCR:
            return t, False
        o = _ocr_pdf(fp)
        if o:
            return o, True
        return t, False
    else:
        o = _ocr_image(fp)
        return o, True if o else False


# ============================================================
# HEURISTIC PARSING (SUGGESTIONS)
# ============================================================
_DOCTYPE_KEYWORDS = [
    ("RECHNUNG", [r"\brechnung\b", r"\binvoice\b"]),
    ("ANGEBOT", [r"\bangebot\b", r"\bquotation\b", r"\boffer\b"]),
    ("AUFTRAGSBESTAETIGUNG", [r"\bauftragsbest", r"\border confirmation\b"]),
    ("MAHNUNG", [r"\bmahnung\b", r"\breminder\b"]),
    ("NACHTRAG", [r"\bnachtrag\b"]),
    ("AW", [r"\baufmaß\b", r"\baufmass\b", r"\bmaß\b", r"\bmass\b"]),
    ("FOTO", [r"\bfoto\b", r"\bimage\b"]),
]


def _detect_doctype(text: str, filename: str) -> str:
    hay = f"{filename}\n{text}".lower()
    best = ("SONSTIGES", 0)
    for dt, pats in _DOCTYPE_KEYWORDS:
        score = 0
        for p in pats:
            if re.search(p, hay, flags=re.IGNORECASE):
                score += 1
        if score > best[1]:
            best = (dt, score)
    return best[0]


def _find_kdnr_candidates(text: str) -> List[Tuple[str, float]]:
    cands: List[str] = []
    for m in re.finditer(r"(kunden[\s\-]*nr\.?\s*[:#]?\s*)(\d{3,})", text, flags=re.IGNORECASE):
        cands.append(m.group(2))
    for m in re.finditer(r"(kdnr\.?\s*[:#]?\s*)(\d{3,})", text, flags=re.IGNORECASE):
        cands.append(m.group(2))
    if not cands:
        for m in re.finditer(r"\b(\d{4,6})\b", text):
            v = m.group(1)
            if v.startswith("20"):
                continue
            cands.append(v)
    freq: Dict[str, int] = {}
    for c in cands:
        freq[c] = freq.get(c, 0) + 1
    ranked = sorted(freq.items(), key=lambda x: (-x[1], x[0]))
    out: List[Tuple[str, float]] = []
    for num, f in ranked[:8]:
        score = round(min(1.0, 0.55 + 0.1 * f), 2)
        out.append((num, score))
    return out


def _find_dates(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    cands: List[Dict[str, Any]] = []

    for m in re.finditer(r"\b(\d{1,2})[.\-/](\d{1,2})[.\-/](\d{2,4})\b", text):
        raw = m.group(0)
        norm = parse_excel_like_date(raw)
        if norm:
            cands.append({"raw": raw, "date": norm, "reason": "DMY"})

    for m in re.finditer(r"\b(20\d{2})[.\-/](\d{1,2})[.\-/](\d{1,2})\b", text):
        raw = m.group(0)
        norm = parse_excel_like_date(raw)
        if norm:
            cands.append({"raw": raw, "date": norm, "reason": "YMD"})

    best = ""
    best_score = -1.0
    low = text.lower()
    for c in cands:
        raw = c["raw"]
        d = c["date"]
        idx = low.find(raw.lower())
        window = low[max(0, idx - 25) : idx + 25] if idx >= 0 else ""
        score = 0.1
        if "datum" in window:
            score += 0.9
        if "rechnung" in window or "angebot" in window:
            score += 0.2
        if score > best_score:
            best_score = score
            best = d

    seen = set()
    uniq: List[Dict[str, Any]] = []
    for c in cands:
        if c["date"] in seen:
            continue
        seen.add(c["date"])
        uniq.append(c)

    return best, uniq[:12]


def _find_name_addr_plzort(text: str) -> Tuple[List[str], List[str], List[str]]:
    lines = [normalize_component(x) for x in (text or "").splitlines()]
    lines = [l for l in lines if l]

    plzort: List[str] = []
    addr: List[str] = []
    name: List[str] = []

    for l in lines:
        m = re.search(r"\b(\d{5})\s+([A-Za-zÄÖÜäöüß\- ]{2,})\b", l)
        if m:
            candidate = normalize_component(f"{m.group(1)} {m.group(2)}")
            if candidate not in plzort:
                plzort.append(candidate)

    for l in lines:
        if re.search(r"\b(str\.?|straße|strasse|weg|allee|platz|ring|damm|ufer|gasse)\b", l, flags=re.IGNORECASE) and re.search(r"\b\d{1,4}[a-zA-Z]?\b", l):
            if l not in addr:
                addr.append(l)

    for l in lines[:15]:
        if len(l) < 3:
            continue
        if any(x in l.lower() for x in ["angebot", "rechnung", "datum:", "kunden-nr", "kunden nr", "projekt-nr", "bearbeiter"]):
            continue
        if re.search(r"(www\.|http|tel|fax|@)", l, flags=re.IGNORECASE):
            continue
        name.append(l)
        break

    return name[:8], addr[:8], plzort[:8]


# ============================================================
# INDEX / SEARCH
# ============================================================
def _fts_put(con: sqlite3.Connection, row: Dict[str, Any]) -> None:
    """
    FIX:
    FTS5 virtual tables do NOT support UPSERT.
    We do: DELETE + INSERT.
    """
    if not (_has_fts5(con) and _table_exists(con, "docs_fts")):
        return

    doc_id = str(row.get("doc_id", "") or "")
    if not doc_id:
        return

    con.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
    con.execute(
        """
        INSERT INTO docs_fts(doc_id, kdnr, doctype, doc_date, file_name, file_path, content)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            doc_id,
            str(row.get("kdnr", "") or ""),
            str(row.get("doctype", "") or ""),
            str(row.get("doc_date", "") or ""),
            str(row.get("file_name", "") or ""),
            str(row.get("file_path", "") or ""),
            (str(row.get("content", "") or ""))[:200000],
        ),
    )


def _compute_group_key(kdnr: str, doctype: str, doc_date: str, file_name: str) -> str:
    k = normalize_component(kdnr)
    t = normalize_component(doctype).upper()
    d = parse_excel_like_date(doc_date) or ""
    stem = Path(file_name).stem
    stem = re.sub(r"_(\d{6})$", "", stem)
    stem_n = _norm_for_match(stem)
    raw = f"{k}|{t}|{d}|{stem_n}"
    return _sha256_bytes(raw.encode("utf-8"))


def index_upsert_document(
    *,
    doc_id: str,
    group_key: str,
    kdnr: str,
    object_folder: str,
    doctype: str,
    doc_date: str,
    file_name: str,
    file_path: str,
    extracted_text: str,
    used_ocr: bool,
    note: str = ""
) -> None:
    with _DB_LOCK:
        con = _db()
        try:
            exists = con.execute("SELECT doc_id FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
            if not exists:
                con.execute(
                    "INSERT INTO docs(doc_id, group_key, kdnr, object_folder, doctype, doc_date, created_at) VALUES (?,?,?,?,?,?,?)",
                    (doc_id, group_key, kdnr, object_folder, doctype, doc_date, _now_iso()),
                )

            row = con.execute("SELECT MAX(version_no) AS mx FROM versions WHERE doc_id=?", (doc_id,)).fetchone()
            mx = int(row["mx"] or 0) if row else 0
            version_no = mx + 1

            con.execute(
                """
                INSERT INTO versions(doc_id, version_no, bytes_sha256, file_name, file_path, extracted_text, used_ocr, note, created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    doc_id,
                    version_no,
                    doc_id,
                    file_name,
                    file_path,
                    extracted_text[:200000],
                    1 if used_ocr else 0,
                    note,
                    _now_iso(),
                ),
            )

            _fts_put(
                con,
                {
                    "doc_id": doc_id,
                    "kdnr": kdnr,
                    "doctype": doctype,
                    "doc_date": doc_date,
                    "file_name": file_name,
                    "file_path": file_path,
                    "content": extracted_text or "",
                },
            )
            con.commit()
        finally:
            con.close()


def assistant_search(query: str, kdnr: str = "", limit: int = ASSISTANT_DEFAULT_LIMIT, role: str = "ADMIN") -> List[Dict[str, Any]]:
    query = normalize_component(query)
    kdnr = normalize_component(kdnr)

    if not query:
        return []

    with _DB_LOCK:
        con = _db()
        try:
            use_fts = _has_fts5(con) and _table_exists(con, "docs_fts")
            rows: List[sqlite3.Row] = []

            if use_fts:
                q = query
                tokens = [t for t in re.split(r"\s+", q) if t]
                if len(tokens) >= 2:
                    q = " OR ".join(tokens)

                if kdnr:
                    rows = con.execute(
                        """
                        SELECT doc_id, kdnr, doctype, doc_date, file_name, file_path,
                               snippet(docs_fts, 6, '', '', ' … ', 12) AS snip
                        FROM docs_fts
                        WHERE docs_fts MATCH ? AND kdnr=?
                        LIMIT ?
                        """,
                        (q, kdnr, int(limit)),
                    ).fetchall()
                else:
                    rows = con.execute(
                        """
                        SELECT doc_id, kdnr, doctype, doc_date, file_name, file_path,
                               snippet(docs_fts, 6, '', '', ' … ', 12) AS snip
                        FROM docs_fts
                        WHERE docs_fts MATCH ?
                        LIMIT ?
                        """,
                        (q, int(limit)),
                    ).fetchall()
            else:
                like = f"%{query}%"
                if kdnr:
                    rows = con.execute(
                        """
                        SELECT d.doc_id, d.kdnr, d.doctype, d.doc_date,
                               v.file_name, v.file_path, substr(v.extracted_text,1,240) AS snip
                        FROM docs d
                        JOIN versions v ON v.doc_id=d.doc_id
                        WHERE d.kdnr=? AND (v.extracted_text LIKE ? OR v.file_name LIKE ? OR v.file_path LIKE ?)
                        GROUP BY d.doc_id
                        ORDER BY v.id DESC
                        LIMIT ?
                        """,
                        (kdnr, like, like, like, int(limit)),
                    ).fetchall()
                else:
                    rows = con.execute(
                        """
                        SELECT d.doc_id, d.kdnr, d.doctype, d.doc_date,
                               v.file_name, v.file_path, substr(v.extracted_text,1,240) AS snip
                        FROM docs d
                        JOIN versions v ON v.doc_id=d.doc_id
                        WHERE (v.extracted_text LIKE ? OR v.file_name LIKE ? OR v.file_path LIKE ?)
                        GROUP BY d.doc_id
                        ORDER BY v.id DESC
                        LIMIT ?
                        """,
                        (like, like, like, int(limit)),
                    ).fetchall()

            out: List[Dict[str, Any]] = []
            for r in rows:
                doc_id = str(r["doc_id"])
                vc = con.execute("SELECT COUNT(*) AS c FROM versions WHERE doc_id=?", (doc_id,)).fetchone()
                version_count = int(vc["c"] or 0) if vc else 0
                out.append(
                    {
                        "doc_id": doc_id,
                        "kdnr": str(r["kdnr"] or ""),
                        "doctype": str(r["doctype"] or ""),
                        "doc_date": str(r["doc_date"] or ""),
                        "file_name": str(r["file_name"] or ""),
                        "file_path": str(r["file_path"] or ""),
                        "version_count": version_count,
                        "note": "",
                        "preview": str(r["snip"] or ""),
                    }
                )
            return out
        finally:
            con.close()


def index_run_full(base_path: Optional[Path] = None) -> Dict[str, Any]:
    base = Path(base_path) if base_path else BASE_PATH
    if not base.exists():
        return {"ok": True, "indexed": 0, "skipped": 0, "errors": 0}

    indexed = 0
    skipped = 0
    errors = 0

    for fp in base.rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix.lower() not in SUPPORTED_EXT:
            continue
        try:
            b = _read_bytes(fp)
            doc_id = _sha256_bytes(b)

            with _DB_LOCK:
                con = _db()
                try:
                    exists = con.execute("SELECT doc_id FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
                finally:
                    con.close()

            if exists:
                skipped += 1
                continue

            file_name = fp.name
            kdnr = ""
            object_folder = ""
            for part in reversed(fp.parts):
                if re.match(r"^\d{3,}_", part):
                    kdnr = part.split("_", 1)[0]
                    object_folder = part
                    break

            text, used_ocr = _extract_text(fp)
            doctype = _detect_doctype(text, file_name)
            best_date, _ = _find_dates(text)
            group_key = _compute_group_key(kdnr, doctype, best_date, file_name)

            index_upsert_document(
                doc_id=doc_id,
                group_key=group_key,
                kdnr=kdnr,
                object_folder=object_folder,
                doctype=doctype,
                doc_date=best_date,
                file_name=file_name,
                file_path=str(fp),
                extracted_text=text,
                used_ocr=used_ocr,
                note="indexed_by_full_scan",
            )
            indexed += 1
        except Exception:
            errors += 1

    return {"ok": True, "indexed": indexed, "skipped": skipped, "errors": errors}


# ============================================================
# BACKGROUND ANALYSIS -> PENDING
# ============================================================
def analyze_to_pending(src: Path) -> str:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)

    t = _token()
    payload: Dict[str, Any] = {
        "status": "ANALYZING",
        "progress": 1.0,
        "progress_phase": "Init…",
        "error": "",
        "path": str(src),
        "filename": src.name,
        "used_ocr": False,
        "extracted_text": "",
        "preview": "",
        "doctype_suggested": "SONSTIGES",
        "doc_date_suggested": "",
        "doc_date_candidates": [],
        "kdnr_ranked": [],
        "name_suggestions": [],
        "addr_suggestions": [],
        "plzort_suggestions": [],
    }
    write_pending(t, payload)

    th = threading.Thread(target=_analyze_worker, args=(t,), daemon=True)
    th.start()
    return t


def start_background_analysis(src: Path) -> str:
    return analyze_to_pending(src)


def _set_progress(token: str, p: float, phase: str) -> None:
    d = read_pending(token) or {}
    d["progress"] = float(max(0.0, min(100.0, p)))
    d["progress_phase"] = phase
    write_pending(token, d)


def _analyze_worker(token: str) -> None:
    try:
        d = read_pending(token)
        if not d:
            return
        src = Path(d.get("path", ""))
        if not src.exists():
            d["status"] = "ERROR"
            d["error"] = "file_missing"
            d["progress"] = 0.0
            d["progress_phase"] = ""
            write_pending(token, d)
            return

        _set_progress(token, 5.0, "Datei lesen…")
        try:
            b = _read_bytes(src)
            doc_id = _sha256_bytes(b)
            d["doc_id"] = doc_id
        except Exception:
            d["doc_id"] = ""

        _set_progress(token, 18.0, "Text extrahieren…")
        text, used_ocr = _extract_text(src)
        d["used_ocr"] = bool(used_ocr)
        d["extracted_text"] = text
        d["preview"] = (text or "").strip()[:900].strip()

        _set_progress(token, 40.0, "Dokumenttyp/Datum erkennen…")
        d["doctype_suggested"] = _detect_doctype(text, src.name)
        best_date, date_cands = _find_dates(text)
        d["doc_date_suggested"] = best_date
        d["doc_date_candidates"] = date_cands

        _set_progress(token, 60.0, "Kundendaten erkennen…")
        d["kdnr_ranked"] = _find_kdnr_candidates(text)
        names, addrs, plzs = _find_name_addr_plzort(text)
        d["name_suggestions"] = names
        d["addr_suggestions"] = addrs
        d["plzort_suggestions"] = plzs

        _set_progress(token, 85.0, "Fertigstellen…")
        d["status"] = "READY"
        d["progress"] = 100.0
        d["progress_phase"] = "Bereit"
        write_pending(token, d)

    except Exception as e:
        d = read_pending(token) or {}
        d["status"] = "ERROR"
        d["error"] = str(e)
        d["progress"] = 0.0
        d["progress_phase"] = ""
        write_pending(token, d)


# ============================================================
# ARCHIVE / PROCESS
# ============================================================
def _doctype_code(doctype: str) -> str:
    doctype = normalize_component(doctype).upper()
    return {
        "RECHNUNG": "RE",
        "ANGEBOT": "ANG",
        "AUFTRAGSBESTAETIGUNG": "AB",
        "AW": "AW",
        "MAHNUNG": "MAH",
        "NACHTRAG": "NTR",
        "FOTO": "FOTO",
        "SONSTIGES": "DOC",
    }.get(doctype, "DOC")


def _compose_object_folder(kdnr: str, name: str, addr: str, plzort: str) -> str:
    parts = [_safe_fs(kdnr), _safe_fs(name), _safe_fs(addr), _safe_fs(plzort)]
    parts = [p for p in parts if p]
    return "_".join(parts)[:180]


def _compose_filename(doctype: str, doc_date: str, kdnr: str, name: str, addr: str, plzort: str, ext: str) -> str:
    code = _doctype_code(doctype)
    d = parse_excel_like_date(doc_date) or datetime.now().strftime("%Y-%m-%d")
    parts = [code, d]
    for x in [kdnr, name, addr, plzort]:
        xs = _safe_fs(x)
        if xs:
            parts.append(xs)
    base = "_".join(parts)
    base = re.sub(r"_+", "_", base).strip("_")[:160]
    return f"{base}{ext}"


def _next_version_suffix(target_dir: Path, base_name: str, ext: str) -> str:
    stem = Path(base_name).stem
    n = 2
    while True:
        cand = f"{stem}_v{n}{ext}"
        if not (target_dir / cand).exists():
            return cand
        n += 1


def _db_has_doc(doc_id: str) -> bool:
    with _DB_LOCK:
        con = _db()
        try:
            r = con.execute("SELECT doc_id FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
            return bool(r)
        finally:
            con.close()


def process_with_answers(src: Path, answers: Dict[str, Any]) -> Tuple[Path, Path, bool]:
    src = Path(src)
    if not src.exists():
        raise FileNotFoundError(src)

    kdnr = normalize_component(answers.get("kdnr", ""))
    use_existing = normalize_component(answers.get("use_existing", ""))
    name = normalize_component(answers.get("name", ""))
    addr = normalize_component(answers.get("addr", ""))
    plzort = normalize_component(answers.get("plzort", ""))
    doctype = normalize_component(answers.get("doctype", "SONSTIGES")).upper()
    doc_date = parse_excel_like_date(answers.get("document_date", "")) or ""

    if not kdnr:
        raise ValueError("kdnr missing")

    BASE_PATH.mkdir(parents=True, exist_ok=True)

    created_new_object = False
    if use_existing:
        folder = Path(use_existing)
        if not folder.exists() or not folder.is_dir():
            folder = BASE_PATH / _compose_object_folder(kdnr, name, addr, plzort)
            created_new_object = True
    else:
        folder_name = _compose_object_folder(kdnr, name, addr, plzort)
        folder = BASE_PATH / folder_name
        if not folder.exists():
            created_new_object = True

    folder.mkdir(parents=True, exist_ok=True)

    ext = src.suffix.lower()
    final_name = _compose_filename(doctype, doc_date, kdnr, name, addr, plzort, ext)
    target = folder / final_name

    b = _read_bytes(src)
    doc_id = _sha256_bytes(b)

    # if target exists, check byte equality
    if target.exists():
        try:
            if _sha256_bytes(_read_bytes(target)) == doc_id:
                # identical bytes: delete src; ensure index exists
                try:
                    src.unlink()
                except Exception:
                    pass
                if not _db_has_doc(doc_id):
                    text, used_ocr = _extract_text(target)
                    group_key = _compute_group_key(kdnr, doctype, doc_date, target.name)
                    index_upsert_document(
                        doc_id=doc_id,
                        group_key=group_key,
                        kdnr=kdnr,
                        object_folder=folder.name,
                        doctype=doctype,
                        doc_date=doc_date,
                        file_name=target.name,
                        file_path=str(target),
                        extracted_text=text,
                        used_ocr=used_ocr,
                        note="dedupe_same_bytes_existing_target",
                    )
                return folder, target, created_new_object
        except Exception:
            pass

        # different bytes => create a versioned filename (filesystem)
        final_name = _next_version_suffix(folder, final_name, ext)
        target = folder / final_name

    # Move into place
    try:
        src.replace(target)
    except Exception:
        target.write_bytes(b)
        try:
            src.unlink()
        except Exception:
            pass

    text, used_ocr = _extract_text(target)
    group_key = _compute_group_key(kdnr, doctype, doc_date, target.name)

    note = ""
    with _DB_LOCK:
        con = _db()
        try:
            g = con.execute("SELECT doc_id FROM docs WHERE group_key=? LIMIT 1", (group_key,)).fetchone()
            if g and str(g["doc_id"]) != doc_id:
                note = "new_version_same_group_key"
        finally:
            con.close()

    index_upsert_document(
        doc_id=doc_id,
        group_key=group_key,
        kdnr=kdnr,
        object_folder=folder.name,
        doctype=doctype,
        doc_date=doc_date,
        file_name=target.name,
        file_path=str(target),
        extracted_text=text,
        used_ocr=used_ocr,
        note=note,
    )

    return folder, target, created_new_object


# ============================================================
# INIT ON IMPORT
# ============================================================
def _bootstrap_dirs() -> None:
    EINGANG.mkdir(parents=True, exist_ok=True)
    BASE_PATH.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    DONE_DIR.mkdir(parents=True, exist_ok=True)


_bootstrap_dirs()
# db_init() is intentionally not auto-called here; your Flask runner calls db_init() at startup.
