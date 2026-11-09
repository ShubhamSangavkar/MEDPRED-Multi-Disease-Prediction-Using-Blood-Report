
from __future__ import annotations

import math
import os
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Optional

import pdfplumber

# tesseract spawns OpenMP threads; we parallelise across pages instead
os.environ.setdefault("OMP_THREAD_LIMIT", "1")


# ===========================================================================
# 1. Text clean-up helpers
# ===========================================================================
_HOMOGLYPHS = str.maketrans({
    # Cyrillic look-alikes that OCR'd text layers love to emit
    "А": "A", "В": "B", "С": "C", "Е": "E", "Н": "H", "К": "K", "М": "M",
    "О": "O", "Р": "P", "Т": "T", "Х": "X", "У": "Y", "І": "I", "Ѕ": "S",
    "а": "a", "с": "c", "е": "e", "о": "o", "р": "p", "х": "x", "у": "y",
    "і": "i", "ѕ": "s",
    # typographic punctuation
    "–": "-", "—": "-", "−": "-", "‐": "-", "‑": "-",
    "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
    "\u00a0": " ", "\u2009": " ", "\u200b": "",
})

_RUN_RE = re.compile(r'(.)\1*', re.S)


def _token_k(tok: str, min_len: int) -> int:
    """If every letter/digit run in the token is a multiple of k (k>=2) the
    token was drawn k times over (bold-font artefact); return k, else 1."""
    runs = [len(m.group(0)) for m in _RUN_RE.finditer(tok) if m.group(1).isalnum()]
    if not runs or sum(runs) < min_len:
        return 1
    g = 0
    for r in runs:
        g = math.gcd(g, r)
    return g if g >= 2 else 1


def _collapse(tok: str, k: int) -> str:
    return _RUN_RE.sub(lambda m: m.group(1) * (len(m.group(0)) // k if len(m.group(0)) % k == 0
                                                else len(m.group(0))), tok)


def dedup_glyphs(line: str) -> str:
    """Collapse 'HHHHaaaaeeee' style duplicated-glyph artefacts, token by token,
    so normal text on the same line ('Billing') is left alone."""
    parts = re.split(r'(\s+)', line)
    ks = [_token_k(p, 4) if not p.isspace() else 1 for p in parts]
    dup = [k for k in ks if k > 1]
    if not dup:
        return line
    k_line = Counter(dup).most_common(1)[0][0]
    out = []
    for p, k in zip(parts, ks):
        if p.isspace() or not p:
            out.append(p)
        elif k > 1:
            out.append(_collapse(p, k))
        elif _token_k(p, 1) == k_line:           # short tokens ("Hb" -> "HHbb")
            out.append(_collapse(p, k_line))
        elif not any(c.isalnum() for c in p) and len(p) % k_line == 0 and len(p) >= k_line:
            out.append(p[::k_line])              # punctuation-only ("::::" -> ":")
        else:
            out.append(p)
    return ''.join(out)


def normalise_line(line: str) -> str:
    line = dedup_glyphs(line.translate(_HOMOGLYPHS).rstrip())
    line = re.sub(r'(?<=\d)\s+(?=\.\d)', '', line)            # "6 .0" -> "6.0"
    line = re.sub(r'(?<=\d),(?=\d{1,2}(?!\d))', '.', line)    # "14,1" -> "14.1"
    line = re.sub(r'\s+', ' ', line)
    return line.strip().strip('|_~¦ ').strip()               # OCR border junk


def normalise_lines(raw_lines) -> list[str]:
    out = []
    for l in raw_lines:
        l = normalise_line(l)
        if l:
            out.append(l)
    return out


# ===========================================================================
# 2. Page text acquisition (native text or OCR)
# ===========================================================================
def _normalize_illumination(gray):
    """Flatten uneven / coloured backgrounds (pure PIL + numpy)."""
    import numpy as np
    from PIL import Image, ImageFilter

    w, h = gray.size
    small = gray.resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR)
    bg = small.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(8))
    bg = bg.resize((w, h), Image.BILINEAR)
    g = np.asarray(gray, dtype=np.float32)
    b = np.asarray(bg, dtype=np.float32)
    return Image.fromarray(np.clip(g / np.maximum(b, 1.0) * 255.0, 0, 255).astype(np.uint8))


def _preprocess_for_ocr(img):
    """Hard binarisation: helps on faint scans with coloured highlighter marks."""
    from PIL import ImageOps, ImageFilter, Image as PILImage

    gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    w, h = gray.size
    if max(w, h) < 2500:
        gray = gray.resize((int(w * 1.5), int(h * 1.5)), PILImage.LANCZOS)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray.point(lambda x: 0 if x < 150 else 255, mode="L")


def _ocr_variants(img):
    from PIL import ImageOps

    wanted = [v.strip() for v in os.environ.get("OCR_VARIANTS", "norm,gray,binary").split(",")]
    gray = ImageOps.autocontrast(ImageOps.grayscale(img), cutoff=1)
    for name in wanted:
        if name == "norm":
            yield name, _normalize_illumination(gray)
        elif name == "gray":
            yield name, gray
        elif name == "binary":
            yield name, _preprocess_for_ocr(img)


def _row_score(rows: list[dict]) -> int:
    """How many parsed rows look like a real result (numeric + unit/range)."""
    n = 0
    for r in rows:
        if re.fullmatch(r'[<>]?=?\s*[-+]?\d+(?:\.\d+)?', r["result"]) and (r["unit"] or r["ref_range"]):
            n += 1
    return n


def ocr_page_lines(pdf_path: str, page_index: int) -> tuple[list[str], str]:
    try:
        from pdf2image import convert_from_path
        import pytesseract
    except ImportError as exc:
        raise RuntimeError(
            "This page has no extractable text (scanned / photographed PDF) and "
            "the OCR dependencies are missing. Run: pip install pytesseract "
            "pdf2image   and install tesseract-ocr + poppler-utils."
        ) from exc

    if os.environ.get("TESSERACT_CMD"):
        pytesseract.pytesseract.tesseract_cmd = os.environ["TESSERACT_CMD"]
    poppler_path = os.environ.get("POPPLER_PATH") or None
    dpi = int(os.environ.get("OCR_DPI", "400"))

    try:
        images = convert_from_path(pdf_path, dpi=dpi, first_page=page_index + 1,
                                   last_page=page_index + 1, poppler_path=poppler_path)
    except Exception as exc:
        raise RuntimeError(
            "OCR page rendering failed. Make sure poppler is installed and on PATH "
            "(pdftoppm / pdfinfo), or set POPPLER_PATH to its bin folder "
            r"(e.g. C:\poppler\Library\bin on Windows). "
            f"Original error: {exc}") from exc
    if not images:
        return [], "none"
    img = images[0]

    best = None  # (score, n_chars, variant, lines)
    for name, im in _ocr_variants(img):
        try:
            txt = pytesseract.image_to_string(im, config="--psm 6")
        except Exception as exc:
            raise RuntimeError(
                "OCR failed. Make sure tesseract-ocr is installed and on PATH, or "
                f"set TESSERACT_CMD to tesseract.exe. Original error: {exc}") from exc
        lines = normalise_lines(txt.split("\n"))
        score = _row_score(parse_lines(lines, "", page_index + 1, ocr=True))
        cand = (score, len(txt), name, lines)
        if best is None or cand[:2] > best[:2]:
            best = cand
        digit_lines = sum(1 for l in lines if re.search(r'\d', l))
        if score >= 3 or (score >= 1 and digit_lines <= 12):
            break          # good enough; skip the remaining (slow) variants
    return best[3], best[2]


def get_page_lines(pdf_path: str, page_index: int, page) -> list[str]:
    """Backwards-compatible helper: text lines of one page (native or OCR)."""
    text = page.extract_text() or ""
    if len(text.strip()) < 20:
        return ocr_page_lines(pdf_path, page_index)[0]
    return normalise_lines(text.split("\n"))


# ===========================================================================
# 3. Patient details
# ===========================================================================
_TITLE_RE = re.compile(r'^(?:mr|mrs|ms|miss|master|mstr|dr|smt|shri|sri|baby|b/o|w/o|d/o|s/o)\b[.\s]*', re.I)
_NAME_STOP = (r'(?:age|sex|gender|ref(?:erred)?\b|referring|date|reg\b|registration|sample|collected|'
              r'collection|lab\b|uhid|facility|cent(?:re|er)|barcode|accession|billing|doctor|visit|'
              r'mrn|phone|mob|report|received)')
_NAME_PATS = [
    re.compile(r'(?:patient\s*name|pt\.?\s*name)\s*[:\-=.]*\s*(?P<v>.+)', re.I),
    re.compile(r'^\s*name\s*[:\-=.]+\s*(?P<v>.+)', re.I),
]
_AGE_RE = re.compile(r'\bage\s*(?:/\s*(?:sex|gender))?\s*[:\-=.]*\s*(?P<n>\d{1,3})\s*'
                     r'(?P<u>years?|yrs?|y|months?|mths?|m|days?|d)?\b', re.I)
_SEX_RES = [
    re.compile(r'\b(?:sex|gender)\s*[:\-=.]*\s*(?P<s>female|male|f|m)\b', re.I),
    re.compile(r'\bage\s*/\s*(?:sex|gender)\b.*?/\s*(?P<s>female|male|f|m)\b', re.I),
]
_ID_RE = re.compile(r'(?:patient\s*id|pt\.?\s*no\.?|p\.?\s*id\s*no|uhid|mrn)\s*[:\-=.]*\s*'
                    r'(?P<v>[A-Za-z0-9][A-Za-z0-9\-/.]*(?:\s\d{5,})?)', re.I)
_DATE_RE = re.compile(r'(?P<d>\d{1,2})[/\-.](?P<m>\d{1,2}|[A-Za-z]{3})[/\-.](?P<y>\d{4}|\d{2})')
_DATE_LABELS = [r'report(?:ed|ing)?\s*date', r'\bdate\b', r'collect\w*|sample\s*coll', r'reg\w*\.?\s*date']


def _to_iso(m: re.Match) -> Optional[str]:
    d, mo, y = m.group('d'), m.group('m'), m.group('y')
    for fmt in ("%d/%m/%Y", "%d/%b/%Y", "%d/%m/%y", "%d/%b/%y"):
        try:
            return datetime.strptime(f"{d}/{mo}/{y}", fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_demographics(lines: list[str]) -> dict:
    head = lines[:40]
    info: dict = {}

    for rx in _NAME_PATS:
        for ln in head:
            m = rx.search(ln)
            if not m:
                continue
            v = re.split(rf'\s+(?={_NAME_STOP})|\s{{3,}}', m.group('v'), maxsplit=1, flags=re.I)[0]
            v = _TITLE_RE.sub('', v.strip(' -:.|'))
            v = re.sub(r'[^A-Za-z .\'\-]', '', v).strip(' .-')
            if 2 <= len(v) <= 60 and len(re.findall(r'[A-Za-z]', v)) >= 2:
                info["name"] = v
                break
        if "name" in info:
            break

    for ln in head:
        m = _AGE_RE.search(ln)
        if m:
            n, u = int(m.group('n')), (m.group('u') or 'y').lower()
            years = n / 12 if u.startswith('m') and not u.startswith('y') else (n / 365 if u.startswith('d') else n)
            info["age_years"] = round(years, 2) if years != int(years) else int(years)
            break

    for ln in head:
        for rx in _SEX_RES:
            m = rx.search(ln)
            if m:
                info["sex"] = "female" if m.group('s').lower().startswith('f') else "male"
                break
        if "sex" in info:
            break

    for ln in head:
        m = _ID_RE.search(ln)
        if m:
            info["patient_id"] = m.group('v').strip()
            break

    for lab in _DATE_LABELS:
        found = False
        for ln in head:
            lm = re.search(lab, ln, re.I)
            if lm:
                dm = _DATE_RE.search(ln[lm.end():])
                if dm:
                    info["report_date"] = _to_iso(dm) or dm.group(0)
                    found = True
                    break
        if found:
            break
    return info


# ===========================================================================
# 4. Row parsing
# ===========================================================================
NUM = r'[-+]?\d+(?:\.\d+)?'
_UNS = r'\d+(?:\.\d+)?'
QUAL = (r'(?:Non[\s-]?Reactive|Reactive|Negative|Positive|Not\s+(?:Detected|Seen)|Detected|'
        r'Absent|Present|Nil|Trace|Normal|Clear|Pale\s+Yellow|Adequate)')
RES = rf'(?:\d+\s*:\s*\d+|\d+\+{{1,4}}|(?:[<>]=?\s*)?{NUM}|{QUAL})'
RANGE_RE = re.compile(
    rf'(?:{_UNS}\s*(?:-|to)\s*{_UNS}|(?:<=?|>=?|≤|≥)\s*{_UNS}|(?:up\s*to|upto)\s*{_UNS})', re.I)

ROW_RE = re.compile(
    rf'^(?P<name>(?:\d{{1,3}}\s*)?[A-Za-z(][A-Za-z0-9\s()\[\]/,.\-+%&\'#]*?)'
    rf'(?P<sep>[\s:=~>_\'"|•*.\-]+)'
    rf'(?P<result>{RES})(?=$|[\s.,;)\]]|[A-Za-z%/µ])'
    rf'(?P<tail>.*)$', re.I)

BLOODGROUP_RE = re.compile(
    r'^(?P<name>ABO\s*Group|Blood\s*Group(?:ing)?)[\s:=>\-~_.|]*(?P<result>AB|A|B|O)\b\s*'
    r'(?P<sign>\+|-|pos(?:itive)?|neg(?:ative)?)?', re.I)

# lines like "Borderline High Risk 200-240", "High 200-499", "Very High >=500"
BAND_LINE_RE = re.compile(
    r'^(?:Desirable|Optimal|Near[\s/]*(?:Above\s*)?Optimal|Above\s*Optimal|'
    r'Borderline(?:\s*High)?(?:\s*Risk)?|(?:Very\s*)?High(?:\s*Risk)?|Low(?:\s*Risk)?|'
    r'Normal|Moderate(?:\s*Risk)?|Intermediate|Increased\s*Risk)\b\s*[:\-]?\s*'
    r'(?:<=?|>=?|≤|≥)?\s*\d[\d.\s\-<>=]*(?:mg/dl|mmol/l|%)?\s*$', re.I)

_UNIT_PATTERNS = [
    r'per\s*c?u?-?\s*mm\d?',
    r'(?:millions?|lakhs?|lacs?|thou(?:sand)?s?|cells|mill?)\s*/\s*(?:cu-?\s*mm|cumm|cmm|mm3|cum|[uµμ]l|l)',
    r'mm\s*(?:at|/)\s*[1lI|t]\s*h(?:r|our)?s?\.?',
    r'(?:x\s*)?10\s*(?:\^\s*\d+|~\s*\d+|[³²⁶⁹]|\d{1,2})?\s*/\s*[A-Za-zµμ]+',
    r'/\s*(?:[uµμ]l|cumm|cmm|mm3|dl|ml|hpf|lpf|hr|l)\b',
    r'[A-Za-zµμ%]{1,6}\s*/\s*[A-Za-zµμ0-9.^]+(?:\s*/\s*[A-Za-z0-9.^]+)*',
    r'g(?:ms?)?\s*%',
    r'[lI|]?%',
    r'(?:gms?|g|mg|[µμu]g|ng|pg|fl|u|iu|miu|[µμu]iu|mmol|[µμu]mol|meq|sec(?:onds?)?|ratio|'
    r'index|cells|hrs?|mm|ph|s/co)(?=[\s.,;)]|$)\.?',
]
UNIT_RE = re.compile(r'^\s*\(?\s*(?:' + '|'.join(_UNIT_PATTERNS) + r')', re.I)
_LABEL_WORDS_RE = re.compile(r'^(?:Normal|Desirable|Optimal|Reference|Range|Adults?|Method)\b[\s:]*', re.I)
_BYSEX_RE = re.compile(rf'\b(?P<s>[MF])\s*[:\-]\s*(?P<r>{_UNS}\s*-\s*{_UNS})')

NOISE_RE = re.compile(
    r'^(?:Patient\s*(?:Name|ID|Registration)|Pt\.?\s*(?:Name|No)|P\.?\s*ID|Age\b|Sex\b|Gender|'
    r'Lab\s*(?:No|Id)|Registration|Reg\.?\s*(?:Lab|Date|No)|Referred|Ref\.?\s*(?:By|Doctor|no)|'
    r'Referring|Cent(?:re|er)\b|Facility|Accession|Collected|Collection|Received|Approved|'
    r'Report(?:ed)?\s*(?:Status|Date|On|Time)|Reporting|Sample\b|Specimen|Method\b|Methodology|'
    r'Technology|Analy[sz]er|Remarks?|Advi[cs]e|Note\b|Interpretation|Clinical\s*Significance|'
    r'Ref\.?\s*Range|Page\b|This\s*is\s*a|Scan\s*to|In\s*case\s*of|\*+\s*End|-+\s*End|Kindly|'
    r'Billing|MaxID|Booking|Test\s*Performed|Helpline|www\.|CIN\b|Barcode|OP/IP|Processed\s*at|'
    r'Dr[.,\s]|Mob\b|Tel\b|Phone|E-?mail|Date\b|Parameter|Investigation|Test\s*Name|'
    r'Haematology\s*Tests|Biochemistry\s*Tests|ELC\s*Test|Scanned\s*with|Working\s*Hours|'
    r'Emergence|Since\b|computeri[sz]ed|Semi\s*Auto|All\s*Tests|Chamber|Fully\s*Auto|'
    r'Well\s*Equipped|Clinical\s*Chemistry|Electrolyte\s*Analy)', re.I)

BANNER_RE = re.compile(
    r'laborator|diagnostic|centre|center|hospital|clinic|pathology|\blabs?\b|health|mission|'
    r'initiative|enterprise|report|\bltd\b|pvt|institute|services?\b|collection', re.I)
SECTION_BLOCK_RE = re.compile(r'^(?:normal\s*range|histograms?|reference|results?|units?|bio\.?\s*ref|'
                              r'method|sample)', re.I)
TABLE_HEADER_RE = re.compile(
    r'^(?:Test(?:\s*Name)?|Investigation|Parameter|Observation|Analyte)\b.*\b(?:Result|Value|Units?)\b', re.I)
SENT_WORDS = {"can", "may", "is", "are", "was", "were", "be", "been", "indicate", "indicates",
              "indicated", "should", "usually", "due", "which", "that", "when", "if", "have",
              "has", "also", "than", "increased", "decreased", "associated", "levels", "level"}
STOP_NAMES = {"after", "before", "ifter", "at", "of", "and", "to", "for", "hr", "hrs", "ee", "a"}
REPORT_TIME_RE = re.compile(r'\b(?:report|collection|collected|reg|registration|billing|sample|'
                            r'receiv\w*|approved|reporting|printed|released)\w*\s*(?:date|time|on)\b', re.I)
FLAG_RE = re.compile(r'^\(?\s*(H|L|High|Low)\s*\)?(?=\s|$)')


def _clean_name(name: str) -> str:
    name = re.sub(r'\s{2,}', ' ', name).strip(" -:>.|_~'\"*•")
    name = re.sub(r'\s*\($', '', name).strip()
    return name


def clean_unit(u: str) -> str:
    u = re.sub(r'\s*/\s*', '/', u.strip().strip('().,;'))
    u = re.sub(r'^[lI|]+%$', '%', u)
    u = re.sub(r'(?i)^g/?d[lb1I]$', 'g/dL', u)
    u = re.sub(r'(?i)^me/', 'mg/', u)
    u = re.sub(r'(?i)/d[i1]$', '/dl', u)
    return u


def _norm_range(r: str) -> str:
    r = re.sub(r'\s+', ' ', r.strip())
    return re.sub(r'(?i)\s+to\s+', ' - ', r)


def parse_tail(tail: str) -> dict:
    """Split everything after the result into unit / reference range / flag."""
    t = tail.strip()
    out = {"unit": "", "ref_range": "", "flag": ""}

    fm = FLAG_RE.match(t)
    if fm:
        out["flag"] = fm.group(1)[0].upper()
        t = t[fm.end():].strip()
    while True:                               # drop "Normal", "Desirable", ...
        m = _LABEL_WORDS_RE.match(t)
        if not m:
            break
        t = t[m.end():]

    rm = RANGE_RE.search(t)
    if rm:
        out["ref_range"] = _norm_range(rm.group(0))
        before, after = t[:rm.start()], t[rm.end():]
    else:
        before, after = t, ""

    for seg in (before, after):
        um = UNIT_RE.match(seg)
        if um:
            out["unit"] = clean_unit(um.group(0))
            break

    if not out["ref_range"]:
        qm = re.search(QUAL + r'\s*$', t, re.I)
        if qm:
            out["ref_range"] = qm.group(0).strip()

    by_sex = {("male" if s == "M" else "female"): _norm_range(r) for s, r in _BYSEX_RE.findall(t)}
    if by_sex:
        out["ref_range_by_sex"] = by_sex
    return out


def _is_sentence(name: str) -> bool:
    toks = name.split()
    if len(toks) >= 10:
        return True
    return len(toks) >= 4 and any(t.lower().strip(',.') in SENT_WORDS for t in toks)


def _looks_like_section_heading(line: str) -> bool:
    if NOISE_RE.match(line) or SECTION_BLOCK_RE.match(line) or BANNER_RE.search(line):
        return False
    if re.search(r'\d', line):
        return False
    words = line.split()
    if not (1 <= len(words) <= 8):
        return False
    return bool(re.match(r'^[A-Z][A-Za-z0-9()/,&\-\s]{2,60}$', line))


def _maybe_fix_decimal(row: dict) -> None:
    """OCR often drops faint decimal points ('141' for '14.1'). If the integer
    is far outside the printed reference range but result/10 or /100 sits
    inside it, restore the decimal and keep the original in result_raw."""
    res = row["result"]
    if not re.fullmatch(r'\d{2,6}', res):
        return
    rng = row["ref_range"]
    m = re.match(rf'^({_UNS})\s*-\s*({_UNS})$', rng)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
    else:
        m = re.match(rf'^(?:<=?|≤)\s*({_UNS})$', rng)
        if not m:
            return
        lo, hi = 0.0, float(m.group(1))
    v = float(res)
    if hi <= 0 or v <= 3 * hi:
        return
    for k in (1, 2):
        c = v / 10 ** k
        if lo * 0.6 <= c <= hi * 1.6:
            row["result_raw"] = res
            row["result"] = f"{c:.{k}f}"
            row["ocr_fix"] = "decimal point restored using the printed reference range"
            return


def _make_row(name, result, tail, section, page_no, source_file, ocr) -> Optional[dict]:
    name = _clean_name(name)
    result = re.sub(r'\s+', '', result) if re.fullmatch(r'\d+\s*:\s*\d+', result) else result.strip().rstrip('.')
    if (not name or len(re.findall(r'[A-Za-z]', name)) < 2 or len(name) > 70
            or NOISE_RE.match(name) or name.lower() in STOP_NAMES
            or _is_sentence(name) or REPORT_TIME_RE.search(name)
            or BAND_LINE_RE.match(f"{name} {result}")):
        return None
    if re.fullmatch(r'\d{8,}', re.sub(r'\D', '', result)) and re.fullmatch(r'[\d.\s]+', result):
        return None                                         # phone / id numbers
    info = parse_tail(tail)
    if re.fullmatch(r'[A-Za-z]?\d{6,}', info["unit"]):
        return None
    row = {
        "test_name": name, "result": result, "unit": info["unit"],
        "ref_range": info["ref_range"], "flag": info["flag"], "section": section,
        "source_page": page_no, "source_file": source_file, "ocr": ocr,
    }
    if "ref_range_by_sex" in info:
        row["ref_range_by_sex"] = info["ref_range_by_sex"]
    if ocr:
        _maybe_fix_decimal(row)
    return row


def parse_lines(lines: list[str], source_file: str, page_no: int, ocr: bool = False) -> list[dict]:
    rows: list[dict] = []
    section = ""
    for raw in lines:
        line = raw.strip().strip('|_~¦ ').strip()
        if not line or TABLE_HEADER_RE.match(line) or NOISE_RE.match(line):
            continue
        if BAND_LINE_RE.match(line):                         # risk-band text under a row
            continue

        if _looks_like_section_heading(line) and (line.isupper() or len(line.split()) <= 4):
            section = line
            continue

        m = BLOODGROUP_RE.match(line)
        if m:
            sign = (m.group('sign') or '')
            res = m.group('result').upper() + ({'pos': '+', 'neg': '-'}.get(sign[:3].lower(), sign) if sign else '')
            row = _make_row(m.group('name'), res, '', section, page_no, source_file, ocr)
            if row:
                rows.append(row)
            continue

        m = ROW_RE.match(line)
        if not m:
            continue
        row = _make_row(m.group('name'), m.group('result'), m.group('tail'),
                        section, page_no, source_file, ocr)
        if not row:
            continue
        # "eGFR by CKD EPI 2021  109.06 ml/min": the year belongs to the name
        if re.fullmatch(r'(?:19|20)\d\d', row["result"]):
            m2 = re.match(rf'^\s*({NUM})\s*(.*)$', m.group('tail'))
            if m2:
                row = _make_row(f"{m.group('name')} {row['result']}", m2.group(1), m2.group(2),
                                section, page_no, source_file, ocr)
                if not row:
                    continue
        rows.append(row)
    return rows


# ===========================================================================
# 5. Top-level driver
# ===========================================================================
def _apply_sex_range(row: dict, sex: Optional[str]) -> None:
    by = row.get("ref_range_by_sex")
    if by and sex in by:
        row["ref_range"] = by[sex]


def extract_report_full(pdf_path: str) -> dict:
    fname = os.path.basename(pdf_path)
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        page_lines: list = [None] * n_pages
        page_ocr = [False] * n_pages
        todo = []
        for i, page in enumerate(pdf.pages):
            text = (page.extract_text() or "")
            stripped = text.strip()
            if len(stripped) >= 150 or (len(stripped) >= 20 and not page.images):
                page_lines[i] = normalise_lines(text.split("\n"))
            else:
                todo.append(i)

    if todo:
        workers = int(os.environ.get("OCR_WORKERS", min(4, os.cpu_count() or 1)))
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            for i, (lines, _variant) in zip(todo, ex.map(lambda p: ocr_page_lines(pdf_path, p), todo)):
                page_lines[i] = lines
                page_ocr[i] = True

    patients: list[dict] = []
    all_rows: list[dict] = []
    current: Optional[int] = None
    for i in range(n_pages):
        lines = page_lines[i] or []
        demo = parse_demographics(lines)
        page_rows = parse_lines(lines, fname, i + 1, ocr=page_ocr[i])

        # which patient is this page about?
        match = None
        if demo.get("name"):
            for idx, p in enumerate(patients):
                if p.get("name") and p["name"].lower() == demo["name"].lower():
                    match = idx
                    break
        if match is None and demo.get("name"):
            patients.append({"patient_index": len(patients), "pages": []})
            match = len(patients) - 1
        if match is None:
            if current is None and page_rows:
                patients.append({"patient_index": len(patients), "pages": []})
                current = len(patients) - 1
            match = current
        if match is not None:
            current = match
            p = patients[match]
            for k, v in demo.items():
                p.setdefault(k, v)
            p["pages"].append(i + 1)
        for r in page_rows:
            r["patient_index"] = match
            if match is not None:
                _apply_sex_range(r, patients[match].get("sex"))
        all_rows.extend(page_rows)

    seen, rows = set(), []
    for r in all_rows:
        key = (r["patient_index"], r["test_name"].lower(), r["result"], r["unit"], r["ref_range"])
        if key not in seen:
            seen.add(key)
            rows.append(r)

    for p in patients:
        for k in ("name", "age_years", "sex", "patient_id", "report_date"):
            p.setdefault(k, None)
    return {"filename": fname, "page_count": n_pages, "patients": patients, "rows": rows}


def extract_report(pdf_path: str) -> list[dict]:
    """Rows only (backwards compatible)."""
    return extract_report_full(pdf_path)["rows"]


def extract_reports(paths: list[str]) -> list[dict]:
    out = []
    for p in paths:
        out.extend(extract_report(p))
    return out


if __name__ == "__main__":
    import json
    for path in sys.argv[1:]:
        print(f"\n=== {path} ===")
        res = extract_report_full(path)
        print(json.dumps(res["patients"], ensure_ascii=False, indent=1))
        for row in res["rows"]:
            print(json.dumps(row, ensure_ascii=False))












"""
lab_report_extractor.py   (v2)
==============================
Extract patient details and test-name / result / unit / reference-range rows
from medical lab report PDFs of any lab / template.

Handles
  * normal text-layer PDFs                         (pdfplumber)
  * "bold glyph duplication" artefacts             (HHHHaaaa -> Ha)
  * homoglyph text layers (Cyrillic "Е" for "E")   (mapped back to Latin)
  * scanned / photographed pages (no text layer)   (OCR, best of several
    image pre-processing variants chosen per page by how many rows parse)
  * several patients' reports bundled in one PDF   (rows carry patient_index)

Public API
----------
    extract_report_full(path) -> {"filename", "page_count", "patients", "rows"}
    extract_report(path)      -> rows only (backwards compatible)

Row keys
--------
    test_name, result, unit, ref_range, flag, section, source_page, source_file,
    patient_index, ocr (bool)
  optional:
    ref_range_by_sex  {"male": "...", "female": "..."}  when the report prints both
    result_raw / ocr_fix   present when a lost decimal point was restored
                           (OCR pages only, using the printed reference range)

Environment variables (all optional)
    TESSERACT_CMD, POPPLER_PATH   explicit binary locations (Windows)
    OCR_DPI        render resolution for scanned pages          (default 400)
    OCR_VARIANTS   comma list from norm,gray,binary             (default all)
    OCR_WORKERS    pages OCR'd in parallel                      (default min(4, cpus))

This is a heuristic extractor: lab reports are not standardised. Spot-check
output before using it for anything clinical.
"""
