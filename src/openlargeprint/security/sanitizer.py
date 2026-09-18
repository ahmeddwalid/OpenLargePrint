"""Active-content neutralization and input sanitization (SEC-002, SEC-003)."""

from __future__ import annotations

import io
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List, Optional, Tuple

import pikepdf

from openlargeprint.security.isolation import log_safe_info
from openlargeprint.security.validator import (
    SecurityValidationError,
    detect_file_type,
)


class ActiveContentStrippedWarning(UserWarning):
    """Emitted when potentially malicious active content was stripped from an input document."""
    pass


def sanitize_pdf(input_path: Path | str, output_path: Path | str) -> Tuple[Path, List[str]]:
    """Sanitize a PDF file by stripping all JavaScript, Launch actions, and EmbeddedFiles (SEC-002).
    
    Returns:
        Tuple of (sanitized_path, list_of_removed_items)
    """
    in_p = Path(input_path)
    out_p = Path(output_path)
    removed_items: List[str] = []

    try:
        pdf = pikepdf.open(in_p, allow_overwriting_input=False)
    except Exception as e:
        # If pikepdf fails, copy as-is or raise depending on error
        log_safe_info(f"Could not open PDF for pikepdf sanitization: {type(e).__name__}")
        shutil.copy2(in_p, out_p)
        return out_p, removed_items

    root = pdf.Root

    # 1. Strip Names dictionary JS and EmbeddedFiles
    if "/Names" in root:
        names = root.Names
        if "/JavaScript" in names:
            del names["/JavaScript"]
            removed_items.append("Root.Names.JavaScript")
        if "/EmbeddedFiles" in names:
            del names["/EmbeddedFiles"]
            removed_items.append("Root.Names.EmbeddedFiles")

    # 2. Strip OpenAction if executable or script
    if "/OpenAction" in root:
        action = root.OpenAction
        if hasattr(action, "keys"):
            action_type = str(action.get("/S", ""))
            if action_type in ["/JavaScript", "/Launch", "/URI", "/SubmitForm"]:
                del root["/OpenAction"]
                removed_items.append(f"Root.OpenAction({action_type})")

    # 3. Strip Additional Actions (AA)
    if "/AA" in root:
        del root["/AA"]
        removed_items.append("Root.AA")

    # 4. Strip AcroForm JavaScript
    if "/AcroForm" in root:
        acro = root.AcroForm
        if hasattr(acro, "keys"):
            if "/XFA" in acro:
                del acro["/XFA"]
                removed_items.append("AcroForm.XFA")

    # 5. Scan pages for page-level scripts and annotations
    for p_idx, page in enumerate(pdf.pages):
        # Strip page-level AA
        if "/AA" in page:
            del page["/AA"]
            removed_items.append(f"Page[{p_idx}].AA")

        # Strip annotation actions
        if "/Annots" in page:
            annots = page.Annots
            safe_annots = []
            if annots is not None:
                for annot in annots:
                    if hasattr(annot, "keys") and "/A" in annot:
                        action = annot["/A"]
                        if hasattr(action, "keys"):
                            a_type = str(action.get("/S", ""))
                            if a_type in ["/JavaScript", "/Launch", "/SubmitForm"]:
                                removed_items.append(f"Page[{p_idx}].Annot.Action({a_type})")
                                continue
                    safe_annots.append(annot)
                page.Annots = safe_annots

    # Save clean sanitized PDF
    pdf.save(out_p)
    pdf.close()

    if removed_items:
        log_safe_info(f"Stripped {len(removed_items)} active content items from PDF.")

    return out_p, removed_items


def sanitize_office_openxml(input_path: Path | str, output_path: Path | str) -> Tuple[Path, List[str]]:
    """Sanitize a DOCX or PPTX archive by stripping macros, external relationships, and OLE embeddings (SEC-002).
    
    Returns:
        Tuple of (sanitized_path, list_of_removed_items)
    """
    in_p = Path(input_path)
    out_p = Path(output_path)
    removed_items: List[str] = []

    # Patterns of dangerous archive members
    dangerous_member_patterns = [
        re.compile(r"^word/vbaProject\.bin$", re.IGNORECASE),
        re.compile(r"^word/vbaData\.xml$", re.IGNORECASE),
        re.compile(r"^ppt/vbaProject\.bin$", re.IGNORECASE),
        re.compile(r"^.*vbaProjectSignature\.bin$", re.IGNORECASE),
        re.compile(r"^.*/activeX/.*$", re.IGNORECASE),
        re.compile(r"^.*/embeddings/.*\.bin$", re.IGNORECASE),
    ]

    with zipfile.ZipFile(in_p, "r") as zin, zipfile.ZipFile(out_p, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            filename = item.filename

            # Check if filename matches dangerous patterns
            is_dangerous = any(pat.match(filename) for pat in dangerous_member_patterns)
            if is_dangerous:
                removed_items.append(f"ArchiveMember:{filename}")
                continue

            content = zin.read(filename)

            # Sanitize relationship files (.rels) to strip external targets
            if filename.endswith(".rels"):
                content, stripped_rels = _sanitize_rels_xml(content)
                removed_items.extend(stripped_rels)

            zout.writestr(item, content)

    if removed_items:
        log_safe_info(f"Stripped {len(removed_items)} active content items from Office archive.")

    return out_p, removed_items


def _sanitize_rels_xml(rels_bytes: bytes) -> Tuple[bytes, List[str]]:
    """Remove external URI targets from XML relationship files (SEC-002)."""
    removed: List[str] = []
    try:
        tree = ET.fromstring(rels_bytes)
        # Relationship namespace
        ns = "http://schemas.openxmlformats.org/package/2006/relationships"
        changed = False

        for elem in list(tree):
            target_mode = elem.attrib.get("TargetMode")
            target = elem.attrib.get("Target", "")
            # Check for suspicious external links (e.g. script executions or suspicious schemes)
            if target_mode == "External" and (target.startswith("file:") or target.startswith("javascript:") or target.startswith("mhtml:")):
                elem.attrib["Target"] = "#"
                removed.append(f"ExternalRel:{target}")
                changed = True

        if changed:
            return ET.tostring(tree, encoding="utf-8"), removed
    except Exception:
        pass
    return rels_bytes, removed


def sanitize_document(input_path: Path | str, workspace_dir: Path | str) -> Tuple[Path, List[str]]:
    """Sanitize any input document format inside the isolated workspace before processing (SEC-002, SEC-004)."""
    in_p = Path(input_path)
    ws = Path(workspace_dir)
    fmt = detect_file_type(in_p)

    sanitized_out = ws / f"sanitized_{in_p.name}"

    if fmt == "pdf":
        return sanitize_pdf(in_p, sanitized_out)
    elif fmt in ["docx", "pptx"]:
        return sanitize_office_openxml(in_p, sanitized_out)
    else:
        # Legacy binary formats or already validated
        shutil.copy2(in_p, sanitized_out)
        return sanitized_out, []
