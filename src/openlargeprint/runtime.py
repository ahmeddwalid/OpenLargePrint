"""How much of the computer a conversion uses (PERF-001).

Pages are converted side by side in worker processes, one per few CPU cores,
as many as the memory allows. Each worker's ONNX Runtime sessions get a share
of the cores so the workers do not fight over them.

On Windows the layout and recognition models can run on the graphics card
through DirectML. The graphics card is used only after a short check that it
gives the same answers as the CPU; on any doubt the CPU is used, so results
never depend on the graphics driver.

Settings come from environment variables, which worker processes inherit:

* ``OLP_PAGE_WORKERS``: number of page workers (1 turns parallel pages off).
* ``OLP_ONNX_THREADS``: threads per ONNX Runtime session.
* ``OLP_GPU``: ``auto`` (default) or ``off``.
"""

from __future__ import annotations

import ctypes
import os
import sys
import threading
from functools import lru_cache
from typing import List, Optional

from openlargeprint.security.isolation import log_safe_info

WORKER_MEMORY_GB = 1.3   # layout model, recognisers and a 300 dpi page, with room to spare
MAX_PAGE_WORKERS = 6
GPU_PROBE_SECONDS = 30.0


def cpu_count() -> int:
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:
        return max(1, os.cpu_count() or 1)


def available_memory_gb() -> Optional[float]:
    """Memory free for new work, or None when it cannot be told."""
    try:
        if sys.platform == "win32":
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullAvailPhys / 1024 ** 3
            return None
        with open("/proc/meminfo", encoding="ascii") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024 ** 2
    except Exception:
        return None
    return None


def _env_int(name: str) -> Optional[int]:
    try:
        value = int(os.environ.get(name, ""))
        return value if value > 0 else None
    except ValueError:
        return None


def page_workers(pages: int, scanned_share: float = 0.0) -> int:
    """How many pages to convert at once.

    ONNX Runtime already spreads one page's layout analysis over about four
    cores, so digital pages gain from more workers only on bigger machines.
    Recognition of a scanned page spends much of its time in small steps that
    use one core, so scans get a worker for every two cores.
    """
    chosen = _env_int("OLP_PAGE_WORKERS")
    if chosen is not None:
        return max(1, min(chosen, pages, MAX_PAGE_WORKERS))
    cores = cpu_count()
    cores_each = 2 if scanned_share >= 0.3 else 4
    workers = max(1, min(MAX_PAGE_WORKERS, cores // cores_each, pages))
    memory = available_memory_gb()
    if memory is not None:
        workers = max(1, min(workers, int((memory - 1.0) / WORKER_MEMORY_GB)))
    return workers


def onnx_threads() -> int:
    """Threads for each ONNX Runtime session in this process."""
    chosen = _env_int("OLP_ONNX_THREADS")
    if chosen is not None:
        return min(chosen, 16)
    return min(8, max(1, cpu_count() - 1))


def threads_for_workers(workers: int, scanned_share: float = 0.0) -> int:
    """ONNX Runtime threads for each page worker.

    Measured on four cores: two workers with one thread each read scans 11%
    faster than one process with all cores, while digital pages do best with
    whole cores per worker.
    """
    per_worker = cpu_count() // max(1, workers)
    if scanned_share >= 0.3:
        per_worker //= 2
    return max(1, per_worker)


# -- graphics card ----------------------------------------------------------------

DML = "DmlExecutionProvider"
CPU = "CPUExecutionProvider"


def gpu_allowed() -> bool:
    return sys.platform == "win32" and os.environ.get("OLP_GPU", "auto").lower() != "off"


def _probe_directml(model_path: str) -> bool:
    """Run a small input through the model on the CPU and on DirectML; True if they agree."""
    import numpy as np
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.log_severity_level = 3
    cpu = ort.InferenceSession(model_path, sess_options=options, providers=[CPU])
    dml_options = ort.SessionOptions()
    dml_options.log_severity_level = 3
    dml_options.enable_mem_pattern = False
    dml_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    dml = ort.InferenceSession(model_path, sess_options=dml_options, providers=[DML, CPU])
    if DML not in dml.get_providers():
        return False
    first = cpu.get_inputs()[0]
    shape = [d if isinstance(d, int) and d > 0 else 64 for d in first.shape]
    rng = np.random.default_rng(7)
    sample = rng.random(shape, dtype=np.float32)
    expected = cpu.run(None, {first.name: sample})[0]
    actual = dml.run(None, {first.name: sample})[0]
    return expected.shape == actual.shape and float(np.max(np.abs(expected - actual))) < 1e-2


@lru_cache(maxsize=1)
def gpu_ready() -> bool:
    """True when DirectML is installed and agrees with the CPU on a test input."""
    if not gpu_allowed():
        return False
    try:
        import onnxruntime as ort
        if DML not in ort.get_available_providers():
            return False
        from openlargeprint.models import model_manager
        path = str(model_manager.get_model_path("PP-OCRv6_det_small", verify=True))
    except Exception as exc:
        log_safe_info(f"Graphics card not used ({type(exc).__name__})")
        return False
    outcome: List[bool] = []

    def probe() -> None:
        try:
            outcome.append(_probe_directml(path))
        except Exception as exc:
            log_safe_info(f"Graphics card check failed ({type(exc).__name__})")
            outcome.append(False)

    worker = threading.Thread(target=probe, daemon=True)
    worker.start()
    worker.join(GPU_PROBE_SECONDS)
    ready = bool(outcome and outcome[0])
    log_safe_info("Using the graphics card (DirectML)" if ready else "Using the CPU")
    return ready


def providers() -> List[str]:
    """Execution providers for ONNX Runtime sessions in this process.

    Worker processes are told the main process's decision through OLP_GPU, so
    the check runs once per conversion, not once per worker.
    """
    decided = os.environ.get("OLP_GPU", "auto").lower()
    if decided == "on" and sys.platform == "win32":
        return [DML, CPU]
    if decided == "auto" and gpu_ready():
        return [DML, CPU]
    return [CPU]


def use_gpu() -> bool:
    return providers()[0] == DML


def settle_gpu() -> bool:
    """Decide once, before workers start, whether this conversion uses the graphics card."""
    if os.environ.get("OLP_GPU", "auto").lower() == "auto":
        os.environ["OLP_GPU"] = "on" if gpu_ready() else "off"
    return use_gpu()


def session_options(ort):
    """ONNX Runtime options for this process's thread share and provider."""
    options = ort.SessionOptions()
    options.intra_op_num_threads = onnx_threads()
    options.inter_op_num_threads = 1
    options.log_severity_level = 3
    if use_gpu():
        # DirectML needs these two; the CPU path keeps the faster defaults.
        options.enable_mem_pattern = False
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    return options
