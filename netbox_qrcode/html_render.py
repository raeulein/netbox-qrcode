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


def render_html_to_png(html: str, height_px: int, width_px: int) -> Image.Image:
    from weasyprint import HTML, CSS                       # Laufzeit-Import

    css = CSS(
        string=f"""
            @page {{ size:{width_px}px {height_px}px; margin:0 }}
            html,body {{ width:{width_px}px; height:{height_px}px; margin:0 }}
        """
    )
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
    pdf       = pdfium.PdfDocument(pdf_bytes)

    page      = pdf.get_page(0)
    pdf_w, _  = page.get_size()
    scale     = width_px / pdf_w                # Faktor → Zielbreite

    # ---------- neue API (pypdfium2 ≥ 4) ----------
    if hasattr(page, "render"):
        bitmap    = page.render(scale=scale)
        pil_image = bitmap.to_pil()

    # ---------- alte API (pypdfium2 2/3) ----------
    else:
        # Bis v3 gab es Helferfunktion render_pdf_topil()
        pil_image = pdfium.render_pdf_topil(
            pdf_bytes, page_indices=[0], scale=scale
        )[0]

    return pil_image