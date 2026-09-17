# OpenLargePrint — CLAUDE.md

This file is intentionally short. It does not restate the product spec or the architecture — it points to where those live, and states the invariants that must never be violated while Claude is writing or modifying code in this repository.

## Source of truth, in this order

1. **`SPEC.md`** — what the product must do. Requirement IDs (`PDF-002`, `OCR-006`, `A11Y-003`, `SEC-009`, etc.) are the vocabulary for discussing correctness.
2. **`DESIGN.md`** — how the system is structured (`DocumentIR`, the classification pipeline, the OCR engine abstraction, the Tauri/sidecar boundary).
3. **`AGENTS.md`** — how any agent, including Claude, is expected to work here: testing requirements, dependency/licensing policy, security and accessibility checklists, and the anti-pattern list.

If Claude is ever unsure whether a plan is consistent with the project, check these three files before writing code — don't infer intent from a single function or file in isolation.

## Invariants Claude must never violate while coding here

- **Never OCR text that already has a usable native extraction.** Check the page classification result first.
- **Never route recognized OCR text through a generative model to "clean it up."** Uncertainty stays visible and traceable, especially for legal text.
- **Never let an importer or exporter bypass `DocumentIR`.** Every format goes in and out through the shared model — no special-cased shortcuts, even for "just this one format."
- **Never drop a page or section on failure.** Flag it, preserve the original, keep the rest of the document intact.
- **Never lose a block's source-page/bounding-box reference.** Provenance is a core feature, not metadata to trim if convenient.
- **Never expose a general shell or unrestricted filesystem bridge to the webview.** Tauri commands stay narrow and typed.
- **Never add a default-path network call.** A standard offline conversion must produce zero network traffic.
- **Never shrink primary controls or hide the three-step main flow to fit more options on screen.** Advanced settings belong behind "More options," not on the home screen.
- **Never mark a platform "supported" on framework capability alone.** It needs the full packaged pipeline validated against the benchmark corpus on that platform.
- **Never add a dependency (code or model weights) without checking its license and recording it**, even if it benchmarks well.
- **Never let PDF handling quality slip in favor of DOCX/PPTX polish.** PDF is the explicit, highest-priority input format — it's what the target reader's books actually arrive as.
- **Never call a screen finished without running it against the anti-slop checklist in `AGENTS.md §7`.** The test that matters: would a screenshot read as AI-generated to someone who's seen a lot of AI-built interfaces?
- **Never treat paper size as an afterthought.** A4 is the default for every export; A3 is a first-class option for the whole book or for just a page/section selection, not a hidden setting.

## Working style for this repo

- State which `SPEC.md` requirement ID(s) a change addresses before diving into implementation, so the change is checkable against the contract rather than against vibes.
- When a task seems to require bending one of the invariants above, stop and say so explicitly rather than finding a clever workaround — these exist because a wrong shortcut here has real consequences for someone who depends on the output being trustworthy (accuracy of a law text) or usable (accessibility of the interface).
- Prefer the smallest change that satisfies a requirement ID cleanly over a broader refactor, unless `DESIGN.md` is itself out of date and needs updating as part of the change.
- If you update a structural decision (schema, IPC protocol, engine routing, security boundary), update `DESIGN.md` in the same change — don't let the document and the code diverge.
