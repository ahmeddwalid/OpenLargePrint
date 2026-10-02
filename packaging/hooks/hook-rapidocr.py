"""Bundle optional runtime/configuration, keeping optional weights out of the base installer."""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

datas = collect_data_files("rapidocr", excludes=["models/**", "**/*.onnx"]) + copy_metadata("rapidocr")
hiddenimports = collect_submodules("rapidocr")
