import base64
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ******************************************************************************************
# Includes useful tools to create the content.
# ******************************************************************************************

##################################          
# Creates a QR code as an image.: https://pypi.org/project/qrcode/3.0/
# --------------------------------
# Parameter:
#   text: Text to be included in the QR code.
#   **kwargs: List of parameters which properties the QR code should have. (e.g. version, box_size, error_correction, border etc.)
def get_qr(text, **kwargs):
    qr = qrcode.QRCode(**kwargs)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image()
    img = img.get_image()
    return img

##################################          
# Converts an image to Base64
# --------------------------------
# Parameter:
#   img: Image file
def get_img_b64(img):
    stream = BytesIO()
    img.save(stream, format='png')
    return str(base64.b64encode(stream.getvalue()), encoding='ascii')

def b64_to_stream(b64_png: str) -> BytesIO:
    """Base64-PNG -> BytesIO (für printing.print_png)."""
    return BytesIO(base64.b64decode(b64_png))

def b64_to_img(b64_png: str) -> Image.Image:
    """Base64-PNG -> PIL-Image."""
    return Image.open(BytesIO(base64.b64decode(b64_png)))

def img_to_stream(img: Image.Image) -> BytesIO:
    """PIL-Image -> BytesIO (PNG)."""
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf