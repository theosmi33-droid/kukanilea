#!/usr/bin/env python3
# -*- coding: utf-8 -*-

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


# ==============================
# KONFIG
# ==============================
EINGANG = Path.home() / "Tophandwerk_Eingang"
BASE_PATH = Path.home() / "Tophandwerk_Kundenablage"
PENDING_DIR = Path.home() / "Tophandwerk_Pending"
DONE_DIR = Path.home() / "Tophandwerk_Done"

DB_PATH = Path.home() / "Tophandwerk_DB.sqlite3"

SUPPORTED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}

# OCR/Extraktion
OCR_MAX_PAGES = 1
OCR_DPI = 220
TESS_LANG = "deu+eng"

# Progress
PROGRESS_MIN_STEP = 0.5  # UI fühlt sich flüssig an

# Template
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

KDN_RE = re.compile(r"\b(\d{3,12})\b")
KUNDEN_KEY_RE = re.compile(r"(kundennr|kunden\-nr|kunden nr|kdnr|kd\-nr)\s*[:#]?\s*(\d{3,12})", re.IGNORECASE)
PLZORT_RE = re.compile(r"\b(\d{5})\s+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*)\b")

STREET_RE = re.compile(
    r"\b([A-ZÄÖÜ][\wÄÖÜäöüß\.\- ]{2,60}"
    r"(straße|str\.|strasse|weg|platz|allee|damm|ring|ufer|gasse|chaussee|promenade|höhe|hof|steig|pfad))\s+(\d{1,4}[a-zA-Z]?)\b",
    re.IGNORECASE
)


# ==============================
# JSON utils
# ==============================
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


# ==============================
# Normalize
# ==============================
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


# ==============================
# DB (Offline “Memory”)
# ==============================
def db_connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con


def db_init():
    con = db_connect()
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers(
        kdnr TEXT PRIMARY KEY,
        name TEXT,
        addr TEXT,
        plzort TEXT,
        updated_at TEXT
    )""")
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_objects_kdnr ON objects(kdnr)")
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kdnr TEXT,
        doctype TEXT,
        file_path TEXT,
        created_at TEXT
    )""")
    con.commit()
    con.close()


def db_upsert_customer(kdnr: str, name: str, addr: str, plzort: str):
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


def db_upsert_object(kdnr: str, folder_path: str, folder_name: str, name: str, addr: str, plzort: str, source_format: str):
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("DELETE FROM objects WHERE folder_path=?", (folder_path,))
    con.execute("""
      INSERT INTO objects(kdnr, folder_path, folder_name, name, addr, plzort, source_format, last_seen, last_used)
      VALUES(?,?,?,?,?,?,?,?,?)
    """, (kdnr, folder_path, folder_name, name, addr, plzort, source_format, now, None))
    con.commit()
    con.close()


def db_get_customer(kdnr: str) -> Optional[Dict]:
    con = db_connect()
    cur = con.cursor()
    cur.execute("SELECT kdnr, name, addr, plzort, updated_at FROM customers WHERE kdnr=?", (kdnr,))
    r = cur.fetchone()
    con.close()
    if not r:
        return None
    return {"kdnr": r[0], "name": r[1], "addr": r[2], "plzort": r[3], "updated_at": r[4]}


def db_touch_object_used(folder_path: str):
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("UPDATE objects SET last_used=? WHERE folder_path=?", (now, folder_path))
    con.commit()
    con.close()


def db_add_document(kdnr: str, doctype: str, file_path: str):
    con = db_connect()
    now = datetime.now().isoformat(timespec="seconds")
    con.execute("INSERT INTO documents(kdnr,doctype,file_path,created_at) VALUES(?,?,?,?)",
                (kdnr, doctype, file_path, now))
    con.commit()
    con.close()


# ==============================
# Template-Repair
# ==============================
def ensure_template_structure(customer_folder: Path):
    customer_folder.mkdir(parents=True, exist_ok=True)
    for sf in TEMPLATE_SUBFOLDERS:
        (customer_folder / sf).mkdir(parents=True, exist_ok=True)
    base01 = customer_folder / TEMPLATE_SUBFOLDERS[0]
    base01.mkdir(parents=True, exist_ok=True)
    for sub in SUBFOLDERS_IN_01:
        (base01 / sub).mkdir(parents=True, exist_ok=True)


# ==============================
# Bestehende Ordner robust erkennen
# ==============================
def extract_plz(plzort: str) -> str:
    m = re.search(r"\b(\d{5})\b", plzort or "")
    return m.group(1) if m else ""


def normalize_address_like_maps(addr: str) -> str:
    a = normalize_component(addr).lower()
    a = a.replace(".", " ").replace(",", " ")
    a = re.sub(r"\bstr\b", "strasse", a)
    a = re.sub(r"\bstrasse\b", "strasse", a)
    a = re.sub(r"\bstraße\b", "strasse", a)
    a = re.sub(r"\bstr\.\b", "strasse", a)
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
    out: List[Path] = []
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
    addr_norm = normalize_address_like_maps(addr)
    best = None
    best_score = 0.0

    for f in existing_folders:
        fields = parse_folder_fields(f.name)
        f_plz = extract_plz(fields.get("plzort", ""))
        if plz and f_plz and plz != f_plz:
            continue
        f_addr = fields.get("addr", "")
        score = similarity(addr_norm, f_addr)
        if score > best_score:
            best_score = score
            best = f

    return best, best_score


# ==============================
# DB Import/Sync aus BASE_PATH
# ==============================
def sync_db_from_filesystem(base_path: Path):
    db_init()
    if not base_path.exists():
        return

    for child in base_path.iterdir():
        if not child.is_dir():
            continue
        fields = parse_folder_fields(child.name)
        kdnr = (fields.get("kdnr") or "").strip()
        if not kdnr:
            continue

        name = fields.get("name") or ""
        addr = fields.get("addr") or ""
        plzort = fields.get("plzort") or ""

        # Template ergänzen (wichtig für Altbestand)
        ensure_template_structure(child)

        db_upsert_customer(kdnr, name, addr, plzort)
        db_upsert_object(kdnr, str(child), child.name, name, addr, plzort, detect_folder_format(child.name))


# ==============================
# Text-Extraktion mit “Bold/Font/Mitte”-Priorität (PDF Seite 1)
# ==============================
def _line_center_weight(y0: float, y1: float, page_h: float) -> float:
    if page_h <= 0:
        return 1.0
    yc = (y0 + y1) / 2.0
    mid = page_h * 0.52  # leicht unter Mitte
    dist = abs(yc - mid) / page_h
    return max(0.3, 1.15 - dist * 1.6)


def extract_pdf_text_weighted(p: Path) -> Tuple[str, bool, str]:
    used_ocr = False
    text_all = ""
    preview = ""

    # Primary: PyMuPDF dict spans
    if fitz is not None:
        try:
            doc = fitz.open(p)
            if len(doc) > 0:
                page = doc[0]
                page_h = float(page.rect.height)

                blocks = page.get_text("dict").get("blocks", [])
                lines_scored: List[Tuple[float, str]] = []
                plain_lines: List[str] = []

                for b in blocks:
                    for ln in b.get("lines", []):
                        spans = ln.get("spans", [])
                        if not spans:
                            continue

                        line_text = "".join((s.get("text") or "") for s in spans).strip()
                        if not line_text:
                            continue

                        max_size = 0.0
                        boldish = 0.0
                        y0 = 1e9
                        y1 = -1e9

                        for s in spans:
                            sz = float(s.get("size") or 0.0)
                            max_size = max(max_size, sz)

                            flags = int(s.get("flags") or 0)
                            if flags & 16:
                                boldish = 1.0
                            fn = (s.get("font") or "").lower()
                            if "bold" in fn:
                                boldish = 1.0

                            bbox = s.get("bbox") or None
                            if bbox and len(bbox) == 4:
                                y0 = min(y0, float(bbox[1]))
                                y1 = max(y1, float(bbox[3]))

                        center_w = _line_center_weight(
                            y0 if y0 != 1e9 else 0.0,
                            y1 if y1 != -1e9 else 0.0,
                            page_h
                        )

                        score = (max_size * 2.2) + (boldish * 18.0)
                        score *= center_w

                        lines_scored.append((score, line_text))
                        plain_lines.append(line_text)

                text_all = "\n".join(plain_lines).strip()
                lines_scored.sort(key=lambda x: -x[0])
                top = [t for _, t in lines_scored[:35]]
                preview = normalize_ws(" | ".join(top))[:900]

            doc.close()
        except Exception:
            text_all = ""
            preview = ""

    # Fallback: pypdf
    if (not text_all or len(text_all) < 80) and PdfReader is not None:
        try:
            reader = PdfReader(str(p))
            if reader.pages:
                t = reader.pages[0].extract_text() or ""
                if t.strip():
                    text_all = t.strip()
                    preview = normalize_ws(text_all[:900])
        except Exception:
            pass

    # OCR fallback: nur Seite 1
    if (not text_all or len(text_all) < 80) and fitz is not None:
        used_ocr = True
        try:
            doc = fitz.open(p)
            if len(doc) > 0:
                page = doc[0]
                pix = page.get_pixmap(dpi=OCR_DPI, alpha=False)
                if pix.width * pix.height <= 60_000_000:
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    ocr = pytesseract.image_to_string(img, lang=TESS_LANG) or ""
                    if ocr.strip():
                        text_all = ocr.strip()
                        preview = normalize_ws(text_all[:900])
            doc.close()
        except Exception:
            pass

    return text_all, used_ocr, preview


def extract_image_text(p: Path) -> Tuple[str, bool, str]:
    used_ocr = True
    try:
        img = Image.open(p)
        t = pytesseract.image_to_string(img, lang=TESS_LANG) or ""
        t = t.strip()
        return t, used_ocr, normalize_ws(t[:900])
    except Exception:
        return "", used_ocr, ""


def extract_text(p: Path) -> Tuple[str, bool, str]:
    ext = p.suffix.lower()
    if ext == ".pdf":
        return extract_pdf_text_weighted(p)
    if ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp"}:
        return extract_image_text(p)
    return "", False, ""


# ==============================
# Vorschläge
# ==============================
def rank_kundennummer(text: str) -> List[List]:
    t = text or ""
    ranked: Dict[str, int] = {}

    for m in KUNDEN_KEY_RE.finditer(t):
        k = m.group(2)
        ranked[k] = ranked.get(k, 0) + 140

    for m in KDN_RE.finditer(t):
        k = m.group(1)
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
        if cand and cand not in out:
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


# ==============================
# Doctype: nur Vorschlag
# ==============================
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


# ==============================
# Pending/Done
# ==============================
def file_token(p: Path) -> str:
    st = p.stat()
    raw = f"{p.resolve()}|{st.st_size}|{st.st_mtime_ns}".encode("utf-8", errors="ignore")
    return hashlib.sha1(raw).hexdigest()


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


# ==============================
# Background Analyse + Progress
# ==============================
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

        _set_progress(token, 10.0, "Text extrahieren (Seite 1 priorisiert)")
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
            "extracted_text": (text or "")[:20000],
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


# ==============================
# Ablage
# ==============================
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

    if prefer_path:
        fp = Path(prefer_path)
        if fp.exists() and fp.is_dir():
            ensure_template_structure(fp)
            return fp, False

    best, score = best_match_object_folder(existing, addr, plzort)
    if best is not None and score >= 0.86:
        ensure_template_structure(best)
        return best, False

    # Neues Objekt (canonical underscore)
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

    shutil.move(str(file_path), str(final_path))

    # DB Memory
    db_upsert_customer(kdnr, name, addr, plzort)
    db_upsert_object(kdnr, str(folder), folder.name, name, addr, plzort, detect_folder_format(folder.name))
    db_touch_object_used(str(folder))
    db_add_document(kdnr, doctype, str(final_path))

    return folder, final_path, created_new


# ==============================
# API-Contract Backward-Compat
# ==============================
def analyze_to_pending(file_path: Path) -> str:
    """
    Backward-compatible entrypoint.
    Upload-UI darf analyze_to_pending importieren, ohne ImportError.
    """
    return start_background_analysis(Path(file_path))


def analyze_to_pending(file_path: Path) -> str:
    return start_background_analysis(Path(file_path))
