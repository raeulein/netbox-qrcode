"""
HTML → Pillow-Image
Funktioniert mit *allen* WeasyPrint-Versionen ab 0.42
"""
from io import BytesIO
from PIL import Image

def render_html_to_png(html: str, width_px: int, height_px: int) -> Image.Image:
    from weasyprint import HTML, CSS

    css = CSS(
        string=f"""
            @page {{ size: {width_px}px {height_px}px; margin:0; }}
            html,body {{ width:{width_px}px; height:{height_px}px; margin:0; }}
        """
    )

    html_obj = HTML(string=html)

    # Neuere Version (≥53) – direkt verfügbar
    if hasattr(html_obj, "write_png"):
        png_bytes = html_obj.write_png(stylesheets=[css])

    # Ältere Version – erst rendern, dann PNG pro Seite erzeugen
    else:
        document = html_obj.render(stylesheets=[css])
        # write_png() liefert Liste von PNG-Byte-Strings (eine pro Seite)
        png_pages = document.write_png()
        png_bytes = png_pages[0]     # wir brauchen nur Seite 1

    return Image.open(BytesIO(png_bytes))
