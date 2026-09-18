#!/usr/bin/env python3
"""Generate crisp, high-contrast accessible application icons for OpenLargePrint (A11Y-001, VIS-001)."""

from pathlib import Path
from PIL import Image, ImageDraw


def generate_icons():
    repo_root = Path(__file__).resolve().parent.parent
    icons_dir = repo_root / "src-tauri" / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    ui_public_dir = repo_root / "ui" / "public"
    ui_public_dir.mkdir(parents=True, exist_ok=True)

    logo_svg = repo_root / "logo.svg"
    logo_png = repo_root / "logo.png"
    size = 512
    img = None

    import shutil

    if logo_svg.exists():
        print(f"Loading official brand vector icon from: {logo_svg}")
        shutil.copy2(logo_svg, ui_public_dir / "logo.svg")
        shutil.copy2(logo_svg, icons_dir / "icon.svg")
        print(f"Copied {logo_svg} to ui/public/logo.svg and src-tauri/icons/icon.svg")

        try:
            import fitz
            import io
            doc = fitz.open(str(logo_svg))
            page = doc[0]
            zoom = 1024.0 / max(page.rect.width, page.rect.height)
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=True)
            raw_img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGBA")
            doc.close()
            img = raw_img.resize((size, size), Image.Resampling.LANCZOS)
            print("Successfully rasterized vector SVG into high-resolution icon master")
        except Exception as err:
            print(f"Notice: vector rasterization fallback ({err})")

    if img is None and logo_png.exists():
        print(f"Loading official brand raster icon from: {logo_png}")
        raw_img = Image.open(logo_png).convert("RGBA")
        img = raw_img.resize((size, size), Image.Resampling.LANCZOS)

    if logo_png.exists():
        shutil.copy2(logo_png, ui_public_dir / "logo.png")

    if img is None:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Rounded background plate: deep navy / bookbinder slate #1E293B
        bg_margin = 24
        corner_radius = 96
        draw.rounded_rectangle(
            [bg_margin, bg_margin, size - bg_margin, size - bg_margin],
            radius=corner_radius,
            fill=(30, 41, 59, 255),  # Slate 800
            outline=(51, 65, 85, 255),  # Slate 700
            width=6,
        )

        # Open book / document silhouette in crisp paper white #F8FAFC
        doc_margin_x = 90
        doc_top = 110
        doc_bottom = 410
        draw.rounded_rectangle(
            [doc_margin_x, doc_top, size - doc_margin_x, doc_bottom],
            radius=32,
            fill=(248, 250, 252, 255),
        )

        # Book spine divider
        center_x = size // 2
        draw.line([(center_x, doc_top + 16), (center_x, doc_bottom - 16)], fill=(203, 213, 225, 255), width=6)

        # Left: Standard "A"
        draw.polygon(
            [(190, 190), (150, 330), (175, 330), (185, 290), (225, 290), (235, 330), (260, 330), (220, 190)],
            fill=(71, 85, 105, 255),
        )
        draw.polygon([(205, 220), (192, 270), (218, 270)], fill=(248, 250, 252, 255))

        # Right: Large-print, bold accessible "A" (warm amber #D97706)
        draw.polygon(
            [(330, 160), (280, 350), (312, 350), (324, 300), (380, 300), (392, 350), (424, 350), (374, 160)],
            fill=(217, 119, 6, 255),
        )
        draw.polygon([(352, 200), (334, 275), (370, 275)], fill=(248, 250, 252, 255))

    # Save primary 512x512 icon.png
    icon_png = icons_dir / "icon.png"
    img.save(icon_png, "PNG")
    print(f"Generated {icon_png}")

    # Also save to ui/public for webview header and favicon
    ui_logo = ui_public_dir / "logo.png"
    img.save(ui_logo, "PNG")
    print(f"Generated {ui_logo}")

    # Specific icon sizes for Tauri / Windows
    sizes = {
        "32x32.png": (32, 32),
        "128x128.png": (128, 128),
        "128x128@2x.png": (256, 256),
        "Square30x30Logo.png": (30, 30),
        "Square44x44Logo.png": (44, 44),
        "Square71x71Logo.png": (71, 71),
        "Square89x89Logo.png": (89, 89),
        "Square107x107Logo.png": (107, 107),
        "Square142x142Logo.png": (142, 142),
        "Square150x150Logo.png": (150, 150),
        "Square284x284Logo.png": (284, 284),
        "Square310x310Logo.png": (310, 310),
        "StoreLogo.png": (50, 50),
    }

    for name, s in sizes.items():
        resized = img.resize(s, Image.Resampling.LANCZOS)
        out_path = icons_dir / name
        resized.save(out_path, "PNG")

    # Multi-resolution Windows ICO file with high-DPI 256x256 layer (A11Y-001, VIS-001)
    ico_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    ico_path = icons_dir / "icon.ico"
    img.save(ico_path, format="ICO", sizes=ico_sizes)
    print(f"Generated high-DPI multi-layer {ico_path}")

    ui_favicon = ui_public_dir / "favicon.ico"
    img.save(ui_favicon, format="ICO", sizes=ico_sizes)
    print(f"Generated high-DPI multi-layer {ui_favicon}")


if __name__ == "__main__":
    generate_icons()
