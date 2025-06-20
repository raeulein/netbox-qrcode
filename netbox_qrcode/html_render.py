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


def render_html_to_png(html: str, width_px: int, height_px: int, want_pdf=False) -> Image.Image:
    from weasyprint import HTML, CSS                       # Laufzeit-Import

    '''css = CSS(
        string=f"""
            @page {{
                
                size: {width_px}px {height_px}px;
                margin: 0;
                orientation: landscape;
            }}
            html, body {{
                width: {width_px}px;
                height: {height_px}px;
                margin: 0;
            }}
        """
    )'''
    css = CSS(
        string=f"""
            @page {{
                size: 1000cm 100cm;
                margin: 0;
            }}
            html, body {{
                width: 1000px;
                height: 100px;
                margin: 0;
            }}
        """
    )

    # ──────────────────────────────────────────────────────────────
    try:
        import pypdfium2 as pdfium              # reines pip-Rad
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "WeasyPrint ≥58 liefert nur noch PDF.  "
            "Installiere pypdfium2 (`pip install pypdfium2`) "
            "oder setze WeasyPrint <58 ein."
        ) from exc

    # 1. Rendern mit Stylesheet
    doc = HTML(string=html).render(stylesheets=[css])

    # 2. PDF daraus bauen
    pdf_bytes = doc.write_pdf()

    pdf = pdfium.PdfDocument(pdf_bytes)
    if want_pdf:
        return pdf_bytes  # PDF zurückgeben, wenn gewünscht

    page = pdf.get_page(0)
    pdf_w, pdf_h = page.get_size()  # ← tatsächliche Breite/Höhe
    scale = width_px / pdf_w        # skaliere auf gewünschte Druckbreite

    bitmap = page.render(scale=scale)
    pil_image = bitmap.to_pil()

    return pil_image