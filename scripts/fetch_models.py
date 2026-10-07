"""Download the pinned models that the installer bundles (SEC-006).

Run once in a development checkout and in the release build:

    python scripts/fetch_models.py

Files land in ``src/openlargeprint/models/weights/`` and are verified against
the size and SHA-256 recorded in ``models/manifest.py``. Models that already
ship inside a Python wheel (RapidOCR's PP-OCRv6 files) are only verified.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from openlargeprint.models.manager import BUNDLED_WEIGHTS_DIR, ModelManager  # noqa: E402
from openlargeprint.models.manifest import PINNED_MODELS  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--from-dir", type=Path, help="Install from already downloaded files instead of the network")
    args = parser.parse_args()

    BUNDLED_WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    store = ModelManager(cache_dir=BUNDLED_WEIGHTS_DIR)
    lookup = ModelManager()
    failed = False
    for key, artifact in PINNED_MODELS.models.items():
        if artifact.package:
            try:
                path = lookup.get_model_path(key, verify=True)
                print(f"ok        {key} ({path.parent.name}/{path.name})")
            except Exception as exc:
                print(f"MISSING   {key}: {exc}")
                failed = True
            continue
        target = BUNDLED_WEIGHTS_DIR / f"{key}.onnx"
        if target.is_file() and store.verify_file(target, artifact.sha256):
            print(f"ok        {key}")
            continue
        try:
            if args.from_dir is not None:
                source = next(p for p in args.from_dir.iterdir()
                              if p.is_file() and store.verify_file(p, artifact.sha256))
                store.install_model(key, source)
            else:
                store.download_model(key, force=True)
            print(f"installed {key}")
        except StopIteration:
            print(f"MISSING   {key}: not found in {args.from_dir}")
            failed = True
        except Exception as exc:
            print(f"FAILED    {key}: {exc}")
            failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
