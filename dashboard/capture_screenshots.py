# ==
# capture_screenshots.py
# Author: Sunday Emmanuel Azeez
# Seamark Global Innovations — Project 2 dashboard
# ==
#
# WHY THIS EXISTS:
# A manual screenshot only captures what fits in the visible window — some
# dashboard sections (Products & Pricing especially) are taller than one
# screen. This script drives a real headless browser, clicks through every
# sidebar section, and saves a FULL-PAGE screenshot of each one (the whole
# scrollable page, not just the visible viewport) — for the README, not for
# the pipeline. It does not touch any data.
#
# REQUIRES THE DASHBOARD ALREADY RUNNING:
#   In one terminal: python -m streamlit run app.py   (from dashboard/)
#   In another:       python capture_screenshots.py   (from dashboard/)
#
# SETUP (one-time):
#   pip install playwright
#   playwright install chromium
#
# OUTPUT:
#   Saves one PNG per section to ../assets/dashboard/, e.g.
#   assets/dashboard/overview.png, assets/dashboard/products_pricing.png
# ==

import re
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright isn't installed. Run:")
    print("  pip install playwright")
    print("  playwright install chromium")
    sys.exit(1)

DASHBOARD_URL = "http://localhost:8501"
OUT_DIR = Path(__file__).resolve().parent.parent / "assets" / "dashboard"

SECTIONS = [
    "Overview",
    "Products & Pricing",
    "Funnel & Checkout",
    "Omnichannel",
    "Affiliates",
    "AI Forecast",
    "Pipeline Health",
    "Stock Alerts",
]


def slug(name: str) -> str:
    name = name.lower().replace("&", "").replace(" ", "_")
    return re.sub(r"_+", "_", name).strip("_")


# Streamlit renders its content inside its own internal scrolling container,
# not the page's actual <body> -- the real <html>/<body> stays fixed at the
# viewport's height no matter how much content is on the page. That means
# Playwright's normal full_page=True screenshot, which measures the real
# document's height, never sees past one screenful: it looks "full page" but
# is really just a same-size copy of whatever's visible. To get a genuinely
# full screenshot, this measures how tall Streamlit's own content container
# actually is, temporarily resizes the browser viewport to match (so nothing
# needs to scroll), takes the shot, then puts the viewport back for the next
# section.
_GET_CONTENT_HEIGHT_JS = """
() => {
    const candidates = [
        document.body,
        document.documentElement,
        document.querySelector('[data-testid="stAppViewContainer"]'),
        document.querySelector('[data-testid="stMain"]'),
        document.querySelector('section.main'),
    ].filter(Boolean);
    return Math.max(...candidates.map(el => el.scrollHeight));
}
"""


def capture_full_page(page, out_path, base_viewport):
    content_height = page.evaluate(_GET_CONTENT_HEIGHT_JS)
    target_height = max(base_viewport["height"], content_height + 40)

    page.set_viewport_size({"width": base_viewport["width"], "height": target_height})
    page.wait_for_timeout(400)  # let vh-based layout reflow at the new size
    page.screenshot(path=str(out_path), full_page=True)
    page.set_viewport_size(base_viewport)  # restore before the next section


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:
            print(f"ERROR: couldn't launch Chromium ({e}).")
            print("Run: playwright install chromium")
            sys.exit(1)

        base_viewport = {"width": 1440, "height": 900}
        page = browser.new_page(viewport=base_viewport)

        print(f"Opening {DASHBOARD_URL} ...")
        try:
            # Streamlit keeps a live websocket open for auto-refresh, so the
            # network never goes fully idle — waiting for "networkidle" here
            # would hang forever. "load" (the page's own load event) is what
            # actually fires once, so that's what this waits for instead.
            page.goto(DASHBOARD_URL, wait_until="load", timeout=20000)
        except Exception as e:
            print(f"ERROR: couldn't reach {DASHBOARD_URL} ({e}).")
            print("Make sure the dashboard is running first: python -m streamlit run app.py")
            browser.close()
            sys.exit(1)

        try:
            # Wait for the sidebar's section control to actually exist —
            # more reliable than a fixed sleep, since Streamlit's first real
            # render can take a few seconds after the page 'load' event.
            page.get_by_text("Overview", exact=True).first.wait_for(timeout=20000)
        except Exception as e:
            print(f"ERROR: the dashboard page loaded but never rendered its sidebar ({e}).")
            print("Check the Streamlit terminal window for errors, then try again.")
            browser.close()
            sys.exit(1)

        page.wait_for_timeout(2000)  # let the first section's charts finish rendering

        try:
            # Streamlit's own local-dev toolbar sometimes shows a "Help agents
            # write better apps" nag box in the top-right corner. It's not part
            # of this dashboard, but it would show up in every screenshot if
            # left alone, so dismiss it once, up front, if it's there.
            page.get_by_text("Don't show again", exact=True).first.click(timeout=3000)
            page.wait_for_timeout(500)
        except Exception:
            pass  # popup didn't appear this run (e.g. already dismissed) — fine

        for section in SECTIONS:
            try:
                page.get_by_text(section, exact=True).first.click()
            except Exception as e:
                print(f"  Skipping '{section}' — couldn't find it on the page ({e})")
                continue

            page.wait_for_timeout(1500)  # let the newly-selected section render

            out_path = OUT_DIR / f"{slug(section)}.png"
            capture_full_page(page, out_path, base_viewport)
            print(f"  Saved {out_path.relative_to(OUT_DIR.parent.parent)}")

        browser.close()

    print("\nDone. Screenshots are in assets/dashboard/")


if __name__ == "__main__":
    main()
