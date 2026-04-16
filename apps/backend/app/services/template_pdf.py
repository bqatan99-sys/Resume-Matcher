"""Template-backed PDF generation using macOS Quick Look previews."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from pathlib import Path
from tempfile import mkdtemp

from app.errors import PDFRenderError
from app.pdf import render_resume_pdf


async def render_template_docx_pdf(
    docx_bytes: bytes,
    *,
    filename_stem: str,
    page_size: str = "A4",
) -> bytes:
    """Render a DOCX file to PDF using Quick Look preview HTML as the source."""

    temp_dir = Path(mkdtemp(prefix="resume-template-pdf-"))
    try:
        def _build_preview() -> str:
            safe_stem = filename_stem.strip() or "resume"
            docx_path = temp_dir / f"{safe_stem}.docx"
            docx_path.write_bytes(docx_bytes)

            result = subprocess.run(
                ["qlmanage", "-o", str(temp_dir), "-p", str(docx_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise PDFRenderError(
                    "Quick Look could not prepare a PDF preview from the template-backed DOCX."
                )

            preview_html = temp_dir / f"{docx_path.name}.qlpreview" / "Preview.html"
            if not preview_html.exists():
                raise PDFRenderError(
                    "Quick Look did not produce a preview for the template-backed DOCX."
                )

            return preview_html.as_uri()

        preview_url = await asyncio.to_thread(_build_preview)
        return await render_resume_pdf(
            preview_url,
            page_size,
            selector="body",
            margins={"top": 0, "right": 0, "bottom": 0, "left": 0},
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
