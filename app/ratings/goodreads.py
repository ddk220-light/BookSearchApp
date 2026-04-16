import re
from urllib.parse import quote_plus
from playwright.async_api import async_playwright


async def scrape_goodreads_rating(
    title: str, author: str
) -> dict | None:
    """Scrape Goodreads for book rating. Returns None on any failure."""
    search_query = quote_plus(f"{title} {author}")
    url = f"https://www.goodreads.com/search?q={search_query}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, timeout=15000)

            # Click first search result
            await page.wait_for_selector(
                'a.bookTitle, [data-testid="searchResult"]', timeout=10000
            )
            first_link = await page.query_selector(
                'a.bookTitle, [data-testid="searchResult"] a'
            )
            if first_link:
                await first_link.click()
                await page.wait_for_load_state("domcontentloaded")

            # Extract rating — Goodreads uses various selectors
            rating = await page.evaluate("""
                () => {
                    const el = document.querySelector(
                        '[data-testid="ratingsCount"]'
                    )?.previousElementSibling
                        || document.querySelector('.RatingStatistics__rating');
                    return el ? parseFloat(el.textContent.trim()) : null;
                }
            """)

            if rating is None:
                await browser.close()
                return None

            # Extract rating count
            count_text = ""
            count_el = await page.query_selector(
                '[data-testid="ratingsCount"]'
            )
            if count_el:
                count_text = await count_el.inner_text()

            count = _parse_count(count_text)
            book_url = page.url

            cover_image = await page.evaluate("""
                () => {
                    const el = document.querySelector(
                        '.BookCover__image img, .ResponsiveImage, #coverImage'
                    );
                    return el ? (el.src || el.getAttribute('src')) : null;
                }
            """)

            reviews = await page.evaluate("""
                () => {
                    const nodes = document.querySelectorAll(
                        'article.ReviewCard, [itemprop="reviews"] .friendReviews .review'
                    );
                    const out = [];
                    nodes.forEach((node) => {
                        if (out.length >= 5) return;
                        const author = node.querySelector(
                            '.ReviewerProfile__name a, .user a'
                        );
                        const ratingEl = node.querySelector(
                            '.ShelfStatus .RatingStars, .RatingStars, .staticStars'
                        );
                        const textEl = node.querySelector(
                            'section.ReviewText span.Formatted, .reviewText span'
                        );
                        const text = textEl ? textEl.textContent.trim() : '';
                        if (!text) return;
                        out.push({
                            author: author ? author.textContent.trim() : 'Goodreads reader',
                            rating: ratingEl ? (ratingEl.getAttribute('aria-label') || ratingEl.textContent.trim()) : null,
                            text: text.length > 600 ? text.slice(0, 600).trimEnd() + '...' : text,
                        });
                    });
                    return out;
                }
            """)

            await browser.close()

            return {
                "rating": rating,
                "count": count,
                "url": book_url,
                "cover_image": cover_image,
                "reviews": reviews or [],
            }
    except Exception:
        return None


def _parse_count(text: str) -> int:
    """Parse '1,234,567 ratings' into 1234567."""
    numbers = re.findall(r"[\d,]+", text)
    if numbers:
        return int(numbers[0].replace(",", ""))
    return 0
