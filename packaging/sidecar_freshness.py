"""Hash-based development sidecar freshness; never trust mere existence (PKG-002)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def fingerprint(root: Path) -> str:
    digest = hashlib.sha256()
    files = list((root / "src/openlargeprint").rglob("*.py"))
    files += [root / name for name in ("uv.lock", "pyproject.toml", "packaging/build_sidecar.py")]
    files += list((root / "src/openlargeprint/models").rglob("*.txt"))
    for path in sorted(p for p in files if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def binary_hash(binary: Path) -> str:
    with binary.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def record_build(root: Path, binary: Path) -> None:
    binary.with_suffix(binary.suffix + ".build.json").write_text(
        json.dumps({"source_sha256": fingerprint(root), "binary_sha256": binary_hash(binary)}),
        encoding="utf-8",
    )


def is_fresh(root: Path, binary: Path) -> bool:
    try:
        record = json.loads(binary.with_suffix(binary.suffix + ".build.json").read_text())
        return record == {"source_sha256": fingerprint(root), "binary_sha256": binary_hash(binary)}
    except (OSError, ValueError):
        return False


if __name__ == "__main__":
    raise SystemExit(0 if is_fresh(Path(__file__).resolve().parents[1], Path(sys.argv[1])) else 1)
