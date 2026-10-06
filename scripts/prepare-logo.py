"""Prepare 纸翼 logo assets from assets/branding/logo.jpg."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
BRAND = ROOT / "assets" / "branding"
PUBLIC = ROOT / "public"
SRC_ASSETS = ROOT / "src" / "assets"
ICONS = ROOT / "src-tauri" / "icons"
SOURCE = BRAND / "logo.jpg"


def knockout_black(im: Image.Image, hard: int = 16, soft: int = 42) -> Image.Image:
    """Turn near-black pixels transparent, keeping the blue orb and glow."""
    rgba = im.convert("RGBA")
    pixels = rgba.load()
    w, h = rgba.size
    span = max(1, soft - hard)
    for y in range(h):
        for x in range(w):
            r, g, b, _a = pixels[x, y]
            peak = max(r, g, b)
            if peak <= hard:
                alpha = 0
            elif peak < soft:
                alpha = int(255 * (peak - hard) / span)
            else:
                alpha = 255
            pixels[x, y] = (r, g, b, alpha)
    return rgba


def crop_content(im: Image.Image, pad: int = 8) -> Image.Image:
    bbox = im.getbbox()
    if not bbox:
        return im
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(im.width, right + pad)
    bottom = min(im.height, bottom + pad)
    return im.crop((left, top, right, bottom))


def square_canvas(im: Image.Image, size: int = 1024, fill: float = 0.92) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    scale = min((size * fill) / im.width, (size * fill) / im.height)
    nw = max(1, int(im.width * scale))
    nh = max(1, int(im.height * scale))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas.paste(resized, ((size - nw) // 2, (size - nh) // 2), resized)
    return canvas


def save_png(im: Image.Image, path: Path, size: int | None = None) -> None:
    out = im.resize((size, size), Image.Resampling.LANCZOS) if size else im
    path.parent.mkdir(parents=True, exist_ok=True)
    out.save(path, format="PNG", optimize=True)


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"missing source logo: {SOURCE}")

    original = Image.open(SOURCE).convert("RGB")
    original.save(BRAND / "logo.png", optimize=True)

    transparent = crop_content(knockout_black(original))
    mark = square_canvas(transparent, 1024)
    mark.save(BRAND / "logo-transparent.png", optimize=True)

    ui = transparent.resize(
        (256, int(256 * transparent.height / transparent.width)),
        Image.Resampling.LANCZOS,
    )
    PUBLIC.mkdir(parents=True, exist_ok=True)
    SRC_ASSETS.mkdir(parents=True, exist_ok=True)
    ui.save(PUBLIC / "logo.png", optimize=True)
    ui.save(SRC_ASSETS / "logo.png", optimize=True)

    save_png(mark, ICONS / "32x32.png", 32)
    save_png(mark, ICONS / "64x64.png", 64)
    save_png(mark, ICONS / "128x128.png", 128)
    save_png(mark, ICONS / "128x128@2x.png", 256)
    save_png(mark, ICONS / "icon.png", 512)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    mark.save(ICONS / "icon.ico", format="ICO", sizes=ico_sizes)
    print(f"source {original.size} -> transparent {transparent.size} -> mark {mark.size}")


if __name__ == "__main__":
    main()
