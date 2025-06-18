import asyncio, os, tempfile
from io import BytesIO
from pyppeteer import launch

CACHE_DIR = "/opt/netbox/pyppeteer-cache"
pathlib.Path(CACHE_DIR).mkdir(parents=True, exist_ok=True)
os.environ.setdefault("PYPPETEER_HOME", CACHE_DIR)
os.environ.setdefault("HOME", CACHE_DIR)



async def _a_render(html: str, width: int, height: int) -> BytesIO:
    # temporäre HTML-Datei anlegen
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    tmp.write(html.encode("utf-8"))
    tmp.close()

    browser = await launch(  # pyppeteer lädt beim ersten Aufruf Chromium nach ~/.pyppeteer
        headless=True,
        args=["--no-sandbox", "--font-render-hinting=medium"],
    )
    page = await browser.newPage()
    await page.setViewport({"width": width, "height": height, "deviceScaleFactor": 1})
    await page.goto(f"file://{tmp.name}")
    png_bytes = await page.screenshot(fullPage=False)
    await browser.close()

    os.unlink(tmp.name)
    return BytesIO(png_bytes)


def render_html_to_png(html: str, width: int, height: int) -> BytesIO:
    """
    Rendert den HTML-String exakt in width×height px
    und gibt einen BytesIO-Stream (PNG) zurück.
    Der erste Aufruf lädt automatisch eine portable Chromium-Binary (~100 MB).
    """
    return asyncio.run(_a_render(html, width, height))
