"""Pinned model artifact definitions and SHA-256 integrity manifest (SEC-006, LIC-001, OCR-004..006)."""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional
from pydantic import BaseModel, Field


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
    }
)
