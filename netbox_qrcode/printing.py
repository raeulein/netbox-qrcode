from io import BytesIO
from typing import Dict, Any

from PIL import Image, ImageDraw, ImageFont
from netbox.plugins.utils import get_plugin_config
from brother_ql import BrotherQLRaster
from brother_ql.conversion import convert
from brother_ql.backends import backend_factory
from .utilities import b64_to_img, img_to_stream

# Pixelmaße bei 300 dpi
_LABEL_SPECS = {
    "12": 106, "29": 306, "38": 413, "50": 554, "54": 590, "62": 696, "102": 1164,
    "17x54": (165, 566),  "17x87": (165, 956),  "23x23":  (202, 202),
    "29x42": (306, 425),  "29x90": (306, 991),  "39x90":  (413, 991),
    "39x48": (425, 495),  "52x29": (578, 271),  "62x29":  (696, 271),
    "62x100": (696, 1109),"102x51":(1164,526), "102x152":(1164,1660),
    "d12": (94, 94), "d24": (236, 236), "d58": (618, 618),
}


def _build_label(qr_b64: str,                     # QR-Code als Base64
                 text: str,                       # fertiger Text (mit <br>)
                 cfg: dict) -> BytesIO:
    """
    Erzeugt ein vollständiges Label-PNG anhand der Plugin-Konfig.
    Gibt einen BytesIO-Stream zurück, der sofort zu brother_ql kann.
    """

    spec = _LABEL_SPECS[cfg["DEFAULT_LABEL_SIZE"]]
    if isinstance(spec, int):
        canvas = Image.new("1", (spec, spec*4), "white")
    else:
        canvas = Image.new("1", spec[::-1], "white")

    draw   = ImageDraw.Draw(canvas)

    def px(val, default=0):
        if val is None: return default
        return int(str(val).rstrip('px'))

    top    = px(cfg.get('label_edge_top'))
    left   = px(cfg.get('label_edge_left'))
    right  = px(cfg.get('label_edge_right'))
    bottom = px(cfg.get('label_edge_bottom'))

    work_w = canvas.width  - left - right
    work_h = canvas.height - top  - bottom

    # QR-Code
    qr_img = b64_to_img(qr_b64).convert("1")
    qr_w   = px(cfg.get('label_qr_width'),  200)
    qr_h   = px(cfg.get('label_qr_height'), 200)
    qr_img = qr_img.resize((qr_w, qr_h), Image.NEAREST)

    text_loc = cfg.get('text_location')     # 'left', 'right', 'up', 'down'
    dist     = px(cfg.get('label_qr_text_distance'), 10)

    if text_loc in ('left', 'right'):
        x_qr = left if text_loc == 'left' else left + work_w - qr_w
        y_qr = top + (work_h - qr_h)//2
        x_txt = x_qr + qr_w + dist if text_loc == 'left' else left
        y_txt = top
        max_txt_w = work_w - qr_w - dist
        max_txt_h = work_h
    else:                     # 'up' oder 'down'
        x_qr = left + (work_w - qr_w)//2
        y_qr = top if text_loc == 'up' else top + work_h - qr_h
        x_txt = left
        y_txt = y_qr + qr_h + dist if text_loc == 'up' else top
        max_txt_w = work_w
        max_txt_h = work_h - qr_h - dist

    canvas.paste(qr_img, (x_qr, y_qr))

    if cfg.get('with_text'):
        font_size = px(cfg.get('font_size'), 24)
        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()

        lines = text.replace('<br>', '\n').split('\n')
        line_h = font.getbbox('Hg')[3]
        cur_y  = y_txt
        for ln in lines:
            if cur_y + line_h > y_txt + max_txt_h: break
            draw.text((x_txt, cur_y), ln, fill=0, font=font)
            cur_y += line_h

    return img_to_stream(canvas)


def _get_printer_cfg() -> tuple[Dict[str, Any], str]:
    printers      = get_plugin_config("netbox_qrcode", "PRINTERS", {})
    default_key   = get_plugin_config("netbox_qrcode", "DEFAULT_PRINTER",
                                      next(iter(printers), None))
    default_label = get_plugin_config("netbox_qrcode", "DEFAULT_LABEL_SIZE", "62")
    return printers.get(default_key, {}), default_label


def print_png(qr_stream: BytesIO, label_size: str | None = None,
              text: str | None = None, cfg_override: dict | None = None):

    p_cfg, default_label = _get_printer_cfg()
    cfg_root = cfg_override or {}
    cfg_root.update({"DEFAULT_LABEL_SIZE": label_size or default_label})

    full_label_stream = _build_label(
        qr_stream.read().decode('ascii'),
        text or '',
        cfg_root
    )

    raster   = BrotherQLRaster(p_cfg["MODEL"])
    instr    = convert(raster, [full_label_stream], 
                       label=cfg_root["DEFAULT_LABEL_SIZE"],
                       rotate="auto")

    be_info       = backend_factory(p_cfg["BACKEND"])
    backend_obj   = be_info["backend_class"](p_cfg["ADDRESS"])
    backend_obj.write(instr)
