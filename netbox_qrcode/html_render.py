from io import BytesIO
from typing import Tuple
from PIL import Image
from django.contrib import messages

def _px_to_in(px, dpi=300):      # Helper
    return px / dpi

def render_html_to_png(html: str, width_px: int, height_px: int, want_pdf=False) -> Image.Image:
    from weasyprint import HTML, CSS                       # Laufzeit-Import

    width_in  = _px_to_in(width_px)
    height_in = _px_to_in(height_px)
    page_size = f"{width_in}in {height_in}in"

    css = CSS(string=f"""
        @page {{ size: {page_size}; margin:0 }}
        html,body {{ width:{page_size.split()[0]}; height:{page_size.split()[1]}; margin:0 }}
    """)

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