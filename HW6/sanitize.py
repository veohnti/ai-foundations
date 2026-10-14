"""Defense layer 1 (code): clean a vendor document before any model sees it.

The Problem 3 reader keeps hidden text and labels it. This one removes everything a
human reader would not see, plus instruction-like text, and records what it removed:

- HTML: hidden elements (display:none, visibility:hidden, 0-1px fonts, white text,
  opacity 0, hidden attribute), comments, scripts and styles.
- PDF: text that is white, smaller than 4pt, or placed outside the page.
- Word: hidden, white, or tiny runs. PowerPoint: speaker notes. Excel: hidden sheets/rows/columns.
- Email: the plain-text body is used. The HTML copy is used only when there is no plain text.
- All formats: zero-width and text-direction characters, plus any line that names our
  internal tools or tries to give the agent orders.
"""

from __future__ import annotations

import email
import io
import re
from dataclasses import dataclass, field
from email import policy
from html.parser import HTMLParser
from pathlib import Path

MIN_PDF_FONT_PT = 4.0
INVISIBLE_CHARS = re.compile("[​‌‍⁠﻿‪-‮⁦-⁩]")
# Lines that try to give the agent orders. A real quote never needs to mention our tools,
# "the reviewer", or "the agent", or tell anyone to ignore instructions.
INSTRUCTION_LINE = re.compile(
    r"send_email|approve_payment|check_purchasing_rules|read_document|lookup_(vendor|sku)"
    r"|ignore (all |any |the )?(previous|prior|above|earlier) (instructions|rules)"
    r"|(the )?(ai|agent|assistant|reviewer|model)\b.{0,40}\b(must|should|sends?|calls?|approves?|puts?|marks?)\b"
    r"|system prompt|you are now|new instructions|in your (reason|answer|report)",
    re.I,
)


@dataclass
class Sanitized:
    text: str
    removed: list[dict] = field(default_factory=list)

    def note(self, kind: str, where: str, text: str) -> None:
        text = " ".join(INVISIBLE_CHARS.sub("", text).split())
        if text:
            self.removed.append({"kind": kind, "where": where, "text": text[:300]})


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

class _VisibleHTML(HTMLParser):
    VOID = {"br", "img", "meta", "link", "hr", "input", "col", "area", "base", "source", "wbr"}
    BLOCK = {"p", "div", "tr", "li", "h1", "h2", "h3", "h4", "h5", "h6", "header", "footer",
             "table", "section", "article", "br", "hr", "title"}
    DROP = {"script", "style", "head", "template", "noscript", "iframe", "object"}
    HIDDEN_STYLE = re.compile(
        r"display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(\.0+)?\s*(;|$)"
        r"|font-size\s*:\s*[0-3](\.\d+)?\s*(px|pt)?\s*(;|$)"
        r"|(?<![-\w])color\s*:\s*(#fff(fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)|transparent)"
        r"|(left|top|text-indent)\s*:\s*-\d{3,}",
        re.I,
    )

    def __init__(self, out: Sanitized, where: str) -> None:
        super().__init__(convert_charrefs=True)
        self.s, self.where = out, where
        self.parts: list[str] = []
        self.stack: list[tuple[str, str | None]] = []  # (tag, why hidden)
        self.hidden_buf: list[str] = []

    def _why(self) -> str | None:
        return next((w for _, w in self.stack if w), None)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        why = None
        if tag in self.DROP:
            why = f"<{tag}>"
        elif "hidden" in a or a.get("aria-hidden") == "true":
            why = "hidden attribute"
        elif m := self.HIDDEN_STYLE.search(a.get("style") or ""):
            why = f"style {m.group(0).strip(' ;')}"
        if tag in self.BLOCK and not self._why():
            self.parts.append("\n")
        if tag in ("td", "th") and not self._why():
            self.parts.append(" | ")
        if tag in self.VOID:
            return
        if why and not self._why():
            self.hidden_buf = []
        self.stack.append((tag, why))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                why_before = self._why()
                del self.stack[i:]
                if why_before and not self._why() and why_before not in ("<head>", "<style>"):
                    kind = "script" if why_before.startswith("<") else "hidden HTML"
                    self.s.note(kind, f"{self.where}: {why_before}", "".join(self.hidden_buf))
                break
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        (self.hidden_buf if self._why() else self.parts).append(data)

    def handle_comment(self, data):
        self.s.note("HTML comment", f"{self.where}: <!-- -->", data)


def _html(raw: str, out: Sanitized, where: str) -> str:
    title = re.search(r"<title[^>]*>(.*?)</title>", raw, re.I | re.S)
    p = _VisibleHTML(out, where)
    p.feed(raw)
    lines = (" ".join(line.split()) for line in "".join(p.parts).splitlines())
    body = "\n".join(line for line in lines if line.strip(" |"))
    return (f"Title: {' '.join(title.group(1).split())}\n" if title else "") + body


# ---------------------------------------------------------------------------
# PDF: keep only text a person would see on the page
# ---------------------------------------------------------------------------

def _pdf(data: bytes, out: Sanitized, where: str) -> str:
    from pypdf import PdfReader

    pages = []
    for n, page in enumerate(PdfReader(io.BytesIO(data)).pages, 1):
        box = page.mediabox
        x0, y0, x1, y1 = float(box.left), float(box.bottom), float(box.right), float(box.top)
        state = {"fill": (0.0, 0.0, 0.0)}
        saved: list[dict] = []
        kept: list[str] = []

        def before(op, args, cm, tm):
            if op == b"q":
                saved.append(dict(state))
            elif op == b"Q" and saved:
                state.update(saved.pop())
            elif op == b"rg" and len(args) == 3:
                state["fill"] = tuple(float(a) for a in args)
            elif op == b"g" and args:
                state["fill"] = (float(args[0]),) * 3
            elif op == b"k" and len(args) == 4:  # CMYK white is 0 0 0 0
                c, m, y, k = (float(a) for a in args)
                state["fill"] = tuple((1 - v) * (1 - k) for v in (c, m, y))

        def visit(text, cm, tm, font, size):
            if not text.strip():
                kept.append(text)
                return
            x = tm[4] * cm[0] + tm[5] * cm[2] + cm[4]
            y = tm[4] * cm[1] + tm[5] * cm[3] + cm[5]
            scale = (abs(tm[3] * cm[3]) or abs(tm[0] * cm[0]) or 1.0)
            eff_size = float(size) * scale
            why = None
            if all(c >= 0.95 for c in state["fill"]):
                why = "white text"
            elif eff_size < MIN_PDF_FONT_PT:
                why = f"{eff_size:g}pt text (too small to read)"
            elif not (x0 - 1 <= x <= x1 and y0 - 1 <= y <= y1):
                why = f"text placed off the page at ({x:g}, {y:g})"
            if why:
                out.note("hidden PDF text", f"{where} page {n}: {why}", text)
                kept.append("\n")
            else:
                kept.append(text)

        page.extract_text(visitor_operand_before=before, visitor_text=visit)
        pages.append(f"--- page {n} ---\n" + "".join(kept))
    return "\n\n".join(pages)


# ---------------------------------------------------------------------------
# Office files
# ---------------------------------------------------------------------------

def _docx(data: bytes, out: Sanitized, where: str) -> str:
    import docx

    d = docx.Document(io.BytesIO(data))
    parts = []

    def run_hidden(r) -> str | None:
        if r.font.hidden:
            return "hidden run"
        rgb = r.font.color.rgb if r.font.color and r.font.color.type is not None else None
        if rgb is not None and str(rgb).upper() == "FFFFFF":
            return "white text"
        if r.font.size is not None and r.font.size.pt < MIN_PDF_FONT_PT:
            return f"{r.font.size.pt:g}pt text"
        return None

    for para in d.paragraphs:
        visible = []
        for r in para.runs:
            if why := run_hidden(r):
                out.note("hidden Word text", f"{where}: {why}", r.text)
            else:
                visible.append(r.text)
        if "".join(visible).strip():
            parts.append("".join(visible))
    for table in d.tables:
        for row in table.rows:
            parts.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(parts)


def _pptx(data: bytes, out: Sanitized, where: str) -> str:
    from pptx import Presentation

    parts = []
    for i, slide in enumerate(Presentation(io.BytesIO(data)).slides, 1):
        parts.append(f"--- slide {i} ---")
        for shape in slide.shapes:
            if shape.has_text_frame and shape.text_frame.text.strip():
                parts.append(shape.text_frame.text)
            if getattr(shape, "has_table", False) and shape.has_table:
                for row in shape.table.rows:
                    parts.append(" | ".join(c.text.strip() for c in row.cells))
        if slide.has_notes_slide:
            out.note("speaker notes", f"{where} slide {i}", slide.notes_slide.notes_text_frame.text)
    return "\n".join(parts)


def _xlsx(data: bytes, out: Sanitized, where: str) -> str:
    from openpyxl import load_workbook

    parts = []
    for ws in load_workbook(io.BytesIO(data), data_only=True).worksheets:
        if ws.sheet_state != "visible":
            out.note("hidden sheet", f"{where}: sheet {ws.title}", ws.title)
            continue
        parts.append(f"--- sheet {ws.title} ---")
        hidden_cols = {k for k, d in ws.column_dimensions.items() if d.hidden}
        for row in ws.iter_rows():
            if not any(c.value is not None for c in row):
                continue
            if ws.row_dimensions[row[0].row].hidden:
                out.note("hidden row", f"{where}: sheet {ws.title} row {row[0].row}",
                         " ".join(str(c.value) for c in row if c.value is not None))
                continue
            parts.append(" | ".join("" if c.value is None or c.column_letter in hidden_cols else str(c.value)
                                    for c in row))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

def _eml(data: bytes, out: Sanitized, where: str) -> str:
    msg = email.message_from_bytes(data, policy=policy.default)
    parts = [f"{h}: {msg[h]}" for h in ("From", "To", "Subject", "Date") if msg[h]]
    plain = [p for p in msg.walk() if not p.is_multipart() and not p.get_filename()
             and p.get_content_type() == "text/plain"]
    html = [p for p in msg.walk() if not p.is_multipart() and not p.get_filename()
            and p.get_content_type() == "text/html"]
    for p in plain:
        parts.append("\n" + p.get_content())
    for p in html:
        if plain:  # the plain text is what we use; record anything hidden in the unused HTML copy
            _html(p.get_content(), out, f"{where} (HTML copy of the email, not used)")
        else:
            parts.append("\n" + _html(p.get_content(), out, f"{where} (HTML body)"))
    for p in msg.walk():
        if not p.is_multipart() and p.get_filename():
            parts.append(f"\n--- attachment: {p.get_filename()} ---")
            parts.append(_extract(p.get_filename(), p.get_payload(decode=True) or b"", out))
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Dispatch and final line filters
# ---------------------------------------------------------------------------

def _extract(name: str, data: bytes, out: Sanitized) -> str:
    ext = Path(name).suffix.lower()
    if ext in (".html", ".htm"):
        return _html(data.decode("utf-8", errors="replace"), out, name)
    if ext == ".pdf":
        return _pdf(data, out, name)
    if ext == ".docx":
        return _docx(data, out, name)
    if ext == ".pptx":
        return _pptx(data, out, name)
    if ext in (".xlsx", ".xlsm"):
        return _xlsx(data, out, name)
    if ext == ".eml":
        return _eml(data, out, name)
    if ext in (".doc", ".ppt", ".xls"):
        return f"[Cannot read legacy {ext} files. Ask the vendor for .docx/.pptx/.xlsx or PDF.]"
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return f"[Unsupported binary file type: {ext or 'no extension'}]"


def sanitize(name: str, data: bytes) -> Sanitized:
    out = Sanitized("")
    text = _extract(name, data, out)
    text, n = INVISIBLE_CHARS.subn("", text)
    if n:
        out.note("invisible characters", name, f"{n} zero-width / text-direction characters")
    kept = []
    for line in text.splitlines():
        if INSTRUCTION_LINE.search(line):
            out.note("instruction aimed at the agent", f"{name}: visible line", line)
        else:
            kept.append(line)
    out.text = "\n".join(kept).strip()
    return out
