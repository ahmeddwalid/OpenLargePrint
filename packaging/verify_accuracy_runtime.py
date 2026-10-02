"""Actual spawned/frozen optional recognition verification (PKG-002, SEC-009)."""
import json
from pathlib import Path
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def main():
    root = Path(__file__).resolve().parent.parent
    binary = root / "src-tauri/binaries/openlargeprint-sidecar-x86_64-pc-windows-msvc.exe"
    with tempfile.TemporaryDirectory(prefix="olp-accuracy-") as folder:
        directory = Path(folder)
        image = Image.new("RGB", (650, 130), "white")
        ImageDraw.Draw(image).text((30, 35), "Judicial Review", font=ImageFont.load_default(size=38), fill="black")
        image_path = directory / "recognition.png"
        image.save(image_path)
        source = directory / "recognition.pdf"
        pdf = canvas.Canvas(str(source), pagesize=A4)
        pdf.drawString(72, 700, "Native wording stays unchanged.")
        pdf.showPage()
        pdf.drawImage(str(image_path), 50, 500, width=500, height=100)
        pdf.showPage()
        pdf.save()
        commands = [{"command": "health"}, {"command": "convert", "id": "accuracy-smoke", "file_path": str(source),
                    "output_path": str(directory / "output.pdf"), "export_format": "pdf", "routing_mode": "max_accuracy"}]
        process = subprocess.run([str(binary), "sidecar"], input="".join(json.dumps(command) + "\n" for command in commands),
                                 capture_output=True, text=True, encoding="utf-8", timeout=180)
        assert process.returncode == 0, "Frozen accuracy process failed"
        events = [json.loads(line) for line in process.stdout.splitlines() if line.startswith("{")]
        health = next(event for event in events if event["type"] == "health")
        assert health["status"] == "ready" and "en" in health["accuracy_languages"], "Frozen optional pack is unavailable"
        result = next(event for event in events if event["type"] == "success")
        blocks = result["document_ir"]["blocks"]
        assert any(block.get("text") == "Native wording stays unchanged." for block in blocks)
        assert any("Judicial Review" in (block.get("text") or "") and block["extraction_method"] == "ocr_maximum" for block in blocks)
        assert (directory / "output.pdf").is_file()
    print("Frozen optional English recognition: verified health, native text, second-page worker recognition, PDF export and profile provenance passed.")


if __name__ == "__main__":
    main()
