"""
PDF Certificate Generator Engine.

================================================================================
ARCHITECTURE & DESIGN PRINCIPLES:
================================================================================
1. Zero HTTP & Zero DB Knowledge:
   This module operates purely on in-memory recipient strings, template layout configs,
   and optional storage interfaces for loading custom background images.

2. Unified Renderer:
   One single renderer handles both Builtin and Custom templates based on layout snapshots:
   - Custom Templates: Renders full-page background image, then overlays text at percentage Y coords.
   - Builtin Templates: Renders background fill, vector frames/borders, title typography, accent dividers,
     and recipient text.

3. Typography & Long String Handling:
   - Dynamic Auto-Shrinking: Recipient names and course titles automatically reduce font size if they
     exceed printable canvas width, preventing clipping or overflow.
   - Unicode / Multi-language Support: Registers DejaVuSans TTF font when available, with clean fallback.
================================================================================
"""

import io
import os
from datetime import date
from typing import Dict, Any, Union, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.services.template_registry import get_template_config
from app.services.storage import StorageInterface


# A4 Landscape Dimensions in Points (72 points per inch)
PAGE_WIDTH, PAGE_HEIGHT = landscape(A4)  # 841.89 x 595.27 pt
MAX_TEXT_WIDTH = PAGE_WIDTH - 120.0     # 721.89 pt max width for text

# Register Unicode Font if available on system
DEFAULT_FONT_NAME = "Helvetica"
UNICODE_FONT_NAME = "Helvetica"

def _setup_fonts() -> str:
    """Attempts to register DejaVuSans for full Unicode/Non-Latin character support."""
    global UNICODE_FONT_NAME
    possible_ttf_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\dejavusans.ttf",
    ]
    for p in possible_ttf_paths:
        if os.path.exists(p):
            try:
                pdfmetrics.registerFont(TTFont("DejaVuSans", p))
                UNICODE_FONT_NAME = "DejaVuSans"
                return "DejaVuSans"
            except Exception:
                pass
    return "Helvetica"

# Initialize font setup
_setup_fonts()


def _extract_template_info(template: Union[Dict[str, Any], Any]) -> Dict[str, Any]:
    """Extract template properties uniformly whether dict or model instance."""
    if isinstance(template, dict):
        kind = template.get("kind", "builtin")
        key = template.get("key", "classic")
        bg_path = template.get("background_path")
        layout = template.get("layout", {})
    else:
        kind = getattr(template, "kind", "builtin")
        key = getattr(template, "key", "classic")
        bg_path = getattr(template, "background_path", None)
        layout = getattr(template, "layout", {})

    if not isinstance(layout, dict):
        layout = getattr(layout, "__dict__", {})

    return {
        "kind": kind,
        "key": key or "classic",
        "background_path": bg_path,
        "layout": layout,
    }


def draw_auto_shrunk_text(
    pdf_canvas: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    font_name: str,
    initial_size: float,
    max_width: float = MAX_TEXT_WIDTH,
    min_size: float = 12.0,
    color_hex: str = "#000000",
) -> float:
    """
    Draw text horizontally centered at (x, y), dynamically shrinking font size
    if width exceeds max_width to ensure text never leaves the page.
    """
    if not text:
        return initial_size

    # Choose registered font if font_name is generic and Unicode font is active
    active_font = font_name
    if UNICODE_FONT_NAME == "DejaVuSans" and font_name in ("Helvetica", "Times-Roman"):
        active_font = UNICODE_FONT_NAME

    current_size = initial_size
    while current_size > min_size:
        try:
            text_width = pdf_canvas.stringWidth(text, active_font, current_size)
        except Exception:
            # Fallback font if glyph missing
            active_font = DEFAULT_FONT_NAME
            text_width = pdf_canvas.stringWidth(text, active_font, current_size)

        if text_width <= max_width:
            break
        current_size -= 1.0

    pdf_canvas.setFont(active_font, current_size)
    pdf_canvas.setFillColor(colors.HexColor(color_hex))
    pdf_canvas.drawCentredString(x, y, text)
    return current_size


def _draw_builtin_borders(pdf_canvas: canvas.Canvas, config: Dict[str, Any]):
    """Render background color and vector borders for built-in templates."""
    colors_cfg = config.get("colors", {})
    border_cfg = config.get("border", {})

    bg_color = colors_cfg.get("background", "#FFFFFF")
    primary_color = colors_cfg.get("primary", "#000000")
    accent_color = colors_cfg.get("accent", "#C59B27")
    border_color = colors_cfg.get("border", "#C59B27")
    inner_border_color = colors_cfg.get("inner_border")

    # Draw full page background fill
    pdf_canvas.setFillColor(colors.HexColor(bg_color))
    pdf_canvas.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)

    style = border_cfg.get("style", "single")
    outer_m = border_cfg.get("outer_margin", 24)
    width = border_cfg.get("width", 2)

    if style in ("gold_double", "double"):
        inner_m = border_cfg.get("inner_margin", 32)
        # Outer Border
        pdf_canvas.setStrokeColor(colors.HexColor(border_color))
        pdf_canvas.setLineWidth(width)
        pdf_canvas.rect(
            outer_m,
            outer_m,
            PAGE_WIDTH - 2 * outer_m,
            PAGE_HEIGHT - 2 * outer_m,
            fill=0,
            stroke=1,
        )

        # Inner Border
        if inner_border_color:
            pdf_canvas.setStrokeColor(colors.HexColor(inner_border_color))
        pdf_canvas.setLineWidth(1)
        pdf_canvas.rect(
            inner_m,
            inner_m,
            PAGE_WIDTH - 2 * inner_m,
            PAGE_HEIGHT - 2 * inner_m,
            fill=0,
            stroke=1,
        )

    elif style == "single_with_accent_bar":
        # Outer thin border
        pdf_canvas.setStrokeColor(colors.HexColor(border_color))
        pdf_canvas.setLineWidth(width)
        pdf_canvas.rect(
            outer_m,
            outer_m,
            PAGE_WIDTH - 2 * outer_m,
            PAGE_HEIGHT - 2 * outer_m,
            fill=0,
            stroke=1,
        )
        # Top accent color bar
        pdf_canvas.setFillColor(colors.HexColor(accent_color))
        pdf_canvas.rect(
            outer_m,
            PAGE_HEIGHT - outer_m - 8,
            PAGE_WIDTH - 2 * outer_m,
            8,
            fill=1,
            stroke=0,
        )

    elif style == "tech_frame":
        # Dark tech frame with corner highlights
        pdf_canvas.setStrokeColor(colors.HexColor(accent_color))
        pdf_canvas.setLineWidth(width)
        pdf_canvas.rect(
            outer_m,
            outer_m,
            PAGE_WIDTH - 2 * outer_m,
            PAGE_HEIGHT - 2 * outer_m,
            fill=0,
            stroke=1,
        )
        # Draw tech corner squares
        pdf_canvas.setFillColor(colors.HexColor(accent_color))
        cs = 10
        pdf_canvas.rect(outer_m - cs / 2, outer_m - cs / 2, cs, cs, fill=1, stroke=0)
        pdf_canvas.rect(PAGE_WIDTH - outer_m - cs / 2, outer_m - cs / 2, cs, cs, fill=1, stroke=0)
        pdf_canvas.rect(outer_m - cs / 2, PAGE_HEIGHT - outer_m - cs / 2, cs, cs, fill=1, stroke=0)
        pdf_canvas.rect(PAGE_WIDTH - outer_m - cs / 2, PAGE_HEIGHT - outer_m - cs / 2, cs, cs, fill=1, stroke=0)

    else:  # Minimal / Single
        pdf_canvas.setStrokeColor(colors.HexColor(border_color))
        pdf_canvas.setLineWidth(width)
        pdf_canvas.rect(
            outer_m,
            outer_m,
            PAGE_WIDTH - 2 * outer_m,
            PAGE_HEIGHT - 2 * outer_m,
            fill=0,
            stroke=1,
        )


def render_certificate(
    recipient_name: str,
    course_title: str,
    issued_date: Union[date, str],
    organization_name: Optional[str],
    template: Union[Dict[str, Any], Any],
    storage: Optional[StorageInterface] = None,
) -> bytes:
    """
    Render a single PDF certificate as bytes.

    Args:
        recipient_name: Full name of recipient
        course_title: Title of course or achievement
        issued_date: Date object or string (YYYY-MM-DD)
        organization_name: Optional organization or issuer name
        template: Template layout dict or Template model instance
        storage: Optional storage backend to load custom background images

    Returns:
        bytes: Output PDF binary content
    """
    buffer = io.BytesIO()
    pdf_canvas = canvas.Canvas(buffer, pagesize=landscape(A4))

    tpl_info = _extract_template_info(template)
    kind = tpl_info["kind"]
    key = tpl_info["key"]
    bg_path = tpl_info["background_path"]
    layout_coords = tpl_info["layout"] or {}

    # Get style config for built-ins
    config = get_template_config(key)

    # 1. Draw Background
    if kind == "custom" and bg_path:
        if storage and storage.exists(bg_path):
            try:
                image_bytes = storage.read(bg_path)
                image_stream = io.BytesIO(image_bytes)
                pdf_canvas.drawImage(
                    image_stream,
                    0,
                    0,
                    width=PAGE_WIDTH,
                    height=PAGE_HEIGHT,
                    preserveAspectRatio=False,
                )
            except Exception:
                _draw_builtin_borders(pdf_canvas, config)
        else:
            _draw_builtin_borders(pdf_canvas, config)
    else:
        _draw_builtin_borders(pdf_canvas, config)

    # 2. Extract layout Y positions (expressed as percentage 0..100 from top of page)
    # Default layout positions if not specified in snapshot:
    default_layout = config.get("layout", {"name_y": 45.0, "course_y": 60.0, "date_y": 78.0})
    name_y_pct = layout_coords.get("name_y", default_layout.get("name_y", 45.0))
    course_y_pct = layout_coords.get("course_y", default_layout.get("course_y", 60.0))
    date_y_pct = layout_coords.get("date_y", default_layout.get("date_y", 78.0))

    # Convert Top-Down Percentage Y to ReportLab Bottom-Up Canvas Points
    center_x = PAGE_WIDTH / 2.0
    name_y_pt = PAGE_HEIGHT * (1.0 - name_y_pct / 100.0)
    course_y_pt = PAGE_HEIGHT * (1.0 - course_y_pct / 100.0)
    date_y_pt = PAGE_HEIGHT * (1.0 - date_y_pct / 100.0)

    colors_cfg = config.get("colors", {})
    primary_hex = colors_cfg.get("primary", "#1A2530")
    secondary_hex = colors_cfg.get("secondary", "#5A6B7C")
    accent_hex = colors_cfg.get("accent", "#C59B27")

    fonts_cfg = config.get("fonts", {})
    header_font = fonts_cfg.get("header", "Helvetica-Bold")
    name_font = fonts_cfg.get("name", "Helvetica-Bold")
    course_font = fonts_cfg.get("course", "Helvetica-Bold")
    date_font = fonts_cfg.get("date", "Helvetica")

    # 3. Draw Builtin Header Typography & Labels (if not custom)
    if kind == "builtin":
        header_title = config.get("header_title", "CERTIFICATE OF COMPLETION")
        subtitle = config.get("subtitle", "PROUDLY PRESENTED TO")
        course_label = config.get("for_course_label", "FOR SUCCESSFUL COMPLETION OF")

        # Header Title (Top area ~18% from top)
        header_y_pt = PAGE_HEIGHT * 0.82
        draw_auto_shrunk_text(
            pdf_canvas,
            header_title,
            center_x,
            header_y_pt,
            header_font,
            initial_size=26,
            max_width=MAX_TEXT_WIDTH,
            color_hex=accent_hex if key in ("classic", "bold", "elegant") else primary_hex,
        )

        # Subtitle above recipient name
        draw_auto_shrunk_text(
            pdf_canvas,
            subtitle,
            center_x,
            name_y_pt + 32.0,
            date_font,
            initial_size=11,
            max_width=MAX_TEXT_WIDTH,
            color_hex=secondary_hex,
        )

        # Course label above course title
        draw_auto_shrunk_text(
            pdf_canvas,
            course_label,
            center_x,
            course_y_pt + 24.0,
            date_font,
            initial_size=10,
            max_width=MAX_TEXT_WIDTH,
            color_hex=secondary_hex,
        )

        # Decorative Accent Line below Recipient Name
        if config.get("decorations", {}).get("accent_line", True):
            pdf_canvas.setStrokeColor(colors.HexColor(accent_hex))
            pdf_canvas.setLineWidth(1.5)
            pdf_canvas.line(center_x - 140, name_y_pt - 10, center_x + 140, name_y_pt - 10)

    # 4. Draw Recipient Name (Auto-shrinks if long)
    draw_auto_shrunk_text(
        pdf_canvas,
        recipient_name,
        center_x,
        name_y_pt,
        name_font,
        initial_size=34 if kind == "builtin" else 32,
        max_width=MAX_TEXT_WIDTH,
        min_size=14,
        color_hex=primary_hex,
    )

    # 5. Draw Course Title / Achievement (Auto-shrinks if long)
    display_title = course_title
    if organization_name:
        display_title = f"{course_title} — {organization_name}"

    draw_auto_shrunk_text(
        pdf_canvas,
        display_title,
        center_x,
        course_y_pt,
        course_font,
        initial_size=20 if kind == "builtin" else 18,
        max_width=MAX_TEXT_WIDTH,
        min_size=11,
        color_hex=primary_hex,
    )

    # 6. Draw Date
    date_str = str(issued_date)
    draw_auto_shrunk_text(
        pdf_canvas,
        f"Issued Date: {date_str}",
        center_x,
        date_y_pt,
        date_font,
        initial_size=12,
        max_width=MAX_TEXT_WIDTH,
        min_size=9,
        color_hex=secondary_hex,
    )

    # Save page and return buffer bytes
    pdf_canvas.showPage()
    pdf_canvas.save()
    return buffer.getvalue()


def render_preview(
    template: Union[Dict[str, Any], Any],
    storage: Optional[StorageInterface] = None,
) -> bytes:
    """Render a sample preview PDF using generic recipient data."""
    return render_certificate(
        recipient_name="Jane Doe",
        course_title="Advanced Software Architecture & Design",
        issued_date=date.today().strftime("%Y-%m-%d"),
        organization_name="Global Tech Institute",
        template=template,
        storage=storage,
    )
