"""Converter dokumen: PDF ops (merge/split/rotate/compress/extract_text) via
PyMuPDF + konversi teks antar docx/xlsx/csv/pptx/txt/md/html/pdf.

Konversi dokumen bersifat TEKS (paragraf, heading, tabel sederhana) —
layout kompleks adalah best-effort.
"""
import csv
import os
import re

from core.errors import TaskCancelled


def _fitz():
    import pymupdf
    return pymupdf


def _docx():
    import docx
    return docx


def _openpyxl():
    from openpyxl import Workbook, load_workbook
    return Workbook, load_workbook


def _pptx():
    from pptx import Presentation
    return Presentation


def _markdown():
    import markdown
    return markdown


def convert(src, dst, target, options, on_prog, cancel_fn=None):
    """Entry point engine. Untuk PDF ops, options["op"] menentukan aksi:
    merge (extra_files), split, rotate (degrees), compress, extract_text.
    """
    op = options.get("op")
    if op == "merge":
        return pdf_merge([src] + list(options.get("extra_files", [])),
                         dst, on_prog, cancel_fn)
    if op == "split":
        return pdf_split(src, dst, on_prog, cancel_fn)
    if op == "rotate":
        return pdf_rotate(src, dst, int(options.get("degrees") or 90), on_prog)
    if op == "compress":
        return pdf_compress(src, dst, on_prog)
    if op == "extract_text":
        return pdf_to_text(src, dst, "txt", on_prog, cancel_fn)

    ext = os.path.splitext(src)[1].lower()

    if ext == ".pdf":
        if target in ("txt", "md"):
            return pdf_to_text(src, dst, target, on_prog, cancel_fn)
        raise RuntimeError("pdf -> %s tidak didukung" % target)
    if ext == ".xlsx":
        return xlsx_convert(src, dst, target, on_prog, cancel_fn)
    if ext == ".csv":
        return csv_convert(src, dst, target, on_prog, cancel_fn)

    text = _extract_text(src, ext)
    on_prog(40)
    if cancel_fn and cancel_fn():
        raise TaskCancelled()

    if target == "txt":
        _write_text(dst, _plain(text))
    elif target == "md":
        _write_text(dst, text)
    elif target == "html":
        _write_text(dst, _render_html(text, ext))
    elif target == "docx":
        _text_to_docx(dst, text)
    elif target == "pdf":
        _text_to_pdf(dst, text, on_prog, cancel_fn)
    else:
        raise RuntimeError("%s -> %s tidak didukung" % (ext, target))
    on_prog(100)


# --- ekstraksi teks dari sumber berbasis teks ----------------------------

def _extract_text(src, ext):
    if ext == ".docx":
        return _docx_to_text(src)
    if ext == ".pptx":
        return _pptx_text(src)
    if ext == ".md":
        with open(src, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    if ext in (".html", ".htm"):
        return _html_to_text(src)
    # .txt
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _docx_to_text(src):
    d = _docx().Document(src)
    out = []
    for block in d.iter_inner_content():
        if hasattr(block, "text"):  # Paragraph
            style = getattr(getattr(block, "style", None), "name", "") or ""
            if style.startswith("Heading"):
                level = style.replace("Heading ", "")
                hashes = "#" * (int(level) if level.isdigit() else 1)
                out.append(hashes + " " + block.text)
            else:
                out.append(block.text)
        else:  # Table
            for row in block.rows:
                out.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(out)


def _pptx_text(src):
    Presentation = _pptx()
    prs = Presentation(src)
    parts = []
    for i, slide in enumerate(prs.slides, 1):
        parts.append("## Slide %d" % i)
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                line = "".join(run.text for run in para.runs)
                if line.strip():
                    parts.append(line)
    return "\n".join(parts)


def _html_to_text(src):
    from html.parser import HTMLParser

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.chunks = []
            self._skip = 0

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                self._skip += 1
            elif tag in ("p", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6",
                         "tr", "li"):
                self.chunks.append("\n")

        def handle_endtag(self, tag):
            if tag in ("script", "style") and self._skip:
                self._skip -= 1

        def handle_data(self, data):
            if not self._skip:
                self.chunks.append(data)

    p = _P()
    with open(src, "r", encoding="utf-8", errors="replace") as f:
        p.feed(f.read())
    text = "".join(p.chunks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- PDF ops (PyMuPDF) ---------------------------------------------------

def pdf_merge(paths, dst, on_prog, cancel_fn=None):
    pymupdf = _fitz()
    merger = pymupdf.open()
    try:
        for i, path in enumerate(paths, 1):
            if cancel_fn and cancel_fn():
                raise TaskCancelled()
            with pymupdf.open(path) as d:
                merger.insert_pdf(d)
            on_prog(int(100 * i / max(1, len(paths))), "file %d" % i)
        merger.save(dst, garbage=3, deflate=True)
    finally:
        merger.close()
    on_prog(100)


def pdf_split(src, dst, on_prog, cancel_fn=None):
    """Pecah per halaman: out.pdf → out_p1.pdf, out_p2.pdf, ..."""
    pymupdf = _fitz()
    stem = os.path.splitext(dst)[0]
    with pymupdf.open(src) as doc:
        total = len(doc)
        for i in range(total):
            if cancel_fn and cancel_fn():
                raise TaskCancelled()
            single = pymupdf.open()
            single.insert_pdf(doc, from_page=i, to_page=i)
            single.save("%s_p%d.pdf" % (stem, i + 1), garbage=3, deflate=True)
            single.close()
            on_prog(int(100 * (i + 1) / total), "halaman %d/%d" % (i + 1, total))
    on_prog(100)


def pdf_rotate(src, dst, degrees, on_prog, cancel_fn=None):
    pymupdf = _fitz()
    with pymupdf.open(src) as doc:
        for page in doc:
            page.set_rotation((page.rotation + degrees) % 360)
        doc.save(dst, garbage=3, deflate=True)
    on_prog(100)


def pdf_compress(src, dst, on_prog, cancel_fn=None):
    pymupdf = _fitz()
    with pymupdf.open(src) as doc:
        doc.save(dst, garbage=4, deflate=True, clean=True)
    on_prog(100)


def pdf_to_text(src, dst, target, on_prog, cancel_fn=None):
    pymupdf = _fitz()
    pages = []
    with pymupdf.open(src) as doc:
        total = len(doc)
        for i, page in enumerate(doc):
            if cancel_fn and cancel_fn():
                raise TaskCancelled()
            pages.append("--- Halaman %d ---\n%s" % (i + 1, page.get_text()))
            on_prog(int(80 * (i + 1) / max(1, total)), "halaman %d/%d" % (i + 1, total))
    _write_text(dst, "\n\n".join(pages))
    on_prog(100)


# --- xlsx / csv ----------------------------------------------------------

def xlsx_convert(src, dst, target, on_prog, cancel_fn=None):
    _, load_workbook = _openpyxl()
    wb = load_workbook(src, read_only=True, data_only=True)
    try:
        ws = wb.active
        rows = []
        for r in ws.iter_rows(values_only=True):
            rows.append(["" if v is None else str(v) for v in r])
            if cancel_fn and cancel_fn():
                raise TaskCancelled()
    finally:
        wb.close()
    on_prog(50, "dibaca")
    _emit_rows(rows, dst, target, on_prog, cancel_fn)


def csv_convert(src, dst, target, on_prog, cancel_fn=None):
    with open(src, "r", encoding="utf-8-sig", errors="replace", newline="") as f:
        rows = [row for row in csv.reader(f)]
    on_prog(50, "dibaca")
    _emit_rows(rows, dst, target, on_prog, cancel_fn)


def _emit_rows(rows, dst, target, on_prog, cancel_fn):
    if target == "csv":
        with open(dst, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(rows)
    elif target == "xlsx":
        Workbook, _ = _openpyxl()
        wb = Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        wb.save(dst)
    elif target == "html":
        parts = ["<html><body><table border='1'>"]
        for row in rows:
            parts.append("<tr>" + "".join("<td>%s</td>" % _esc(c)
                          for c in row) + "</tr>")
        parts.append("</table></body></html>")
        _write_text(dst, "\n".join(parts))
    elif target == "pdf":
        lines = ["\t".join(row) for row in rows]
        _text_to_pdf(dst, "\n".join(lines), on_prog, cancel_fn)
    else:
        raise RuntimeError("tabel -> %s tidak didukung" % target)
    on_prog(100)


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


# --- util teks: plain / html / docx / pdf --------------------------------

def _plain(s):
    s = re.sub(r"^#{1,6}\s*", "", s, flags=re.M)   # heading md
    s = re.sub(r"\*\*|__|`", "", s)                 # bold/italic/code
    s = re.sub(r"^[-*+]\s+", "- ", s, flags=re.M)   # bullet
    return s


def _render_html(text, ext):
    if ext == ".md":
        markdown = _markdown()
        body = markdown.markdown(text, extensions=["tables", "fenced_code"])
    else:
        body = "\n".join("<p>%s</p>" % _esc(line) if line.strip() else ""
                         for line in _plain(text).splitlines())
    return ("<!DOCTYPE html><html><head><meta charset='utf-8'>"
            "<title>Converted</title></head><body>%s</body></html>" % body)


def _write_text(dst, s):
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)


def _text_to_docx(dst, text):
    docx = _docx()
    d = docx.Document()
    for line in text.splitlines():
        if not line.strip():
            d.add_paragraph()
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            d.add_heading(m.group(2), level=len(m.group(1)))
        else:
            d.add_paragraph(line)
    d.save(dst)


def _text_to_pdf(dst, text, on_prog, cancel_fn=None):
    """PDF teks sederhana: wrap ~90 karakter, ~40 baris per halaman."""
    pymupdf = _fitz()
    doc = pymupdf.open()
    wrapped = []
    for raw in text.splitlines():
        while len(raw) > 90:
            wrapped.append(raw[:90])
            raw = raw[90:]
        wrapped.append(raw)
    per_page = 40
    pages = [wrapped[i:i + per_page]
             for i in range(0, len(wrapped), per_page)] or [[]]
    for i, lines in enumerate(pages):
        if cancel_fn and cancel_fn():
            raise TaskCancelled()
        page = doc.new_page()
        y = 72
        for line in lines:
            page.insert_text((50, y), line, fontsize=10, fontname="helv")
            y += 14
            if y > 780:
                break
        on_prog(int(80 * (i + 1) / len(pages)), "halaman %d/%d"
                % (i + 1, len(pages)))
    doc.save(dst, garbage=3, deflate=True)
    doc.close()
    on_prog(100)
