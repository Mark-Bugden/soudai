"""Render the demo's stills from the built demo into demo/public/, in the dark and light themes.

- static.webp and static-light.webp: the opening state, the Forecast tab on 18 C 33/2024 at Jihlava,
  at filing. Shown while the demo loads, and without JavaScript.
- thumb.webp and thumb-light.webp: the Process map for all courts, for the project card. The stage is
  shot at 720 x 450: small, so its arrows stay readable on the card, but no smaller than the site shows
  it, so its labels have the room they have there. That's 16:10, the card's shape, centred on the
  theme's page colour at 1200 x 675. The card trims those margins.
- og.jpg: the same map at 1200 x 630, dark only, for link previews.

Serves the built demo (demo/dist/, from `npm run build`), opens it in a browser and screenshots the
stage alone at 2x. Then rebuild, so the bundle carries the new stills.

    cd demo && npm run build && cd ..
    uv run --with playwright --with pillow python scripts/stills.py

It drives Microsoft Edge; `--channel chrome` drives Chrome instead.
"""

import argparse
import functools
import http.server
import io
import re
import threading
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

DEMO = Path(__file__).resolve().parents[1] / "demo"
SCALE = 2
THEMES = ("dark", "light")

# Show the stage alone, at the still's size.
CSS = """
[data-demo] .dk-body { grid-template-columns: max-content !important; }
[data-demo] .dk-rail, [data-demo] .dk-header, [data-demo] .dk-bar,
[data-demo] .dk-about, [data-demo] .dk-links { display: none !important; }
[data-demo] .dk-stage { width: %dpx; height: %dpx !important; aspect-ratio: auto !important; }
"""


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def open_page(browser, url, errors):
    page = browser.new_page(
        viewport={"width": 1400, "height": 900}, device_scale_factor=SCALE, reduced_motion="reduce"
    )
    page.on("console", lambda message: message.type == "error" and errors.append(message.text))
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(url)
    page.wait_for_selector(".sd-forecast .sd-chart path")
    page.evaluate("document.head.append(Object.assign(document.createElement('style'), { id: 'still' }))")
    return page


def shoot(page, theme, width, height):
    """Screenshots the stage at width x height CSS px in the theme.

    Returns the image, with the page's colour as (r, g, b).
    """
    page.evaluate(
        "([theme, css]) => { document.documentElement.dataset.theme = theme;"
        " document.getElementById('still').textContent = css; }",
        [theme, CSS % (width, height)],
    )
    page.mouse.move(0, 0)
    page.wait_for_timeout(500)  # the frame redraws on the resize
    png = page.locator(".dk-stage").screenshot()
    background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    colour = tuple(int(c) for c in re.findall(r"\d+", background)[:3])
    return Image.open(io.BytesIO(png)).convert("RGB"), colour


def render(browser, url, errors):
    stills = {}
    page = open_page(browser, url, errors)
    for theme in THEMES:
        stills["static", theme] = shoot(page, theme, 1200, 675)
    page.close()

    page = open_page(browser, url, errors)
    page.get_by_role("radio", name="Process map", exact=True).check(
        force=True
    )  # each radio sits under its label
    page.wait_for_selector(".sd-flow path")
    for theme in THEMES:
        stills["thumb", theme] = shoot(page, theme, 720, 450)
    stills["og", "dark"] = shoot(page, "dark", 800, 420)
    page.close()
    return stills


def fit(still, width, height):
    image, background = still
    scale = min(width / image.width, height / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGB", (width, height), background)
    canvas.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    return canvas


def save(image, name, fmt, limit=None, **options):
    for quality in range(90, 40, -5):
        buffer = io.BytesIO()
        image.save(buffer, fmt, quality=quality, **options)
        if limit is None or buffer.tell() < limit:
            break
    else:
        raise SystemExit(f"{name}: could not get under {limit / 1000:.0f} KB")
    (DEMO / "public" / name).write_bytes(buffer.getvalue())
    print(f"{name}: {image.width}x{image.height}, quality {quality}, {buffer.tell() / 1000:.1f} KB")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--channel", default="msedge", help="the installed browser Playwright drives")
    args = parser.parse_args()

    server = http.server.ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(QuietHandler, directory=DEMO / "dist")
    )
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    errors = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel=args.channel)
            stills = render(browser, url, errors)
            browser.close()
    finally:
        server.shutdown()
    if errors:
        raise SystemExit("console errors:\n" + "\n".join(errors))

    for theme in THEMES:
        suffix = "" if theme == "dark" else "-light"
        save(fit(stills["static", theme], 1200, 675), f"static{suffix}.webp", "WEBP", method=6)
        save(fit(stills["thumb", theme], 1200, 675), f"thumb{suffix}.webp", "WEBP", 80_000, method=6)
    save(fit(stills["og", "dark"], 1200, 630), "og.jpg", "JPEG", 150_000, optimize=True, progressive=True)


if __name__ == "__main__":
    main()
