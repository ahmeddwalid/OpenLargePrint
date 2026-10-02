"""Explicit network-enabled model preparation, separate from conversion (SEC-006/009)."""
import argparse
from pathlib import Path

from openlargeprint.models import ModelManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare hash-verified optional recognition models.")
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--language", choices=("en", "ar", "both"), default="en", help="Arabic is a research candidate, disabled in conversion.")
    args = parser.parse_args()
    manager = ModelManager(cache_dir=args.directory)
    keys = {"en": "PP-OCRv6_rec_medium", "ar": "arabic_PP-OCRv5_rec_mobile"}
    for language, key in keys.items():
        if args.language in (language, "both"):
            manager.download_model(key)
            print("Verified optional English recognition model." if language == "en" else "Verified Arabic research candidate; conversion remains disabled.")


if __name__ == "__main__":
    main()
