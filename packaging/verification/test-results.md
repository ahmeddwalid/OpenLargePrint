# Final automated checks

- .venv/Scripts/python.exe -m pytest tests/ -q: 236 passed, 3 skipped in119.62s after routing, native-Arabic preservation, model-safety and reference-metric fixes.
- npm --prefix ui test -- --run: six files,25 tests passed.
- npm --prefix ui run build: TypeScript/Vite production build passed.
- packaging/verify_packaging.py: frozen native/scanned multi-page, A4/A3,
  PDF/DOCX, selected pages, health/version, icons/frontend smoke passed.
- packaging/sidecar_freshness.py: previous frozen sidecar verified fresh before the latest source changes; requires rebuilding for this revision.
- packaging/verify_benchmark.py: 16 execution passes, zero expectation mismatches; per-metric JSON and Markdown persisted. Fidelity acceptance remains separate.
- cargo fmt --manifest-path src-tauri/Cargo.toml --check: passed.
- PowerShell AST parse of development/build/signature/installed checks: passed.
- cargo test / development installer: blocked by Application Control OS4551.
- No trusted signing identity, installed acceptance, or public installer available.

All eight full-book source diagnostics completed on an intermediate revision. They are
not included in these final-revision automated results. No full rebuilt-GUI
acceptance or physical printing claim is made.
