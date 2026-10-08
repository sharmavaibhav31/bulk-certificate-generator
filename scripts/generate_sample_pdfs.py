"""
Sample PDF Generator Script.

Renders sample PDFs for all 5 built-in certificate templates ('classic', 'modern',
'minimal', 'elegant', 'bold') and saves them to a 'samples/' directory.
"""

import os
from pathlib import Path
from app.services.pdf_generator import render_certificate, render_preview
from app.services.template_registry import BUILTIN_STYLE_CONFIGS


def generate_all_samples():
    output_dir = Path("samples")
    output_dir.mkdir(exist_ok=True)

    print("Generating sample PDFs for all 5 builtin templates...")

    for key, config in BUILTIN_STYLE_CONFIGS.items():
        template_snapshot = {
            "kind": "builtin",
            "key": key,
            "layout": config["layout"],
        }

        # Generate sample PDF bytes
        pdf_bytes = render_preview(template_snapshot)

        output_path = output_dir / f"sample_{key}.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)

        print(f"  [+] Saved {output_path} ({len(pdf_bytes)} bytes)")

    print(f"\nSuccessfully generated {len(BUILTIN_STYLE_CONFIGS)} sample PDFs in '{output_dir.resolve()}'")


if __name__ == "__main__":
    generate_all_samples()
