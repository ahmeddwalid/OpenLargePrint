"""Bundle rapid-layout's PP-DocLayout pre/post-processing.

Only the processing code is used: the layout model itself is the pinned
PP-DocLayoutV2 file from openlargeprint/models/weights, so the wheel's own
model files are left out of the installer.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = collect_data_files("rapid_layout", excludes=["models/**", "**/*.onnx"]) + copy_metadata("rapid_layout")
hiddenimports = collect_submodules("rapid_layout")
