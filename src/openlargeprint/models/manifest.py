"""Pinned model artifact definitions and SHA-256 integrity manifest (SEC-006, LIC-001, OCR-004..006)."""

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
    VLM = "vlm"


class ModelFramework(str, Enum):
    ONNX = "onnx"
    PADDLE = "paddle"
    PYTORCH = "pytorch"


class ModelArtifact(BaseModel):
    """Metadata and integrity specification for a pinned model weight artifact (SEC-006)."""

    key: str = Field(..., description="Unique internal identifier for the model artifact")
    name: str = Field(..., description="Human-readable model name")
    task: ModelTask = Field(..., description="Target OCR/layout stage")
    framework: ModelFramework = Field(..., description="Underlying inference framework")
    version: str = Field(..., description="Pinned upstream version")
    sha256: str = Field(..., description="Cryptographic SHA-256 checksum of weights")
    file_size_bytes: int = Field(..., description="Expected file size in bytes")
    code_license: str = Field(..., description="Code license of the underlying architecture")
    weight_license: str = Field(..., description="Model weight distribution license (LIC-001)")
    download_url: Optional[str] = Field(None, description="Official upstream repository URL")
    is_default: bool = Field(True, description="True if required for standard CPU installation")
    description: str = Field("", description="Purpose and performance characteristics")


class ModelCatalog(BaseModel):
    """Collection of verified, pinned model artifacts."""

    models: Dict[str, ModelArtifact] = Field(default_factory=dict)

    def get(self, key: str) -> Optional[ModelArtifact]:
        return self.models.get(key)

    def list_defaults(self) -> Dict[str, ModelArtifact]:
        return {k: m for k, m in self.models.items() if m.is_default}


# Pinned baseline models used by OpenLargePrint (RapidOCR ONNX default stack)
PINNED_MODELS = ModelCatalog(
    models={
        "PP-OCRv6_rec_medium": ModelArtifact(
            key="PP-OCRv6_rec_medium", name="PP-OCRv6 medium recognition (ONNX)",
            task=ModelTask.RECOGNITION, framework=ModelFramework.ONNX,
            version="PP-OCRv6/RapidOCR-3.9.2",
            sha256="eef444829dbbe18d7fea59a3f6eb75647518d2b3a9568d27c92e42940204894b",
            file_size_bytes=76629984, code_license="Apache-2.0", weight_license="Apache-2.0",
            download_url="https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/4e9666f0fbf5fac850d30e530bf0a2e0d886aa78/onnx/PP-OCRv6/rec/PP-OCRv6_rec_medium.onnx",
            is_default=False, description="Optional CPU Chinese/English recognition; no semantic layout claims",
        ),
        "arabic_PP-OCRv5_rec_mobile": ModelArtifact(
            key="arabic_PP-OCRv5_rec_mobile", name="PP-OCRv5 Arabic recognition (ONNX)",
            task=ModelTask.RECOGNITION, framework=ModelFramework.ONNX,
            version="PP-OCRv5/RapidOCR-3.9.2",
            sha256="c1192e632d0baa9146ae5b756a0e635e3dc63c1733737ebfd1629e87144e9295",
            file_size_bytes=8023828, code_license="Apache-2.0", weight_license="Apache-2.0",
            download_url="https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/b8ff564a23de421e7144385bfe120fe2bb869932/onnx/PP-OCRv5/rec/arabic_PP-OCRv5_rec_mobile.onnx",
            is_default=False, description="Optional CPU Arabic recognition candidate; direction acceptance pending, disabled in conversion",
        ),
        "ch_PP-OCRv4_det": ModelArtifact(
            key="ch_PP-OCRv4_det",
            name="PP-OCRv4 Text Detection (ONNX)",
            task=ModelTask.DETECTION,
            framework=ModelFramework.ONNX,
            version="v4.0.0",
            sha256="d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9",
            file_size_bytes=4745517,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url=None,
            is_default=True,
            description="Ultra-lightweight CPU text detector bounding box predictor",
        ),
        "ch_ppocr_mobile_v2.0_cls": ModelArtifact(
            key="ch_ppocr_mobile_v2.0_cls",
            name="PP-OCR Direction Classifier (ONNX)",
            task=ModelTask.CLASSIFICATION,
            framework=ModelFramework.ONNX,
            version="v2.0.0",
            sha256="e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c",
            file_size_bytes=585532,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url=None,
            is_default=True,
            description="Text orientation angle (0 vs 180 degrees) classifier",
        ),
        "ch_PP-OCRv4_rec": ModelArtifact(
            key="ch_PP-OCRv4_rec",
            name="PP-OCRv4 Chinese/English Text Recognition (ONNX)",
            task=ModelTask.RECOGNITION,
            framework=ModelFramework.ONNX,
            version="v4.0.0",
            sha256="48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b",
            file_size_bytes=10857958,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url=None,
            is_default=True,
            description="CPU-optimized Chinese/English text recognition engine",
        ),
        "arabic_PP-OCRv3_rec": ModelArtifact(
            key="arabic_PP-OCRv3_rec",
            name="PP-OCRv3 Arabic Text Recognition (ONNX)",
            task=ModelTask.RECOGNITION,
            framework=ModelFramework.ONNX,
            version="v3.0.0",
            sha256="7982d371612785238fd99080cff36354deaec84fdc6ff7da9c82af4243fa0c9a",
            file_size_bytes=8978664,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://huggingface.co/monkt/paddleocr-onnx/resolve/main/languages/arabic/rec.onnx",
            is_default=False,
            description="Optional on-device Arabic text recognition model (PaddleOCR v3 ONNX)",
        ),
    }
)

