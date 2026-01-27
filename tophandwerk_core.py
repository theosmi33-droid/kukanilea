#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Tophandwerk Core
- stabile Exporte / API-Contract für Flask UI
- Background Analyse + Progress (Pending/Done JSON)
- robuste Bestandskunden-Erkennung (underscore + commas)
- Template-Repair (01..09 + Unterordner in -01)
- bessere PDF-Extraktion: Seite 1, Region-für-Region, sinnvolle Reihenfolge, Bold/Font/Mitte gewichtung für Preview
- SQLite “Memory”: customers, objects, documents, users/roles, audit
- Assistant: Index + Search (inkl. Plug&Play: scan BASE_PATH)
"""

import os
import re
import json
import shutil
import hashlib
import unicodedata
import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from difflib import SequenceMatcher

from PIL import Image
import pytesseract

try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None


# ============================================================
# KONFIG / EXPORTS
# ============================================================
EINGANG = Path.home() / "Tophandwerk_Eingang"
BASE_PATH = Path.home() / "Tophandwerk_Kundenablage"
PENDING_DIR = Path.home() / "Tophandwerk_Pending"
DONE_DIR = Path.home() / "Tophandwerk_Done"

DB_PATH = Path.home() / "Tophandwerk_DB.sqlite3"

SUPPORTED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# OCR/Extraktion
OCR_MAX_PAGES = 1          # Fokus Seite 1
OCR_DPI = 220
TESS_LANG = "deu+eng"

# Template: 01..09
TEMPLATE_SUBFOLDERS = [
    "-01-- Kopien von Ausgang- AB + AN + AW + RE",
    "-02-- Händler- AN + RE",
    "-03-- SUB- AN + RE",
    "-04-- Aufmass Grundriss",
    "-05-- Ausschreibungsunterlagen",
    "-06-- Fotos",
    "-07-- Schriftverkehr",
    "-08-- Vertrag",
    "-09-- Sonstiges",
]
SUBFOLDERS_IN_01 = ["Angebote", "Auftragsbestaetigungen", "AW", "Rechnungen", "Mahnungen", "Nachtraege"]

# Doctype -> -01 Unterordner
DOCTYPE_TO_01 = {
    "ANGEBOT": "Angebote",
    "AN": "Angebote",
    "AUFTRAGSBESTAETIGUNG": "Auftragsbestaetigungen",
    "AB": "Auftragsbestaetigungen",
    "AW": "AW",
    "RECHNUNG": "Rechnungen",
    "RE": "Rechnungen",
    "MAHNUNG": "Mahnungen",
    "NACHTRAG": "Nachtraege",
}

# Kundennummer / Heuristiken
KDN_RE = re.compile(r"\b(\d{3,12})\b")
KUNDEN_KEY_RE = re.compile(r"(kundennr|kunden\-nr|kunden nr|kdnr|kd\-nr)\s*[:#]?\s*(\d{3,12})", re.IGNORECASE)
PLZORT_RE = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*)\b")

# Straße + Nr: deutlich toleranter (str / str. / straße etc.)
STREET_RE = re.compile(
    r"\b([A-ZÄÖÜa-zäöüß][\wÄÖÜäöüß\.\- ]{2,70}"
    r"(straße|strasse|str\.|str|weg|platz|allee|damm|ring|ufer|gasse|chaussee|promenade|höhe|hof|steig|pfad))\s+(\d{1,4}[a-zA-Z]?)\b",
    re.IGNORECASE
)


# ============================================================
# JSON utils (Pending/Done)
# ============================================================
def _load_json(path: Path, default):
    try:
        if not path.exists():
            return default
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


# ============================================================
# Normalize
# ============================================================
def normalize_ws(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def normalize_component(s: str) -> str:
    s = normalize_ws(s)
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("ß", "ss")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s\.\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def safe_filename(s: str) -> str:
    s = normalize_ws(s)
    s = unicodedata.normalize("NFKD", s)
    s = s.replace("ß", "ss")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^\w\s\.\-]", "", s, flags=re.UNICODE)
    s = s.replace(" ", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:180] if len(s) > 180 else s


# ============================================================
# DB Helpers (migrations-safe)
# ============================================================
def db_connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con


def _db_table_columns(con: sqlite3.Connection, table: str) -> List[str]:
    cur = con.cursor()
    try:
        cur.execute(f"PRAGMA table_info({table})")
        return [r[1] for r in cur.fetchall()]
    except Exception:
        return []


def _db_has_table(con: sqlite3.Connection, table: str) -> bool:
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def _db_add_column_if_missing(con: sqlite3.Connection, table: str, col: str, decl: str):
    cols = _db_table_columns(con, table)
    if col in cols:
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def _db_create_index_safe(con: sqlite3.Connection, sql: str):
    try:
        con.execute(sql)
    except Exception:
        pass


def db_init():
    """
    Muss alte DBs tolerieren (keine harten Annahmen über Spalten).
    """
    con = db_connect()
    cur = con.cursor()

    # customers
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        kdnr TEXT PRIMARY KEY,
        name TEXT,
        addr TEXT,
        plzort TEXT,
        updated_at TEXT
    )""")

    # objects
    cur.execute("""
    CREATE TABLE IF NOT EXISTS objects(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kdnr TEXT,
        folder_path TEXT,
        folder_name TEXT,
        name TEXT,
        addr TEXT,
        plzort TEXT,
        source_format TEXT,
        last_seen TEXT,
        last_used TEXT
    )""")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_objects_kdnr ON objects(kdnr)")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_objects_folder_path ON objects(folder_path)")

    # documents (Assistant index)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kdnr TEXT,
        doctype TEXT,
        file_path TEXT,
        file_name TEXT,
        file_hash TEXT,
        preview TEXT,
        extracted_text TEXT,
        indexed_at TEXT
    )""")
    # migrations: add any missing columns (future-proof)
    for col, decl in [
        ("kdnr", "TEXT"),
        ("doctype", "TEXT"),
        ("file_path", "TEXT"),
        ("file_name", "TEXT"),
        ("file_hash", "TEXT"),
        ("preview", "TEXT"),
        ("extracted_text", "TEXT"),
        ("indexed_at", "TEXT"),
    ]:
        _db_add_column_if_missing(con, "documents", col, decl)

    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_documents_path ON documents(file_path)")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_documents_kdnr ON documents(kdnr)")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_documents_name ON documents(file_name)")

    # RBAC
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users(
        username TEXT PRIMARY KEY,
        password_hash TEXT,
        created_at TEXT
    )""")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS user_roles(
        username TEXT,
        role TEXT,
        created_at TEXT,
        UNIQUE(username, role)
    )""")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(username)")

    # Audit
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT,
        user TEXT,
        role TEXT,
        action TEXT,
        target TEXT,
        meta_json TEXT
    )""")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit(ts)")
    _db_create_index_safe(con, "CREATE INDEX IF NOT EXISTS idx_audit_user ON audit(user)")

    con.commit()
    con.close()


# ============================================================
# RBAC (minimal)
# ============================================================
def _pw_hash(username: str, password: str) -> str:
    # salted with username; stable and local-only
    raw = (username.lower().strip() + "|" + password).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def rbac_create_user(username: str, password: str) -> str:
    db_init()
    u = (username or "").strip().lower()
    if not u or not password:
        raise ValueError("username/password required")
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute(
        "INSERT OR REPLACE INTO users(username,password_hash,created_at) VALUES(?,?,?)",
        (u, _pw_hash(u, password), now),
    )
    con.commit()
    con.close()
    return u


def rbac_assign_role(username: str, role: str):
    db_init()
    u = (username or "").strip().lower()
    r = (role or "").strip().upper()
    if not u or not r:
        return
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute(
        "INSERT OR IGNORE INTO user_roles(username,role,created_at) VALUES(?,?,?)",
        (u, r, now),
    )
    con.commit()
    con.close()


def rbac_get_user_roles(username: str) -> List[str]:
    db_init()
    u = (username or "").strip().lower()
    if not u:
        return []
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT role FROM user_roles WHERE username=? ORDER BY role", (u,))
    roles = [r[0] for r in cur.fetchall()]
    con.close()
    return roles


def rbac_verify_user(username: str, password: str) -> bool:
    db_init()
    u = (username or "").strip().lower()
    if not u or not password:
        return False
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT password_hash FROM users WHERE username=?", (u,))
    row = cur.fetchone()
    con.close()
    if not row:
        return False
    return row[0] == _pw_hash(u, password)


# ============================================================
# Audit
# ============================================================
def audit_log(user: str, role: str, action: str, target: str = "", meta: Optional[dict] = None):
    db_init()
    con = db_connect()
    ts = datetime.now().isoformat(timespec="seconds")
    meta_json = json.dumps(meta or {}, ensure_ascii=False)
    con.execute(
        "INSERT INTO audit(ts,user,role,action,target,meta_json) VALUES(?,?,?,?,?,?)",
        (ts, (user or ""), (role or ""), (action or ""), (target or ""), meta_json),
    )
    con.commit()
    con.close()


# ============================================================
# Template-Repair
# ============================================================
def ensure_template_structure(customer_folder: Path):
    customer_folder.mkdir(parents=True, exist_ok=True)
    for sf in TEMPLATE_SUBFOLDERS:
        (customer_folder / sf).mkdir(parents=True, exist_ok=True)
    base01 = customer_folder / TEMPLATE_SUBFOLDERS[0]
    base01.mkdir(parents=True, exist_ok=True)
    for sub in SUBFOLDERS_IN_01:
        (base01 / sub).mkdir(parents=True, exist_ok=True)


# ============================================================
# Bestehende Ordner robust erkennen
# ============================================================
def extract_plz(plzort: str) -> str:
    m = re.search(r"\b(\d{5})\b", plzort or "")
    return m.group(1) if m else ""


def normalize_address_like_maps(addr: str) -> str:
    a = normalize_component(addr).lower()
    a = a.replace(".", " ").replace(",", " ")
    a = re.sub(r"\bstr\b", "strasse", a)
    a = re.sub(r"\bstr\.\b", "strasse", a)
    a = re.sub(r"\bstraße\b", "strasse", a)
    a = re.sub(r"\bstra?ss?e\b", "strasse", a)
    a = re.sub(r"\s+", " ", a).strip()
    return a


def similarity(a: str, b: str) -> float:
    a = normalize_address_like_maps(a)
    b = normalize_address_like_maps(b)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def parse_folder_fields_underscore(foldername: str) -> Dict[str, str]:
    parts = (foldername or "").split("_")
    out = {"kdnr": "", "name": "", "addr": "", "plzort": ""}
    if len(parts) >= 1:
        out["kdnr"] = parts[0]
    if len(parts) >= 2:
        out["name"] = parts[1]
    if len(parts) >= 3:
        out["addr"] = parts[2]
    if len(parts) >= 4:
        out["plzort"] = "_".join(parts[3:])
    return out


def parse_folder_fields_commas(foldername: str) -> Dict[str, str]:
    # Beispiel: "3648 BBB SO Wuhlheide, Treskowallee 211, 12459 Berlin"
    out = {"kdnr": "", "name": "", "addr": "", "plzort": ""}
    parts = [p.strip() for p in (foldername or "").split(",") if p.strip()]
    if not parts:
        return out

    first = parts[0]
    m = re.match(r"^\s*(\d{3,12})\s+(.*)$", first)
    if m:
        out["kdnr"] = m.group(1).strip()
        out["name"] = normalize_component(m.group(2))
    else:
        m2 = re.match(r"^\s*(\d{3,12})\s*$", first)
        if m2:
            out["kdnr"] = m2.group(1)

    if len(parts) >= 2:
        out["addr"] = normalize_component(parts[1])
    if len(parts) >= 3:
        out["plzort"] = normalize_component(parts[2])
    return out


def detect_folder_format(foldername: str) -> str:
    if "_" in foldername and re.match(r"^\d{3,12}_", foldername):
        return "underscore"
    if "," in foldername and re.match(r"^\s*\d{3,12}\s+", foldername):
        return "commas"
    return "unknown"


def parse_folder_fields(foldername: str) -> Dict[str, str]:
    fmt = detect_folder_format(foldername)
    if fmt == "underscore":
        return parse_folder_fields_underscore(foldername)
    if fmt == "commas":
        return parse_folder_fields_commas(foldername)
    return {"kdnr": "", "name": "", "addr": "", "plzort": ""}


def find_existing_customer_folders(base_path: Path, kdnr: str) -> List[Path]:
    if not base_path.exists():
        return []
    out = []
    kdnr = (kdnr or "").strip()
    if not kdnr:
        return []

    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        nm = child.name
        fmt = detect_folder_format(nm)
        if fmt == "underscore":
            if nm.startswith(f"{kdnr}_"):
                out.append(child)
        elif fmt == "commas":
            ff = parse_folder_fields_commas(nm)
            if ff.get("kdnr") == kdnr:
                out.append(child)

    out.sort(key=lambda x: x.name.lower())
    return out


def best_match_object_folder(existing_folders: List[Path], addr: str, plzort: str) -> Tuple[Optional[Path], float]:
    if not existing_folders:
        return None, 0.0

    plz = extract_plz(plzort)
    best = None
    best_score = 0.0

    for f in existing_folders:
        fields = parse_folder_fields(f.name)
        f_plz = extract_plz(fields.get("plzort", ""))
        if plz and f_plz and plz != f_plz:
            continue
        score = similarity(addr, fields.get("addr", ""))
        if score > best_score:
            best_score = score
            best = f

    return best, best_score


# ============================================================
# DB “Memory”: customers/objects/documents
# ============================================================
def db_upsert_customer(kdnr: str, name: str, addr: str, plzort: str):
    db_init()
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("""
      INSERT INTO customers(kdnr,name,addr,plzort,updated_at)
      VALUES(?,?,?,?,?)
      ON CONFLICT(kdnr) DO UPDATE SET
        name=excluded.name,
        addr=excluded.addr,
        plzort=excluded.plzort,
        updated_at=excluded.updated_at
    """, (kdnr, name, addr, plzort, now))
    con.commit()
    con.close()


def db_get_customer(kdnr: str) -> Optional[Dict]:
    db_init()
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT kdnr, name, addr, plzort, updated_at FROM customers WHERE kdnr=?", (kdnr,))
    r = cur.fetchone()
    con.close()
    if not r:
        return None
    return {"kdnr": r[0], "name": r[1], "addr": r[2], "plzort": r[3], "updated_at": r[4]}


def db_upsert_object(kdnr: str, folder_path: str, folder_name: str, name: str, addr: str, plzort: str, source_format: str):
    db_init()
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("DELETE FROM objects WHERE folder_path=?", (folder_path,))
    con.execute("""
      INSERT INTO objects(kdnr, folder_path, folder_name, name, addr, plzort, source_format, last_seen, last_used)
      VALUES(?,?,?,?,?,?,?,?,?)
    """, (kdnr, folder_path, folder_name, name, addr, plzort, source_format, now, None))
    con.commit()
    con.close()


def db_touch_object_used(folder_path: str):
    db_init()
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("UPDATE objects SET last_used=? WHERE folder_path=?", (now, folder_path))
    con.commit()
    con.close()


def db_add_or_update_document(kdnr: str, doctype: str, file_path: str, preview: str = "", extracted_text: str = ""):
    db_init()
    fp = str(Path(file_path).resolve())
    fn = Path(fp).name
    fh = file_hash(Path(fp))
    now = datetime.now().isoformat(timespec="seconds")

    con = db_connect()
    # dedupe by file_path (canonical)
    con.execute("DELETE FROM documents WHERE file_path=?", (fp,))
    con.execute("""
      INSERT INTO documents(kdnr, doctype, file_path, file_name, file_hash, preview, extracted_text, indexed_at)
      VALUES(?,?,?,?,?,?,?,?)
    """, (kdnr, doctype, fp, fn, fh, preview, extracted_text, now))
    con.commit()
    con.close()


def db_search_documents(query: str, kdnr: str = "", limit: int = 25) -> List[Dict]:
    db_init()
    q = (query or "").strip()
    if not q:
        return []
    k = (kdnr or "").strip()

    like = f"%{q}%"
    con = db_connect()
    cur = con.cursor()

    if k:
        cur.execute("""
          SELECT kdnr, doctype, file_path, file_name, preview
          FROM documents
          WHERE kdnr=?
            AND (file_name LIKE ? OR file_path LIKE ? OR preview LIKE ? OR extracted_text LIKE ?)
          ORDER BY indexed_at DESC
          LIMIT ?
        """, (k, like, like, like, like, int(limit)))
    else:
        cur.execute("""
          SELECT kdnr, doctype, file_path, file_name, preview
          FROM documents
          WHERE (file_name LIKE ? OR file_path LIKE ? OR preview LIKE ? OR extracted_text LIKE ?)
          ORDER BY indexed_at DESC
          LIMIT ?
        """, (like, like, like, like, int(limit)))

    rows = cur.fetchall()
    con.close()

    out = []
    for r in rows:
        out.append({
            "kdnr": r[0],
            "doctype": r[1],
            "file_path": r[2],
            "file_name": r[3],
            "preview": (r[4] or "")[:500],
        })
    return out


# ============================================================
# Sync DB (customers/objects) aus BASE_PATH (performant)
# ============================================================
def sync_db_from_filesystem(base_path: Path):
    db_init()
    if not base_path.exists():
        return

    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        fmt = detect_folder_format(child.name)
        fields = parse_folder_fields(child.name)
        kdnr = (fields.get("kdnr") or "").strip()
        if not kdnr:
            continue

        name = fields.get("name") or ""
        addr = fields.get("addr") or ""
        plzort = fields.get("plzort") or ""

        ensure_template_structure(child)
        db_upsert_customer(kdnr, name, addr, plzort)
        db_upsert_object(kdnr, str(child), child.name, name, addr, plzort, fmt)


# ============================================================
# Assistant Index (Plug&Play): scan BASE_PATH for existing docs
# ============================================================
def _infer_kdnr_from_path(fp: Path) -> str:
    # Expect customer folder begins with digits
    parts = fp.parts
    for seg in parts:
        if re.match(r"^\d{3,12}[_\s,]", seg) or re.match(r"^\d{3,12}$", seg):
            m = re.match(r"^(\d{3,12})", seg)
            if m:
                return m.group(1)
    # fallback: any digits folder name
    for seg in parts:
        m = re.match(r"^(\d{3,12})_", seg)
        if m:
            return m.group(1)
    return ""


def _infer_doctype_from_path(fp: Path) -> str:
    low = str(fp).lower()
    if "angebote" in low:
        return "ANGEBOT"
    if "rechnungen" in low:
        return "RECHNUNG"
    if "auftragsbestaet" in low or "auftragsbest" in low:
        return "AUFTRAGSBESTAETIGUNG"
    if re.search(r"\baw\b", low) or "/aw/" in low:
        return "AW"
    if "mahnung" in low:
        return "MAHNUNG"
    if "nachtra" in low:
        return "NACHTRAG"
    if "fotos" in low:
        return "FOTO"
    return "SONSTIGES"


def assistant_sync_index(base_path: Path = BASE_PATH, max_files: int = 2000):
    """
    Plug&Play: indexiert vorhandene Dokumente aus BASE_PATH.
    - Fokus: PDFs (Seite 1 text layer), Images nur minimal (Dateiname) um nicht alles zu OCRn.
    """
    db_init()
    if not base_path.exists():
        return

    count = 0
    for fp in base_path.rglob("*"):
        if count >= max_files:
            break
        if not fp.is_file():
            continue
        ext = fp.suffix.lower()
        if ext not in SUPPORTED_EXT:
            continue

        # skip Eingang/DONE/PENDING falls darin mal indexiert wird
        try:
            rp = fp.resolve()
            if str(rp).startswith(str(EINGANG.resolve()) + os.sep):
                continue
            if str(rp).startswith(str(PENDING_DIR.resolve()) + os.sep):
                continue
            if str(rp).startswith(str(DONE_DIR.resolve()) + os.sep):
                continue
        except Exception:
            pass

        kdnr = _infer_kdnr_from_path(fp)
        doctype = _infer_doctype_from_path(fp)

        preview = ""
        extracted = ""
        # PDFs: leichter Extract, keine OCR-Orgie
        if ext == ".pdf":
            extracted, _, preview = extract_pdf_text_weighted(fp, allow_ocr=False)
        else:
            # Images: nur Dateiname/Path als “light index”
            preview = fp.name
            extracted = ""

        db_add_or_update_document(kdnr, doctype, str(fp), preview=preview[:900], extracted_text=extracted[:5000])
        count += 1


def assistant_search(query: str, kdnr: str = "", limit: int = 25) -> List[Dict]:
    """
    Sucht nur in Kundenablage-Index (Eingang bleibt implizit im Hintergrund).
    """
    # ensure at least some index exists (plug&play)
    assistant_sync_index(BASE_PATH, max_files=800)

    rows = db_search_documents(query=query, kdnr=kdnr, limit=limit)

    # Dedup: collapse variants "...file.pdf" and "...file_114520.pdf"
    out = []
    seen = set()

    def _dedupe_key(path: str) -> str:
        p = Path(path)
        stem = re.sub(r"_(\d{6})$", "", p.stem)
        return str(p.parent).lower() + "/" + stem.lower() + p.suffix.lower()

    for r in rows:
        fp = r.get("file_path") or ""
        if not fp:
            continue
        key = _dedupe_key(fp)
        if key in seen:
            continue
        seen.add(key)
        out.append(r)

    return out


# ============================================================
# Text-Extraktion (PDF Seite 1) – Region + Weighted Preview
# ============================================================
def _clean_text(s: str) -> str:
    if not s:
        return ""
    # remove control characters but keep newline/tab
    s = "".join(ch for ch in s if ch == "\n" or ch == "\t" or (ord(ch) >= 32 and ord(ch) != 127))
    # unify whitespace (but keep line breaks for structure)
    s = s.replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    # fix hyphenation across line breaks: "Ange-\nbot" -> "Angebot"
    s = re.sub(r"(\w)-\n(\w)", r"\1\2", s)
    # normalize
    s = s.strip()
    return s


def _line_center_weight(y0: float, y1: float, page_h: float) -> float:
    if page_h <= 0:
        return 1.0
    yc = (y0 + y1) / 2.0
    mid = page_h * 0.52  # leicht unter Mitte
    dist = abs(yc - mid) / page_h
    return max(0.30, 1.15 - dist * 1.6)


def _sort_spans_reading_order(spans: List[dict]) -> List[dict]:
    # Sort by y then x using bbox
    def key(s):
        bb = s.get("bbox") or [0, 0, 0, 0]
        return (round(float(bb[1]) / 3.0), float(bb[0]))
    return sorted(spans, key=key)


def _reconstruct_text_regions(page_dict: dict, page_h: float) -> Tuple[str, List[Tuple[float, str]]]:
    """
    Build structured text region-by-region (top/header, middle, bottom) using spans order.
    Also returns scored lines for preview.
    """
    blocks = (page_dict or {}).get("blocks", [])
    all_lines = []
    scored_lines: List[Tuple[float, str]] = []

    # Gather spans with positions
    spans_all = []
    for b in blocks:
        for ln in b.get("lines", []) or []:
            for s in ln.get("spans", []) or []:
                txt = (s.get("text") or "")
                if not txt.strip():
                    continue
                spans_all.append(s)

    spans_all = _sort_spans_reading_order(spans_all)
    if not spans_all:
        return "", []

    # Determine region boundaries (top/middle/bottom)
    top_cut = page_h * 0.25
    mid_cut = page_h * 0.70

    regions = {"TOP": [], "MID": [], "BOT": []}
    for s in spans_all:
        bb = s.get("bbox") or [0, 0, 0, 0]
        y = float(bb[1])
        if y <= top_cut:
            regions["TOP"].append(s)
        elif y <= mid_cut:
            regions["MID"].append(s)
        else:
            regions["BOT"].append(s)

    def region_to_lines(spans: List[dict]) -> List[str]:
        # Bucket by approximate line y
        buckets = {}
        for s in spans:
            bb = s.get("bbox") or [0, 0, 0, 0]
            y = float(bb[1])
            ky = round(y / 3.0)  # coarse lines
            buckets.setdefault(ky, []).append(s)

        lines = []
        for ky in sorted(buckets.keys()):
            row = _sort_spans_reading_order(buckets[ky])
            # join with spaces if needed
            parts = []
            prev_x1 = None
            for sp in row:
                t = (sp.get("text") or "").strip()
                if not t:
                    continue
                bb = sp.get("bbox") or [0, 0, 0, 0]
                x0 = float(bb[0])
                if prev_x1 is not None and x0 - prev_x1 > 8:
                    parts.append(" ")
                elif parts:
                    parts.append(" ")
                parts.append(t)
                prev_x1 = float(bb[2])
            line = "".join(parts).strip()
            # de-duplicate weird single chars
            line = re.sub(r"[•·]{2,}", "•", line)
            if line:
                lines.append(line)
        return lines

    # Build text in region order
    for reg in ["TOP", "MID", "BOT"]:
        lines = region_to_lines(regions[reg])
        if lines:
            all_lines.append(f"[{reg}]")
            all_lines.extend(lines)
            all_lines.append("")  # blank line

    # For preview: score lines using font size + bold + center weight
    # We'll score from original blocks/lines to better preserve bold/size
    for b in blocks:
        for ln in b.get("lines", []) or []:
            spans = ln.get("spans", []) or []
            if not spans:
                continue
            line_text = "".join((sp.get("text") or "") for sp in spans).strip()
            if not line_text:
                continue

            max_size = 0.0
            boldish = 0.0
            y0 = 1e9
            y1 = -1e9
            for sp in spans:
                sz = float(sp.get("size") or 0.0)
                max_size = max(max_size, sz)
                flags = int(sp.get("flags") or 0)
                if flags & 16:
                    boldish = 1.0
                fn = (sp.get("font") or "").lower()
                if "bold" in fn:
                    boldish = 1.0

                bb = sp.get("bbox") or None
                if bb and len(bb) == 4:
                    y0 = min(y0, float(bb[1]))
                    y1 = max(y1, float(bb[3]))

            center_w = _line_center_weight(y0 if y0 != 1e9 else 0.0, y1 if y1 != -1e9 else 0.0, page_h)
            score = (max_size * 2.2) + (boldish * 18.0)
            score *= center_w
            scored_lines.append((score, line_text))

    full = _clean_text("\n".join(all_lines))
    return full, scored_lines


def extract_pdf_text_weighted(p: Path, allow_ocr: bool = True) -> Tuple[str, bool, str]:
    """
    Returns: extracted_text, used_ocr, preview
    - Page 1 only
    - PyMuPDF dict extraction -> region reconstruction
    - fallback pypdf text layer
    - OCR only if allow_ocr and text layer weak
    """
    used_ocr = False
    extracted_text = ""
    preview = ""

    # Primary: PyMuPDF dict
    if fitz is not None:
        try:
            doc = fitz.open(p)
            if len(doc) > 0:
                page = doc[0]
                page_h = float(page.rect.height)
                page_dict = page.get_text("dict")
                extracted_text, scored_lines = _reconstruct_text_regions(page_dict, page_h)

                # Preview = top scored lines
                scored_lines.sort(key=lambda x: -x[0])
                top = [t for _, t in scored_lines[:40]]
                preview = normalize_ws(" | ".join(top))[:900]
            doc.close()
        except Exception:
            extracted_text = ""
            preview = ""

    # Fallback: pypdf
    if (not extracted_text or len(extracted_text) < 120) and PdfReader is not None:
        try:
            reader = PdfReader(str(p))
            if reader.pages:
                t = reader.pages[0].extract_text() or ""
                t = _clean_text(t)
                if t.strip():
                    extracted_text = t.strip()
                    preview = normalize_ws(extracted_text[:900])
        except Exception:
            pass

    # OCR fallback (page 1 only)
    if allow_ocr and (not extracted_text or len(extracted_text) < 120) and fitz is not None:
        used_ocr = True
        try:
            doc = fitz.open(p)
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
                if pix.width * pix.height <= 60_000_000:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr = pytesseract.image_to_string(img, lang=TESS_LANG) or ""
                    ocr = _clean_text(ocr)
                    if ocr.strip():
                        extracted_text = ocr.strip()
                        preview = normalize_ws(extracted_text[:900])
            doc.close()
        except Exception:
            pass

    return extracted_text, used_ocr, preview


def extract_image_text(p: Path) -> Tuple[str, bool, str]:
    used_ocr = True
    try:
        img = Image.open(p)
        t = pytesseract.image_to_string(img, lang=TESS_LANG) or ""
        t = _clean_text(t)
        return t, used_ocr, normalize_ws(t[:900])
    except Exception:
        return "", used_ocr, ""


def extract_text(p: Path) -> Tuple[str, bool, str]:
    ext = p.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text_weighted(p, allow_ocr=True)
    if ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}:
        return extract_image_text(p)
    return "", False, ""


# ============================================================
# Vorschläge
# ============================================================
def rank_kundennummer(text: str) -> List[List]:
    t = text or ""
    ranked: Dict[str, int] = {}

    for m in KUNDEN_KEY_RE.finditer(t):
        k = m.group(2)
        ranked[k] = ranked.get(k, 0) + 160

    for m in KDN_RE.finditer(t):
        k = m.group(1)
        # defensive noise filter
        if len(k) == 4 and k.startswith("20"):
            continue
        ranked[k] = ranked.get(k, 0) + 10

    out = [[k, v] for k, v in ranked.items()]
    out.sort(key=lambda x: (-x[1], x[0]))
    return out[:12]


def suggest_plzort(text: str) -> List[str]:
    out = []
    for m in PLZORT_RE.finditer(text or ""):
        cand = f"{m.group(1)} {normalize_component(m.group(2))}".strip()
        if cand not in out:
            out.append(cand)
    return out[:10]


def suggest_address(text: str) -> List[str]:
    out = []
    for m in STREET_RE.finditer(text or ""):
        street = normalize_component(m.group(1))
        hn = normalize_component(m.group(3))
        cand = f"{street} {hn}".strip()
        cand = cand.replace(" Str ", " Strasse ").replace(" str ", " strasse ")
        if cand and cand not in out:
            out.append(cand)
    # small extra heuristic: "Str." variants
    if not out:
        t = (text or "")
        # detect "Xxxstr. 12"
        m2 = re.search(r"\b([A-ZÄÖÜa-zäöüß][\wÄÖÜäöüß\.\- ]{2,70}str\.)\s*(\d{1,4}[a-zA-Z]?)\b", t, flags=re.IGNORECASE)
        if m2:
            cand = f"{normalize_component(m2.group(1))} {normalize_component(m2.group(2))}"
            if cand not in out:
                out.append(cand)
    return out[:10]


def suggest_name_from_text(filename: str, text: str) -> List[str]:
    out = []
    fn = Path(filename).stem if filename else ""
    fn = normalize_component(fn)
    if fn and len(fn) >= 3:
        out.append(fn[:60])

    t = text or ""
    for pat in [
        r"\bHerrn?\s+([A-ZÄÖÜ][^\n,]{3,60})",
        r"\bFrau\s+([A-ZÄÖÜ][^\n,]{3,60})",
        r"\bFirma\s*[:\-]\s*([A-ZÄÖÜ][^\n,]{3,80})",
        r"\bKunde\s*[:\-]\s*([A-ZÄÖÜ][^\n,]{3,80})",
    ]:
        m = re.search(pat, t, flags=re.IGNORECASE)
        if m:
            cand = normalize_component(m.group(1))
            if cand and cand not in out:
                out.append(cand)

    if "Kunde" not in out:
        out.append("Kunde")
    return out[:8]


def suggest_from_db(kdnr: str) -> Dict[str, List[str]]:
    c = db_get_customer(kdnr)
    if not c:
        return {"name": [], "addr": [], "plzort": []}
    out = {"name": [], "addr": [], "plzort": []}
    if c.get("name"):
        out["name"].append(c["name"])
    if c.get("addr"):
        out["addr"].append(c["addr"])
    if c.get("plzort"):
        out["plzort"].append(c["plzort"])
    return out


def guess_doctype(filename: str, text: str) -> str:
    f = (filename or "").lower()
    t = (text or "").lower()
    if "mahnung" in f or "mahnung" in t:
        return "MAHNUNG"
    if re.search(r"\baw\b", f) or "arbeitswert" in t:
        return "AW"
    if "auftragsbest" in f or "auftragsbest" in t:
        return "AUFTRAGSBESTAETIGUNG"
    if "rechnung" in f or "rechnung" in t or re.search(r"\brg\b", f):
        return "RECHNUNG"
    if "angebot" in f or "angebot" in t:
        return "ANGEBOT"
    if "nachtrag" in f or "nachtrag" in t:
        return "NACHTRAG"
    return "SONSTIGES"


# ============================================================
# Pending/Done API (EXPORTS)
# ============================================================
def file_token(p: Path) -> str:
    st = p.stat()
    raw = f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()


def file_hash(p: Path) -> str:
    try:
        st = p.stat()
        raw = f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", errors="ignore")
        return hashlib.sha1(raw).hexdigest()
    except Exception:
        return hashlib.sha1(str(p).encode("utf-8")).hexdigest()


def write_pending(token: str, payload: Dict):
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    _save_json(PENDING_DIR / f"{token}.json", payload)


def read_pending(token: str) -> Optional[Dict]:
    p = PENDING_DIR / f"{token}.json"
    if not p.exists():
        return None
    return _load_json(p, None)


def delete_pending(token: str):
    p = PENDING_DIR / f"{token}.json"
    if p.exists():
        try:
            p.unlink()
        except Exception:
            pass


def list_pending() -> List[Dict]:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(PENDING_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        obj = _load_json(f, None)
        if obj:
            obj["_token"] = f.stem
            items.append(obj)
    return items


def write_done(token: str, payload: Dict):
    DONE_DIR.mkdir(parents=True, exist_ok=True)
    _save_json(DONE_DIR / f"{token}.json", payload)


def read_done(token: str) -> Optional[Dict]:
    p = DONE_DIR / f"{token}.json"
    if not p.exists():
        return None
    return _load_json(p, None)


# ============================================================
# Background Analyse + Progress (EXPORT)
# ============================================================
def _set_progress(token: str, pct: float, phase: str = ""):
    p = read_pending(token) or {}
    pct = max(0.0, min(100.0, float(pct)))
    p["progress"] = pct
    if phase:
        p["progress_phase"] = phase
    write_pending(token, p)


def _analyze_worker(token: str, file_path: Path):
    try:
        _set_progress(token, 2.0, "Datei vorbereitet")

        _set_progress(token, 6.0, "Bestand synchronisieren")
        sync_db_from_filesystem(BASE_PATH)

        _set_progress(token, 10.0, "Text extrahieren (Seite 1, strukturiert)")
        text, used_ocr, preview = extract_text(file_path)

        _set_progress(token, 55.0, "Vorschläge berechnen")
        kdnr_ranked = rank_kundennummer(text)
        plz_sug = suggest_plzort(text)
        addr_sug = suggest_address(text)
        name_sug = suggest_name_from_text(file_path.name, text)
        doctype_sug = guess_doctype(file_path.name, text)

        payload = read_pending(token) or {}
        payload.update({
            "filename": file_path.name,
            "path": str(file_path),
            "used_ocr": bool(used_ocr),
            "preview": preview,
            "extracted_text": (text or "")[:25000],
            "kdnr_ranked": kdnr_ranked,
            "name_suggestions": name_sug,
            "addr_suggestions": addr_sug,
            "plzort_suggestions": plz_sug,
            "doctype_suggested": doctype_sug,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "READY",
        })
        write_pending(token, payload)

        _set_progress(token, 100.0, "Fertig")
    except Exception as e:
        payload = read_pending(token) or {}
        payload["status"] = "ERROR"
        payload["error"] = str(e)
        _set_progress(token, 100.0, "Fehler")
        write_pending(token, payload)


def start_background_analysis(file_path: Path) -> str:
    db_init()
    token = file_token(file_path)
    if (PENDING_DIR / f"{token}.json").exists():
        return token

    write_pending(token, {
        "filename": file_path.name,
        "path": str(file_path),
        "status": "ANALYZING",
        "progress": 0.0,
        "progress_phase": "Start",
        "created_at": datetime.now().isoformat(timespec="seconds"),
    })

    t = threading.Thread(target=_analyze_worker, args=(token, file_path), daemon=True)
    t.start()
    return token


# Backward-compat alias (UPLOAD imports analyze_to_pending)
def analyze_to_pending(file_path: Path) -> str:
    return start_background_analysis(file_path)


# ============================================================
# Ablage (EXPORT)
# ============================================================
def target_subfolder(folder: Path, doctype: str) -> Path:
    dt = (doctype or "SONSTIGES").upper()
    if dt in DOCTYPE_TO_01:
        return folder / TEMPLATE_SUBFOLDERS[0] / DOCTYPE_TO_01[dt]
    return folder / TEMPLATE_SUBFOLDERS[8]


def standard_filename(doctype: str, kdnr: str, name: str, addr: str, plzort: str, original_ext: str) -> str:
    dt = datetime.now().strftime("%Y-%m-%d")
    doctype = (doctype or "DOC").upper()
    code = {
        "RECHNUNG": "RE",
        "RE": "RE",
        "ANGEBOT": "ANG",
        "AN": "ANG",
        "AUFTRAGSBESTAETIGUNG": "AB",
        "AB": "AB",
        "AW": "AW",
        "MAHNUNG": "MAH",
        "NACHTRAG": "NTR",
    }.get(doctype, "DOC")

    core = f"{code}_{dt}_{kdnr}_{name}_{addr}_{plzort}"
    core = safe_filename(core)
    return f"{core}{original_ext.lower()}"


def choose_or_create_object_folder(kdnr: str, name: str, addr: str, plzort: str, prefer_path: str = "") -> Tuple[Path, bool]:
    existing = find_existing_customer_folders(BASE_PATH, kdnr)

    # UI: explizit gewählt
    if prefer_path:
        fp = Path(prefer_path)
        if fp.exists() and fp.is_dir():
            ensure_template_structure(fp)
            return fp, False

    # Fuzzy Match
    best, score = best_match_object_folder(existing, addr, plzort)
    if best is not None and score >= 0.86:
        ensure_template_structure(best)
        return best, False

    # Neuer Ordner (underscore canonical)
    kdnr_n = normalize_component(kdnr)
    name_n = normalize_component(name)
    addr_n = normalize_component(addr)
    plzort_n = normalize_component(plzort)
    foldername = f"{kdnr_n}_{name_n}_{addr_n}_{plzort_n}".replace(" ", "_")
    folder = BASE_PATH / foldername
    folder.mkdir(parents=True, exist_ok=True)
    ensure_template_structure(folder)
    return folder, True


def process_with_answers(file_path: Path, answers: Dict[str, str]) -> Tuple[Path, Path, bool]:
    kdnr = normalize_component(answers.get("kdnr", ""))
    name = normalize_component(answers.get("name", "Kunde"))
    addr = normalize_component(answers.get("addr", "Adresse"))
    plzort = normalize_component(answers.get("plzort", "PLZ Ort"))
    doctype = (answers.get("doctype") or "SONSTIGES").upper()
    prefer_existing = (answers.get("use_existing") or "").strip()

    folder, created_new = choose_or_create_object_folder(kdnr, name, addr, plzort, prefer_path=prefer_existing)
    ensure_template_structure(folder)

    dest_dir = target_subfolder(folder, doctype)
    dest_dir.mkdir(parents=True, exist_ok=True)

    new_name = standard_filename(doctype, kdnr, name, addr, plzort, file_path.suffix)
    final_path = dest_dir / new_name
    if final_path.exists():
        ts = datetime.now().strftime("%H%M%S")
        final_path = dest_dir / f"{final_path.stem}_{ts}{final_path.suffix}"

    # MOVE (niemals kopieren)
    shutil.move(str(file_path), str(final_path))

    # DB Memory
    db_upsert_customer(kdnr, name, addr, plzort)
    db_upsert_object(kdnr, str(folder), folder.name, name, addr, plzort, detect_folder_format(folder.name))
    db_touch_object_used(str(folder))

    # Index doc (Assistant): lightweight, prefer preview from filename if expensive
    try:
        ext = final_path.suffix.lower()
        preview = ""
        extracted = ""
        if ext == ".pdf":
            extracted, _, preview = extract_pdf_text_weighted(final_path, allow_ocr=False)
        db_add_or_update_document(kdnr, doctype, str(final_path), preview=preview[:900], extracted_text=extracted[:8000])
    except Exception:
        pass

    return folder, final_path, created_new
# ==============================
# Index (BASE_PATH only) + Dedupe + Versions
# ==============================
import os
import hashlib

INDEX_SUPPORTED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

def _sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()

def _iter_files_under(root: Path):
    # scan only BASE_PATH, ignore hidden
    root = root.resolve()
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        # skip hidden dirs
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue
            p = Path(dirpath) / fn
            try:
                if not p.is_file():
                    continue
            except Exception:
                continue
            ext = p.suffix.lower()
            if ext in INDEX_SUPPORTED_EXT:
                yield p

def _db_exec(con, sql: str, params=()):
    cur = con.cursor()
    cur.execute(sql, params)
    return cur

def _db_table_has_column(con, table: str, col: str) -> bool:
    try:
        cur = con.cursor()
        cur.execute(f"PRAGMA table_info({table})")
        cols = [r[1] for r in cur.fetchall()]
        return col in cols
    except Exception:
        return False

def _ensure_index_tables():
    """
    Create minimal index tables if missing.
    This must NOT crash on older DBs.
    """
    con = db_connect()
    cur = con.cursor()

    # documents table (doc_id as PK)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents(
        doc_id TEXT PRIMARY KEY,
        kdnr TEXT,
        object_path TEXT,
        doctype TEXT,
        title TEXT,
        created_at TEXT,
        updated_at TEXT,
        current_version_id TEXT
    )""")

    # versions table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS document_versions(
        version_id TEXT PRIMARY KEY,
        doc_id TEXT,
        file_path TEXT,
        sha256 TEXT,
        size INTEGER,
        mtime_ns INTEGER,
        created_at TEXT
    )""")

    # indices (safe)
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions_doc ON document_versions(doc_id)")
    except Exception:
        pass
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_doc_versions_sha ON document_versions(sha256)")
    except Exception:
        pass
    try:
        cur.execute("CREATE INDEX IF NOT EXISTS idx_documents_kdnr ON documents(kdnr)")
    except Exception:
        pass

    con.commit()
    con.close()

def index_upsert_file(file_path: Path, kdnr: str = "", doctype: str = "") -> str:
    """
    Upsert one file into documents + document_versions.
    Dedupe by doc_id = sha256(content).
    Adds a new version row if file_path or mtime differs and version_id not present.
    """
    _ensure_index_tables()

    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(str(p))
    if p.suffix.lower() not in INDEX_SUPPORTED_EXT:
        return ""

    st = p.stat()
    sha = _sha256_file(p)
    doc_id = sha  # content-addressed doc_id

    now = datetime.now().isoformat(timespec="seconds")
    title = p.stem

    # version_id: stable per path+mtime+sha
    version_id = hashlib.sha1(f"{sha}|{st.st_size}|{st.st_mtime_ns}|{p.resolve()}".encode("utf-8", "ignore")).hexdigest()

    con = db_connect()
    cur = con.cursor()

    # upsert documents
    cur.execute("SELECT doc_id, current_version_id FROM documents WHERE doc_id=?", (doc_id,))
    row = cur.fetchone()
    if row is None:
        cur.execute("""
          INSERT INTO documents(doc_id,kdnr,object_path,doctype,title,created_at,updated_at,current_version_id)
          VALUES(?,?,?,?,?,?,?,?)
        """, (doc_id, kdnr or None, None, (doctype or None), title, now, now, version_id))
    else:
        # update meta if provided
        cur.execute("""
          UPDATE documents SET
            kdnr=COALESCE(?, kdnr),
            doctype=COALESCE(?, doctype),
            title=COALESCE(?, title),
            updated_at=?,
            current_version_id=?
          WHERE doc_id=?
        """, (kdnr or None, doctype or None, title or None, now, version_id, doc_id))

    # insert version if not exists
    cur.execute("SELECT version_id FROM document_versions WHERE version_id=?", (version_id,))
    if cur.fetchone() is None:
        cur.execute("""
          INSERT INTO document_versions(version_id,doc_id,file_path,sha256,size,mtime_ns,created_at)
          VALUES(?,?,?,?,?,?,?)
        """, (version_id, doc_id, str(p.resolve()), sha, int(st.st_size), int(st.st_mtime_ns), now))

    con.commit()
    con.close()
    return doc_id

def index_run_full(scan_limit: Optional[int] = None) -> Dict[str, int]:
    """
    Full scan of BASE_PATH only.
    No OCR. No Eingang.
    """
    _ensure_index_tables()

    files_seen = 0
    docs_upserted = 0

    for p in _iter_files_under(BASE_PATH):
        try:
            files_seen += 1
            doc_id = index_upsert_file(p)
            if doc_id:
                docs_upserted += 1
        except Exception:
            # best effort; do not crash full scan
            pass

        if scan_limit and files_seen >= scan_limit:
            break

    return {"files_seen": files_seen, "docs_upserted": docs_upserted}

def index_search(query: str, role: str = "ADMIN", limit: int = 20) -> List[Dict]:
    """
    Minimal search: filename/title contains query (case-insensitive).
    RBAC gating will be added when template_nodes are fully wired to docs.
    For now:
      - ADMIN: sees all
      - non-admin: sees nothing (secure default)
    """
    q = normalize_ws(query or "").strip()
    if not q:
        return []

    if (role or "").upper() != "ADMIN":
        return []

    _ensure_index_tables()

    con = db_connect()
    cur = con.cursor()
    like = f"%{q.lower()}%"
    cur.execute("""
      SELECT d.doc_id, d.title, d.kdnr, d.doctype, d.current_version_id,
             v.file_path,
             (SELECT COUNT(*) FROM document_versions vv WHERE vv.doc_id=d.doc_id) as version_count
      FROM documents d
      LEFT JOIN document_versions v ON v.version_id = d.current_version_id
      WHERE lower(d.title) LIKE ?
      ORDER BY d.updated_at DESC
      LIMIT ?
    """, (like, int(limit)))

    rows = cur.fetchall()
    con.close()

    out = []
    for r in rows:
        out.append({
            "doc_id": r[0],
            "title": r[1],
            "kdnr": r[2],
            "doctype": r[3],
            "current_path": r[5],
            "version_count": int(r[6] or 0),
        })
    return out

def assistant_sync_index(scan_limit: Optional[int] = None) -> Dict[str, int]:
    """
    Backward compatible wrapper.
    """
    return index_run_full(scan_limit=scan_limit)
