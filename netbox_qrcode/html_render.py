# netbox_qrcode/html_render.py
import asyncio, tempfile, os
from io import BytesIO
from pyppeteer import launch

async def _a_render(html: str, width: int, height: int) -> BytesIO:
    # legt die temp-Datei automatisch in PYPPETEER_HOME an
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    tmp.write(html.encode())
    tmp.close()

    browser = await launch(headless=True, args=["--no-sandbox"])
    page = await browser.newPage()
    await page.setViewport({"width": width, "height": height, "deviceScaleFactor": 1})
    await page.goto(f"file://{tmp.name}")
    png = await page.screenshot(fullPage=False)
    await browser.close()
    os.unlink(tmp.name)
    return BytesIO(png)

def render_html_to_png(html: str, width: int, height: int) -> BytesIO:
    return asyncio.run(_a_render(html, width, height))
