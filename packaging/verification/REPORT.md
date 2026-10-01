# Verification report: faithful conversion and Windows releases

Status: implementation changes prepared; release acceptance remains blocked.
Branch: codex/faithful-conversion-windows. Source version: 0.5.0.
No dependencies/model weights added; SBOM unchanged.

## Demonstrated GUI failure

The pre-existing desktop executable and adjacent engine are 0.1.0. No installed
registry entry was found; the existing release executable was used. The c1/c2
306-page input reached 306/306, then failed during final export. The retained
source-table image on source page 294 was 481.89 x 718.09pt, versus a frame of
469.89 x 716.50pt, on output page 1640. This demonstrates a final-export failure;
a second-page stall was not reproduced in that run. Elapsed time and engine peak
memory for this GUI run were not measured. Content-free telemetry is in
[gui-reproduction.json](gui-reproduction.json).

The new source uses frame-padding-aware image bounds, constrains both dimensions,
and has a real-output regression for a tall retained table at 20pt/28pt. The real
source page 294 exports at both sizes too. Its rendered output was inspected;
inferred-table and OCR fidelity still require review. A source-engine page test
is not a full-document rebuilt-GUI comparison.

## Implementation and requirement coverage

- PDF-001..006, DOC-001..003, OCR-004..007: source-character ownership, no default
  spelling/letter-spacing/hyphen/bullet/margin rewriting, column/section ordering,
  mixed-page reconciliation, blank-page anchors, exact OCR text preservation,
  failed/uncertain page imagery, optional evidence failures retain extracted text.
- IMG-001..003, TBL-001..002: decoded-content image matching, scanned figure crops,
  retained covers/artwork, consistent native/scanned table geometry, uncertainty
  warnings/source crops, shared merged-cell traversal and repeated PDF headers.
- FN-001..002, OUT-001..003/005..010: readable warnings, heading/caption association,
  frame-safe images, table row splitting, shared IR exports and re-export/selection.
- UI-002..005, PERF-002, SEC-007..009: elapsed progress heartbeats through export,
  terminal-event ordering, worker timeout/cancel/crash/restart regressions,
  content-free diagnostics, offline conversion checks.
- PKG-001..002, SEC-006: source/dependency sidecar fingerprints, real startup health
  and version checks, mandatory trusted public signing, native payload/NSIS
  uninstaller signing wiring, installed signature verification and exact-artifact
  enforced-SAC publication gate. Installed acceptance is open.

## Automated and visual evidence

Final command results are recorded in the accompanying handoff ledger. The full
Python suite includes malformed/security, schema, worker recovery, native and
scanned samples, actual PDF/DOCX/Reader output, A4/A3 and selected-page checks.
Three LibreOffice-dependent tests are skipped because LibreOffice is unavailable.
Frontend: 25 tests across six files passed; TypeScript/Vite production build passed.
Rust formatting passes. Rust compilation/tests and installer creation are blocked
by Application Control, described below. PowerShell packaging scripts parse.

The frozen sidecar smoke test performs native + second-page OCR, actual A4/A3 PDF
and DOCX exports, selected-page exports, exact health/version, icons and UI assets.
No newly frozen binary is labelled as a signed public distribution.

Progress-screen QA used the actual React component in Edge through bundled
Playwright: keyboard focus and Enter cancellation, minimum 44px cancel target,
200% text scale, narrow viewport, high contrast, reduced motion, no horizontal
overflow and no page errors. The visual craft checklist was reviewed for the
changed progress screen; existing typography, restrained surfaces and controls
were preserved. Evidence:

![Progress at 200% text scale](screenshots/progress-200-percent.png)

[Normal](screenshots/progress-normal.png),
[high contrast](screenshots/progress-high-contrast.png),
[machine-readable UI checks](screenshots/progress-check.json).

## Benchmark fidelity, speed and memory

[Per-case metrics](benchmark-results.md) list all 16 synthetic cases separately.
Execution PASS means completed conversion or safe rejection, not fidelity acceptance.
Native English CER/WER is 0. English scan CER/WER is 0.031/0.333; Arabic scan
0.938/1.000; scanned table 0.488/1.750. Arabic/table fidelity is not release quality.
Skewed/low-resolution scan character metrics are zero for these synthetic samples.
The mixed digital/scan image metric remains 0 and is open for investigation.
Reading-order/table values are heuristics, not ground-truth accuracy. Missing
CER/WER is N/A. VRAM and child-process peak RAM are unmeasured; process RAM is a
lifetime parent-process peak. Speed was measured under concurrent test load and
must not be treated as an isolated performance comparison.

## Full-book diagnostic run

The source-engine run started on an intermediate revision and is **not final
acceptance evidence**. Completed diagnostics: a1/a2 318/318 with all anchors,
1,117 output pages at 20pt / 1,846 at 28pt; b1/b2 394/394 with all anchors,
2,532 / 3,880 output pages. Both selected A3 exports have six pages and embedded
paper dimensions were checked. Extraction/export timings: 1,272.94s and 232.22s;
end-to-end including re-export: 1,282.11s and 338.02s. Parent lifetime peaks:
310.5MB and 807.7MB respectively; child RAM/VRAM unmeasured.

The longer all-eight source diagnostic continues separately and writes
packaging/verification/books/results.json after each completed book. These private
book outputs are ignored by Git. Unfinished books, final-revision all-eight GUI
conversions, representative full-book visual acceptance, and physical 100%-scale
printing are not claimed complete. Source documents were left unchanged.

## Windows release blockers

The corrected development installer configuration reaches Rust compilation, where
Windows Application Control blocks build-script executables and procedural-macro
DLLs (OS error 4551). Code Integrity events identify the blocked compiler artifacts.
Examples include rfd's build-script-build and zerovec_derive DLL. Fresh Rust tests
are blocked too. No security policy was changed. The complete VS2019 BuildTools
installation works; an incomplete VS2022 installation is skipped.

No trusted signing identity is available. Consequently no rebuilt installer,
installed uninstall.exe verification, enforced-SAC launch/OCR/update/removal, or
full rebuilt-GUI corpus acceptance is delivered. The release workflow fails closed
until exact signed-artifact acceptance is supplied in a protected environment.
See [SIGNING.md](../../SIGNING.md) for provisioning, installed checks and the
acceptance manifest contract. A suitable build host and trusted signing access
are prerequisites, followed by the full enforced-mode acceptance run.

No principle-level conflict was resolved by relaxing preservation or security.
OCR uncertainty and missing acceptance remain explicit limitations.
