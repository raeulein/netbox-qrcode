from io import BytesIO
from typing import Tuple
from PIL import Image
from django.contrib import messages


def render_html_to_png(html: str, width_mm: int, height_mm: int, want_pdf=False) -> Image.Image:
    from weasyprint import HTML, CSS                       # Laufzeit-Import

    page_size = f"{width_mm}mm {height_mm}mm"

    css = CSS(string=f"""
        @page {{ size: {page_size}; margin:0 }}
        html,body {{ width:{page_size.split()[0]}; height:{page_size.split()[1]}; margin:0 }}
    """)

    # ──────────────────────────────────────────────────────────────
    import pypdfium2 as pdfium              # reines pip-Rad

    # 1. Rendern mit Stylesheet
    doc = HTML(string=html).render(stylesheets=[css])

    # 2. PDF daraus bauen
    pdf_bytes = doc.write_pdf()

    pdf = pdfium.PdfDocument(pdf_bytes)
    if want_pdf:
        return pdf_bytes  # PDF zurückgeben, wenn gewünscht

    page = pdf.get_page(0)

    # Rendere die Seite als 300dpi Bitmap
    bitmap = page.render(scale=300 / 72)  # WeasyPrint gibt 72dpi aus, wir wollen 300dpi


    pil_image = bitmap.to_pil()

    return pil_image