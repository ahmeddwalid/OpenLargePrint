"""Model manager enforcing cryptographic SHA-256 verification and offline execution (SEC-006, SEC-009)."""

from __future__ import annotations

import hashlib
import hmac
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

from openlargeprint.models.manifest import (
    ModelArtifact,
    ModelCatalog,
    PINNED_MODELS,
)
from openlargeprint.security.isolation import log_safe_info
from openlargeprint.security.validator import SecurityValidationError


class ModelIntegrityError(SecurityValidationError):
    """Raised when model weights fail cryptographic SHA-256 verification (SEC-006)."""
    pass


class ModelManager:
    """Manages local model storage, integrity verification, and offline checks."""

    def __init__(
        self,
        catalog: Optional[ModelCatalog] = None,
        cache_dir: Optional[Path | str] = None,
    ):
        self.catalog = catalog or PINNED_MODELS
        self._cache_dir: Optional[Path] = Path(cache_dir) if cache_dir else None

    @property
    def cache_dir(self) -> Path:
        """Resolve model storage path respecting OPENLARGEPRINT_MODEL_DIR environment variable."""
        if self._cache_dir:
            self._cache_dir.mkdir(parents=True, exist_ok=True)
            return self._cache_dir

        env_dir = os.getenv("OPENLARGEPRINT_MODEL_DIR")
        if env_dir:
            p = Path(env_dir).resolve()
        else:
            # Fall back to standard XDG / user cache dir
            p = Path.home() / ".cache" / "openlargeprint" / "models"

        p.mkdir(parents=True, exist_ok=True)
        return p

    @staticmethod
    def compute_sha256(file_path: Path | str) -> str:
        """Compute SHA-256 checksum of a file in 64KB blocks."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Target model file does not exist: {path}")

        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def verify_file(self, file_path: Path | str, expected_sha256: str) -> bool:
        """Cryptographically verify file integrity using constant-time digest comparison (SEC-006)."""
        actual_hash = self.compute_sha256(file_path)
        return hmac.compare_digest(actual_hash.lower(), expected_sha256.lower())

    def get_model_path(self, key: str, verify: bool = True) -> Path:
        """Get path to a verified model file.
        
        Raises:
            KeyError: if model key is not in catalog.
            FileNotFoundError: if model file is not present locally.
            ModelIntegrityError: if SHA-256 does not match pinned manifest (SEC-006).
        """
        artifact = self.catalog.get(key)
        if not artifact:
            raise KeyError(f"Unknown model artifact: {key}")

        model_file = self.cache_dir / f"{key}.onnx"
        if not model_file.exists():
            raise FileNotFoundError(
                f"Model '{artifact.name}' ({key}) is not installed locally in {self.cache_dir}."
            )

        if verify:
            if not self.verify_file(model_file, artifact.sha256):
                raise ModelIntegrityError(
                    f"Model '{key}' failed integrity verification! Expected SHA-256 {artifact.sha256}, "
                    f"got {self.compute_sha256(model_file)}. Possible corruption or tampering."
                )

        return model_file

    def install_model(self, key: str, source_path: Path | str) -> Path:
        """Install and verify a model file into the local model store (SEC-006)."""
        artifact = self.catalog.get(key)
        if not artifact:
            raise KeyError(f"Cannot install unregistered model: {key}")

        src = Path(source_path)
        if not src.is_file():
            raise FileNotFoundError(f"Source file not found: {src}")

        # Compute and verify hash before committing to cache
        actual_hash = self.compute_sha256(src)
        if not hmac.compare_digest(actual_hash.lower(), artifact.sha256.lower()):
            raise ModelIntegrityError(
                f"Cannot install model '{key}': hash mismatch. Expected {artifact.sha256}, got {actual_hash}."
            )

        dest = self.cache_dir / f"{key}.onnx"
        shutil.copy2(src, dest)
        log_safe_info(f"Installed model '{key}' successfully into {dest}")
        return dest

    def is_offline_ready(self, keys: Optional[List[str]] = None) -> bool:
        """Check if all requested models are installed and hash-verified for offline conversion (SEC-009)."""
        target_keys = keys or list(self.catalog.list_defaults().keys())
        for k in target_keys:
            try:
                self.get_model_path(k, verify=True)
            except (FileNotFoundError, ModelIntegrityError, KeyError):
                return False
        return True


# Global default instance
model_manager = ModelManager()
