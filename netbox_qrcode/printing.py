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
# Pixelmaße bei 300 dpi – Keys entsprechen Brother‑Labelcodes
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
# Konfiguration aus den NetBox‑Settings holen
# ---------------------------------------------------------------------------

def _get_printer_cfg() -> tuple[Dict[str, Any], str]:
    printers = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key = get_plugin_config(
        "netbox_qrcode", "DEFAULT_PRINTER", next(iter(printers), None)
    )
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


# ---------------------------------------------------------------------------
#   Hauptfunktion: HTML → Brother‑QL‑Druck
# ---------------------------------------------------------------------------

def print_label_from_html(html: str, label_code: str | None = None) -> None:
    """Rendert HTML in ein PNG, skaliert/rotiert es und sendet es zum Drucker."""

    # 1) Drucker‑ und Label‑Spezifikation ermitteln
    p_cfg, default_label = _get_printer_cfg()
    code = label_code or default_label

    try:
        spec = _LABEL_SPECS[code]
    except KeyError as exc:
        raise RuntimeError(f"Unbekannter Label‑Code '{code}'.") from exc

    if isinstance(spec, int):               # Endlosband
        width_px, height_px = spec, spec * 4
    else:                                   # Vorgestanztes Etikett
        width_px, height_px = spec

    # 2) HTML → Pillow‑Bild (WeasyPrint liefert 96 dpi)
    img: Image.Image = render_html_to_png(html, width_px, height_px)

    # 3) Wenn das Bild schmaler als das Band ist, fehlende Auflösung hochskalieren.
    #    (canvas_width war in älteren brother_ql‑Versionen nicht vorhanden.)
    if img.width < width_px:
        scale = width_px / img.width
        new_size = (width_px, int(img.height * scale))
        img = img.resize(new_size, Image.LANCZOS)

    # 4) Für querformatige Etiketten (Breite > Höhe) muss das Bild gedreht werden,
    #    wenn es noch hochkant ist.
    if img.height > img.width:
        img = img.rotate(90, expand=True)

    # 5) In Brother‑Raster wandeln und schicken
    raster = BrotherQLRaster(p_cfg["MODEL"])
    instr = convert(raster, [img], label=code, rotate="0")  # bereits korrekt orientiert

    backend_cls = backend_factory(p_cfg["BACKEND"])["backend_class"]
    backend_cls(p_cfg["ADDRESS"]).write(instr)


# ---------------------------------------------------------------------------
#   HTML‑Snippet aus qrcode3.html herauslösen
# ---------------------------------------------------------------------------

def extract_label_html(rendered_html: str, div_id: str, width_px: int, height_px: int) -> str:
    """Extrahiert den Label‑DIV aus dem vollständigen Template und legt ihn in ein
    minimalistisches HTML‑Dokument mit exakter Seiten‑/Body‑Größe ab."""

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