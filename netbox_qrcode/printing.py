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
# Druck- und CSS-Konstanten
# ---------------------------------------------------------------------------
_PRINTER_DPI = 300
_CSS_DPI     = 96
_SCALE_HTML  = _PRINTER_DPI / _CSS_DPI        # 3,125

# ---------------------------------------------------------------------------
# Pixel-Maße (bei 300 dpi) – Keys entsprechen Brother-Labelcodes
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
# rotate-Wert abhängig von Label-Orientierung
# ---------------------------------------------------------------------------
def _rotation_for_printer(width_px: int, height_px: int) -> str:
    """
    Brother-QL erwartet Hochformat.
    Ist das Label höher als breit (klassisches 62×100 mm),
    müssen wir um 90° drehen.
    """
    return "90" if height_px > width_px else "0"


# ---------------------------------------------------------------------------
# Hauptfunktion: HTML → Brother-QL-Druck
# ---------------------------------------------------------------------------
def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """Rendert das Label-HTML, skaliert es auf 300 dpi und schickt es an den Drucker."""

    # 1) Drucker- und Label-Spezifikation ermitteln
    p_cfg, default_label = _get_printer_cfg()
    code = label_code or default_label

    try:
        spec = _LABEL_SPECS[code]
    except KeyError as exc:
        raise RuntimeError(f"Unbekannter Label-Code '{code}'.") from exc

    width_px, height_px = (spec, spec * 4) if isinstance(spec, int) else spec

    # 2) Label-HTML skalierend verpacken (96 → 300 dpi)
    html_scaled = extract_label_html(html, "QR-Code-Label", width_px, height_px)

    # 3) WeasyPrint → PNG (Bildgröße = width_px × height_px)
    img: Image.Image = render_html_to_png(html_scaled, width_px, height_px)

    # 4) Rasterdaten erzeugen & senden
    raster = BrotherQLRaster(p_cfg["MODEL"])
    rotate = _rotation_for_printer(width_px, height_px)
    instr  = convert(raster, [img], label=code, rotate=rotate)

    backend_cls = backend_factory(p_cfg["BACKEND"])["backend_class"]
    backend_cls(p_cfg["ADDRESS"]).write(instr)


# ---------------------------------------------------------------------------
# Label-DIV herauslösen & Wrapper mit transform:scale()
# ---------------------------------------------------------------------------
def extract_label_html(
    rendered_html: str,
    div_id: str,
    width_px: int,
    height_px: int,
) -> str:
    """
    Vergrößert den DIV-Inhalt von 96 dpi auf 300 dpi,
    ohne das Endformat zu ändern.
    """
    soup = BeautifulSoup(rendered_html, "html.parser")
    label_div = soup.find(id=div_id)
    if label_div is None:
        raise RuntimeError(
            f"DIV #{div_id} nicht gefunden – Template evtl. geändert?"
        )

    # Innengröße → 1/3,125 der Zielgröße
    inner_w = round(width_px  / _SCALE_HTML)
    inner_h = round(height_px / _SCALE_HTML)

    return (
        "<!DOCTYPE html>\n"
        "<html><head><style>"
        f"@page {{ size:{width_px}px {height_px}px; margin:0 }}"
        f"html,body {{ width:{width_px}px; height:{height_px}px; margin:0;padding:0 }}"
        "</style></head><body>"
        f"<div style='width:{inner_w}px;height:{inner_h}px;"
        f"transform:scale({_SCALE_HTML});transform-origin:top left'>"
        f"{label_div}"
        "</div>"
        "</body></html>"
    )
