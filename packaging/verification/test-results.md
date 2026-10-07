# Final automated checks

- .venv/Scripts/python.exe -m pytest tests/ -q: 250 passed, 3 skipped in 118.21s with the locally verified optional English pack, after routing, native-only evidence retention, model-safety, real health and reference-metric fixes. The subsequent packaging-hook regression reproduced stale reuse and then passed with all three freshness tests; the full suite predates that isolated fingerprint change.
- npm --prefix ui test -- --run: seven files, 33 tests passed.
- npm --prefix ui run build: TypeScript/Vite production build passed.
- packaging/verify_packaging.py: frozen native/scanned multi-page, A4/A3,
  PDF/DOCX, selected pages, health/version, icons/frontend smoke passed.
- packaging/sidecar_freshness.py: final rebuilt sidecar source/binary fingerprint verified; packaging hooks participate in invalidation.
- packaging/verify_accuracy_runtime.py: frozen verified capability, exact native text, spawned second-page English recognition, PDF export and optional-profile provenance passed.
- Advanced screen: keyboard/visible focus, 48px control, 200% text, narrow viewport, high contrast/reduced motion and RTL passed.
- packaging/verify_benchmark.py: 16 execution passes, zero expectation mismatches; baseline and optional-English per-metric JSON and Markdown persisted; table sample improves but skewed sample regresses, so the default remains unchanged. Fidelity acceptance remains separate.
- cargo fmt --manifest-path src-tauri/Cargo.toml --check: passed.
- PowerShell AST parse of development/build/signature/installed checks: passed.
- cargo test / development installer: blocked by Application Control OS4551.
- No trusted signing identity, installed acceptance, or public installer available.

All eight full-book source diagnostics completed on an intermediate revision. They are
not included in these final-revision automated results. No full rebuilt-GUI
acceptance or physical printing claim is made.
