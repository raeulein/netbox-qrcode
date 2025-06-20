from io import BytesIO
from typing import Dict, Any, Tuple

from netbox.plugins.utils import get_plugin_config
from brother_ql import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends import backend_factory
from PIL import Image
from bs4 import BeautifulSoup

from .html_render import render_html_to_png

# ---------------------------------------------------------------------------
# Pixel-Maße bei 300 dpi – Keys entsprechen Brother-Labelcodes
# ---------------------------------------------------------------------------
_LABEL_SPECS: dict[str, int | tuple[int, int]] = {
    "12": 106,
    "29": 306,
    "38": 413,
    "50": 554,
    "54": 590,
    "62": 696,
    "102": 1164,
    "17x54": (165, 566),
    "17x87": (165, 956),
    "23x23": (202, 202),
    "29x42": (306, 425),
    "29x90": (306, 991),
    "39x90": (413, 991),
    "39x48": (425, 495),
    "52x29": (578, 271),
    "62x29": (696, 271),
    "62x100": (696, 1109),
    "102x51": (1164, 526),
    "102x152": (1164, 1660),
    "d12": (94, 94),
    "d24": (236, 236),
    "d58": (618, 618),
}

# ---------------------------------------------------------------------------
# Konfiguration aus NetBox-Settings laden
# ---------------------------------------------------------------------------


def _get_printer_cfg() -> Tuple[Dict[str, Any], str]:
    printers = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key = get_plugin_config(
        "netbox_qrcode", "DEFAULT_PRINTER", next(iter(printers), None)
    )
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


# ---------------------------------------------------------------------------
# Helfer: rotate-Wert abhängig von Bild- und Label-Orientierung
# ---------------------------------------------------------------------------


def _rotation_for_printer(img: Image.Image, width_px: int, height_px: int) -> str:
    """
    Liefert "0" (nichts drehen) oder "90" (90 ° rechts),
    wenn die Orientierung des gerenderten PNGs nicht zur
    Brother-Label-Spezifikation passt.  Die Drehung übernimmt
    anschließend `brother_ql.convert()`, das die Abmessungen beibehält.
    """
    img_landscape = img.width > img.height
    label_landscape = width_px > height_px
    return "90" if img_landscape != label_landscape else "0"


# ---------------------------------------------------------------------------
# Hauptfunktion: HTML → Brother-QL-Druck
# ---------------------------------------------------------------------------


def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """Rendert HTML, bestimmt korrekte Drehung und schickt Rasterdaten an den Drucker."""

    # 1) Drucker- und Label-Spezifikation ermitteln
    p_cfg, default_label = _get_printer_cfg()
    code = label_code or default_label

    try:
        spec = _LABEL_SPECS[code]
    except KeyError as exc:
        raise RuntimeError(f"Unbekannter Label-Code '{code}'.") from exc

    width_px, height_px = (spec, spec * 4) if isinstance(spec, int) else spec

    # 2) HTML → Pillow (WeasyPrint rendert direkt in die richtigen Abmessungen)
    img: Image.Image = render_html_to_png(html, width_px, height_px)

    # 3) rotate-Wert ermitteln (Brother dreht dann selbst – Bildgröße bleibt unverändert)
    rotate = _rotation_for_printer(img, width_px, height_px)

    # 4) In Brother-Raster wandeln und senden
    raster = BrotherQLRaster(p_cfg["MODEL"])
    instr = convert(raster, [img], label=code, rotate=rotate)

    backend_cls = backend_factory(p_cfg["BACKEND"])["backend_class"]
    backend_cls(p_cfg["ADDRESS"]).write(instr)


# ---------------------------------------------------------------------------
# Label-DIV aus qrcode3.html extrahieren
# ---------------------------------------------------------------------------


def extract_label_html(
    rendered_html: str, div_id: str, width_px: int, height_px: int
) -> str:
    """Extrahiert den Label-Container und setzt ihn in ein Minimal-HTML."""

    soup = BeautifulSoup(rendered_html, "html.parser")
    label_div = soup.find(id=div_id)
    if label_div is None:
        raise RuntimeError(
            f"DIV #{div_id} nicht gefunden – Template evtl. geändert?"
        )

    return (
        "<!DOCTYPE html>\n"
        "<html><head><style>"
        f"@page {{ size:{width_px}px {height_px}px; margin:0 }}"
        f"html,body {{ width:{width_px}px; height:{height_px}px; margin:0;padding:0 }}"
        "</style></head><body>"
        f"{label_div}"  # bereits gerenderter HTML-Code
        "</body></html>"
    )
