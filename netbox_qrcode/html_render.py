from io import BytesIO
from typing import Tuple

from PIL import Image
from weasyprint import HTML, CSS


def render_html_to_png(html: str, width_px: int, height_px: int) -> Image.Image:
    # WeasyPrint bekommt über @page die exakte Seitengröße (keine Ränder!)
    css = CSS(
        string=f"""
            @page {{
                size: {width_px}px {height_px}px;
                margin: 0;
            }}
            html, body {{
                width:  {width_px}px;
                height: {height_px}px;
                margin: 0;
                padding: 0;
            }}
        """
    )

    # 1. HTML → PNG-Bytes, 2. PNG-Bytes → Pillow-Image
    png_bytes: bytes = HTML(string=html).write_png(stylesheets=[css])
    return Image.open(BytesIO(png_bytes))
