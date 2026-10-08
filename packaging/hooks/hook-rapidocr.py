"""Bundle RapidOCR with its PP-OCRv6 detection, recognition and orientation models.

The models ship inside the wheel and are verified at runtime against the
SHA-256 pins in openlargeprint/models/manifest.py (SEC-006).
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = collect_data_files("rapidocr") + copy_metadata("rapidocr")
hiddenimports = collect_submodules("rapidocr")
