"""
Registry of Built-in Template Configurations.

Provides styling, color palettes, typography specs, border rules, and default percentage
layouts for the 5 built-in certificate styles:
- Classic: Gold frame & traditional serif aesthetics
- Modern: Clean sans-serif, vibrant indigo/teal accents, minimalist divider lines
- Minimal: Ultra-clean spacing, dark slate typography, subtle borders
- Elegant: Deep navy & gold accents, sophisticated serif typography
- Bold: Vibrant tech styling, high-contrast dark accents, bold headers
"""

from typing import Dict, Any

BUILTIN_STYLE_CONFIGS: Dict[str, Dict[str, Any]] = {
    "classic": {
        "key": "classic",
        "name": "Classic Gold",
        "header_title": "CERTIFICATE OF ACHIEVEMENT",
        "subtitle": "THIS IS PROUDLY PRESENTED TO",
        "for_course_label": "FOR SUCCESSFUL COMPLETION OF",
        "layout": {"name_y": 45.0, "course_y": 62.0, "date_y": 78.0},
        "colors": {
            "background": "#FFFDF7",  # Cream
            "primary": "#1A2530",     # Dark Slate
            "secondary": "#5A6B7C",   # Muted Slate
            "accent": "#C59B27",      # Classic Gold
            "border": "#C59B27",      # Gold Border
            "inner_border": "#1A2530",
        },
        "border": {
            "style": "gold_double",
            "outer_margin": 24,
            "inner_margin": 32,
            "width": 3,
        },
        "fonts": {
            "header": "Times-Bold",
            "subtitle": "Helvetica",
            "name": "Times-BoldItalic",
            "course": "Times-Bold",
            "date": "Helvetica",
        },
        "decorations": {
            "accent_line": True,
            "corner_accents": True,
        },
    },
    "modern": {
        "key": "modern",
        "name": "Modern Minimal",
        "header_title": "CERTIFICATE OF COMPLETION",
        "subtitle": "PROUDLY PRESENTED TO",
        "for_course_label": "HAS SUCCESSFULLY COMPLETED THE COURSE",
        "layout": {"name_y": 42.0, "course_y": 60.0, "date_y": 76.0},
        "colors": {
            "background": "#F8FAFC",  # Off-white / Cool Grey
            "primary": "#0F172A",     # Slate 900
            "secondary": "#475569",   # Slate 600
            "accent": "#2563EB",      # Royal Blue
            "border": "#E2E8F0",      # Slate 200
            "inner_border": "#2563EB",
        },
        "border": {
            "style": "single_with_accent_bar",
            "outer_margin": 20,
            "width": 2,
        },
        "fonts": {
            "header": "Helvetica-Bold",
            "subtitle": "Helvetica",
            "name": "Helvetica-Bold",
            "course": "Helvetica-Bold",
            "date": "Helvetica",
        },
        "decorations": {
            "accent_line": True,
            "top_accent_bar": True,
        },
    },
    "minimal": {
        "key": "minimal",
        "name": "Minimal Clean",
        "header_title": "CERTIFICATE OF EXCELLENCE",
        "subtitle": "AWARDED TO",
        "for_course_label": "IN RECOGNITION OF COMPLETING",
        "layout": {"name_y": 45.0, "course_y": 60.0, "date_y": 78.0},
        "colors": {
            "background": "#FFFFFF",  # Pure White
            "primary": "#111827",     # Gray 900
            "secondary": "#6B7280",   # Gray 500
            "accent": "#111827",      # Monochromatic Dark
            "border": "#E5E7EB",      # Gray 200
            "inner_border": None,
        },
        "border": {
            "style": "minimal_thin",
            "outer_margin": 30,
            "width": 1,
        },
        "fonts": {
            "header": "Helvetica-Bold",
            "subtitle": "Helvetica",
            "name": "Helvetica-Bold",
            "course": "Helvetica",
            "date": "Helvetica",
        },
        "decorations": {
            "accent_line": False,
        },
    },
    "elegant": {
        "key": "elegant",
        "name": "Elegant Navy",
        "header_title": "CERTIFICATE OF APPRECIATION",
        "subtitle": "THIS CERTIFICATE IS IS GRANTED TO",
        "for_course_label": "FOR SUCCESSFUL PARTICIPATION IN",
        "layout": {"name_y": 38.0, "course_y": 55.0, "date_y": 72.0},
        "colors": {
            "background": "#FAF9F6",  # Warm Alabaster
            "primary": "#0A192F",     # Deep Navy
            "secondary": "#4A5568",   # Charcoal
            "accent": "#D4AF37",      # Soft Metallic Gold
            "border": "#0A192F",      # Navy Outer
            "inner_border": "#D4AF37",# Gold Inner
        },
        "border": {
            "style": "gold_double",
            "outer_margin": 25,
            "inner_margin": 32,
            "width": 2,
        },
        "fonts": {
            "header": "Times-Bold",
            "subtitle": "Times-Italic",
            "name": "Times-BoldItalic",
            "course": "Times-Bold",
            "date": "Times-Roman",
        },
        "decorations": {
            "accent_line": True,
            "ornament_star": True,
        },
    },
    "bold": {
        "key": "bold",
        "name": "Bold Tech",
        "header_title": "CERTIFICATE OF ACHIEVEMENT",
        "subtitle": "PRESENTED TO",
        "for_course_label": "FOR MASTERING THE COURSE",
        "layout": {"name_y": 44.0, "course_y": 62.0, "date_y": 80.0},
        "colors": {
            "background": "#0F172A",  # Dark Mode Background
            "primary": "#F8FAFC",     # Bright White
            "secondary": "#94A3B8",   # Slate 400
            "accent": "#06B6D4",      # Vibrant Cyan
            "border": "#06B6D4",      # Cyan Frame
            "inner_border": "#1E293B",
        },
        "border": {
            "style": "tech_frame",
            "outer_margin": 20,
            "width": 3,
        },
        "fonts": {
            "header": "Helvetica-Bold",
            "subtitle": "Helvetica-Bold",
            "name": "Helvetica-Bold",
            "course": "Helvetica-Bold",
            "date": "Helvetica",
        },
        "decorations": {
            "accent_line": True,
            "cyan_accents": True,
        },
    },
}


def get_template_config(key: str) -> Dict[str, Any]:
    """Retrieve builtin style configuration by key (defaults to 'classic' if not found)."""
    return BUILTIN_STYLE_CONFIGS.get(key, BUILTIN_STYLE_CONFIGS["classic"])
