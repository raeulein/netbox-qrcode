# netbox_qrcode/html_render.py
from io import BytesIO
from html2image import Html2Image

def render_html_to_png(html: str, width: int, height: int) -> BytesIO:
    hti = Html2Image(output_path="/tmp", size=(width, height))
    file_path = hti.screenshot(html_str=html, save_as="label_tmp.png")[0]
    png_stream = BytesIO(open(file_path, "rb").read())
    return png_stream
