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
            sha256="05a968a3e78e6f111812903b0d402325ce03531b7829283f5c94285aa16262fe",
            file_size_bytes=4860432,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://github.com/RapidAI/RapidOCR/releases/download/v1.1.0/ch_PP-OCRv4_det_infer.onnx",
            is_default=True,
            description="Ultra-lightweight CPU text detector bounding box predictor",
        ),
        "ch_ppocr_mobile_v2.0_cls": ModelArtifact(
            key="ch_ppocr_mobile_v2.0_cls",
            name="PP-OCR Direction Classifier (ONNX)",
            task=ModelTask.CLASSIFICATION,
            framework=ModelFramework.ONNX,
            version="v2.0.0",
            sha256="5261d7bfa5d38a536da49fa5eb803e498c8f0003fb7c6d66e746522c069eb814",
            file_size_bytes=1477756,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://github.com/RapidAI/RapidOCR/releases/download/v1.1.0/ch_ppocr_mobile_v2.0_cls_infer.onnx",
            is_default=True,
            description="Text orientation angle (0 vs 180 degrees) classifier",
        ),
        "ch_PP-OCRv4_rec": ModelArtifact(
            key="ch_PP-OCRv4_rec",
            name="PP-OCRv4 Multilingual Text Recognition (ONNX)",
            task=ModelTask.RECOGNITION,
            framework=ModelFramework.ONNX,
            version="v4.0.0",
            sha256="eb0c2a8c3d3a4658e3703c7e7b686d0614138e6ea47d4e339d2fead31e21b714",
            file_size_bytes=10842270,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://github.com/RapidAI/RapidOCR/releases/download/v1.1.0/ch_PP-OCRv4_rec_infer.onnx",
            is_default=True,
            description="CPU-optimized multilingual text recognition engine",
        ),
        "picodet_lcnet_layout": ModelArtifact(
            key="picodet_lcnet_layout",
            name="PP-StructureV3 PicoDet Layout Analysis (ONNX)",
            task=ModelTask.LAYOUT,
            framework=ModelFramework.ONNX,
            version="v3.0.0",
            sha256="b4e18d6bc9f0cf192534a6ef29bc7886470875e5339c02ffc457d7cfb3952f1e",
            file_size_bytes=8192000,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://github.com/PaddlePaddle/PaddleOCR/releases/download/PP-StructureV3/picodet_lcnet_layout.onnx",
            is_default=True,
            description="Document layout segmenter identifying headers, tables, images, and text columns",
        ),
        "ch_ppstructure_table_slanet": ModelArtifact(
            key="ch_ppstructure_table_slanet",
            name="PP-Structure SLANet Table Recognition (ONNX)",
            task=ModelTask.TABLE,
            framework=ModelFramework.ONNX,
            version="v2.0.0",
            sha256="a7d23910c6fe34beea23fef617d12108740c062c31e9c56fa769742eb518290f",
            file_size_bytes=7208960,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://github.com/PaddlePaddle/PaddleOCR/releases/download/PP-StructureV2/ch_ppstructure_mobile_v2.0_SLANet_infer.onnx",
            is_default=True,
            description="Structural table cell grid and span reconstruction",
        ),
        "paddleocr_vl_1.6": ModelArtifact(
            key="paddleocr_vl_1.6",
            name="PaddleOCR-VL-1.6 Maximum Accuracy VLM (ONNX)",
            task=ModelTask.VLM,
            framework=ModelFramework.ONNX,
            version="v1.6.0",
            sha256="c987a245f7823b189d98412e69772bf22095ea817c0a91176b92f44dc6e88102",
            file_size_bytes=382900000,
            code_license="Apache-2.0",
            weight_license="Apache-2.0",
            download_url="https://github.com/PaddlePaddle/PaddleOCR/releases/download/PaddleOCR-VL/paddleocr_vl_1.6_cpu.onnx",
            is_default=False,
            description="Optional high-accuracy vision-language model for dense two-column legal tables",
        ),
    }
)
