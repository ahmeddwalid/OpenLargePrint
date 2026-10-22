# Choosing the recogniser

OpenLargePrint reads scanned pages with the PP-OCR models from PaddleOCR,
run through RapidOCR and ONNX Runtime: PP-OCRv6 for Latin script and the
PP-OCRv5 Arabic recogniser, with PP-DocLayoutV2 for page layout. This page
records how that choice was checked against the usual alternatives for
version 0.7.0.

## Benchmark

`scripts/bench_ocr.py` draws pages of Arabic and English legal text in four
typefaces per script (Noto Naskh Arabic, Noto Sans Arabic, Amiri, Tajawal;
Noto Serif, Noto Sans, Atkinson Hyperlegible, Andika), at 10, 12 and 14 pt,
200 and 300 dpi, clean and degraded (blur, noise, JPEG artefacts, a slight
skew). Arabic is shaped with HarfBuzz (Raqm). It scores the character error
rate of each whole page. Lower is better.

| Recogniser | Arabic clean | Arabic degraded | English clean | English degraded | s/page |
| --- | --- | --- | --- | --- | --- |
| PP-OCR (bundled) | 2.4% | 5.8% | 0.0% | 0.0% | 2.11 |
| Tesseract 5.3.4 | 3.9% | 6.7% | 0.0% | 0.0% | 1.16 |
| Tesseract 5.3.4 (tessdata_best) | 3.3% | 4.5% | 0.0% | 0.0% | 1.51 |

Times are on a four-core CPU. Most Arabic errors for both engines come from
Amiri, a calligraphic Naskh face with many stacked ligatures; on Noto Naskh
Arabic PP-OCR reads 0.4% of characters wrongly, clean or degraded.

## Decision

* **PaddleOCR**: kept. The app already runs PaddleOCR's own models; the full
  PaddlePaddle framework would add several hundred megabytes and gain nothing.
* **Tesseract**: not added. With its best models it is slightly better on
  degraded Arabic and worse on clean Arabic, and equal on English. That is not
  enough to justify shipping a second engine and its language data on every
  platform. The benchmark stays in the repository so the question can be
  asked again when either engine changes.
* **OCRmyPDF**: not used. It adds a hidden text layer to the original PDF; it
  does not rebuild the document in large print. The "searchable copy of the
  original" option already does that job, and OCRmyPDF would bring
  Ghostscript (AGPL) and Tesseract with it.
* **Docling**: not used. Its layout analysis does the same job as
  PP-DocLayoutV2, which the app already runs, but it needs PyTorch (one to two
  gigabytes) and has weaker Arabic support.

## What the benchmark found

Running the benchmark turned up three faults in 0.6.0, all fixed in 0.7.0:

* The Arabic recogniser needs `python-bidi`, which was not installed, so every
  Arabic page failed and was read with the Latin recogniser instead.
* The per-line orientation classifier turned some upright lines upside down
  before reading them, so about one line in five on a clean scan came out as
  letter salad. On a twelve-page English scan the error rate went from 20.6%
  to 0.1% once it was turned off. Pages scanned upside down are now detected
  as a whole instead.
* A page of Arabic read with the Latin recogniser could return one confident
  number and nothing else, which looked like a good reading. Readings are now
  compared by how much text they confidently hold.
