"""Self-contained large-print Reader page (OUT-002, A11Y-001..005).

One HTML file with the text, the pictures and the reading font inside it, so it
opens the same way on any computer, offline. Text size, line spacing and
colours change instantly in the page itself (OUT-002).
"""

from __future__ import annotations

import base64
import html
from collections import Counter
from pathlib import Path
from typing import List, Optional

from openlargeprint.ir.models import Block, BlockType, DocumentIR, TextDirection
from openlargeprint.layout.table import evaluate_table_fit, iter_visible_cells, TableTier
from openlargeprint.security.isolation import log_safe_info
from .base import BaseExporter, ExportOptions
from .common import (
    BLANK_TOKEN,
    PRINT_REMINDER,
    caption_label,
    has_original_crop,
    is_retained_page,
    page_label,
    pages_by_number,
    reader_note,
    split_marker,
    styled_segments,
    table_as_entries,
)
from .fonts import bundled_font_dir


def _data_url(path: str, mime: str) -> Optional[str]:
    file = Path(path)
    if not file.is_file():
        return None
    return f"data:{mime};base64,{base64.b64encode(file.read_bytes()).decode('ascii')}"


def _font_faces(arabic: bool = False) -> str:
    faces = []
    if arabic:
        # Only books with Arabic text carry the Arabic font, so others stay small.
        url = _data_url(str(bundled_font_dir() / "NotoSansArabic.ttf"), "font/ttf")
        if url:
            faces.append(f'@font-face {{ font-family: "Noto Sans Arabic"; font-weight: 100 900; '
                         f'src: url("{url}") format("truetype"); }}')
    for weight, style, name in (("400", "normal", "Regular"), ("700", "normal", "Bold"),
                                ("400", "italic", "Italic"), ("700", "italic", "BoldItalic")):
        url = _data_url(str(bundled_font_dir() / f"AtkinsonHyperlegible-{name}.ttf"), "font/ttf")
        if url:
            faces.append(f'@font-face {{ font-family: "Atkinson Hyperlegible"; font-weight: {weight}; '
                         f'font-style: {style}; src: url("{url}") format("truetype"); }}')
    return "\n".join(faces)


STYLE = """
:root { --size: %(size)spt; --spacing: %(spacing)s; --width: 38em;
  --paper: #fbfaf6; --ink: #1b1a17; --muted: #55524a; --line: #b9b3a3; --shade: #ece8dc; --focus: #3d5a2b; }
:root[data-theme="sepia"] { --paper: #f4ecd8; --ink: #2b2318; --muted: #5d5241; --line: #b8a88a; --shade: #e8dcc0; }
:root[data-theme="dark"] { --paper: #121210; --ink: #f2f0e8; --muted: #b9b4a6; --line: #55524a; --shade: #262521; --focus: #b8cf9a; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--paper); color: var(--ink);
  font-family: "Atkinson Hyperlegible", "DejaVu Sans", "Segoe UI", Arial, sans-serif;
  font-size: var(--size); line-height: var(--spacing); }
[dir="rtl"] { font-family: "Noto Sans Arabic", "Segoe UI", "Arial", sans-serif; }
:focus-visible { outline: 3px solid var(--focus); outline-offset: 3px; }
.bar { position: sticky; top: 0; z-index: 2; display: flex; flex-wrap: wrap; gap: 8px 18px; align-items: center;
  padding: 10px 16px; background: var(--shade); border-bottom: 1px solid var(--line); font-size: 17px; line-height: 1.3; }
.bar .group { display: flex; align-items: center; gap: 6px; }
.bar button { min-width: 48px; min-height: 48px; padding: 0 14px; font: inherit; font-weight: 700; color: var(--ink);
  background: var(--paper); border: 1px solid var(--line); border-radius: 6px; cursor: pointer; }
.bar button[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.bar .label { color: var(--muted); }
main { max-width: var(--width); margin: 0 auto; padding: 1.2em 1em 4em; }
h1 { font-size: 1.55em; line-height: 1.25; margin: 1.2em 0 .4em; }
h2 { font-size: 1.3em; line-height: 1.25; margin: 1.1em 0 .35em; }
h3 { font-size: 1.1em; line-height: 1.3; margin: 1em 0 .3em; }
p { margin: 0 0 .6em; }
.item { display: grid; grid-template-columns: max-content 1fr; column-gap: .55em; margin: 0 0 .35em; }
.item .marker { min-width: 1.2em; }
.item.dialogue .marker { font-weight: 700; }
.indent-1 { margin-inline-start: 1.7em; } .indent-2 { margin-inline-start: 3.4em; } .indent-3 { margin-inline-start: 5.1em; }
.blank { display: inline-block; min-width: 5em; border-bottom: 2px solid currentColor; height: 1em; vertical-align: -0.15em; }
.page { margin: 2em 0 1em; padding-top: .4em; border-top: 1px solid var(--line); color: var(--muted);
  font-size: max(12pt, .65em); font-weight: 700; }
figure { margin: 1em 0; text-align: center; }
figure img { max-width: 100%%; height: auto; }
.caption, figcaption { color: var(--muted); font-style: italic; margin: .2em 0 .8em; }
.caption .label { font-weight: 700; }
.note { color: var(--muted); font-style: italic; font-size: max(14pt, .82em); margin: 0 0 .6em; }
blockquote { margin: 0 0 .8em 1.4em; font-style: italic; }
.aside { border: 1px solid var(--line); border-radius: 4px; padding: .5em .7em; margin: 0 0 .8em; }
.footnote { font-size: max(14pt, .82em); border-top: 1px solid var(--line); padding-top: .3em; margin-top: 1em; }
table { border-collapse: collapse; width: 100%%; margin: .6em 0 1.2em; font-size: max(14pt, .88em); }
th, td { border: 1px solid var(--line); padding: .35em .5em; vertical-align: top; text-align: start; }
th { background: var(--shade); }
table caption { caption-side: top; text-align: start; color: var(--muted); font-style: italic; padding-bottom: .3em; }
.entry .lead { font-weight: 700; margin: .4em 0 .1em; }
.entry .detail { margin: 0 0 .2em 1.4em; }
@media print { .bar { display: none; } body { background: #fff; color: #000; } main { max-width: none; } }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
"""

SCRIPT = """
(function () {
  var root = document.documentElement, size = %(size)s, label = document.getElementById("size");
  function setSize(value) { size = Math.max(12, Math.min(48, value)); root.style.setProperty("--size", size + "pt");
    label.textContent = size + " pt"; }
  document.getElementById("smaller").onclick = function () { setSize(size - 2); };
  document.getElementById("larger").onclick = function () { setSize(size + 2); };
  document.querySelectorAll("[data-spacing]").forEach(function (b) { b.onclick = function () {
    root.style.setProperty("--spacing", b.dataset.spacing);
    document.querySelectorAll("[data-spacing]").forEach(function (o) { o.setAttribute("aria-pressed", o === b); }); }; });
  document.querySelectorAll("[data-theme-choice]").forEach(function (b) { b.onclick = function () {
    root.setAttribute("data-theme", b.dataset.themeChoice);
    document.querySelectorAll("[data-theme-choice]").forEach(function (o) { o.setAttribute("aria-pressed", o === b); }); }; });
  document.querySelectorAll("[data-width]").forEach(function (b) { b.onclick = function () {
    root.style.setProperty("--width", b.dataset.width);
    document.querySelectorAll("[data-width]").forEach(function (o) { o.setAttribute("aria-pressed", o === b); }); }; });
  document.getElementById("print").onclick = function () { window.print(); };
})();
"""


class ReaderExporter(BaseExporter):
    """Renders DocumentIR into a single accessible HTML file."""

    def export(self, doc: DocumentIR, output_path: Path, options: Optional[ExportOptions] = None) -> Path:
        options = options or ExportOptions()
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log_safe_info(f"Writing Reader page at {options.body_pt}pt")
        output_path.write_text(self.render(doc, options), encoding="utf-8")
        return output_path

    def render(self, doc: DocumentIR, options: ExportOptions) -> str:
        self._options = options
        self._pages = pages_by_number(doc)
        title = html.escape(doc.metadata.title or "Large print")
        languages = Counter(b.language for b in doc.blocks if b.text and b.language)
        lang = languages.most_common(1)[0][0] if languages else "en"
        arabic = any(b.text_direction == TextDirection.RTL for b in doc.blocks)
        body: List[str] = [f"<h1>{title}</h1>", f'<p class="note">{html.escape(PRINT_REMINDER)}</p>']
        for block in doc.blocks:
            body.append(self._block(block))
        spacing = options.line_spacing
        spacing_buttons = "".join(
            f'<button type="button" data-spacing="{v}" aria-pressed="{str(abs(v - spacing) < 0.01).lower()}">{v:g}</button>'
            for v in (1.3, 1.5, 1.8))
        return f"""<!DOCTYPE html>
<html lang="{html.escape(lang)}" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{_font_faces(arabic)}
{STYLE % {"size": f"{options.body_pt:g}", "spacing": options.line_spacing}}
</style>
</head>
<body>
<div class="bar" role="toolbar" aria-label="Reading settings">
  <div class="group" role="group" aria-label="Text size"><span class="label">Size</span>
    <button type="button" id="smaller" aria-label="Smaller text">A&minus;</button>
    <span id="size" aria-live="polite">{options.body_pt:g} pt</span>
    <button type="button" id="larger" aria-label="Larger text">A+</button>
  </div>
  <div class="group" role="group" aria-label="Line spacing"><span class="label">Spacing</span>{spacing_buttons}</div>
  <div class="group" role="group" aria-label="Colours">
    <button type="button" data-theme-choice="light" aria-pressed="true">Light</button>
    <button type="button" data-theme-choice="sepia" aria-pressed="false">Sepia</button>
    <button type="button" data-theme-choice="dark" aria-pressed="false">Dark</button>
  </div>
  <div class="group" role="group" aria-label="Line length"><span class="label">Width</span>
    <button type="button" data-width="28em" aria-pressed="false">Narrow</button>
    <button type="button" data-width="38em" aria-pressed="true">Medium</button>
    <button type="button" data-width="52em" aria-pressed="false">Wide</button>
  </div>
  <div class="group"><button type="button" id="print">Print</button></div>
</div>
<main>
{chr(10).join(part for part in body if part)}
</main>
<script>{SCRIPT % {"size": f"{options.body_pt:g}"}}</script>
</body>
</html>
"""

    # ------------------------------------------------------------------
    def _text(self, text: str, block: Optional[Block] = None, offset: int = 0) -> str:
        parts = []
        for segment, tags in styled_segments(text, block.styles if block else [], offset):
            escaped = html.escape(segment).replace(BLANK_TOKEN, '<span class="blank" aria-label="blank"></span>')
            escaped = escaped.replace("\n", "<br>")
            tag_map = {"b": "strong", "i": "em", "u": "u"}
            parts.append("".join(f"<{tag_map[t]}>" for t in tags) + escaped
                         + "".join(f"</{tag_map[t]}>" for t in reversed(tags)))
        return "".join(parts)

    def _dir(self, block: Block) -> str:
        return ' dir="rtl"' if block.text_direction == TextDirection.RTL else ""

    def _image(self, block: Block, alt: str) -> str:
        asset = block.image_asset
        url = _data_url(asset.file_path, asset.mime_type) if asset and asset.file_path else None
        if not url:
            return ""
        return f'<figure><img src="{url}" alt="{html.escape(alt)}"></figure>'

    def _notes(self, block: Block) -> str:
        out = []
        note = reader_note(block)
        if note:
            out.append(f'<p class="note">{html.escape(note)}</p>')
        if has_original_crop(block):
            out.append(self._image(block, f"The original lines from page {block.source_page}"))
        return "".join(out)

    def _block(self, block: Block) -> str:
        d = self._dir(block)
        if block.type == BlockType.PAGE_MARKER:
            if not self._options.include_page_markers or block.page_marker is None:
                return ""
            label = page_label(block.page_marker, self._pages.get(block.page_marker))
            return f'<p class="page" id="page-{block.page_marker}">{html.escape(label)}</p>'
        if block.type in (BlockType.TITLE, BlockType.HEADING):
            level = 1 if block.type == BlockType.TITLE else max(1, min(3, block.level or 2))
            return f"<h{level}{d}>{self._text(block.text or '', block)}</h{level}>"
        if block.type == BlockType.LIST:
            marker, rest = split_marker(block)
            classes = ["item"] + (["dialogue"] if block.role == "dialogue" else []) \
                + ([f"indent-{min(3, block.indent_level)}"] if block.indent_level else [])
            if marker:
                inner = (f'<span class="marker">{html.escape(marker)}</span>'
                         f'<span>{self._text(rest, block, len(block.text or "") - len(rest))}</span>')
            else:
                inner = f'<span></span><span>{self._text(block.text or "", block)}</span>'
            return f'<div class="{" ".join(classes)}"{d}>{inner}</div>{self._notes(block)}'
        if block.type == BlockType.CAPTION:
            label = caption_label(block)
            prefix = f'<span class="label">{html.escape(label)}</span>' if label else ""
            return f'<p class="caption"{d}>{prefix}{self._text(block.text or "", block)}</p>'
        if block.type == BlockType.QUOTE:
            return f"<blockquote{d}>{self._text(block.text or '', block)}</blockquote>"
        if block.type == BlockType.FOOTNOTE:
            return f'<p class="footnote" role="doc-footnote"{d}>{self._text(block.text or "", block)}</p>'
        if block.type == BlockType.ASIDE:
            cls = "note" if block.role == "page_note" else "aside"
            return f'<p class="{cls}"{d}>{self._text(block.text or "", block)}</p>'
        if block.type == BlockType.TABLE and block.table_structure:
            return self._table(block)
        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            alt = asset.alt_text or f"Picture from page {block.source_page}"
            note = reader_note(block) if is_retained_page(block) else None
            prefix = f'<p class="note">{html.escape(note)}</p>' if note else ""
            return prefix + self._image(block, alt)
        return f"<p{d}>{self._text(block.text or '', block)}</p>{self._notes(block)}"

    def _table(self, block: Block) -> str:
        table = block.table_structure
        d = self._dir(block)
        out = []
        fit = evaluate_table_fit(table, available_width=520, font_pt=14.0, min_readable_pt=14.0)
        for note in dict.fromkeys(n for n in (reader_note(block), fit.warning) if n):
            out.append(f'<p class="note">{html.escape(note)}</p>')
        if block.image_asset:
            out.append(self._image(block, block.image_asset.alt_text or f"Original table from page {block.source_page}"))
        if fit.tier == TableTier.LINEARIZE:
            if table.caption:
                out.append(f'<p class="caption"{d}>{self._text(table.caption)}</p>')
            for lead, details in table_as_entries(table):
                rows = "".join(
                    f'<p class="detail">{"<strong>" + html.escape(label) + ":</strong> " if label else ""}{self._text(value)}</p>'
                    for label, value in details)
                out.append(f'<div class="entry"{d}><p class="lead">{self._text(lead)}</p>{rows}</div>')
            return "".join(out)
        parts = fit.split_tables if fit.tier == TableTier.SPLIT and fit.split_tables else [table]
        for part in parts:
            out.append(self._grid(part, d))
        return "".join(out)

    def _grid(self, table, d: str) -> str:
        visible = {(r, c): (rs, cs) for r, c, _, rs, cs in iter_visible_cells(table)}
        rows_html = []
        for r, row in enumerate(table.rows):
            tag = "th" if r == 0 and table.has_header else "td"
            cells = []
            for c, cell in enumerate(row):
                if (r, c) not in visible:
                    continue
                rs, cs = visible[(r, c)]
                attrs = (' scope="col"' if tag == "th" else "") + (f' rowspan="{rs}"' if rs > 1 else "") \
                    + (f' colspan="{cs}"' if cs > 1 else "")
                cells.append(f"<{tag}{attrs}>{self._text(cell.text or '')}</{tag}>")
            rows_html.append(f"<tr>{''.join(cells)}</tr>")
        head = rows_html[0] if table.has_header and rows_html else ""
        body_rows = rows_html[1:] if head else rows_html
        caption = f"<caption>{self._text(table.caption)}</caption>" if table.caption else ""
        return (f"<table{d}>" + caption + (f"<thead>{head}</thead>" if head else "")
                + f"<tbody>{''.join(body_rows)}</tbody></table>")
