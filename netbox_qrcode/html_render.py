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

    css = CSS(
        string=f"""
            @page {{ size:{width_px}px {height_px}px; margin:0 }}
            html,body {{ width:{width_px}px; height:{height_px}px; margin:0 }}
        """
    )
    html_obj = HTML(string=html)

    # ──────────────────────────────────────────────────────────────
    # 1) WeasyPrint ≤ 52  → HTML.write_png() existiert noch
    if hasattr(html_obj, "write_png"):
        png_bytes: bytes = html_obj.write_png(stylesheets=[css])

    # 2) WeasyPrint 53-57 → Document.write_png()
    else:
        doc = html_obj.render(stylesheets=[css])
        if hasattr(doc, "write_png"):
            png_bytes: bytes = doc.write_png()
        # 3) WeasyPrint ≥ 58 → Kein PNG-Support mehr ⇒ PDF → PNG
        else:
            try:
                import pypdfium2 as pdfium                # pip-only!
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "WeasyPrint ≥58 liefert nur noch PDF. "
                    "Installiere pypdfium2 (`pip install pypdfium2`) "
                    "oder nutze WeasyPrint ≤52."
                ) from exc

            pdf_bytes: bytes = html_obj.write_pdf(stylesheets=[css])
            pdf = pdfium.PdfDocument(pdf_bytes)

            page = pdf.get_page(0)
            # Skalierung so wählen, dass die Breite passt
            pdf_w, _ = page.get_size()
            scale = width_px / pdf_w
            pil_image = page.render_topil(scale=scale)
            return pil_image

    # PNG-Bytes → Pillow-Image
    return Image.open(BytesIO(png_bytes))
