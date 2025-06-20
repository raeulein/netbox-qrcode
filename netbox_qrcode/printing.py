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
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62x100")
    return printers.get(default_key, {}), default_label

# ---------------------------------------------------------------------------
# Bild in Label-Größe bringen und richtig (im Uhrzeigersinn) ausrichten
# ---------------------------------------------------------------------------
from PIL import Image


def _scale_image_to_label(img: Image.Image, width_px: int, height_px: int) -> Image.Image:
    """
    Skaliert das gerenderte PNG so, dass es vollständig innerhalb des Ziel­formats
    bleibt (keine Überstände) und zentriert es anschließend auf einem weißen
    Canvas der exakten Brother-Pixelmaße.  Ergebnisgröße ist immer
    (width_px × height_px).
    """
    if img.size == (width_px, height_px):
        return img  # passt bereits

    # *Innen*-Fit: größte Vergrößerung, bei der beide Seiten ≤ Zielmaß bleiben
    scale = min(width_px / img.width, height_px / img.height)
    new_size = (round(img.width * scale), round(img.height * scale))
    img = img.resize(new_size, Image.LANCZOS)

    bg = Image.new("RGB", (width_px, height_px), "white")
    offset = ((width_px - new_size[0]) // 2, (height_px - new_size[1]) // 2)
    bg.paste(img, offset)
    return bg


def _orient_image(img: Image.Image, width_px: int, height_px: int) -> Image.Image:
    """
    Dreht das Bild genau dann, wenn Breite und Höhe vertauscht sind – allerdings
    **im Uhrzeigersinn** (-90 °), weil Pillow positive Winkel gegen den
    Uhrzeigersinn dreht.  Danach stimmen Abmessungen und Ausrichtung für den
    Brother-Treiber, so dass `convert(..., rotate="0")` genügt.
    """
    if img.size == (width_px, height_px):
        return img
    if img.size == (height_px, width_px):
        # clockwise 90° → Pillow: -90 °
        return img.rotate(-90, expand=True)

    # Sonderfall: zunächst korrekt einpassen, dann Rekursion
    img = _scale_image_to_label(img, height_px, width_px)
    return _orient_image(img, width_px, height_px)

# ---------------------------------------------------------------------------
# Hauptfunktion: HTML → Brother-QL-Druck
# ---------------------------------------------------------------------------

def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """Rendert HTML, skaliert es passend und schickt es an den Brother-Drucker."""

    # 1) Drucker-/Label-Specs
    p_cfg, default_label = _get_printer_cfg()
    code = label_code or default_label
    spec = _LABEL_SPECS[code]
    width_px, height_px = (spec, spec * 4) if isinstance(spec, int) else spec
    width_mm = height_px / 300 * 25.4  # mm für WeasyPrint
    height_mm = width_px / 300 * 25.4  # mm für WeasyPrint
    
    # 2) HTML → PNG
    img = render_html_to_png(html, width_mm, height_mm)

    # 3) Einpassen (niemals Beschnitt)
    img = _scale_image_to_label(img, width_px, height_px)

    #4) Ausrichtung: Breite/Höhe vertauscht?
    img = _orient_image(img, width_px, height_px)

    # 5) Am Brother erst *jetzt* drehen: Hochformat-Labels → 90 °
    rotate_mode = "0"

    # 6) In Brother-Raster wandeln und senden
    raster = BrotherQLRaster(p_cfg["MODEL"])
    instr = convert(raster, [img], label=code, rotate=rotate_mode)

    backend_cls = backend_factory(p_cfg["BACKEND"])["backend_class"]
    backend_cls(p_cfg["ADDRESS"]).write(instr)


# ---------------------------------------------------------------------------
# Label‑DIV aus qrcode3.html extrahieren
# ---------------------------------------------------------------------------

def extract_label_html(rendered_html: str, div_id: str) -> str:
    """Extrahiert den Label‑Container und setzt ihn in ein Minimal‑HTML."""

    soup = BeautifulSoup(rendered_html, "html.parser")
    label_div = soup.find(id=div_id)
    if label_div is None:
        raise RuntimeError(f"DIV #{div_id} nicht gefunden – Template evtl. geändert?")

    return (
        "<!DOCTYPE html>\n"
        "<html><head></head><body>"
        f"{label_div}"  # bereits gerenderter HTML‑Code
        "</body></html>"
    )
