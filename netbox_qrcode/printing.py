from io import BytesIO
from typing import Dict, Any

from PIL import Image
from netbox.plugins.utils import get_plugin_config           # NetBox ≥ 3
from brother_ql import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends import backend_factory              # Fork-kompatibel


# 300-dpi-Pixel­maße für alle Brother-Labelcodes
_LABEL_SPECS = {
    "12": 106, "29": 306, "38": 413, "50": 554, "54": 590, "62": 696, "102": 1164,
    "17x54": (165, 566),  "17x87": (165, 956),  "23x23":  (202, 202),
    "29x42": (306, 425),  "29x90": (306, 991),  "39x90":  (413, 991),
    "39x48": (425, 495),  "52x29": (578, 271),  "62x29": (696, 271),
    "62x100": (696,1109), "102x51":(1164,526), "102x152":(1164,1660),
    "d12": (94,94), "d24": (236,236), "d58": (618,618),
}


def _prepare_image(raw_png: BytesIO, label_code: str) -> BytesIO:
    """ skaliert & rotiert das PNG exakt auf die Druck­pixel des Bandes """
    img = Image.open(raw_png)

    spec = _LABEL_SPECS[label_code]
    if isinstance(spec, int):                 # Endlosband
        scale     = spec / img.width
        new_size  = (spec, int(img.height * scale))
    else:                                     # Gestanzt
        new_size  = spec

    img = img.resize(new_size, Image.LANCZOS).rotate(90, expand=True)

    out = BytesIO()
    img.save(out, format="PNG")
    out.seek(0)
    return out


def _get_printer_cfg() -> tuple[Dict[str, Any], str]:
    """liest alle Drucker­einstellungen robust aus der NetBox-Config"""
    printers      = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key   = get_plugin_config(
        "netbox_qrcode", "DEFAULT_PRINTER", next(iter(printers), None)
    )
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


def print_png(image: BytesIO, label_size: str | None = None) -> None:
    """wandelt PNG → Brother-Raster und schickt es an den definierten Drucker"""
    p_cfg, default_label = _get_printer_cfg()
    label = label_size or default_label

    img_prepared = _prepare_image(image, label)

    raster   = BrotherQLRaster(p_cfg["MODEL"])
    instr    = convert(raster, [img_prepared], label=label, rotate="0")

    be_info       = backend_factory(p_cfg["BACKEND"])       # z. B. "network"
    backend_obj   = be_info["backend_class"](p_cfg["ADDRESS"])
    backend_obj.write(instr)
