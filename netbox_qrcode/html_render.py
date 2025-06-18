# netbox_qrcode/html_render.py
from io import BytesIO
from html2image import Html2Image


def render_html_to_png(html: str, width: int, height: int) -> BytesIO:

    hti = Html2Image(
        size=(width, height),
        browser_executable=None,   # None ⇒ auto-detect / auto-download
        download=True,             # <-- wichtig!
        cache_path="/opt/netbox/hti_cache"  # beliebiger Schreibpfad
    )

    file_path = hti.screenshot(html_str=html, save_as="label_tmp.png")[0]
    with open(file_path, "rb") as f:
        return BytesIO(f.read())
