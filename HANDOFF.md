# OpenLargePrint — Handoff Notes

Status: **complete and committed** on branch `main`, pushed to GitHub. This file summarizes
the reliability/output-fidelity passes so the next agent can continue without re-deriving context.

Full plan: `~/.commandcode/plans/openlargeprint-reliability-fix-plan.md`.

Precedence reminder (AGENTS.md): `SPEC.md` defines what must be true, `DESIGN.md` how it is built.
Nothing here overrides those.

---

## Goal of this pass

Make conversions reliable and produce genuinely readable large-print output that (a) retains
images, (b) retains layout, and (c) honors the configured text size — without ever dropping a
page (SPEC §2). Scope agreed with the requester: full stack, implement documented-but-missing
features, cross-platform correctness, verify with pytest + UI tests.

---

## Completed and verified

Python engine test suite: **132 passed** (`uv run python -m pytest tests/ -q`).

### Image retention (IMG-001/002/003, DOC-002, SEC-004)
- `src/openlargeprint/security/assets.py` (new): `JobAssetStore` — persistent per-job media dir
  under a platform cache root (`OPENLARGEPRINT_CACHE_DIR`, default `~/.cache/openlargeprint`
  / macOS caches / `%LOCALAPPDATA%`), plus `prune()`.
- `src/openlargeprint/security/isolation.py`: `JobWorkspace` accepts an optional `asset_store`;
  scratch stays disposable, extracted media now persists.
- `src/openlargeprint/pipeline/orchestrator.py`: `convert(..., asset_store=...)`; `ConversionResult.asset_root`.
- `src/openlargeprint/sidecar/runner.py`: builds a store per job id, prunes, passes it through.
- `src/openlargeprint/ir/serialization.py`: `document_to_ui_dict()` embeds base64 `data_url`s
  for IMAGE/TABLE assets so the Tauri webview can render them (CSP `data:`; no new FS bridge — SEC-005).
- `src/openlargeprint/importers/pdf/images.py`: recursive `get_images()`, warns instead of
  silently dropping, reports SEC-003 bound failures.
- `src/openlargeprint/importers/pdf/native.py`: IMAGE+FORM bounds pairing, page-filling-raster
  filter raised to 0.90 and no longer silent, image warnings attached to page blocks.
- `src/openlargeprint/importers/pdf/vector_figures.py` (new): IMG-002 region-render fallback for
  vector artwork with no embedded raster. Note: pypdfium2 `render(crop=...)` takes **edge margins**
  (left, bottom, right, top), not absolute coordinates.
- `src/openlargeprint/importers/pdf/scanned.py`: retained table crop written to the job assets dir,
  not `tempfile.gettempdir()`.
- `src/openlargeprint/importers/office/{docx,pptx}.py`: unreadable/oversized images now produce
  document warnings instead of silent drops.
- UI: `ui/src/types.ts` (`ImageAsset`), `ui/src/api/sidecarClient.ts` (backend→UI block-type map,
  `level`→`heading_level`, `image_asset` mapping), `ui/src/components/ReaderView.tsx` (renders
  figure/footnote/caption/quote/list_item/page_marker).

### Configured text size (OUT-001/002/006/009, LANG-001/002)
- `src/openlargeprint/exporters/reader.py`: base size in **pt** (was px), resolved font stack,
  reading-width control; print CSS uses `--print-font-size`.
- `src/openlargeprint/exporters/fonts.py` (new): cross-platform font resolution (host font dirs →
  ReportLab TTFs) + CSS stack; Arabic font lookup now covers Windows/macOS (was Linux-only).
- `src/openlargeprint/exporters/pdf.py`: uses resolved faces; `_ensure_arabic_font` moved to `fonts.py`.
- Custom size wired: `cli.py --body-pt/--line-spacing`, `sidecar/protocol.py` +
  `sidecar/runner.py`, `src-tauri/src/main.rs`, `ui` (`TextSizeSelector` custom card, `ConversionSettings.customBodyPt`).
- UI Reader: pt units, reading-width select, print size variable.

### Layout fidelity (TBL-001, OUT-003/009)
- `pdf.py`: bullet `&nbsp;` double-escape fixed (numeric entities); image height clamped
  (`usable_height * 0.92` — the ReportLab frame is smaller than `doc_template.height`);
  monochrome footnote divider + retained table image.
- `docx.py`: `cantSplit` only on the header row; image fit by width **and** height; monochrome
  table shading/borders/warning colour; retained table image monochrome.

### Searchable PDF (OUT-004)
- `src/openlargeprint/exporters/searchable_pdf.py` (new) + wired through `exporters/__init__.py`,
  orchestrator (`export_format="searchable_pdf"`), Rust extension mapping, UI format option.
  Uses existing OCR only for pages without a native text layer. Invisible text via
  `textobject.setTextRenderMode(3)` (canvas has no `setTextRenderMode`).

### Cross-platform + safety
- `src-tauri/src/main.rs`: platform sidecar binary names, `user_home()` for paths, `xdg-open`/`open`
  for open/reveal, collision-resistant `uuid_short`, custom-size pass-through, `automatic` routing default.
- `src/openlargeprint/security/sanitizer.py`: refuses to hand back an unsanitized PDF when pikepdf
  cannot open it (SEC-002); `.rels` byte-level external-target fallback.
- `src/openlargeprint/qa/benchmark.py`: real reading-order/anchor/table metrics (no self-comparison);
  tempdir instead of `/tmp`.

### Tests added
- `tests/test_output_fidelity.py` (new, 11 tests): image persistence + `data_url`, IMG-002 vector
  figures, no false-positive figures on text pages, custom size in DOCX, Reader pt/width control,
  PDF bullet rendering, tall-image clamping, `cantSplit` count, searchable PDF,
  searchable-PDF-rejects-non-PDF.
- `ui/src/__tests__/ReaderView.test.tsx`: figure/footnote/page-marker/list rendering + reading width.

---

## Second pass (by another agent — reviewed and integrated)

A subsequent agent extended this work. Verified present in the tree:

- `DESIGN.md` / `README.md`: claims downgraded to match reality (installed recognizer is RapidOCR
  1.4.4, PP-OCRv4; no verified Arabic OCR; "maximum accuracy" is a warned standard-recognition
  fallback, not VLM; layout/table are heuristics). See DESIGN §4.1, §8.2, §11.1.
- `pyproject.toml` / `uv.lock`: Python constrained to `>=3.11,<3.13`, `rapidocr-onnxruntime==1.4.4`.
- Atomic export writes + input-overwrite rejection + real page-range validation (DESIGN §8.2).
- `security/validator.py`: `bounded_pdf_scale()` bounds raster allocation; used by
  `scanned.py`, `native.py`, `vector_figures.py`, `searchable_pdf.py`.
- `ocr/router.py` + `ocr/vlm_engine.py`: honest maximum-accuracy fallback that attaches a
  "needs review" warning.
- `qa/metrics.py` / `qa/corpus_builder.py`: missing references report as unavailable, not zero error.
- `packaging/*`, `.github/workflows/*`, `sbom.json`, `models/manifest.py`: pinning/SBOM/CI updates.
- Extra tests in `tests/test_security_hardening.py`, `test_pdf_exporter.py`,
  `test_ocr_engine.py`, `test_page_range_slicing.py`, `test_sidecar_protocol.py`,
  and `tests/test_output_fidelity.py`.

## Final state (all work committed)

A third pass completed the review flow, hardened the update system, and redesigned the interface:

- **Review flow** (`UI-004`, `UI-005`, `OUT-002`): flagged sections are reviewed per block; the
  original page is shown as a bounded preview image; retry shows the repeated recognition result
  for comparison; corrections typed in review are applied on export via `text_edits`.
- **Update hardening** (`SEC-006`, `SEC-009`): checks are opt-in (no network before opt-in);
  downloads are restricted to the OpenLargePrint GitHub release repository and require a valid
  SHA-256 digest, verified in-process with the `sha2` crate.
- **Interface redesign** (`VIS-001..004`, `A11Y-001..005`, `UI-001`): rem-based type scale on
  bundled Source Sans 3 and Noto Sans Arabic (OFL, recorded in `sbom.json`); olive accent on warm
  sepia; flat option strips; export location behind a "Save location" disclosure; 48px targets;
  reduced-motion and forced-colors media queries. `ui/audit.*` regenerate VIS screenshots.
- **Linux dialogs** (`PKG-001`, `SEC-005`): open/save dialogs via `tauri-plugin-dialog`.
- **Demo fallbacks removed** (`UI-005`): the sidecar client reports a plain-language error when the
  desktop bridge is unavailable instead of synthesizing a mock conversion.

Verified on this machine: 148 pytest passed, 12 vitest passed, `tsc --noEmit` clean, `cargo check`
clean, `cargo test` clean, production `npm run build` succeeds with the fonts in `ui/dist/fonts/`.

## Still open (release blockers, unchanged)

- Optional higher-accuracy OCR pack and verified Arabic scan recognition (`OCR-002..003`, `LANG-002`).
- `BenchmarkCase.expected_*` fields still unused (metrics are real, but not compared against
  per-case expectations).
- Packaged Windows CPU/GPU corpus runs, Linux desktop tests, screen-reader checks, physical printing
  at 100% scale, and target-machine RAM/VRAM measurement (`PKG-001`, `PERF-002`, `QA-001`).

---

## Environment gotchas (this machine)

- The shell exports `NODE_ENV=production`, which breaks vitest/React `act`. Use `NODE_ENV=test`.
- npm is globally configured with `omit=dev` — install UI deps with `npm install --include=dev`.
- Python deps: `uv sync --extra dev --all-groups`; run tests with `uv run python -m pytest`
  (plain `uv run pytest` resolves to a system pytest missing the venv packages).

## Verification commands

```bash
uv run python -m pytest tests/ -q
cd ui && NODE_ENV=test npx vitest run
cd ui && npx tsc --noEmit
cd src-tauri && cargo check
```

## Commit history

All three passes are committed to `main` and pushed to GitHub. Commit messages follow the
existing `type(scope): summary (REQ-IDs)` style seen in `git log`; the final commits are the UI
redesign, the review/update hardening, and the documentation sync.
