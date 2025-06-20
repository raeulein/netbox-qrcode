"""
HTML-Fragment → Pillow-Image

Funktioniert mit *allen* WeasyPrint-Versionen:
•  ≤ 52       :  HTML.write_png()
•  53 – 57    :  Document.write_png()
•  ≥ 58       :  PDF-Umweg + pypdfium2.render_topil()
"""

from io import BytesIO
from typing import Tuple
from PIL import Image


def render_html_to_png(html: str, width_px: int, height_px: int) -> Image.Image:
    from weasyprint import HTML, CSS                       # Laufzeit-Import

    css = CSS(string="""
        @page { size: auto; margin: 0 }
        html, body { margin: 0; padding: 0 }
    """)


    html_obj = HTML(string=html)

    # ──────────────────────────────────────────────────────────────
    try:
        import pypdfium2 as pdfium              # reines pip-Rad
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "WeasyPrint ≥58 liefert nur noch PDF.  "
            "Installiere pypdfium2 (`pip install pypdfium2`) "
            "oder setze WeasyPrint <58 ein."
        ) from exc

    pdf_bytes = html_obj.write_pdf(stylesheets=[css])
    pdf = pdfium.PdfDocument(pdf_bytes)

    page = pdf.get_page(0)
    pdf_w, pdf_h = page.get_size()  # ← tatsächliche Breite/Höhe
    scale = width_px / pdf_w        # skaliere auf gewünschte Druckbreite

    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()

    return pil_image