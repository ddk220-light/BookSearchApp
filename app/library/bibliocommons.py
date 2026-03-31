import re
from urllib.parse import quote_plus
from playwright.async_api import async_playwright
from app.config import settings

CATALOG_URL = "https://burlingame.bibliocommons.com"
AUDIO_FORMATS = {"audiobook", "audio cd", "audio", "playaway", "cd"}
DIGITAL_FORMATS = {"ebook", "ebook - overdrive", "kindle", "digital"}


async def search_library(title: str, author: str) -> dict:
    """Search Burlingame library catalog for physical editions of a book."""
    search_query = quote_plus(f"{title} {author}")
    url = f"{CATALOG_URL}/v2/search?query={search_query}&searchType=smart"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=15000)

            try:
                await page.wait_for_selector(
                    ".cp-search-result-item", timeout=10000
                )
            except Exception:
                await browser.close()
                return {"available": False, "editions": [], "best_edition": None}

            # Extract edition data from search results
            editions = await page.evaluate("""
                () => {
                    const results = document.querySelectorAll('.cp-search-result-item');
                    const editions = [];
                    for (const result of results) {
                        const formatEl = result.querySelector('.format-info, .cp-format-info');
                        const format = formatEl ? formatEl.textContent.trim() : '';
                        const availEl = result.querySelector('.availability-status, .cp-availability');
                        const availText = availEl ? availEl.textContent.trim() : '';
                        const linkEl = result.querySelector('a.title-link, a[data-key="bib-title"]');
                        const id = linkEl ? linkEl.getAttribute('href') : '';
                        editions.push({ format, availText, id });
                    }
                    return editions;
                }
            """)

            await browser.close()

            # Filter to physical books only
            physical = []
            for ed in editions:
                fmt_lower = ed.get("format", "").lower()
                if any(af in fmt_lower for af in AUDIO_FORMATS):
                    continue
                if any(df in fmt_lower for df in DIGITAL_FORMATS):
                    continue
                physical.append(_parse_edition(ed))

            if not physical:
                return {"available": False, "editions": [], "best_edition": None}

            best = _select_best_edition(physical)
            return {
                "available": True,
                "editions": physical,
                "best_edition": best,
            }
    except Exception:
        return {"available": False, "editions": [], "best_edition": None}


def _parse_edition(raw: dict) -> dict:
    """Parse raw scraped edition data into structured format."""
    avail_text = raw.get("availText", "").lower()
    copies = 0
    available = 0
    hold_queue = 0

    copies_match = re.search(r"(\d+)\s+cop", avail_text)
    if copies_match:
        copies = int(copies_match.group(1))

    avail_match = re.search(r"(\d+)\s+of\s+\d+.*available", avail_text)
    if avail_match:
        available = int(avail_match.group(1))

    holds_match = re.search(r"(\d+)\s+hold", avail_text)
    if holds_match:
        hold_queue = int(holds_match.group(1))

    return {
        "format": raw.get("format", "Unknown"),
        "copies": copies,
        "available": available,
        "hold_queue": hold_queue,
        "id": raw.get("id", ""),
    }


def _select_best_edition(editions: list[dict]) -> dict | None:
    """Pick the physical edition with the shortest wait time."""
    scored = []
    for ed in editions:
        if ed["copies"] == 0:
            continue
        if ed["available"] > 0:
            wait = 0
        else:
            wait = (ed["hold_queue"] / ed["copies"]) * 14
        scored.append({**ed, "estimated_wait_days": round(wait)})

    if not scored:
        return None

    scored.sort(key=lambda x: x["estimated_wait_days"])
    return scored[0]


async def place_hold(edition_id: str, title: str) -> dict:
    """Log into BiblioCommons and place a hold on the specified edition."""
    if not settings.library_card_number or not settings.library_pin:
        return {
            "success": False,
            "message": "Library credentials not configured.",
            "details": None,
        }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Navigate to login
            await page.goto(
                f"{CATALOG_URL}/user/login", timeout=15000
            )

            # Fill login form
            await page.fill(
                'input[name="user_pin"], input[name="name"], #userID',
                settings.library_card_number,
            )
            await page.fill(
                'input[name="pin"], input[type="password"], #password',
                settings.library_pin,
            )
            await page.click(
                'input[type="submit"], button[type="submit"]'
            )
            await page.wait_for_load_state("networkidle")

            # Check for login failure
            error = await page.query_selector(".login-error, .alert-danger")
            if error:
                await browser.close()
                return {
                    "success": False,
                    "message": "Library login failed. Check your credentials.",
                    "details": None,
                }

            # Navigate to the book and place hold
            await page.goto(
                f"{CATALOG_URL}{edition_id}", timeout=15000
            )

            hold_button = await page.query_selector(
                'a.place-hold-link, button[data-key="place-hold"], '
                '.btn-holds-modal'
            )
            if not hold_button:
                await browser.close()
                return {
                    "success": False,
                    "message": "Could not find hold button. The book may already be on hold.",
                    "details": None,
                }

            await hold_button.click()
            await page.wait_for_load_state("networkidle")

            # Confirm hold in modal if present
            confirm = await page.query_selector(
                'button.confirm-hold, button[data-key="confirm"]'
            )
            if confirm:
                await confirm.click()
                await page.wait_for_load_state("networkidle")

            await browser.close()

            return {
                "success": True,
                "message": "Hold placed successfully",
                "details": {
                    "title": title,
                    "library": "Burlingame Public Library",
                },
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Hold placement failed: {str(e)}",
            "details": None,
        }
