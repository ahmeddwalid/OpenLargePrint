# Final automated checks

- .venv/Scripts/python.exe -m pytest tests/ -q: 213 passed, 3 skipped in198.03s.
- npm --prefix ui test -- --run: six files,25 tests passed.
- npm --prefix ui run build: TypeScript/Vite production build passed.
- packaging/verify_packaging.py: frozen native/scanned multi-page, A4/A3,
  PDF/DOCX, selected pages, health/version, icons/frontend smoke passed.
- packaging/sidecar_freshness.py: final frozen sidecar is fresh.
- cargo fmt --manifest-path src-tauri/Cargo.toml --check: passed.
- PowerShell AST parse of development/build/signature/installed checks: passed.
- cargo test / development installer: blocked by Application Control OS4551.
- No trusted signing identity, installed acceptance, or public installer available.

Full-book source diagnostic is still running on an intermediate revision. It is
not included in these final-revision automated results. No full rebuilt-GUI
acceptance or physical printing claim is made.
