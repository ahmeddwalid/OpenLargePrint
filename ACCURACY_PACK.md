# Optional offline English recognition pack

The standard CPU recognizer remains the default. An optional adapter uses RapidOCR
3.9.2 and PP-OCRv6 medium recognition with the existing verified detector and
orientation classifier. It preserves the recognizer's text and sends all output
through DocumentIR. It does not claim semantic layout or VLM support.

The model is 76,629,984 bytes, SHA-256
`eef444829dbbe18d7fea59a3f6eb75647518d2b3a9568d27c92e42940204894b`.
Code and weights separately use Apache-2.0. The immutable download is pinned in
`models/manifest.py`, and runtime/dependency artifacts are locked in `uv.lock`.
Sources: [pinned RapidOCR catalogue](https://github.com/RapidAI/RapidOCR/blob/095232a4c94f7f0e6600ba5bba1177010ad696d4/python/rapidocr/default_models.yaml),
[upstream model licence](https://huggingface.co/PaddlePaddle/PP-OCRv6_medium_rec).

## Developer preparation

Setup may use the network. Conversion does not invoke setup or download models.
This developer script is not an end-user installation flow; packaged acquisition
and enforced-SAC installer acceptance remain release work.

```powershell
uv sync --locked --dev --extra dev --extra accuracy --python 3.12
uv run --extra accuracy python packaging/prepare_accuracy_pack.py --directory packaging/build/accuracy-models
$env:OPENLARGEPRINT_MODEL_DIR = (Resolve-Path packaging/build/accuracy-models).Path
uv run --extra accuracy python packaging/verify_benchmark.py --accuracy
```

The desktop health response advertises available languages only after checking
the pinned runtime version and model digest. The advanced English accuracy option
stays disabled until the verified pack is available. Recognition validates model
digests and embedded decoder vocabulary again in its disposable worker. Worker
network connections/name resolution are blocked. The installer includes runtime
code/configuration when built with the accuracy extra; optional weights are excluded.

The CLI/library Maximum accuracy mode uses the optional English adapter when
available. Missing/invalid packs fall back to standard recognition with a review
warning. Native text is extracted directly in all recognition modes. Native text
only mode performs no recognition and keeps scanned pages for review.

## Measured limits

The rights-safe corpus completed all 16 executions in both modes. English scanned
table CER/WER improved from 0.049/0.500 to 0.012/0.167; the main English scan remained
0.031/0.333, while skewed scan CER/WER regressed from 0/0 to 0.045/0.667. Exact native
English and distinct-image pixels remained preserved. These small synthetic
samples do not establish general superiority, so the default remains unchanged.
See the separate baseline and optional-pack reports under `packaging/verification`.
Timings include initialization and concurrent load; child RAM/VRAM are unmeasured.

The pinned Arabic-v5 model is a **disabled research candidate**. Actual inference
under the proposed no-display-reordering configuration emitted reversed visual
Arabic at high confidence. Mixed-direction logical-text acceptance has not passed.
It is not advertised or selected for conversion, and no heuristic reversal was
added. Arabic/mixed-script quality remains open. Layout candidates also remain
unimplemented; recognition alone does not resolve every structural ambiguity.
