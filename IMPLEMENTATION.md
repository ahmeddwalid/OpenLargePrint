# Faithful conversion implementation ledger

Requirements: PDF-001..006, DOC-001..003, OCR-004..007, IMG-001..003,
TBL-001..002, FN-001..002, OUT-001..003/005..010, UI-002..005,
SEC-006..009, PERF-002, PKG-001..002.

Confirmed before implementation: source 0.5.0 versus local frozen sidecar
0.1.0; first four pages of b1/b2 and c1/c2 complete through both protocols.
Installed GUI stall not reproduced. No publicly trusted signing identity exists.

Ruling: work on codex/faithful-conversion-windows in the existing checkout;
the user explicitly authorized implementation, and the checkout is clean.
Keep dependencies and source documents unchanged. No publication authorized.

Acceptance remains blocked until installed GUI full-book testing and trusted
signing with Smart App Control enforced succeed.

Final verification: 213 Python tests passed, 3 LibreOffice tests skipped;
25 UI tests passed, production TypeScript/Vite build passed; frozen-engine
packaging smoke passed; Rust formatting and PowerShell syntax passed.
Rust tests/installer build blocked by enforced Application Control (OS error4551).
GUI c1/c2 reached306/306 then failed old-engine PDF export at source294;
new-source tall-table and actual page294 exports pass at20pt/28pt.
All-eight rebuilt-GUI/SAC acceptance remains open. Diagnostic all-eight
source run is intermediate revision and continues in a separate process.
See packaging/verification/REPORT.md for metrics, screenshots and blockers.
