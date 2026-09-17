"""Semantic HTML Reader exporter with instant client-side restyling (OUT-002, A11Y-001..004)."""

from __future__ import annotations

import base64
import html
from pathlib import Path
from typing import Optional

from openlargeprint.ir.models import Block, BlockType, DocumentIR
from openlargeprint.security.isolation import log_safe_info
from .base import BaseExporter, ExportOptions


class ReaderExporter(BaseExporter):
    """Renders DocumentIR into an accessible, self-contained semantic HTML5 Reader."""

    def export(self, doc: DocumentIR, output_path: Path, options: Optional[ExportOptions] = None) -> Path:
        """Render DocumentIR into an interactive, accessible HTML reader file."""
        if options is None:
            options = ExportOptions()

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        log_safe_info(f"Generating Semantic HTML Reader -> {output_path.name}")

        html_content = self._build_reader_html(doc, options)
        output_path.write_text(html_content, encoding="utf-8")

        log_safe_info(f"Semantic HTML Reader saved: {output_path.name}")
        return output_path

    def _build_reader_html(self, doc: DocumentIR, options: ExportOptions) -> str:
        """Construct the complete standalone HTML document."""
        title = html.escape(doc.metadata.title or "OpenLargePrint Document")
        body_blocks_html = []
        toc_items_html = []

        for block in doc.blocks:
            b_html, toc_item = self._render_block(block, options)
            if b_html:
                body_blocks_html.append(b_html)
            if toc_item:
                toc_items_html.append(toc_item)

        content_html = "\n".join(body_blocks_html)
        toc_html = "\n".join(toc_items_html)

        return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} — OpenLargePrint Reader</title>
  <style>
    :root {{
      --base-font-size: {int(options.body_pt)}px;
      --line-height: {options.line_spacing};
      --reading-width: 85ch;
      --bg-color: #fcfbf9;
      --surface-color: #ffffff;
      --text-color: #1a1a1a;
      --heading-color: #0d0d0d;
      --muted-color: #666666;
      --border-color: #e0ded8;
      --focus-outline: #005fcc;
      --button-bg: #f0eee9;
      --button-hover: #e4e1d8;
    }}

    [data-theme="dark"] {{
      --bg-color: #121212;
      --surface-color: #1e1e1e;
      --text-color: #f4f4f4;
      --heading-color: #ffffff;
      --muted-color: #aaaaaa;
      --border-color: #333333;
      --focus-outline: #ffd700;
      --button-bg: #2a2a2a;
      --button-hover: #3a3a3a;
    }}

    [data-theme="sepia"] {{
      --bg-color: #f5efe3;
      --surface-color: #fcf8f0;
      --text-color: #2b221a;
      --heading-color: #1f1812;
      --muted-color: #736353;
      --border-color: #ded3bf;
      --focus-outline: #8c531b;
      --button-bg: #eadecd;
      --button-hover: #decbb4;
    }}

    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif;
      background-color: var(--bg-color);
      color: var(--text-color);
      line-height: var(--line-height);
      font-size: var(--base-font-size);
      transition: background-color 0.15s ease, color 0.15s ease;
    }}

    /* Accessible focus state (A11Y-003) */
    :focus-visible {{
      outline: 3px solid var(--focus-outline);
      outline-offset: 2px;
    }}

    /* Toolbar meeting A11Y-001 touch target standards (min 44px) */
    .reader-toolbar {{
      position: sticky;
      top: 0;
      z-index: 100;
      background-color: var(--surface-color);
      border-bottom: 2px solid var(--border-color);
      padding: 10px 20px;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }}

    .toolbar-group {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .toolbar-btn {{
      min-width: 44px;
      min-height: 44px;
      padding: 8px 14px;
      font-size: 16px;
      font-weight: 600;
      background-color: var(--button-bg);
      color: var(--text-color);
      border: 1px solid var(--border-color);
      border-radius: 6px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      user-select: none;
    }}

    .toolbar-btn:hover {{
      background-color: var(--button-hover);
    }}

    .size-indicator {{
      min-width: 44px;
      text-align: center;
      font-weight: bold;
      font-size: 16px;
    }}

    /* Layout structure */
    .reader-container {{
      display: flex;
      max-width: 1400px;
      margin: 0 auto;
      padding: 20px;
      gap: 30px;
    }}

    .reader-toc {{
      width: 280px;
      flex-shrink: 0;
      background-color: var(--surface-color);
      border: 1px solid var(--border-color);
      border-radius: 8px;
      padding: 16px;
      max-height: calc(100vh - 120px);
      position: sticky;
      top: 80px;
      overflow-y: auto;
    }}

    .reader-toc h2 {{
      font-size: 18px;
      margin-bottom: 12px;
      color: var(--heading-color);
    }}

    .reader-toc ul {{
      list-style: none;
    }}

    .reader-toc li {{
      margin-bottom: 8px;
    }}

    .reader-toc a {{
      color: var(--text-color);
      text-decoration: none;
      font-size: 15px;
      display: block;
      padding: 6px 8px;
      border-radius: 4px;
    }}

    .reader-toc a:hover {{
      background-color: var(--button-bg);
    }}

    .reader-main {{
      flex-grow: 1;
      max-width: var(--reading-width);
      margin: 0 auto;
    }}

    /* Content styling */
    h1, h2, h3, h4 {{
      color: var(--heading-color);
      margin-top: 1.4em;
      margin-bottom: 0.6em;
      line-height: 1.25;
    }}

    h1 {{ font-size: 1.6em; }}
    h2 {{ font-size: 1.35em; }}
    h3 {{ font-size: 1.15em; }}

    p {{
      margin-bottom: 0.8em;
    }}

    ul, ol {{
      margin-left: 1.6em;
      margin-bottom: 0.8em;
    }}

    li {{
      margin-bottom: 0.4em;
    }}

    blockquote {{
      border-left: 4px solid var(--border-color);
      padding-left: 16px;
      margin: 1em 0;
      font-style: italic;
      color: var(--muted-color);
    }}

    .page-marker {{
      margin: 2em 0 1.2em 0;
      padding: 8px 16px;
      background-color: var(--button-bg);
      border: 1px dashed var(--border-color);
      border-radius: 6px;
      text-align: center;
      font-size: 0.8em;
      font-weight: bold;
      color: var(--muted-color);
    }}

    .figure-container {{
      margin: 1.5em 0;
      text-align: center;
    }}

    .figure-container img {{
      max-width: 100%;
      height: auto;
      border-radius: 4px;
      border: 1px solid var(--border-color);
    }}

    .figure-caption {{
      font-size: 0.85em;
      font-style: italic;
      color: var(--muted-color);
      margin-top: 6px;
    }}

    .footnote-block {{
      font-size: 0.85em;
      font-style: italic;
      color: var(--muted-color);
      border-top: 1px solid var(--border-color);
      padding-top: 8px;
      margin-top: 1.5em;
    }}

    /* Print media styling */
    @media print {{
      .reader-toolbar, .reader-toc {{
        display: none !important;
      }}
      body {{
        background: white !important;
        color: black !important;
      }}
      .reader-main {{
        max-width: 100% !important;
      }}
    }}
  </style>
</head>
<body>
  <!-- Header with Accessible Controls (A11Y-001..004) -->
  <header class="reader-toolbar" role="banner">
    <div class="toolbar-group">
      <span style="font-weight: bold; font-size: 17px;">OpenLargePrint</span>
    </div>

    <!-- Font Size Controls (OUT-002) -->
    <div class="toolbar-group" aria-label="Text Size Adjustment">
      <button id="btn-size-dec" class="toolbar-btn" aria-label="Decrease Text Size" title="Smaller text (A-)">A−</button>
      <span id="current-size-label" class="size-indicator" aria-live="polite">{int(options.body_pt)}px</span>
      <button id="btn-size-inc" class="toolbar-btn" aria-label="Increase Text Size" title="Larger text (A+)">A+</button>
    </div>

    <!-- Line Spacing Controls (OUT-002) -->
    <div class="toolbar-group" aria-label="Line Spacing">
      <button id="btn-spacing-14" class="toolbar-btn" title="Line Spacing 1.4">1.4</button>
      <button id="btn-spacing-15" class="toolbar-btn" title="Line Spacing 1.5">1.5</button>
      <button id="btn-spacing-16" class="toolbar-btn" title="Line Spacing 1.6">1.6</button>
    </div>

    <!-- Theme Switcher (A11Y-004) -->
    <div class="toolbar-group" aria-label="Visual Theme">
      <button id="theme-light" class="toolbar-btn" title="Light Theme">Light</button>
      <button id="theme-sepia" class="toolbar-btn" title="Warm Sepia Theme">Sepia</button>
      <button id="theme-dark" class="toolbar-btn" title="High-Contrast Dark Theme">Dark</button>
    </div>

    <!-- Print / Export Action (OUT-010, OUT-011) -->
    <div class="toolbar-group" aria-label="Print and Export">
      <button id="btn-print" class="toolbar-btn" style="background-color: var(--text-color); color: var(--bg-color);" title="Print or Save Selection">Print / Export</button>
    </div>
  </header>

  <div class="reader-container">
    <!-- Table of Contents Sidebar -->
    <nav class="reader-toc" role="navigation" aria-label="Document Outline">
      <h2>Contents</h2>
      <ul>
        {toc_html}
      </ul>
    </nav>

    <!-- Reflowed Semantic Document Content -->
    <main class="reader-main" role="main">
      {content_html}
    </main>
  </div>

  <!-- Instant client-side re-styling script (OUT-002, zero network traffic SEC-009) -->
  <script>
    let currentSize = {int(options.body_pt)};
    const root = document.documentElement;
    const sizeLabel = document.getElementById("current-size-label");

    function setFontSize(newSize) {{
      if (newSize < 14) newSize = 14;
      if (newSize > 48) newSize = 48;
      currentSize = newSize;
      root.style.setProperty("--base-font-size", currentSize + "px");
      if (sizeLabel) sizeLabel.textContent = currentSize + "px";
    }}

    document.getElementById("btn-size-dec").addEventListener("click", () => setFontSize(currentSize - 2));
    document.getElementById("btn-size-inc").addEventListener("click", () => setFontSize(currentSize + 2));

    document.getElementById("btn-spacing-14").addEventListener("click", () => root.style.setProperty("--line-height", "1.4"));
    document.getElementById("btn-spacing-15").addEventListener("click", () => root.style.setProperty("--line-height", "1.5"));
    document.getElementById("btn-spacing-16").addEventListener("click", () => root.style.setProperty("--line-height", "1.6"));

    document.getElementById("theme-light").addEventListener("click", () => root.setAttribute("data-theme", "light"));
    document.getElementById("theme-sepia").addEventListener("click", () => root.setAttribute("data-theme", "sepia"));
    document.getElementById("theme-dark").addEventListener("click", () => root.setAttribute("data-theme", "dark"));

    document.getElementById("btn-print").addEventListener("click", () => window.print());
  </script>
</body>
</html>
"""

    def _render_block(self, block: Block, options: ExportOptions) -> tuple[Optional[str], Optional[str]]:
        """Render a single semantic block to HTML, returning (block_html, toc_item_html)."""
        # Page marker (OUT-005)
        if block.type == BlockType.PAGE_MARKER:
            if options.include_page_markers and block.page_marker is not None:
                anchor_id = f"orig-page-{block.page_marker}"
                b_html = f'<div class="page-marker" id="{anchor_id}">— Original Page {block.page_marker} —</div>'
                toc_html = f'<li><a href="#{anchor_id}">Page {block.page_marker}</a></li>'
                return b_html, toc_html
            return None, None

        # Headings
        if block.type in (BlockType.TITLE, BlockType.HEADING):
            level = block.level or 1
            tag = "h1" if block.type == BlockType.TITLE or level == 1 else (f"h{min(level, 4)}")
            heading_id = f"heading-{block.id}"
            safe_text = html.escape(block.text or "")
            b_html = f'<{tag} id="{heading_id}">{safe_text}</{tag}>'
            toc_html = f'<li><a href="#{heading_id}">{safe_text}</a></li>'
            return b_html, toc_html

        # Lists
        if block.type == BlockType.LIST:
            raw_text = (block.text or "").lstrip("•-* \t")
            safe_text = html.escape(raw_text)
            return f"<ul><li>{safe_text}</li></ul>", None

        # Quotes
        if block.type == BlockType.QUOTE:
            safe_text = html.escape(block.text or "")
            return f"<blockquote><p>{safe_text}</p></blockquote>", None

        # Footnotes / Captions
        if block.type in (BlockType.FOOTNOTE, BlockType.CAPTION):
            safe_text = html.escape(block.text or "")
            return f'<div class="footnote-block"><p>{safe_text}</p></div>', None

        # Images (IMG-001)
        if block.type == BlockType.IMAGE and block.image_asset:
            asset = block.image_asset
            if asset.file_path and Path(asset.file_path).exists():
                img_bytes = Path(asset.file_path).read_bytes()
                b64_src = f"data:{asset.mime_type};base64,{base64.b64encode(img_bytes).decode('ascii')}"
                alt = html.escape(asset.alt_text or f"Figure from page {block.source_page}")
                return f'<div class="figure-container"><img src="{b64_src}" alt="{alt}"></div>', None
            return None, None

        # Default body paragraph
        safe_text = html.escape(block.text or "")
        return f"<p>{safe_text}</p>", None
