from io import BytesIO
from typing import Dict, Any

from netbox.plugins.utils import get_plugin_config
from brother_ql import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends import backend_factory
from PIL import Image
from bs4 import BeautifulSoup

from .html_render import render_html_to_png

# ---------------------------------------------------------------------------
# Pixelmaße bei 300 dpi – Keys entsprechen Brother-Labelcodes
# ---------------------------------------------------------------------------
_LABEL_SPECS: dict[str, int | tuple[int, int]] = {
    "12": 106, "29": 306, "38": 413, "50": 554, "54": 590, "62": 696, "102": 1164,
    "17x54": (165, 566), "17x87": (165, 956), "23x23": (202, 202),
    "29x42": (306, 425), "29x90": (306, 991), "39x90": (413, 991),
    "39x48": (425, 495), "52x29": (578, 271), "62x29": (696, 271),
    "62x100": (696, 1109), "102x51": (1164, 526), "102x152": (1164, 1660),
    "d12": (94, 94), "d24": (236, 236), "d58": (618, 618),
}


# ---------------------------------------------------------------------------
# Helper: Lade Druckerkonfiguration aus NetBox settings.py
# ---------------------------------------------------------------------------

def _get_printer_cfg() -> tuple[Dict[str, Any], str]:
    """Liest das PRINTER‑Dict, den Default‑Key und den Default‑Labelcode."""
    printers = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key = get_plugin_config(
        "netbox_qrcode", "DEFAULT_PRINTER", next(iter(printers), None)
    )
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


# ---------------------------------------------------------------------------
# Hauptfunktion: HTML‑Fragment direkt auf Brother‑QL drucken
# ---------------------------------------------------------------------------

def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """Rendert *html* in 96 dpi → skaliert es auf native 300 dpi → rotiert
    »quer« (falls nötig) → sendet Rasterdaten an den Brother‑Drucker.
    
    * label_code – einer der Keys aus ``_LABEL_SPECS``; fällt auf Plugin‑Default
      zurück, falls *None* übergeben wird.
    """
    # ----------------------------------------------------
    # 1) Drucker‑ und Labelparameter bestimmen
    p_cfg, default_code = _get_printer_cfg()
    code = label_code or default_code

    spec = _LABEL_SPECS[code]
    if isinstance(spec, int):
        width_lbl, height_lbl = spec, spec * 4  # Endlosband: 1 Dot Breite = 4 Dots Höhe
    else:
        width_lbl, height_lbl = spec

    # ----------------------------------------------------
    # 2) HTML → Pillow‑Bild (WeasyPrint rendert mit 96 dpi)
    img: Image.Image = render_html_to_png(html, width_lbl, height_lbl)

    # ----------------------------------------------------
    # 3) Hochskalieren auf native 300 dpi des Geräts
    raster = BrotherQLRaster(p_cfg["MODEL"])
    native_w = raster.canvas_width               # z. B. 696 Dots bei 62 mm‑Band
    scale = native_w / img.width                 # ≈ 300 / 96 ≈ 3,125
    if scale != 1:
        native_h = int(img.height * scale)
        img = img.resize((native_w, native_h), Image.LANCZOS)

    # ----------------------------------------------------
    # 4) Bild ggf. um 90° drehen (Querformat)
    if img.width < img.height:
        img = img.rotate(90, expand=True)

    # ----------------------------------------------------
    # 5) Rasterdaten erzeugen & an Drucker schicken
    instr = convert(raster, [img], label=code, rotate="0")  # bereits gedreht
    backend_cls = backend_factory(p_cfg["BACKEND"])["backend_class"]
    backend_cls(p_cfg["ADDRESS"]).write(instr)


# ---------------------------------------------------------------------------
# HTML‑Schnipsel aus qrcode3.html herauslösen, um ihn 1:1 zu drucken
# ---------------------------------------------------------------------------

def extract_label_html(rendered_html: str, div_id: str, width_px: int, height_px: int) -> str:
    """Schneidet den DIV *div_id* aus *rendered_html* heraus und packt ihn in
    ein minimales HTML‑Dokument mit exakt *width_px*×*height_px* großen Body.
    """
    soup = BeautifulSoup(rendered_html, "html.parser")
    label_div = soup.find(id=div_id)
    if label_div is None:
        raise RuntimeError(f"DIV #{div_id} nicht gefunden – Template geändert?")

    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    @page {{ size:{width_px}px {height_px}px; margin:0 }}
    html,body {{ width:{width_px}px; height:{height_px}px; margin:0; padding:0 }}
  </style>
</head>
<body>
{label_div}
</body>
</html>"""
