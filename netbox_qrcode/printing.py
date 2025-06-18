from io import BytesIO
from typing import Dict, Any
from netbox.plugins.utils import get_plugin_config
from brother_ql import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends import backend_factory
from .html_render import render_html_to_png
from PIL import Image
from bs4 import BeautifulSoup

# Pixelmaße bei 300 dpi
_LABEL_SPECS = {
    "12": 106, "29": 306, "38": 413, "50": 554, "54": 590, "62": 696, "102": 1164,
    "17x54": (165, 566),  "17x87": (165, 956),  "23x23":  (202, 202),
    "29x42": (306, 425),  "29x90": (306, 991),  "39x90":  (413, 991),
    "39x48": (425, 495),  "52x29": (578, 271),  "62x29":  (696, 271),
    "62x100": (696, 1109),"102x51":(1164,526), "102x152":(1164,1660),
    "d12": (94, 94), "d24": (236, 236), "d58": (618, 618),
}


def _get_printer_cfg() -> tuple[Dict[str, Any], str]:
    printers      = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key   = get_plugin_config("netbox_qrcode", "DEFAULT_PRINTER",
                                      next(iter(printers), None))
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """rendert Browser-Layout ➜ Brother-Raster ➜ schickt an Drucker"""
    p_cfg, default_label = _get_printer_cfg()
    code = label_code or default_label

    spec = _LABEL_SPECS[code]
    if isinstance(spec, int):
        width, height = spec, spec * 4          # großzügige Höhe bei Endlosband
    else:
        width, height = spec

    img = render_html_to_png(html, width, height)   # PIL.Image.Image

    # 2. An Brother-QL-Treiber übergeben
    raster = BrotherQLRaster(p_cfg["MODEL"])
    instr  = convert(raster, [img], label=code, rotate="auto")

    BackendClass = backend_factory(p_cfg["BACKEND"])["backend_class"]
    BackendClass(p_cfg["ADDRESS"]).write(instr)

def extract_label_html(rendered_html: str, div_id: str, width_px: int, height_px: int) -> str:
    """
    Schneidet aus dem von qrcode3.html gerenderten Code den eigentlichen
    Label-DIV heraus und packt ihn in ein Mini-HTML-Dokument,
    dessen <body> exakt die Etikettgröße hat.
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
    html,body {{ width:{width_px}px; height:{height_px}px; margin:0;padding:0 }}
  </style>
</head>
<body>
{label_div}
</body>
</html>"""