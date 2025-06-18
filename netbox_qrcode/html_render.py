from io import BytesIO
from PIL import Image

def render_html_to_png(html: str, width_px: int, height_px: int) -> Image.Image:
    from weasyprint import HTML, CSS

    css = CSS(string=f"""
        @page {{ size:{width_px}px {height_px}px; margin:0 }}
        html,body {{ width:{width_px}px; height:{height_px}px; margin:0 }}
    """)
    html_obj = HTML(string=html)

    # Weg 1 – neue API (≥53)
    if hasattr(html_obj, "write_png"):
        png_bytes = html_obj.write_png(stylesheets=[css])

    # Weg 2 – halb-neue API (0.53 – 0.52)
    else:
        doc = html_obj.render(stylesheets=[css])
        if hasattr(doc, "write_png"):
            png_bytes = doc.write_png()
        # Weg 3 – Steinzeit-API (0.42 – 0.51)
        else:
            # Erste Seite herauspicken und per Cairo in PNG schreiben
            page = doc.pages[0]
            surface, _ = page.paint(dpi=96)
            buf = BytesIO()
            surface.write_to_png(buf)     # cairo.Surface-Methode
            png_bytes = buf.getvalue()

    return Image.open(BytesIO(png_bytes))
