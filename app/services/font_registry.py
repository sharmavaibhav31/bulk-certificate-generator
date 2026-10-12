"""
Font Registry: Manages bundled OFL-licensed TrueType fonts and size caching.
"""

from pathlib import Path
from typing import Dict, Tuple
from PIL import ImageFont

FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

ALLOWED_FONT_KEYS = {
    "dejavu_sans": "dejavu_sans.ttf",
    "dejavu_serif": "dejavu_serif.ttf",
    "liberation_sans": "liberation_sans.ttf",
    "liberation_serif": "liberation_serif.ttf",
}

DEFAULT_FONT_KEY = "dejavu_sans"

# In-memory font cache: (font_key, size_int) -> ImageFont
_font_cache: Dict[Tuple[str, int], ImageFont.FreeTypeFont] = {}


def get_font(font_key: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font at a specific integer point size.
    Falls back to DejaVu Sans (Unicode capable) if font_key is unknown or missing.
    """
    target_key = font_key if font_key in ALLOWED_FONT_KEYS else DEFAULT_FONT_KEY
    size_int = max(8, int(round(size)))
    cache_key = (target_key, size_int)

    if cache_key in _font_cache:
        return _font_cache[cache_key]

    font_file = FONTS_DIR / ALLOWED_FONT_KEYS[target_key]
    if font_file.exists():
        try:
            font = ImageFont.truetype(str(font_file), size_int)
            _font_cache[cache_key] = font
            return font
        except Exception:
            pass

    # Fallback to default DejaVu Sans
    fallback_file = FONTS_DIR / ALLOWED_FONT_KEYS[DEFAULT_FONT_KEY]
    if fallback_file.exists():
        try:
            font = ImageFont.truetype(str(fallback_file), size_int)
            _font_cache[cache_key] = font
            return font
        except Exception:
            pass

    # System fallback
    return ImageFont.load_default()
