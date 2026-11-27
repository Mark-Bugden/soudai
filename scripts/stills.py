"""Render the demo's stills from the built demo into demo/public/, in the dark and light themes.

- static.webp and static-light.webp: the opening state, the Process map for all courts. Shown while
  the demo loads, and without JavaScript.
- thumb.webp and thumb-light.webp: the Forecast tab's chart on the case it opens on, for the project
  card (Mark, 2026-11-26: it looks better there than the map). It has no text (Mark, 2026-11-26:
  "the thumbnails should show no text and only visual indications of the demo itself"): no heading
  or boxes, and none of the chart's labels, so the chart fills the stage. The stage is shot at
  720 x 450, 16:10, the card's shape, centred on the theme's page colour at 1200 x 675. The card
  trims those margins.
- og.jpg: the Forecast tab, with its text, at 1200 x 630, dark only, for link previews.

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

# For the thumbnail: the forecast's chart alone, filling the stage, with none of its text.
BARE = """
[data-demo] .sd-forecast { grid-template-rows: minmax(0, 1fr); padding: var(--space-4); }
[data-demo] .sd-forecast .sd-case, [data-demo] .sd-forecast .sd-chances,
[data-demo] .sd-forecast .sd-chart text { display: none !important; }
"""

# The room the chart keeps for its labels beyond what it keeps on the opposite side: on the left for
# the lanes' names and the ticks, against the right; below for the time axis, against the line of the
# day of the forecast at the top. The thumbnail's chart box reaches that far past the stage's padding,
# so the drawing sits evenly in it.
ROOM = """() => {
  const svg = document.querySelector('.sd-forecast .sd-chart');
  const lane = svg.querySelector('.sd-lane');
  const axis = svg.querySelector('.sd-axis-line');
  const now = svg.querySelector('.sd-now');
  const [width, height] = [svg.width.baseVal.value, svg.height.baseVal.value];
  return [lane.x1.baseVal.value - (width - lane.x2.baseVal.value),
    height - axis.y1.baseVal.value - now.y1.baseVal.value];
}"""
REACH = "[data-demo] .sd-forecast .sd-chart-box { margin: 0 0 -%.1fpx -%.1fpx; }"


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
    page.wait_for_selector(".sd-flow .sd-node")
    page.evaluate("document.head.append(Object.assign(document.createElement('style'), { id: 'still' }))")
    return page


def style(page, theme, css):
    """Sets the theme and the still's CSS, and waits for the frame to redraw."""
    page.evaluate(
        "([theme, css]) => { document.documentElement.dataset.theme = theme;"
        " document.getElementById('still').textContent = css; }",
        [theme, css],
    )
    page.mouse.move(0, 0)
    page.wait_for_timeout(500)  # the frame redraws on the resize


def shoot(page, theme, width, height, extra=""):
    """Screenshots the stage at width x height CSS px in the theme, with `extra` CSS.

    Returns the image, with the page's colour as (r, g, b).
    """
    style(page, theme, CSS % (width, height) + extra)
    png = page.locator(".dk-stage").screenshot()
    background = page.evaluate("getComputedStyle(document.body).backgroundColor")
    colour = tuple(int(c) for c in re.findall(r"\d+", background)[:3])
    return Image.open(io.BytesIO(png)).convert("RGB"), colour


def show_tab(page, label):
    """Switches to a tab. The rail is hidden for the stills, so its button is pressed from a script."""
    page.evaluate(
        "label => [...document.querySelectorAll('.sd-segment')]"
        ".find((segment) => segment.textContent.trim() === label).querySelector('input').click()",
        label,
    )


def render(browser, url, errors):
    stills = {}
    page = open_page(browser, url, errors)
    for theme in THEMES:
        stills["static", theme] = shoot(page, theme, 1200, 675)
    show_tab(page, "Forecast")
    page.wait_for_selector(".sd-forecast .sd-forecast-line")
    stills["og", "dark"] = shoot(page, "dark", 800, 420)
    # The frame redraws only when the stage changes size, so the room is measured on the link
    # preview's chart, which keeps the same, and the thumbnail's size brings the redraw.
    bare = BARE + REACH % tuple(reversed(page.evaluate(ROOM)))
    for theme in THEMES:
        stills["thumb", theme] = shoot(page, theme, 720, 450, bare)
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
