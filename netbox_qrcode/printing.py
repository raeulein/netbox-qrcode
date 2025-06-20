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
# 1) Skalierung auf ≥ 300 dpi
# ---------------------------------------------------------------------------
def _scale_image_to_label(img: Image.Image, width_px: int, height_px: int) -> Image.Image:
    """Skaliert das WeasyPrint-PNG so, dass es mindestens 300 dpi erreicht.

    WeasyPrint rendert CSS-Pixel mit 96 dpi. Brother-QL erwartet ~300 dpi.
    Wir wählen daher den größten Skalierungsfaktor aus:
        • geometrische Zielgröße (width_px/height_px) und
        • dpi-Faktor (300 / Quell-DPI).
    Schrumpfen (scale < 1) vermeiden wir, um Qualität zu behalten.
    """
    dpi_src = img.info.get("dpi", (96, 96))[0] or 96
    dpi_factor = 300 / dpi_src                   # 3,125 bei 96 dpi
    geo_factor = max(width_px / img.width, height_px / img.height)
    scale      = max(dpi_factor, geo_factor, 1)  # nie kleiner als 1

    if scale == 1:
        return img

    new_size = (round(img.width * scale), round(img.height * scale))
    return img.resize(new_size, Image.LANCZOS)

# ---------------------------------------------------------------------------
# 2) Ausrichtung des Bildes
# ---------------------------------------------------------------------------
def _orient_image(img: Image.Image, width_px: int, height_px: int) -> Image.Image:
    """Dreht das Bild bei Bedarf um 90 °, damit es im Hochformat zum Drucker passt."""
    img_landscape  = img.width  > img.height
    label_landscape = width_px  > height_px

    if img_landscape != label_landscape:
        return img.rotate(90, expand=True)
    return img

# ---------------------------------------------------------------------------
# 3) rotate-Wert für brother_ql ermitteln
# ---------------------------------------------------------------------------
def _rotation_for_printer(width_px: int, height_px: int) -> str:
    """Gibt den rotate-Parameter (‘0’ oder ‘90’) für brother_ql.convert() zurück."""
    # Brother-QL erwartet Bilder im Hochformat; sind sie quer, dreht convert() sie.
    return "90" if width_px > height_px else "0"

# ---------------------------------------------------------------------------
# 4) Hauptfunktion – Abschnitt 5: an brother_ql senden
# ---------------------------------------------------------------------------
# 5) In Brother-Raster wandeln und senden
raster = BrotherQLRaster(p_cfg["MODEL"])
rotate = _rotation_for_printer(width_px, height_px)
instr  = convert(raster, [img], label=code, rotate=rotate)

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
