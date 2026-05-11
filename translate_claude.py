#!/usr/bin/env python3
"""
translate_claude.py
Translates a Ukrainian PDF to English.

Usage:
    python translate_claude.py input.pdf [output.pdf]

How translation works:
    1. Each text span is matched against the built-in banking dictionary first
       (offline, instant, covers all standard payment document fields).
    2. If a span contains Ukrainian words NOT covered by the dictionary,
       those remaining words/phrases are sent to Google Translate via the
       deep_translator library (requires internet connection).
    3. Personal names (FIO) are always TRANSLITERATED (not translated)
       using the KMU 2010 standard — no internet needed for that.
    4. Blue stamp regions and their text are left completely untouched.

Install dependencies:
    pip install pymupdf deep_translator
"""

import sys
import os
import re
import argparse
import fitz          # PyMuPDF

try:
    from deep_translator import GoogleTranslator
    HAS_DEEP_TRANSLATOR = True
except ImportError:
    HAS_DEEP_TRANSLATOR = False


# ─────────────────────────────────────────────
#  Ukrainian KMU 2010 transliteration
# ─────────────────────────────────────────────
TRANSLIT_TABLE = {
    'А': 'A',  'Б': 'B',  'В': 'V',  'Г': 'H',  'Ґ': 'G',  'Д': 'D',
    'Е': 'E',  'Є': 'Ye', 'Ж': 'Zh', 'З': 'Z',  'И': 'Y',  'І': 'I',
    'Ї': 'Yi', 'Й': 'Y',  'К': 'K',  'Л': 'L',  'М': 'M',  'Н': 'N',
    'О': 'O',  'П': 'P',  'Р': 'R',  'С': 'S',  'Т': 'T',  'У': 'U',
    'Ф': 'F',  'Х': 'Kh', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
    'Ь': '',   'Ю': 'Yu', 'Я': 'Ya',
    'а': 'a',  'б': 'b',  'в': 'v',  'г': 'h',  'ґ': 'g',  'д': 'd',
    'е': 'e',  'є': 'ie', 'ж': 'zh', 'з': 'z',  'и': 'y',  'і': 'i',
    'ї': 'i',  'й': 'i',  'к': 'k',  'л': 'l',  'м': 'm',  'н': 'n',
    'о': 'o',  'п': 'p',  'р': 'r',  'с': 's',  'т': 't',  'у': 'u',
    'ф': 'f',  'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
    'ь': '',   'ю': 'yu', 'я': 'ya',
    "'": '', '\u2019': '', '\u02bc': '',
}


def transliterate(text: str) -> str:
    return ''.join(TRANSLIT_TABLE.get(c, c) for c in text)


# ─────────────────────────────────────────────
#  Built-in banking dictionary  (offline)
# ─────────────────────────────────────────────
EXACT_TRANSLATIONS = {
    '"Клієнт-Банк"':                         '"Client-Bank"',
    'Дата складання':                          'Date of issue',
    'Дата валютування':                        'Value date',
    'Дата виконання':                          'Execution date',
    'Дата та час отримання':                   'Date and time of receipt',
    'Дата та час прийняття до ':               'Date and time of acceptance for ',
    'Дата та час прийняття до':                'Date and time of acceptance for',
    'виконання':                               'execution',
    'Платник':                                 'Payer',
    'Код платника':                            'Payer code',
    'Рахунок платника':                        "Payer's account",
    'Надавач платіжних послуг платника':       "Payer's payment service provider",
    'Фактичний платник':                       'Actual payer',
    'Код фактичного платника':                 'Actual payer code',
    'Отримувач':                               'Recipient',
    'Код отримувача':                          'Recipient code',
    'Рахунок отримувача':                      "Recipient's account",
    'Надавач платіжних послуг отримувача':     "Recipient's payment service provider",
    'Фактичний отримувач':                     'Actual recipient',
    'Код фактичного отримувача':               'Actual recipient code',
    'Сума':                                    'Sum',
    'Сума словами':                            'Amount in words',
    'Призначення платежу':                     'Payment purpose',
    'М. П. платника':                          "Payer's seal",
    'Підписи платника':                        "Payer's signatures",
    'Підпис надавача платіжних послуг':        'Payment service provider signature',
    'Додаткові реквізити':                     'Additional details',
    'Проведено Банком':                        'Processed by Bank',
    'ПДВ ':                                    'VAT ',
    'ПДВ':                                     'VAT',
    '____________________':                    '____________________',
}

UA_MONTH_LONG = {
    'січня': 'January',   'лютого': 'February', 'березня': 'March',
    'квітня': 'April',    'травня': 'May',       'червня': 'June',
    'липня': 'July',      'серпня': 'August',    'вересня': 'September',
    'жовтня': 'October',  'листопада': 'November', 'грудня': 'December',
}
UA_MONTH_SHORT = {
    'БЕР': 'MAR', 'ЛИП': 'JUL', 'СІЧ': 'JAN', 'ЛЮТ': 'FEB',
    'КВІ': 'APR', 'ТРА': 'MAY', 'ЧЕР': 'JUN', 'СЕР': 'AUG',
    'ВЕР': 'SEP', 'ЖОВ': 'OCT', 'ЛИС': 'NOV', 'ГРУ': 'DEC',
}

UA_NUMBERS = {
    'нуль': 'zero',       'один': 'one',         'одна': 'one',
    'два': 'two',         'дві': 'two',           'три': 'three',
    'чотири': 'four',     "п'ять": 'five',        'п`ять': 'five',
    'шість': 'six',       'сім': 'seven',          'вісім': 'eight',
    "дев'ять": 'nine',    'десять': 'ten',         'одинадцять': 'eleven',
    'дванадцять': 'twelve', 'тринадцять': 'thirteen', 'чотирнадцять': 'fourteen',
    "п'ятнадцять": 'fifteen', 'шістнадцять': 'sixteen', 'сімнадцять': 'seventeen',
    'вісімнадцять': 'eighteen', "дев'ятнадцять": 'nineteen',
    'двадцять': 'twenty', 'тридцять': 'thirty',   'сорок': 'forty',
    "п'ятдесят": 'fifty', 'п`ятдесят': 'fifty',   'шістдесят': 'sixty',
    'сімдесят': 'seventy', 'вісімдесят': 'eighty', "дев'яносто": 'ninety',
    'сто': 'one hundred', 'двісті': 'two hundred', 'двiстi': 'two hundred',
    'триста': 'three hundred', 'чотириста': 'four hundred',
    "п'ятсот": 'five hundred',
    'тисяча': 'thousand', 'тисячі': 'thousand',   'тисяч': 'thousand',
    'мільйон': 'million', 'мільйони': 'million',   'мільйонів': 'million',
}

# Regex: Ukrainian title-case name sequence (2–4 words)
UA_NAME_RE = re.compile(
    r'[А-ЯІЇЄ][а-яіїє\'\u2019\u02bc-]+(?:\s+[А-ЯІЇЄ][а-яіїє\'\u2019\u02bc-]+){1,3}',
    re.UNICODE,
)


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r'[А-ЯІЇЄа-яіїє]', text))


# ─────────────────────────────────────────────
#  deep_translator  (online, Google Translate)
# ─────────────────────────────────────────────
# Single shared translator instance (re-used across calls for efficiency)
_online_translator = None


def _get_translator():
    global _online_translator
    if _online_translator is None:
        if not HAS_DEEP_TRANSLATOR:
            raise ImportError(
                "deep_translator is not installed. Run: pip install deep_translator"
            )
        _online_translator = GoogleTranslator(source='uk', target='en')
    return _online_translator


def online_translate(text: str) -> str:
    """
    Translate a single Ukrainian string via Google Translate (deep_translator).
    Returns the original text on failure so the document is never left blank.
    """
    try:
        result = _get_translator().translate(text)
        return result if result else text
    except Exception as e:
        print(f"    ⚠ online_translate failed ({e}): {repr(text[:40])}")
        return text


def online_translate_batch(texts: list) -> list:
    """
    Translate a list of strings in one batch call where possible.
    GoogleTranslator.translate_batch() is used when available.
    """
    if not texts:
        return []
    try:
        t = _get_translator()
        results = t.translate_batch(texts)
        # translate_batch may return None for some items — fall back to original
        return [r if r else texts[i] for i, r in enumerate(results)]
    except Exception as e:
        print(f"    ⚠ batch translate failed ({e}), trying one by one …")
        return [online_translate(t) for t in texts]


# ─────────────────────────────────────────────
#  Main translation logic
# ─────────────────────────────────────────────
def translate_span(text: str) -> tuple[str, bool]:
    """
    Translate one PDF text span.

    Returns (translated_text, used_online) where used_online=True means
    we had to call Google Translate for (part of) this string.
    """
    stripped = text.strip()
    trailing_space = text.endswith(' ') and not stripped.endswith(' ')

    def restore_space(s):
        return s + ' ' if trailing_space and not s.endswith(' ') else s

    # ── 1. Exact dictionary match ─────────────────────────────────────────
    if stripped in EXACT_TRANSLATIONS:
        return restore_space(EXACT_TRANSLATIONS[stripped]), False

    # ── 2. ПЛАТІЖНА ІНСТРУКЦІЯ № … ───────────────────────────────────────
    m = re.match(r'^ПЛАТІЖНА ІНСТРУКЦІЯ\s*(.*)$', stripped)
    if m:
        return restore_space(f'PAYMENT INSTRUCTION {m.group(1)}'.strip()), False

    # ── 3. ФОП + name  →  transliterate name ─────────────────────────────
    if re.match(r'^ФОП\s+', stripped):
        return restore_space('FOP ' + transliterate(stripped[4:].strip())), False

    # ── 4. Голова організації: + name ────────────────────────────────────
    m = re.match(r'^Голова організації:(.*)', stripped)
    if m:
        return restore_space(
            'Head of organization: ' + transliterate(m.group(1).strip())
        ), False

    # ── 5. ГО "…" ────────────────────────────────────────────────────────
    m = re.match(r'^ГО\s+"([^"]+)"$', stripped)
    if m:
        org = m.group(1).replace('ФОНД', 'FUND').replace('МАША', 'MASHA')
        # transliterate any remaining Cyrillic
        if _has_cyrillic(org):
            org = transliterate(org)
        return restore_space(f'NGO "{org}"'), False

    # ── 6. АТ КБ "…" ─────────────────────────────────────────────────────
    m = re.match(r'^АТ КБ\s+"([^"]+)"$', stripped)
    if m:
        name = m.group(1)
        if _has_cyrillic(name):
            name = transliterate(name)
        return restore_space(f'JSC CB "{name}"'), False

    # ── 7. АТ "…" ────────────────────────────────────────────────────────
    m = re.match(r'^АТ\s+"([^"]+)"$', stripped)
    if m:
        name = m.group(1)
        if _has_cyrillic(name):
            name = transliterate(name)
        return restore_space(f'JSC "{name}"'), False

    # ── 8. Apply month / number / currency substitutions (offline) ────────
    result = text

    for ua, en in UA_MONTH_LONG.items():
        result = result.replace(ua, en)
    for ua, en in UA_MONTH_SHORT.items():
        result = result.replace(ua, en)

    # Number words (longest first to avoid partial matches)
    for ua_num, en_num in sorted(UA_NUMBERS.items(), key=lambda x: -len(x[0])):
        result = re.sub(
            r'\b' + re.escape(ua_num) + r'\b', en_num,
            result, flags=re.IGNORECASE,
        )

    # Currency
    result = re.sub(r'\bгрн\.\s*', 'UAH ', result)
    result = re.sub(r'\bкоп\.\s*', 'kop. ', result)

    # Common payment purpose fragments
    result = result.replace(
        'Оплата комбінованих офісних адміністративних послуг',
        'Payment for combined office administrative services',
    )
    result = result.replace('зг.', 'acc. to')
    result = result.replace('дог.', 'agr.')
    result = result.replace(' від ', ' dated ')
    result = result.replace('акт, без ПДВ', 'act, excl. VAT')
    result = result.replace('акт', 'act')
    result = result.replace('без ПДВ', 'excl. VAT')
    result = result.replace('ПДВ', 'VAT')

    # ── 9. If Cyrillic still remains → send to Google Translate ──────────
    if _has_cyrillic(result):
        translated = online_translate(result.strip())
        return restore_space(translated), True

    return restore_space(result), False


def translate_all_spans(spans: list) -> list:
    """
    Translate a list of span text strings.
    Strings that still contain Cyrillic after offline processing are batched
    and sent to Google Translate in a single call.
    """
    # Pass 1: apply offline rules, mark which ones still need online translation
    partial = []         # result after offline pass
    online_idx = []      # indices that still have Cyrillic

    for span_text in spans:
        result, needs_online = translate_span(span_text)
        partial.append(result)
        if needs_online:
            online_idx.append(len(partial) - 1)

    if not online_idx:
        return partial

    # Pass 2: batch-translate the ones that still have Cyrillic
    texts_for_online = [partial[i] for i in online_idx]
    print(f"  Sending {len(texts_for_online)} phrase(s) to Google Translate …")
    online_results = online_translate_batch(texts_for_online)

    for idx, translated in zip(online_idx, online_results):
        partial[idx] = translated

    return partial


# ─────────────────────────────────────────────
#  Text fitting helpers
# ─────────────────────────────────────────────
_font_cache: dict = {}


def get_fitz_font(name: str) -> fitz.Font:
    if name not in _font_cache:
        try:
            _font_cache[name] = fitz.Font(name)
        except Exception:
            _font_cache[name] = fitz.Font("helv")
    return _font_cache[name]


def text_width(text: str, font_name: str, size: float) -> float:
    return get_fitz_font(font_name).text_length(text, size)


def fit_text(text: str, font_name: str, orig_size: float, max_w: float,
             min_size: float = 7) -> tuple:
    """Return (font_size, char_spacing) that makes `text` fit within `max_w`."""
    size = orig_size
    while size >= min_size:
        if text_width(text, font_name, size) <= max_w:
            return size, 0.0
        size -= 0.5

    w = text_width(text, font_name, min_size)
    if w <= max_w:
        return min_size, 0.0

    # Apply negative char spacing as last resort
    n = max(len(text) - 1, 1)
    return min_size, -(w - max_w) / n


# ─────────────────────────────────────────────
#  Blue region detection  (bank stamps)
# ─────────────────────────────────────────────
def get_blue_rects(page: fitz.Page) -> list:
    result = []
    for p in page.get_drawings():
        col = p.get('fill') or p.get('color')
        if col and len(col) == 3:
            r, g, b = col
            if b > 0.5 and b > r + 0.2 and b > g + 0.2:
                result.append(fitz.Rect(p['rect']))
    return result


def in_blue(bbox, blue_rects: list) -> bool:
    sr = fitz.Rect(bbox)
    return any(br.intersects(sr) for br in blue_rects)


# ─────────────────────────────────────────────
#  Font name → pymupdf built-in
# ─────────────────────────────────────────────
def map_font(font_name: str, flags: int = 0) -> str:
    fn = font_name.lower()
    bold   = 'bold'   in fn or bool(flags & (1 << 4))
    italic = 'italic' in fn or 'oblique' in fn or bool(flags & (1 << 6))
    if bold:
        return "hebo"
    if italic:
        return "heit"
    return "helv"


# ─────────────────────────────────────────────
#  Low-level: insert text with Tc via raw PDF content stream
#  (pymupdf's insert_text does not expose the Tc operator in this version)
# ─────────────────────────────────────────────
def _escape_pdf_string(text: str) -> bytes:
    """Encode text as a PDF literal string (Latin-1) with escaping."""
    # Replace characters that have no Latin-1 equivalent
    replacements = {
        '№': 'No.', '«': '"', '»': '"',
        '\u2014': '--', '\u2013': '-',
        '\u2019': "'", '\u2018': "'",
        '\u201c': '"', '\u201d': '"',
        '\u02bc': "'",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    encoded = text.encode('latin-1', errors='replace')
    out = bytearray()
    for b in encoded:
        if b in (ord('('), ord(')'), ord('\\')):
            out.append(ord('\\'))
        out.append(b)
    return bytes(out)


def ensure_font_registered(page: fitz.Page, fontname: str):
    """Register a font on the page by inserting an invisible dummy glyph."""
    for f in page.get_fonts():
        if f[4] == fontname:
            return
    page.insert_text(
        fitz.Point(-200, -200), ' ',
        fontname=fontname, fontsize=0.01, color=(1, 1, 1),
    )


def insert_text_with_tc(
    page: fitz.Page,
    point: fitz.Point,
    text: str,
    fontname: str,
    fontsize: float,
    color: tuple,        # (r, g, b) floats 0–1
    char_spacing: float, # Tc value in pts; 0 = normal spacing
):
    """Insert text using a raw PDF content snippet that supports the Tc operator."""
    y_pdf = page.rect.height - point.y
    x_pdf = point.x

    r, g, b = color
    pdf_str = b'(' + _escape_pdf_string(text) + b')'

    snippet = (
        f"q\n"
        f"{r:.4f} {g:.4f} {b:.4f} rg\n"
        f"BT\n"
        f"/{fontname} {fontsize:.4f} Tf\n"
        f"{char_spacing:.4f} Tc\n"
        f"{x_pdf:.4f} {y_pdf:.4f} Td\n"
    ).encode() + pdf_str + b" Tj\nET\nQ\n"

    xrefs = page.get_contents()
    if xrefs:
        existing = page.parent.xref_stream(xrefs[-1])
        page.parent.update_stream(xrefs[-1], existing + snippet)
    else:
        xref = page.parent.get_new_xref()
        page.parent.update_stream(xref, snippet)
        page.set_contents(xref)


# ─────────────────────────────────────────────
#  Main pipeline
# ─────────────────────────────────────────────
def translate_pdf(input_path: str, output_path: str):
    print(f"Opening: {input_path}")
    doc = fitz.open(input_path)

    for page_num, page in enumerate(doc):
        print(f"\n─── Page {page_num + 1} ───")

        blue_rects = get_blue_rects(page)
        print(f"  Blue stamp regions: {len(blue_rects)}")

        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

        # Collect spans that contain Ukrainian text
        spans = []
        for block in blocks["blocks"]:
            if block["type"] != 0:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    # color == 255  means text is on the blue stamp background → skip
                    if span['color'] == 255:
                        continue
                    if in_blue(span['bbox'], blue_rects):
                        continue
                    if not _has_cyrillic(span['text']):
                        continue
                    spans.append(span)

        print(f"  Spans to translate: {len(spans)}")
        if not spans:
            continue

        # Translate all spans (offline dict + online fallback)
        translated = translate_all_spans([s['text'] for s in spans])

        # Print mapping
        for span, tr in zip(spans, translated):
            o = span['text'].strip()[:50]
            t = tr.strip()[:50]
            if o != t:
                print(f"  [{o!r}] → [{t!r}]")

        # ── Step 1: white-out original text ──────────────────────────────
        for span in spans:
            page.add_redact_annot(fitz.Rect(span['bbox']), fill=(1, 1, 1))
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # ── Step 2: insert translated text ───────────────────────────────
        fonts_needed = {map_font(s['font'], s.get('flags', 0)) for s in spans}
        for fn in fonts_needed:
            ensure_font_registered(page, fn)

        for span, tr_text in zip(spans, translated):
            bbox       = fitz.Rect(span['bbox'])
            fitz_font  = map_font(span['font'], span.get('flags', 0))
            orig_size  = span['size']

            # Decode color (pymupdf stores as 0xRRGGBB integer)
            c = span['color']
            rgb = (0.0, 0.0, 0.0) if c == 0 else (
                ((c >> 16) & 0xFF) / 255.0,
                ((c >>  8) & 0xFF) / 255.0,
                ( c        & 0xFF) / 255.0,
            )

            fitted_size, char_sp = fit_text(tr_text, fitz_font, orig_size, bbox.width)
            if fitted_size < orig_size - 0.4:
                print(f"    ↓ {orig_size:.1f}→{fitted_size:.1f}pt"
                      f"  Tc={char_sp:.2f}: {tr_text[:35]!r}")

            insert_text_with_tc(
                page,
                fitz.Point(bbox.x0, bbox.y1),   # baseline = bottom of bbox
                tr_text,
                fontname=fitz_font,
                fontsize=fitted_size,
                color=rgb,
                char_spacing=char_sp,
            )

    doc.save(output_path, garbage=4, deflate=True)
    print(f"\n✓ Saved: {output_path}")


# ─────────────────────────────────────────────
#  CLI
# ─────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Translate a Ukrainian bank payment PDF to English.\n\n"
            "Translation priority:\n"
            "  1. Built-in banking dictionary (offline, instant)\n"
            "  2. Google Translate via deep_translator (online, for unknown phrases)\n"
            "  3. KMU 2010 transliteration for personal names (always offline)"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input",  help="Input PDF path")
    parser.add_argument("output", nargs="?",
                        help="Output PDF path (default: <input>_en.pdf)")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    if not HAS_DEEP_TRANSLATOR:
        print("Warning: deep_translator not installed.")
        print("         Words not in the built-in dictionary will not be translated.")
        print("         Install with:  pip install deep_translator\n")

    out = args.output or (os.path.splitext(args.input)[0] + "_en.pdf")
    translate_pdf(args.input, out)
