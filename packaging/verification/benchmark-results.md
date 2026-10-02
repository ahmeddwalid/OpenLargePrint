# Source benchmark results

| Case Name | Format | Pages | CER | WER | Order reference | Table reference | Image pixels | Order heuristic | Table heuristic | Images | Anchors | Speed (s/p) | Process peak RAM (MB) | VRAM (MB) | Execution |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| born_digital_english | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.04 | 92.3 | N/A | PASS |
| two_column_law | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 0.67 | 1.00 | 1.00 | 1.00 | 0.04 | 92.3 | N/A | PASS |
| legal_footnotes | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.04 | 92.3 | N/A | PASS |
| scanned_english | docx | 1 | 0.031 | 0.333 | 0.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 3.50 | 160.7 | N/A | PASS |
| arabic_scan | docx | 1 | 0.825 | 1.000 | 0.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.99 | 168.9 | N/A | PASS |
| mixed_bidi | docx | 1 | 0.560 | 0.824 | 0.33 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.85 | 168.9 | N/A | PASS |
| scanned_table | docx | 1 | 0.049 | 0.500 | 0.67 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.69 | 168.9 | N/A | PASS |
| images_captions | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.05 | 168.9 | N/A | PASS |
| rotated_page | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.53 | 168.9 | N/A | PASS |
| skewed_page | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.44 | 168.9 | N/A | PASS |
| low_res_scan | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 2.39 | 168.9 | N/A | PASS |
| mixed_digital_scan | docx | 2 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 1.25 | 168.9 | N/A | PASS |
| page_numbering | docx | 2 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.02 | 168.9 | N/A | PASS |
| malformed_pdf | pdf | 1 | N/A | N/A | N/A | N/A | N/A | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 168.9 | N/A | PASS |
| docx_sample | docx | 1 | 0.000 | 0.000 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.05 | 168.9 | N/A | PASS |
| pptx_sample | docx | 1 | 0.138 | 0.143 | 1.00 | 1.00 | N/A | 1.00 | 1.00 | 1.00 | 1.00 | 0.05 | 168.9 | N/A | PASS |

PASS means conversion completed or malformed input was rejected safely. It is not a fidelity acceptance result. N/A means unmeasured. Reference columns compare authored order/cells/original image pixels; separate order/table columns are heuristics; RAM excludes child processes and records the lifetime process peak.
