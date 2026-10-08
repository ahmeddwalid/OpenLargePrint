"""Layout detectors (PDF-001, PDF-003).

``PPDocLayoutDetector`` runs PP-DocLayoutV2 (PaddlePaddle, Apache-2.0) on the
CPU through ONNX Runtime. It predicts region classes *and* reading order, which
is what turns a two-column textbook page into a correctly ordered single column.

``HeuristicLayoutDetector`` is the fallback when the model file is missing: it
returns no regions, and the assembler then orders text by its own column logic.
Neither detector ever touches text content.
"""

from __future__ import annotations

import os
import threading
from typing import List, Optional

import numpy as np
from PIL import Image

from openlargeprint.models import model_manager
from openlargeprint.security.isolation import log_safe_info
from .regions import LABEL_KINDS, LayoutRegion, PageLayout, RegionKind

LAYOUT_MODEL_KEY = "pp_doc_layoutv2"
LAYOUT_INPUT_SIZE = 800
LAYOUT_MIN_SCORE = 0.40


class HeuristicLayoutDetector:
    name = "heuristic"

    def detect(self, image: Image.Image, page_width: float, page_height: float) -> PageLayout:
        return PageLayout(width=page_width, height=page_height, regions=[], source="heuristic")


class PPDocLayoutDetector:
    name = "pp_doc_layoutv2"

    def __init__(self, model_path: str):
        import onnxruntime as ort
        from rapid_layout.model_handler.pp_doc_layout.post_process import PPDocLayoutPostProcess
        from rapid_layout.model_handler.pp_doc_layout.pre_process import PPDocLayoutPreProcess

        options = ort.SessionOptions()
        options.intra_op_num_threads = min(8, max(1, (os.cpu_count() or 4) - 1))
        options.inter_op_num_threads = 1
        options.log_severity_level = 3
        self._session = ort.InferenceSession(model_path, sess_options=options,
                                             providers=["CPUExecutionProvider"])
        labels = self._session.get_modelmeta().custom_metadata_map.get("character", "").splitlines()
        if not labels:
            raise RuntimeError("The layout model has no label table.")
        self._labels = labels
        self._inputs = [i.name for i in self._session.get_inputs()]
        self._pre = PPDocLayoutPreProcess(img_size=(LAYOUT_INPUT_SIZE, LAYOUT_INPUT_SIZE))
        self._post = PPDocLayoutPostProcess(labels=labels)
        self._lock = threading.Lock()

    def detect(self, image: Image.Image, page_width: float, page_height: float) -> PageLayout:
        rgb = np.asarray(image.convert("RGB"))
        bgr = np.ascontiguousarray(rgb[:, :, ::-1])
        ori, batch = self._pre(bgr)
        feeds = dict(zip(self._inputs, batch))
        with self._lock:
            outputs = self._session.run(None, feeds)
        count = int(outputs[1][0])
        raw = np.array(outputs[0][:count])
        if raw.size == 0:
            return PageLayout(width=page_width, height=page_height, regions=[])
        boxes, scores, names = self._post(
            batch_outputs=[{"boxes": raw}], datas=[ori], threshold=LAYOUT_MIN_SCORE,
            layout_nms=True, layout_shape_mode="rect", filter_overlap_boxes=True,
            skip_order_labels=[],
        )
        sx = page_width / image.width
        sy = page_height / image.height
        regions: List[LayoutRegion] = []
        for order, (box, score, label) in enumerate(zip(boxes, scores, names)):
            kind = LABEL_KINDS.get(label)
            if kind is None:
                continue
            x0, y0, x1, y1 = (float(v) for v in box[:4])
            regions.append(LayoutRegion(
                kind=kind, x0=max(0.0, x0 * sx), y0=max(0.0, y0 * sy),
                x1=min(page_width, x1 * sx), y1=min(page_height, y1 * sy),
                score=float(score), order=order, label=label,
                decorative=label in ("header_image", "footer_image", "seal"),
            ))
        return PageLayout(width=page_width, height=page_height, regions=regions, source="model")


_detector_lock = threading.Lock()
_detector: Optional[object] = None


def get_layout_detector():
    """Process-wide detector; falls back to the heuristic detector if the model is unavailable."""
    global _detector
    with _detector_lock:
        if _detector is None:
            try:
                path = model_manager.get_model_path(LAYOUT_MODEL_KEY, verify=True)
                _detector = PPDocLayoutDetector(str(path))
                log_safe_info("Layout model loaded")
            except Exception as exc:  # missing or damaged model never stops a conversion
                log_safe_info(f"Layout model unavailable ({type(exc).__name__}); using geometric layout")
                _detector = HeuristicLayoutDetector()
        return _detector


def reset_layout_detector() -> None:
    global _detector
    with _detector_lock:
        _detector = None


def is_text_region(region: LayoutRegion) -> bool:
    return region.kind not in (RegionKind.FIGURE, RegionKind.TABLE, RegionKind.FORMULA)
