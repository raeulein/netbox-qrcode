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
        @page {
            size: auto;
            margin: 0;
        }
        html, body {
            margin: 0;
        }
    """)


    html_obj = HTML(string=html)
    pdf_bytes = html_obj.write_pdf(stylesheets=[css])

    # PDF öffnen, Größe automatisch bestimmen
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_bytes)
    page = pdf.get_page(0)
    pdf_w, pdf_h = page.get_size()

    # z. B. mit DPI-Skalierung rendern
    scale = 2.0
    bitmap = page.render(scale=scale)
    image = bitmap.to_pil()

    return image