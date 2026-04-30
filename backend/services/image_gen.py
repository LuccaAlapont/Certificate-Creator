"""Certificate rendering via Pillow."""
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).parent.parent.parent / "fonts"
_font_cache: dict[str, ImageFont.FreeTypeFont] = {}

# Supported output formats
OUTPUT_FORMATS = {"png", "jpeg_cmyk", "pdf"}


def _load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    cache_key = f"{font_name}:{size}"
    if cache_key in _font_cache:
        return _font_cache[cache_key]

    candidates: list[Path] = []
    if font_name:
        exact = FONTS_DIR / font_name
        if exact.exists():
            candidates.append(exact)
        for ext in (".ttf", ".otf"):
            p = FONTS_DIR / (font_name + ext)
            if p.exists():
                candidates.append(p)

    for ext in ("*.ttf", "*.otf", "*.TTF", "*.OTF"):
        candidates.extend(FONTS_DIR.glob(ext))

    if candidates:
        font = ImageFont.truetype(str(candidates[0]), size)
    else:
        font = ImageFont.load_default(size=size)

    _font_cache[cache_key] = font
    return font


def _measure_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> tuple[float, float]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _composite(img_path: Path, name: str, config: dict) -> tuple[Image.Image, bool]:
    """Render name onto template; return (RGB PIL image, font_was_reduced)."""
    img = Image.open(str(img_path)).convert("RGBA")
    img_w, img_h = img.size

    center_x  = float(config.get("center_x",  0.5)) * img_w
    center_y  = float(config.get("center_y",  0.5)) * img_h
    max_width = float(config.get("max_width", 0.7))  * img_w
    base_size = int(config.get("font_size",   200))
    font_name = config.get("font_name", "")
    color     = config.get("color",     "#ffffff")
    alignment = config.get("alignment", "center")

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    font_size    = base_size
    min_size     = max(int(base_size * 0.5), 10)
    font_reduced = False

    font = _load_font(font_name, font_size)
    text_w, _ = _measure_text(draw, name, font)

    while text_w > max_width and font_size > min_size:
        font_size   -= 2
        font_reduced = font_size < base_size
        font         = _load_font(font_name, font_size)
        text_w, _    = _measure_text(draw, name, font)

    if alignment == "center":
        anchor, x = "mm", center_x
    elif alignment == "left":
        anchor, x = "lm", center_x - max_width / 2
    else:
        anchor, x = "rm", center_x + max_width / 2

    draw.text((x, center_y), name, font=font, fill=color, anchor=anchor)
    composite = Image.alpha_composite(img, overlay).convert("RGB")
    return composite, font_reduced


def render_certificate(
    img_path: Path,
    name: str,
    config: dict,
    output_format: str = "png",
) -> tuple[bytes, bool]:
    """
    Render name onto template and encode to the requested format.
    output_format: 'png' | 'jpeg_cmyk' | 'pdf'
    Returns (bytes, font_was_reduced).
    """
    composite, font_reduced = _composite(img_path, name, config)

    buf = io.BytesIO()
    if output_format == "jpeg_cmyk":
        composite.convert("CMYK").save(buf, format="JPEG", quality=95, subsampling=0)
    elif output_format == "pdf":
        # 300 DPI single-page PDF; pixel dimensions determine physical size
        composite.save(buf, format="PDF", resolution=300)
    else:
        composite.save(buf, format="PNG")

    return buf.getvalue(), font_reduced


def render_certificate_pil(
    img_path: Path,
    name: str,
    config: dict,
) -> tuple[Image.Image, bool]:
    """Return raw PIL Image (RGB) for building combined PDFs."""
    return _composite(img_path, name, config)
