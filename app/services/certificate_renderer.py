"""
Pillow Certificate Rendering Engine.

Replaces ReportLab with a unified Pillow drawing pipeline:
- Pixel-precise canvas rendering for both Custom backgrounds and 5 Builtin styles.
- Custom templates: uses native resolution background image, auto-shrinks recipient name,
  anchors at (name_x%, name_y%) using 'mm', and draws zero extraneous elements.
- Strict error handling: raises FileNotFoundError/ValueError if custom background is missing.
- Multi-format encoding: PNG (compress_level 3), JPG (quality 92), PDF (Pillow PDF save with resolution).
"""

import io
from typing import Dict, Any, Optional, Union
from PIL import Image, ImageDraw, ImageColor

from app.services.font_registry import get_font, DEFAULT_FONT_KEY
from app.services.storage import StorageInterface, LocalStorage
from app.services.template_registry import BUILTIN_STYLE_CONFIGS, get_template_config

BUILTIN_CANVAS_WIDTH = 3508
BUILTIN_CANVAS_HEIGHT = 2480


def encode_image(img: Image.Image, output_format: str = "pdf") -> bytes:
    """
    Encode Pillow Image into requested format binary bytes.
    - png: compress_level 3
    - jpg: RGB quality 92
    - pdf: Pillow PDF save with resolution so physical page matches image
    """
    fmt = (output_format or "pdf").lower()
    buffer = io.BytesIO()

    if fmt == "png":
        img.save(buffer, format="PNG", compress_level=3)
    elif fmt in ("jpg", "jpeg"):
        rgb_img = img.convert("RGB") if img.mode != "RGB" else img
        rgb_img.save(buffer, format="JPEG", quality=92)
    else:  # pdf
        rgb_img = img.convert("RGB") if img.mode != "RGB" else img
        # 300 DPI standard resolution
        dpi = img.info.get("dpi", (300, 300))
        dpi_val = float(dpi[0]) if isinstance(dpi, tuple) else float(dpi)
        if dpi_val <= 0:
            dpi_val = 300.0
        rgb_img.save(buffer, format="PDF", resolution=dpi_val, quality=95)

    return buffer.getvalue()


def _draw_builtin_canvas(
    img: Image.Image,
    name: str,
    job_fields: Dict[str, Any],
    config: Dict[str, Any],
) -> None:
    """Draw built-in style elements (borders, titles, text) on high-res 3508x2480 canvas."""
    draw = ImageDraw.Draw(img)
    W, H = img.size
    cx = W / 2.0

    colors_cfg = config.get("colors", {})
    border_cfg = config.get("border", {})
    fonts_cfg = config.get("fonts", {})

    primary_hex = colors_cfg.get("primary", "#1A2530")
    secondary_hex = colors_cfg.get("secondary", "#5A6B7C")
    accent_hex = colors_cfg.get("accent", "#C59B27")
    border_hex = colors_cfg.get("border", "#C59B27")
    inner_border_hex = colors_cfg.get("inner_border")

    border_style = border_cfg.get("style", "single")
    outer_m = int(round(border_cfg.get("outer_margin", 24) * (W / 842.0)))
    border_w = max(4, int(round(border_cfg.get("width", 2) * (W / 842.0))))

    # 1. Draw Borders
    if border_style == "gold_double":
        inner_m = int(round(border_cfg.get("inner_margin", 32) * (W / 842.0)))
        draw.rectangle([outer_m, outer_m, W - outer_m, H - outer_m], outline=border_hex, width=border_w)
        if inner_border_hex:
            draw.rectangle([inner_m, inner_m, W - inner_m, H - inner_m], outline=inner_border_hex, width=max(2, border_w // 2))

    elif border_style == "single_with_accent_bar":
        draw.rectangle([outer_m, outer_m, W - outer_m, H - outer_m], outline=border_hex, width=border_w)
        bar_h = int(round(24 * (H / 595.0)))
        draw.rectangle([outer_m, outer_m, W - outer_m, outer_m + bar_h], fill=accent_hex)

    elif border_style == "tech_frame":
        draw.rectangle([outer_m, outer_m, W - outer_m, H - outer_m], outline=accent_hex, width=border_w)
        cs = int(round(40 * (W / 842.0)))
        draw.rectangle([outer_m - cs // 2, outer_m - cs // 2, outer_m + cs // 2, outer_m + cs // 2], fill=accent_hex)
        draw.rectangle([W - outer_m - cs // 2, outer_m - cs // 2, W - outer_m + cs // 2, outer_m + cs // 2], fill=accent_hex)
        draw.rectangle([outer_m - cs // 2, H - outer_m - cs // 2, outer_m + cs // 2, H - outer_m + cs // 2], fill=accent_hex)
        draw.rectangle([W - outer_m - cs // 2, H - outer_m - cs // 2, W - outer_m + cs // 2, H - outer_m + cs // 2], fill=accent_hex)

    else:
        draw.rectangle([outer_m, outer_m, W - outer_m, H - outer_m], outline=border_hex, width=border_w)

    # 2. Extract Field Values
    title = str(job_fields.get("title") or "Certificate of Achievement")
    org_name = job_fields.get("organization_name")
    issued_date = str(job_fields.get("issued_date") or "")

    font_key = fonts_cfg.get("name_font", "dejavu_serif" if config.get("key") in ("classic", "elegant") else "dejavu_sans")

    # Header Title
    header_title = config.get("header_title", "CERTIFICATE OF ACHIEVEMENT")
    f_header = get_font(font_key, int(round(72 * (H / 595.0))))
    draw.text((cx, H * 0.18), header_title, fill=accent_hex if config.get("key") in ("classic", "bold", "elegant") else primary_hex, font=f_header, anchor="mm")

    # Subtitle
    subtitle = config.get("subtitle", "THIS IS PROUDLY PRESENTED TO")
    f_sub = get_font(font_key, int(round(28 * (H / 595.0))))
    draw.text((cx, H * 0.32), subtitle, fill=secondary_hex, font=f_sub, anchor="mm")

    # Recipient Name with Auto-Shrink
    max_w = W * 0.75
    f_size_name = int(round(110 * (H / 595.0)))
    while f_size_name > 24:
        f_name = get_font(font_key, f_size_name)
        bbox = draw.textbbox((0, 0), name, font=f_name, anchor="mm")
        if (bbox[2] - bbox[0]) <= max_w:
            break
        f_size_name -= 4
    draw.text((cx, H * 0.45), name, fill=primary_hex, font=f_name, anchor="mm")

    # Accent divider line below name
    if config.get("decorations", {}).get("accent_line", True):
        line_w = int(round(350 * (W / 842.0)))
        line_y = int(round(H * 0.52))
        draw.line([cx - line_w, line_y, cx + line_w, line_y], fill=accent_hex, width=max(2, border_w // 2))

    # Course Label & Title
    course_label = config.get("for_course_label", "FOR SUCCESSFUL COMPLETION OF")
    draw.text((cx, H * 0.58), course_label, fill=secondary_hex, font=f_sub, anchor="mm")

    display_title = title
    if org_name:
        display_title = f"{title} — {org_name}"

    f_size_title = int(round(56 * (H / 595.0)))
    while f_size_title > 20:
        f_title = get_font(font_key, f_size_title)
        bbox = draw.textbbox((0, 0), display_title, font=f_title, anchor="mm")
        if (bbox[2] - bbox[0]) <= max_w:
            break
        f_size_title -= 3
    draw.text((cx, H * 0.66), display_title, fill=primary_hex, font=f_title, anchor="mm")

    # Date
    if issued_date:
        f_date = get_font(font_key, int(round(32 * (H / 595.0))))
        draw.text((cx, H * 0.78), f"Issued Date: {issued_date}", fill=secondary_hex, font=f_date, anchor="mm")


def render_certificate(
    name: str,
    template_snapshot: Dict[str, Any],
    job_fields: Optional[Dict[str, Any]] = None,
    output_format: str = "pdf",
    storage: Optional[StorageInterface] = None,
    preloaded_base_image: Optional[Image.Image] = None,
) -> bytes:
    """
    Render an individual certificate using Pillow.

    Args:
        name: Recipient full name
        template_snapshot: Frozen snapshot dict from job (kind, background_path, layout, required_fields)
        job_fields: Dict of job fields: title, organization_name, issued_date
        output_format: "pdf", "png", or "jpg"
        storage: Optional storage interface to read custom background
        preloaded_base_image: Optional pre-loaded base Image.Image for worker performance optimization

    Returns:
        bytes: Binary encoded certificate content (PDF, PNG, or JPG)
    """
    if job_fields is None:
        job_fields = {}
    if storage is None:
        storage = LocalStorage()

    kind = template_snapshot.get("kind", "builtin")
    layout = template_snapshot.get("layout") or {}
    bg_path = template_snapshot.get("background_path")

    # =========================================================================
    # 1. CUSTOM TEMPLATE RENDERING
    # =========================================================================
    if kind == "custom":
        if preloaded_base_image is not None:
            img = preloaded_base_image.copy()
        else:
            if not bg_path:
                raise ValueError("Custom template is missing background_path.")
            if not storage.exists(bg_path):
                raise FileNotFoundError(f"Custom template background image '{bg_path}' not found in storage.")
            try:
                bg_bytes = storage.read(bg_path)
                loaded_img = Image.open(io.BytesIO(bg_bytes))
                if loaded_img.mode not in ("RGB", "RGBA"):
                    loaded_img = loaded_img.convert("RGBA" if "A" in loaded_img.mode else "RGB")
                img = loaded_img.copy()
            except Exception as e:
                raise ValueError(f"Failed to open custom background image '{bg_path}': {str(e)}")

        W, H = img.size
        draw = ImageDraw.Draw(img)

        # Coordinates & Layout specs
        name_x_pct = float(layout.get("name_x", 50.0))
        name_y_pct = float(layout.get("name_y", 57.0))
        font_key = str(layout.get("font", DEFAULT_FONT_KEY)).strip().lower()
        font_size_pct = float(layout.get("font_size_pct", 5.0))
        color_hex = str(layout.get("color", "#1A202C")).strip()
        max_width_pct = float(layout.get("max_width_pct", 70.0))

        X = W * (name_x_pct / 100.0)
        Y = H * (name_y_pct / 100.0)
        max_allowed_w = W * (max_width_pct / 100.0)

        # Initial font size as percentage of image height
        initial_font_size = max(10, int(round(H * (font_size_pct / 100.0))))
        min_font_size = 8

        # Auto-shrink loop until text width <= max_width_pct of image width
        current_font_size = initial_font_size
        while current_font_size > min_font_size:
            fnt = get_font(font_key, current_font_size)
            bbox = draw.textbbox((0, 0), name, font=fnt, anchor="mm")
            w = bbox[2] - bbox[0]
            if w <= max_allowed_w:
                break
            current_font_size -= 1

        final_font = get_font(font_key, current_font_size)
        # Draw recipient name centered using anchor "mm" (middle middle)
        draw.text((X, Y), name, fill=color_hex, font=final_font, anchor="mm")

        # Do NOT draw anything else on top of custom background
        return encode_image(img, output_format)

    # =========================================================================
    # 2. BUILTIN TEMPLATE RENDERING
    # =========================================================================
    key = template_snapshot.get("key", "classic")
    config = get_template_config(key)
    bg_color = config.get("colors", {}).get("background", "#FFFDF7")

    if preloaded_base_image is not None:
        img = preloaded_base_image.copy()
    else:
        img = Image.new("RGB", (BUILTIN_CANVAS_WIDTH, BUILTIN_CANVAS_HEIGHT), color=bg_color)

    _draw_builtin_canvas(img, name, job_fields, config)
    return encode_image(img, output_format)


def render_preview(
    template_snapshot: Dict[str, Any],
    sample_name: str = "Jane Doe",
    storage: Optional[StorageInterface] = None,
) -> bytes:
    """
    Render exact live preview as a lossless PNG using the exact same rendering pipeline.
    """
    job_fields = {
        "title": "Certificate of Completion",
        "organization_name": "Acme Institute of Technology",
        "issued_date": "2026-10-12",
    }
    return render_certificate(
        name=sample_name,
        template_snapshot=template_snapshot,
        job_fields=job_fields,
        output_format="png",
        storage=storage,
    )
