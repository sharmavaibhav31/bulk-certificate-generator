"""
Legacy PDF Generator module stub.
Forwards all calls to the unified Pillow certificate rendering engine.
Zero ReportLab imports.
"""

from app.services.certificate_renderer import render_certificate, render_preview

__all__ = ["render_certificate", "render_preview"]
