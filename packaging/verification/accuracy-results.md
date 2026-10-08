# Source benchmark results

Optional English PP-OCRv6 mode. Arabic still falls back with review warnings.

| Case Name | Format | Pages | CER | WER | Order reference | Table reference | Image pixels | Order heuristic | Table heuristic | Images | Anchors | Speed (s/p) | Process peak RAM (MB) | VRAM (MB) | Execution |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| born_digital_english | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.04 | 92.8 | N/A | PASS |
| two_column_law | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 0.67 | 1.00 | 1.00 | 1.00 | 0.03 | 92.8 | N/A | PASS |
| legal_footnotes | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.03 | 92.8 | N/A | PASS |
| scanned_english | docx | 1 | 0.031 | 0.333 | 0.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 3.33 | 161.4 | N/A | PASS |
| arabic_scan | docx | 1 | 0.887 | 1.000 | 0.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.61 | 168.6 | N/A | PASS |
| mixed_bidi | docx | 1 | 0.630 | 0.647 | 0.33 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 3.21 | 172.4 | N/A | PASS |
| scanned_table | docx | 1 | 0.012 | 0.167 | 0.67 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 3.17 | 172.4 | N/A | PASS |
| images_captions | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.04 | 172.4 | N/A | PASS |
| rotated_page | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.94 | 172.4 | N/A | PASS |
| skewed_page | docx | 1 | 0.045 | 0.667 | 0.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.87 | 172.4 | N/A | PASS |
| low_res_scan | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.82 | 172.4 | N/A | PASS |
| mixed_digital_scan | docx | 2 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 1.47 | 172.4 | N/A | PASS |
| page_numbering | docx | 2 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.02 | 172.4 | N/A | PASS |
| malformed_pdf | pdf | 1 | N/A | N/A | N/A | N/A | N/A | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 172.4 | N/A | PASS |
| docx_sample | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.05 | 172.4 | N/A | PASS |
| pptx_sample | docx | 1 | 0.138 | 0.143 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.05 | 172.4 | N/A | PASS |

PASS means conversion completed or malformed input was rejected safely. It is not a fidelity acceptance result. N/A means unmeasured. Reference columns compare authored order/cells/original image pixels; separate order/table columns are heuristics; RAM excludes child processes and records the lifetime process peak.
