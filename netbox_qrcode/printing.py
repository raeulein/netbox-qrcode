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
# Pixel‑Maße bei 300 dpi – Keys entsprechen Brother‑Labelcodes
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
# Konfiguration aus NetBox‑Settings laden
# ---------------------------------------------------------------------------

def _get_printer_cfg() -> Tuple[Dict[str, Any], str]:
    printers = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key = get_plugin_config(
        "netbox_qrcode", "DEFAULT_PRINTER", next(iter(printers), None)
    )
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


# ---------------------------------------------------------------------------
# Hauptfunktion: HTML → Brother‑QL‑Druck
# ---------------------------------------------------------------------------

def _scale_image_to_label(img: Image.Image, width_px: int, height_px: int) -> Image.Image:
    """
    Bringt das Bild auf mindestens 300 dpi.
    Ist es bereits groß genug, bleibt es unverändert – dadurch
    geht die zuvor erzeugte höhere Auflösung nicht wieder verloren.
    """
    if img.width >= width_px and img.height >= height_px:
        return img                          # schon groß genug
    scale = max(width_px / img.width, height_px / img.height)
    new_size = (round(img.width * scale), round(img.height * scale))
    return img.resize(new_size, Image.LANCZOS)


def _orient_image(img: Image.Image, width_px: int, height_px: int) -> Image.Image:
    """Dreht das Bild, falls Breite/Höhe vertauscht sind."""
    if img.size == (width_px, height_px):
        return img
    if img.size == (height_px, width_px):
        return img.rotate(90, expand=True)
    raise RuntimeError(
        f"Bad image dimensions after scaling: {img.size}. Expecting {width_px}×{height_px}."
    )


def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """Rendert HTML, skaliert/rotiert es passend und schickt es an den Brother‑Drucker."""

    # 1) Drucker‑ und Label‑Spezifikation ermitteln
    p_cfg, default_label = _get_printer_cfg()
    code = label_code or default_label

    try:
        spec = _LABEL_SPECS[code]
    except KeyError as exc:
        raise RuntimeError(f"Unbekannter Label‑Code '{code}'.") from exc

    width_px, height_px = (spec, spec * 4) if isinstance(spec, int) else spec

    # 2) HTML → Pillow (WeasyPrint rendert in 96 dpi → zu klein)
    img: Image.Image = render_html_to_png(html, width_px, height_px)

    # 3) Auf Ziel‑Auflösung hochskalieren
    img = _scale_image_to_label(img, width_px, height_px)

    # 4) Orientierung prüfen / drehen
    img = _orient_image(img, width_px, height_px)

    # 5) In Brother-Raster wandeln und senden
    rotation = "90" if height_px > width_px else "0"   # Hochformat-Etiketten drehen
    raster = BrotherQLRaster(p_cfg["MODEL"])
    instr  = convert(raster, [img], label=code, rotate=rotation)


    backend_cls = backend_factory(p_cfg["BACKEND"])["backend_class"]
    backend_cls(p_cfg["ADDRESS"]).write(instr)


# ---------------------------------------------------------------------------
# Label‑DIV aus qrcode3.html extrahieren
# ---------------------------------------------------------------------------

def extract_label_html(rendered_html: str, div_id: str, width_px: int, height_px: int) -> str:
    """Extrahiert den Label‑Container und setzt ihn in ein Minimal‑HTML."""

    soup = BeautifulSoup(rendered_html, "html.parser")
    label_div = soup.find(id=div_id)
    if label_div is None:
        raise RuntimeError(f"DIV #{div_id} nicht gefunden – Template evtl. geändert?")

    return (
        "<!DOCTYPE html>\n"
        "<html><head><style>"
        f"@page {{ size:{width_px}px {height_px}px; margin:0 }}"
        f"html,body {{ width:{width_px}px; height:{height_px}px; margin:0;padding:0 }}"
        "</style></head><body>"
        f"{label_div}"  # bereits gerenderter HTML‑Code
        "</body></html>"
    )
