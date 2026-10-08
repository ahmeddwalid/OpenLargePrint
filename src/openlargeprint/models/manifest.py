"""Pinned model artifacts and their SHA-256 integrity manifest (SEC-006, LIC-001, OCR-002).

Every model used by a conversion is listed here with its exact size and digest.
All of them ship inside the application; a normal conversion never downloads
anything (SEC-009). ``download_url`` is used only by the build scripts that
assemble the installer.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field

ARABIC_DICTIONARY_SHA256 = "637c27c88512c22089bef927b34ada08f748dc132ac70facd68d8202384c2726"


class ModelTask(str, Enum):
    DETECTION = "detection"
    RECOGNITION = "recognition"
    CLASSIFICATION = "classification"
    LAYOUT = "layout"
    TABLE = "table"


class ModelFramework(str, Enum):
    ONNX = "onnx"


class ModelArtifact(BaseModel):
    """Metadata and integrity specification for one pinned model file (SEC-006)."""

    key: str
    name: str
    task: ModelTask
    framework: ModelFramework = ModelFramework.ONNX
    version: str
    sha256: str
    file_size_bytes: int
    code_license: str
    weight_license: str
    download_url: Optional[str] = None
    # Files that ship inside a Python wheel are located relative to that package
    # instead of the application's model folder.
    package: Optional[str] = None
    filename: Optional[str] = None
    is_default: bool = True
    description: str = ""

    @property
    def file_name(self) -> str:
        return self.filename or f"{self.key}.onnx"


class ModelCatalog(BaseModel):
    models: Dict[str, ModelArtifact] = Field(default_factory=dict)

    def get(self, key: str) -> Optional[ModelArtifact]:
        return self.models.get(key)

    def list_defaults(self) -> Dict[str, ModelArtifact]:
        return {k: m for k, m in self.models.items() if m.is_default}


_MODELSCOPE_OCR = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/onnx"
_MODELSCOPE_LAYOUT = "https://www.modelscope.cn/models/RapidAI/RapidLayout/resolve/v1.2.0/onnx"

PINNED_MODELS = ModelCatalog(models={
    "pp_doc_layoutv2": ModelArtifact(
        key="pp_doc_layoutv2", name="PP-DocLayoutV2 layout and reading order",
        task=ModelTask.LAYOUT, version="PP-DocLayoutV2/RapidLayout-1.2.0",
        sha256="0bd2ea0997fe0789f0300292291f8bbf897d890b44a9a3bd5be72afd6198aa90",
        file_size_bytes=213963993, code_license="Apache-2.0", weight_license="Apache-2.0",
        download_url=f"{_MODELSCOPE_LAYOUT}/pp_doc_layout/pp_doc_layoutv2.onnx",
        description="Finds titles, paragraphs, lists, tables, figures, captions and page furniture, in reading order",
    ),
    "PP-OCRv6_det_small": ModelArtifact(
        key="PP-OCRv6_det_small", name="PP-OCRv6 small text detection",
        task=ModelTask.DETECTION, version="PP-OCRv6/RapidOCR-3.9.2",
        sha256="090f04abcd9d9a7498bc4ebf677e4cb9bdce1fe4197ddb7e529f1ef44e1ff94f",
        file_size_bytes=9929594, code_license="Apache-2.0", weight_license="Apache-2.0",
        download_url=f"{_MODELSCOPE_OCR}/PP-OCRv6/det/PP-OCRv6_det_small.onnx",
        package="rapidocr", filename="models/PP-OCRv6_det_small.onnx",
        description="Finds lines of text on scanned pages",
    ),
    "PP-OCRv6_rec_small": ModelArtifact(
        key="PP-OCRv6_rec_small", name="PP-OCRv6 small text recognition",
        task=ModelTask.RECOGNITION, version="PP-OCRv6/RapidOCR-3.9.2",
        sha256="6f327246b50388f3c176ae304bd95767ea6dc0c9ae92153ef8cbe210b3c14884",
        file_size_bytes=21234383, code_license="Apache-2.0", weight_license="Apache-2.0",
        download_url=f"{_MODELSCOPE_OCR}/PP-OCRv6/rec/PP-OCRv6_rec_small.onnx",
        package="rapidocr", filename="models/PP-OCRv6_rec_small.onnx",
        description="Reads Latin-script and Chinese text, including word spacing and punctuation",
    ),
    "ch_ppocr_mobile_v2.0_cls": ModelArtifact(
        key="ch_ppocr_mobile_v2.0_cls", name="PP-OCR text-line orientation",
        task=ModelTask.CLASSIFICATION, version="PP-OCRv2/RapidOCR-3.9.2",
        sha256="e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
        file_size_bytes=585532, code_license="Apache-2.0", weight_license="Apache-2.0",
        download_url=f"{_MODELSCOPE_OCR}/PP-OCRv4/cls/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        package="rapidocr", filename="models/ch_ppocr_mobile_v2.0_cls_mobile.onnx",
        description="Detects upside-down text lines before recognition",
    ),
    "arabic_PP-OCRv5_rec_mobile": ModelArtifact(
        key="arabic_PP-OCRv5_rec_mobile", name="PP-OCRv5 Arabic text recognition",
        task=ModelTask.RECOGNITION, version="PP-OCRv5/RapidOCR-3.9.2",
        sha256="c1192e632d0baa9146ae5b756a0e635e3dc63c1733737ebfd1629e87144e9295",
        file_size_bytes=8023828, code_license="Apache-2.0", weight_license="Apache-2.0",
        download_url=f"{_MODELSCOPE_OCR}/PP-OCRv5/rec/arabic_PP-OCRv5_rec_mobile.onnx",
        description="Reads Arabic script on scanned pages",
    ),
})
