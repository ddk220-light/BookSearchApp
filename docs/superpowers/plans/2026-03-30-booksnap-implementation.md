# BookSnap Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a mobile-first web app that OCRs book covers, fetches ratings from multiple sources, synthesizes a recommendation, and places holds at Burlingame Public Library.

**Architecture:** FastAPI backend with three service layers (OCR, ratings, library automation). Playwright handles Goodreads scraping and BiblioCommons automation. Vanilla HTML/CSS/JS frontend served as static files. All services are async and run in parallel where possible.

**Tech Stack:** Python 3.12, FastAPI, pytesseract, Playwright, Anthropic SDK, httpx, vanilla HTML/CSS/JS, Docker

**Spec:** `docs/superpowers/specs/2026-03-30-book-search-app-design.md`

---

## File Structure

```
BookSearchApp/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, routes, lifespan
│   ├── config.py             # Settings from env vars via pydantic-settings
│   ├── ocr.py               # Tesseract OCR + Claude fallback
│   ├── ratings/
│   │   ├── __init__.py
│   │   ├── goodreads.py     # Playwright Goodreads scraper
│   │   ├── google_books.py  # Google Books API client
│   │   ├── llm.py           # Claude LLM assessment
│   │   └── synthesizer.py   # Combine ratings → recommendation
│   ├── library/
│   │   ├── __init__.py
│   │   └── bibliocommons.py # Playwright BiblioCommons automation
│   └── static/
│       ├── index.html
│       ├── style.css
│       └── app.js
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # Shared fixtures
│   ├── test_ocr.py
│   ├── test_goodreads.py
│   ├── test_google_books.py
│   ├── test_llm.py
│   ├── test_synthesizer.py
│   ├── test_bibliocommons.py
│   └── test_api.py
├── Dockerfile
├── requirements.txt
├── .env.example
├── .gitignore
└── pytest.ini
```

---

## Chunk 1: Project Setup + OCR Service

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `pytest.ini`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-multipart==0.0.18
pytesseract==0.3.13
Pillow==11.1.0
playwright==1.49.1
httpx==0.28.1
anthropic==0.43.0
pydantic-settings==2.7.1
python-dotenv==1.0.1
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: Create .env.example**

```
LIBRARY_CARD_NUMBER=your_library_card_number
LIBRARY_PIN=your_library_pin
GOOGLE_BOOKS_API_KEY=your_google_books_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

- [ ] **Step 3: Create .gitignore**

```
__pycache__/
*.pyc
.env
.venv/
.superpowers/
```

- [ ] **Step 4: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 5: Create app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    library_card_number: str = ""
    library_pin: str = ""
    google_books_api_key: str = ""
    anthropic_api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
```

- [ ] **Step 6: Create app/__init__.py and tests/__init__.py**

Both are empty files.

- [ ] **Step 7: Create tests/conftest.py**

```python
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
```

- [ ] **Step 8: Create minimal app/main.py to verify setup**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="BookSnap")

static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
```

- [ ] **Step 9: Install dependencies and verify**

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "chore: project scaffolding with dependencies and config"
```

---

### Task 2: OCR Service

**Files:**
- Create: `app/ocr.py`
- Create: `tests/test_ocr.py`
- Create: `tests/fixtures/` (test images)

- [ ] **Step 1: Write failing tests for OCR**

Create `tests/test_ocr.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
from app.ocr import extract_book_info


@pytest.fixture
def mock_tesseract_output():
    return "The Midnight Library\nMatt Haig\nA Novel"


class TestExtractBookInfo:
    @patch("app.ocr.pytesseract.image_to_data")
    @patch("app.ocr.Image.open")
    async def test_extracts_title_and_author(self, mock_open, mock_ocr):
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        mock_ocr.return_value = {
            "text": ["The Midnight Library", "Matt Haig", "A Novel", ""],
            "height": [50, 30, 20, 0],
            "conf": [90, 85, 80, -1],
        }

        result = await extract_book_info("fake_path.jpg")

        assert result["title"] == "The Midnight Library"
        assert result["author"] == "Matt Haig"

    @patch("app.ocr.pytesseract.image_to_data")
    @patch("app.ocr.Image.open")
    async def test_returns_none_on_empty_ocr(self, mock_open, mock_ocr):
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        mock_ocr.return_value = {
            "text": ["", ""],
            "height": [0, 0],
            "conf": [-1, -1],
        }

        result = await extract_book_info("fake_path.jpg")

        assert result is None

    @patch("app.ocr.pytesseract.image_to_data")
    @patch("app.ocr.Image.open")
    @patch("app.ocr.parse_with_llm")
    async def test_falls_back_to_llm_on_ambiguous(
        self, mock_llm, mock_open, mock_ocr
    ):
        mock_img = MagicMock()
        mock_open.return_value = mock_img
        # Only one text line detected — ambiguous (no clear author)
        mock_ocr.return_value = {
            "text": ["Sapiens", ""],
            "height": [40, 0],
            "conf": [70, -1],
        }
        mock_llm.return_value = {"title": "Sapiens", "author": "Yuval Noah Harari"}

        result = await extract_book_info("fake_path.jpg")

        assert result["title"] == "Sapiens"
        assert result["author"] == "Yuval Noah Harari"
        mock_llm.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_ocr.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'app.ocr'`

- [ ] **Step 3: Implement app/ocr.py**

```python
import pytesseract
from PIL import Image
from anthropic import AsyncAnthropic
from app.config import settings


async def extract_book_info(image_path: str) -> dict | None:
    """Extract title and author from a book cover image.

    Uses Tesseract OCR with heuristic parsing. Falls back to Claude
    if the extraction is ambiguous (e.g., only one text block found).
    """
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Filter to lines with actual text and reasonable confidence
    lines = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text and data["conf"][i] > 0:
            lines.append({"text": text, "height": data["height"][i]})

    if not lines:
        return None

    # Sort by text height descending — largest text is likely the title
    lines.sort(key=lambda x: x["height"], reverse=True)

    title = lines[0]["text"]
    author = lines[1]["text"] if len(lines) > 1 else None

    # If we only found one line or author looks suspicious, ask the LLM
    if author is None or len(lines) < 2:
        raw_text = " ".join(line["text"] for line in lines)
        llm_result = await parse_with_llm(raw_text)
        if llm_result:
            return llm_result
        return None

    return {"title": title, "author": author}


async def parse_with_llm(raw_text: str) -> dict | None:
    """Use Claude to parse title/author from ambiguous OCR text."""
    if not settings.anthropic_api_key:
        return None

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract the book title and author from this OCR text: '{raw_text}'. "
                    "Respond with ONLY JSON: {\"title\": \"...\", \"author\": \"...\"}"
                ),
            }
        ],
    )
    import json

    try:
        return json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_ocr.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/ocr.py tests/test_ocr.py
git commit -m "feat: OCR service with Tesseract and Claude fallback"
```

---

## Chunk 2: Rating Pipeline

### Task 3: Google Books API Client

**Files:**
- Create: `app/ratings/__init__.py`
- Create: `app/ratings/google_books.py`
- Create: `tests/test_google_books.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_google_books.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
from app.ratings.google_books import fetch_google_books_rating


class TestGoogleBooksRating:
    @patch("app.ratings.google_books.httpx.AsyncClient")
    async def test_returns_rating_when_available(self, mock_client_cls):
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "items": [
                {
                    "volumeInfo": {
                        "averageRating": 4.1,
                        "ratingsCount": 350,
                    }
                }
            ]
        }
        mock_response.raise_for_status = lambda: None
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await fetch_google_books_rating("The Midnight Library", "Matt Haig")

        assert result["rating"] == 4.1
        assert result["count"] == 350

    @patch("app.ratings.google_books.httpx.AsyncClient")
    async def test_returns_none_when_no_rating(self, mock_client_cls):
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "items": [{"volumeInfo": {"title": "Some Book"}}]
        }
        mock_response.raise_for_status = lambda: None
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value = mock_client

        result = await fetch_google_books_rating("Unknown Book", "Unknown Author")

        assert result is None

    @patch("app.ratings.google_books.httpx.AsyncClient")
    async def test_returns_none_on_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client_cls.return_value = mock_client

        result = await fetch_google_books_rating("Any Book", "Any Author")

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_google_books.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement app/ratings/google_books.py**

Create `app/ratings/__init__.py` (empty file).

Create `app/ratings/google_books.py`:

```python
import httpx
from app.config import settings

GOOGLE_BOOKS_URL = "https://www.googleapis.com/books/v1/volumes"


async def fetch_google_books_rating(
    title: str, author: str
) -> dict | None:
    """Fetch rating from Google Books API. Returns None if unavailable."""
    params = {
        "q": f"{title}+inauthor:{author}",
        "key": settings.google_books_api_key,
        "maxResults": 1,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(GOOGLE_BOOKS_URL, params=params)
            response.raise_for_status()
            data = response.json()

        items = data.get("items", [])
        if not items:
            return None

        volume = items[0].get("volumeInfo", {})
        rating = volume.get("averageRating")
        count = volume.get("ratingsCount")

        if rating is None:
            return None

        return {"rating": rating, "count": count or 0}
    except Exception:
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_google_books.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/ratings/__init__.py app/ratings/google_books.py tests/test_google_books.py
git commit -m "feat: Google Books API client for ratings"
```

---

### Task 4: Claude LLM Assessment

**Files:**
- Create: `app/ratings/llm.py`
- Create: `tests/test_llm.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_llm.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.ratings.llm import assess_book


class TestLLMAssessment:
    @patch("app.ratings.llm.AsyncAnthropic")
    async def test_returns_assessment(self, mock_anthropic_cls):
        mock_client = AsyncMock()
        mock_message = MagicMock()
        mock_message.content = [
            MagicMock(
                text='{"quality_tier": "highly_acclaimed", "confidence": "high", '
                '"notable_awards": ["Goodreads Choice Award 2020"], '
                '"brief_rationale": "Widely praised novel about parallel lives."}'
            )
        ]
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic_cls.return_value = mock_client

        result = await assess_book("The Midnight Library", "Matt Haig")

        assert result["quality_tier"] == "highly_acclaimed"
        assert result["confidence"] == "high"
        assert isinstance(result["notable_awards"], list)
        assert result["brief_rationale"]

    @patch("app.ratings.llm.AsyncAnthropic")
    async def test_returns_none_on_api_error(self, mock_anthropic_cls):
        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(
            side_effect=Exception("API error")
        )
        mock_anthropic_cls.return_value = mock_client

        result = await assess_book("Any Book", "Any Author")

        assert result is None

    @patch("app.ratings.llm.AsyncAnthropic")
    async def test_returns_none_on_malformed_json(self, mock_anthropic_cls):
        mock_client = AsyncMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="not json at all")]
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        mock_anthropic_cls.return_value = mock_client

        result = await assess_book("Any Book", "Any Author")

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_llm.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement app/ratings/llm.py**

```python
import json
from anthropic import AsyncAnthropic
from app.config import settings


async def assess_book(title: str, author: str) -> dict | None:
    """Use Claude to assess how well-regarded a book is."""
    if not settings.anthropic_api_key:
        return None

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Given the book "{title}" by {author}, assess how well-regarded this book is. '
                        "Respond with ONLY JSON: "
                        '{"quality_tier": "<classic|highly_acclaimed|well_received|mixed|poorly_received|unknown>", '
                        '"confidence": "<high|medium|low>", '
                        '"notable_awards": ["..."], '
                        '"brief_rationale": "one sentence"}'
                    ),
                }
            ],
        )
        return json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError, Exception):
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/ratings/llm.py tests/test_llm.py
git commit -m "feat: Claude LLM book assessment service"
```

---

### Task 5: Goodreads Scraper

**Files:**
- Create: `app/ratings/goodreads.py`
- Create: `tests/test_goodreads.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_goodreads.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.ratings.goodreads import scrape_goodreads_rating


class TestGoodreadsScraper:
    @patch("app.ratings.goodreads.async_playwright")
    async def test_returns_rating_on_success(self, mock_pw):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        # Mock the rating element
        mock_rating_el = AsyncMock()
        mock_rating_el.inner_text = AsyncMock(return_value="4.02")
        mock_page.query_selector = AsyncMock(
            side_effect=lambda sel: {
                '[data-testid="ratingsCount"]': AsyncMock(
                    inner_text=AsyncMock(return_value="1,234,567 ratings")
                ),
            }.get(sel, mock_rating_el)
        )
        mock_page.url = "https://www.goodreads.com/book/show/12345"

        # Mock rating via evaluate
        mock_page.evaluate = AsyncMock(return_value=4.02)

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_context_mgr = AsyncMock()
        mock_context_mgr.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context_mgr)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scrape_goodreads_rating("The Midnight Library", "Matt Haig")

        assert result is not None
        assert result["rating"] == 4.02

    @patch("app.ratings.goodreads.async_playwright")
    async def test_returns_none_on_timeout(self, mock_pw):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=TimeoutError("Timed out"))

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_context_mgr = AsyncMock()
        mock_context_mgr.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context_mgr)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scrape_goodreads_rating("Any Book", "Any Author")

        assert result is None

    @patch("app.ratings.goodreads.async_playwright")
    async def test_returns_none_on_missing_elements(self, mock_pw):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(
            side_effect=TimeoutError("Element not found")
        )

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_context_mgr = AsyncMock()
        mock_context_mgr.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context_mgr)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await scrape_goodreads_rating("Any Book", "Any Author")

        assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_goodreads.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement app/ratings/goodreads.py**

```python
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

            await browser.close()

            return {
                "rating": rating,
                "count": count,
                "url": book_url,
            }
    except Exception:
        return None


def _parse_count(text: str) -> int:
    """Parse '1,234,567 ratings' into 1234567."""
    numbers = re.findall(r"[\d,]+", text)
    if numbers:
        return int(numbers[0].replace(",", ""))
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_goodreads.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/ratings/goodreads.py tests/test_goodreads.py
git commit -m "feat: Goodreads Playwright scraper"
```

---

### Task 6: Rating Synthesizer

**Files:**
- Create: `app/ratings/synthesizer.py`
- Create: `tests/test_synthesizer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_synthesizer.py`:

```python
import pytest
from app.ratings.synthesizer import synthesize


class TestSynthesizer:
    def test_recommended_from_goodreads(self):
        result = synthesize(
            goodreads={"rating": 4.2, "count": 100000, "url": "..."},
            google_books=None,
            llm=None,
        )
        assert result["verdict"] == "Recommended"

    def test_recommended_from_google_books(self):
        result = synthesize(
            goodreads=None,
            google_books={"rating": 4.3, "count": 200},
            llm=None,
        )
        assert result["verdict"] == "Recommended"

    def test_recommended_from_llm_only(self):
        result = synthesize(
            goodreads=None,
            google_books=None,
            llm={
                "quality_tier": "highly_acclaimed",
                "confidence": "high",
                "notable_awards": ["Pulitzer Prize"],
                "brief_rationale": "Masterful novel.",
            },
        )
        assert result["verdict"] == "Recommended"

    def test_mixed_reviews(self):
        result = synthesize(
            goodreads={"rating": 3.5, "count": 50000, "url": "..."},
            google_books=None,
            llm=None,
        )
        assert result["verdict"] == "Mixed Reviews"

    def test_not_recommended(self):
        result = synthesize(
            goodreads={"rating": 2.5, "count": 10000, "url": "..."},
            google_books=None,
            llm=None,
        )
        assert result["verdict"] == "Not Recommended"

    def test_not_enough_data(self):
        result = synthesize(goodreads=None, google_books=None, llm=None)
        assert result["verdict"] == "Not Enough Data"

    def test_conflicting_signals(self):
        result = synthesize(
            goodreads={"rating": 4.5, "count": 100000, "url": "..."},
            google_books=None,
            llm={
                "quality_tier": "poorly_received",
                "confidence": "high",
                "notable_awards": [],
                "brief_rationale": "Generally disliked.",
            },
        )
        assert result["verdict"] == "Mixed Signals"

    def test_summary_mentions_sources(self):
        result = synthesize(
            goodreads={"rating": 4.2, "count": 100000, "url": "..."},
            google_books={"rating": 4.0, "count": 50},
            llm={
                "quality_tier": "well_received",
                "confidence": "high",
                "notable_awards": [],
                "brief_rationale": "Solid novel.",
            },
        )
        assert "Goodreads" in result["summary"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_synthesizer.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement app/ratings/synthesizer.py**

```python
POSITIVE_TIERS = {"classic", "highly_acclaimed"}
NEGATIVE_TIERS = {"poorly_received"}


def synthesize(
    goodreads: dict | None,
    google_books: dict | None,
    llm: dict | None,
) -> dict:
    """Combine all rating signals into a single recommendation."""
    sources = []
    parts = []

    gr_rating = goodreads["rating"] if goodreads else None
    gb_rating = google_books["rating"] if google_books else None
    llm_tier = llm["quality_tier"] if llm else None
    llm_confidence = llm.get("confidence", "low") if llm else "low"

    # Rule 1: Not enough data
    if gr_rating is None and gb_rating is None and llm is None:
        return {
            "verdict": "Not Enough Data",
            "summary": "Couldn't find ratings from any source.",
        }

    # Collect source descriptions
    if gr_rating is not None:
        sources.append(f"Goodreads: {gr_rating}/5")
    if gb_rating is not None:
        sources.append(f"Google Books: {gb_rating}/5")
    if llm:
        sources.append(f"AI assessment: {llm_tier}")

    # Rule 2: Conflicting signals
    best_numeric = max(
        r for r in [gr_rating, gb_rating] if r is not None
    ) if any(r is not None for r in [gr_rating, gb_rating]) else None

    if best_numeric is not None and best_numeric >= 4.0 and llm_tier in NEGATIVE_TIERS and llm_confidence == "high":
        summary = f"Mixed signals — check reviews. {'. '.join(sources)}."
        if llm and llm.get("brief_rationale"):
            summary += f" AI says: {llm['brief_rationale']}"
        return {"verdict": "Mixed Signals", "summary": summary}

    if best_numeric is not None and best_numeric < 3.0 and llm_tier in POSITIVE_TIERS and llm_confidence == "high":
        summary = f"Mixed signals — check reviews. {'. '.join(sources)}."
        return {"verdict": "Mixed Signals", "summary": summary}

    # Rule 3: Recommended
    numeric_recommended = (gr_rating is not None and gr_rating >= 4.0) or (
        gb_rating is not None and gb_rating >= 4.0
    )
    llm_recommended = llm_tier in POSITIVE_TIERS and llm_confidence == "high"

    if numeric_recommended or llm_recommended:
        summary = f"{'. '.join(sources)}."
        if llm and llm.get("notable_awards"):
            summary += f" Awards: {', '.join(llm['notable_awards'])}."
        if llm and llm.get("brief_rationale"):
            summary += f" {llm['brief_rationale']}"
        return {"verdict": "Recommended", "summary": summary}

    # Rule 4: Mixed reviews
    numeric_mixed = (gr_rating is not None and 3.0 <= gr_rating < 4.0) or (
        gb_rating is not None and 3.0 <= gb_rating < 4.0
    )
    llm_mixed = llm_tier in {"mixed", "well_received"}

    if numeric_mixed or llm_mixed:
        summary = f"{'. '.join(sources)}."
        if llm and llm.get("brief_rationale"):
            summary += f" {llm['brief_rationale']}"
        return {"verdict": "Mixed Reviews", "summary": summary}

    # Rule 5: Not recommended
    numeric_low = (gr_rating is not None and gr_rating < 3.0) or (
        gb_rating is not None and gb_rating < 3.0
    )
    llm_low = llm_tier in NEGATIVE_TIERS and llm_confidence == "high"

    if numeric_low or llm_low:
        summary = f"{'. '.join(sources)}."
        if llm and llm.get("brief_rationale"):
            summary += f" {llm['brief_rationale']}"
        return {"verdict": "Not Recommended", "summary": summary}

    # Fallback
    summary = f"{'. '.join(sources)}."
    return {"verdict": "Not Enough Data", "summary": summary}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_synthesizer.py -v
```

Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add app/ratings/synthesizer.py tests/test_synthesizer.py
git commit -m "feat: rating synthesizer combining all sources"
```

---

## Chunk 3: Library Automation + API Routes

### Task 7: BiblioCommons Library Automation

**Files:**
- Create: `app/library/__init__.py`
- Create: `app/library/bibliocommons.py`
- Create: `tests/test_bibliocommons.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_bibliocommons.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.library.bibliocommons import (
    search_library,
    place_hold,
    _select_best_edition,
)


class TestSelectBestEdition:
    def test_picks_available_copy(self):
        editions = [
            {"format": "Hardcover", "copies": 2, "available": 0, "hold_queue": 5, "id": "hc1"},
            {"format": "Paperback", "copies": 3, "available": 1, "hold_queue": 0, "id": "pb1"},
        ]
        best = _select_best_edition(editions)
        assert best["id"] == "pb1"
        assert best["estimated_wait_days"] == 0

    def test_picks_shortest_queue(self):
        editions = [
            {"format": "Hardcover", "copies": 2, "available": 0, "hold_queue": 10, "id": "hc1"},
            {"format": "Paperback", "copies": 4, "available": 0, "hold_queue": 4, "id": "pb1"},
        ]
        best = _select_best_edition(editions)
        assert best["id"] == "pb1"

    def test_skips_zero_copies(self):
        editions = [
            {"format": "Hardcover", "copies": 0, "available": 0, "hold_queue": 0, "id": "hc1"},
            {"format": "Paperback", "copies": 1, "available": 1, "hold_queue": 0, "id": "pb1"},
        ]
        best = _select_best_edition(editions)
        assert best["id"] == "pb1"

    def test_returns_none_when_no_editions(self):
        best = _select_best_edition([])
        assert best is None

    def test_returns_none_when_all_zero_copies(self):
        editions = [
            {"format": "Hardcover", "copies": 0, "available": 0, "hold_queue": 0, "id": "hc1"},
        ]
        best = _select_best_edition(editions)
        assert best is None


class TestSearchLibrary:
    @patch("app.library.bibliocommons.async_playwright")
    async def test_returns_editions_on_success(self, mock_pw):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.fill = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        # Mock search results — return items that look like physical books
        mock_page.evaluate = AsyncMock(
            return_value=[
                {
                    "format": "Paperback",
                    "copies": 3,
                    "available": 2,
                    "hold_queue": 0,
                    "id": "pb1",
                }
            ]
        )

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_context_mgr = AsyncMock()
        mock_context_mgr.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context_mgr)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await search_library("The Midnight Library", "Matt Haig")

        assert result is not None
        assert result["available"] is True
        assert len(result["editions"]) == 1

    @patch("app.library.bibliocommons.async_playwright")
    async def test_returns_unavailable_on_no_results(self, mock_pw):
        mock_page = AsyncMock()
        mock_page.goto = AsyncMock()
        mock_page.fill = AsyncMock()
        mock_page.click = AsyncMock()
        mock_page.wait_for_selector = AsyncMock(
            side_effect=TimeoutError("No results")
        )
        mock_page.evaluate = AsyncMock(return_value=[])

        mock_browser = AsyncMock()
        mock_browser.new_page = AsyncMock(return_value=mock_page)
        mock_context_mgr = AsyncMock()
        mock_context_mgr.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_pw.return_value.__aenter__ = AsyncMock(return_value=mock_context_mgr)
        mock_pw.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await search_library("Nonexistent Book", "Nobody")

        assert result is not None
        assert result["available"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_bibliocommons.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement app/library/bibliocommons.py**

Create `app/library/__init__.py` (empty file).

Create `app/library/bibliocommons.py`:

```python
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

    # Try to parse "X of Y copies available" or "X holds on Y copies"
    import re

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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_bibliocommons.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add app/library/__init__.py app/library/bibliocommons.py tests/test_bibliocommons.py
git commit -m "feat: BiblioCommons library search and hold placement"
```

---

### Task 8: FastAPI Routes

**Files:**
- Modify: `app/main.py`
- Create: `tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_api.py`:

```python
import pytest
from unittest.mock import patch, AsyncMock
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestScanEndpoint:
    @patch("app.main.search_library", new_callable=AsyncMock)
    @patch("app.main.assess_book", new_callable=AsyncMock)
    @patch("app.main.fetch_google_books_rating", new_callable=AsyncMock)
    @patch("app.main.scrape_goodreads_rating", new_callable=AsyncMock)
    @patch("app.main.extract_book_info", new_callable=AsyncMock)
    async def test_scan_returns_recommendation(
        self, mock_ocr, mock_gr, mock_gb, mock_llm, mock_lib, client
    ):
        mock_ocr.return_value = {
            "title": "The Midnight Library",
            "author": "Matt Haig",
        }
        mock_gr.return_value = {"rating": 4.02, "count": 1200000, "url": "..."}
        mock_gb.return_value = {"rating": 4.1, "count": 350}
        mock_llm.return_value = {
            "quality_tier": "highly_acclaimed",
            "confidence": "high",
            "notable_awards": [],
            "brief_rationale": "Great book.",
        }
        mock_lib.return_value = {
            "available": True,
            "editions": [],
            "best_edition": {"format": "Paperback", "estimated_wait_days": 0, "id": "/item/123"},
        }

        # Create a fake image file
        import io
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        response = await client.post(
            "/api/scan",
            files={"image": ("test.png", buf, "image/png")},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "The Midnight Library"
        assert data["recommendation"]["verdict"] == "Recommended"

    @patch("app.main.extract_book_info", new_callable=AsyncMock)
    async def test_scan_returns_error_on_ocr_failure(self, mock_ocr, client):
        mock_ocr.return_value = None

        import io
        from PIL import Image

        img = Image.new("RGB", (100, 100), color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)

        response = await client.post(
            "/api/scan",
            files={"image": ("test.png", buf, "image/png")},
        )

        assert response.status_code == 400
        assert "Couldn't read" in response.json()["detail"]


class TestHoldEndpoint:
    @patch("app.main.place_hold", new_callable=AsyncMock)
    async def test_hold_returns_success(self, mock_hold, client):
        mock_hold.return_value = {
            "success": True,
            "message": "Hold placed successfully",
            "details": {
                "title": "The Midnight Library",
                "library": "Burlingame Public Library",
            },
        }

        response = await client.post(
            "/api/hold",
            json={"edition_id": "/item/123", "title": "The Midnight Library"},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    @patch("app.main.place_hold", new_callable=AsyncMock)
    async def test_hold_returns_failure(self, mock_hold, client):
        mock_hold.return_value = {
            "success": False,
            "message": "Library login failed.",
            "details": None,
        }

        response = await client.post(
            "/api/hold",
            json={"edition_id": "/item/123", "title": "Some Book"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_api.py -v
```

Expected: FAIL — routes not defined

- [ ] **Step 3: Implement app/main.py**

```python
import asyncio
import os
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.ocr import extract_book_info
from app.ratings.goodreads import scrape_goodreads_rating
from app.ratings.google_books import fetch_google_books_rating
from app.ratings.llm import assess_book
from app.ratings.synthesizer import synthesize
from app.library.bibliocommons import search_library, place_hold

app = FastAPI(title="BookSnap")


class HoldRequest(BaseModel):
    edition_id: str
    title: str


@app.post("/api/scan")
async def scan_book(image: UploadFile = File(...)):
    # Save uploaded image to temp file
    suffix = os.path.splitext(image.filename or "image.png")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await image.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # OCR
        book_info = await extract_book_info(tmp_path)
        if not book_info:
            raise HTTPException(
                status_code=400,
                detail="Couldn't read the cover. Try again with better lighting.",
            )

        title = book_info["title"]
        author = book_info["author"]

        # Run rating pipeline + library search in parallel
        goodreads_task = scrape_goodreads_rating(title, author)
        google_task = fetch_google_books_rating(title, author)
        llm_task = assess_book(title, author)
        library_task = search_library(title, author)

        goodreads, google_books, llm, library = await asyncio.gather(
            goodreads_task, google_task, llm_task, library_task
        )

        recommendation = synthesize(goodreads, google_books, llm)

        return {
            "title": title,
            "author": author,
            "ratings": {
                "goodreads": goodreads,
                "google_books": google_books,
                "llm": llm,
            },
            "recommendation": recommendation,
            "library": library,
        }
    finally:
        os.unlink(tmp_path)


@app.post("/api/hold")
async def hold_book(request: HoldRequest):
    result = await place_hold(request.edition_id, request.title)
    return result


# Mount static files last so API routes take priority
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_api.py -v
```

Expected: 4 passed

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: All tests pass (17+ tests)

- [ ] **Step 6: Commit**

```bash
git add app/main.py tests/test_api.py tests/conftest.py
git commit -m "feat: FastAPI routes for /api/scan and /api/hold"
```

---

## Chunk 4: Frontend + Deployment

### Task 9: Frontend — Mobile UI

**Files:**
- Create: `app/static/index.html`
- Create: `app/static/style.css`
- Create: `app/static/app.js`

- [ ] **Step 1: Create index.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>BookSnap</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div id="app">
        <header>
            <h1>BookSnap</h1>
            <p class="tagline">Snap a cover. Get a recommendation.</p>
        </header>

        <!-- State 1: Capture -->
        <div id="capture-screen" class="screen active">
            <div class="capture-area" onclick="document.getElementById('camera-input').click()">
                <div class="camera-icon">&#128247;</div>
                <p>Tap to take a photo<br>of a book cover</p>
            </div>
            <input type="file" id="camera-input" accept="image/*" capture="environment" hidden>
            <button class="btn-primary" onclick="document.getElementById('camera-input').click()">
                Take Photo
            </button>
            <label class="upload-link">
                or upload an image
                <input type="file" id="upload-input" accept="image/*" hidden>
            </label>
        </div>

        <!-- Loading -->
        <div id="loading-screen" class="screen">
            <div class="spinner"></div>
            <p id="loading-text">Reading cover...</p>
        </div>

        <!-- State 2: Results -->
        <div id="results-screen" class="screen">
            <div class="book-info">
                <div class="book-cover" id="book-cover"></div>
                <div class="book-details">
                    <h2 id="book-title"></h2>
                    <p id="book-author"></p>
                    <div id="rating-badges"></div>
                </div>
            </div>
            <div id="recommendation-card" class="recommendation-card"></div>
            <div id="library-section" class="library-section"></div>
            <button id="hold-btn" class="btn-primary" style="display:none">
                Place Hold
            </button>
            <button class="btn-secondary" onclick="resetApp()">Scan Another Book</button>
        </div>

        <!-- State 3: Confirmation -->
        <div id="confirm-screen" class="screen">
            <div class="confirm-icon">&#9989;</div>
            <h2>Hold Placed!</h2>
            <div id="confirm-details"></div>
            <button class="btn-primary" onclick="resetApp()">Scan Another Book</button>
            <a id="library-link" class="link" href="#" target="_blank">View on Library Site</a>
        </div>

        <!-- Error -->
        <div id="error-screen" class="screen">
            <div class="error-icon">&#9888;</div>
            <p id="error-text"></p>
            <button class="btn-primary" onclick="resetApp()">Try Again</button>
        </div>
    </div>
    <script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create style.css**

```css
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f1a;
    color: #e0e0e0;
    min-height: 100vh;
    display: flex;
    justify-content: center;
}

#app {
    width: 100%;
    max-width: 420px;
    padding: 20px;
}

header {
    text-align: center;
    margin-bottom: 24px;
}

header h1 {
    font-size: 24px;
    font-weight: 700;
}

.tagline {
    color: #888;
    font-size: 13px;
    margin-top: 4px;
}

.screen {
    display: none;
}

.screen.active {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 16px;
}

/* Capture */
.capture-area {
    width: 100%;
    min-height: 250px;
    border: 2px dashed #333;
    border-radius: 16px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    transition: border-color 0.2s;
}

.capture-area:active {
    border-color: #6c5ce7;
}

.camera-icon {
    font-size: 48px;
    margin-bottom: 12px;
}

.capture-area p {
    color: #888;
    text-align: center;
    font-size: 14px;
    line-height: 1.5;
}

/* Buttons */
.btn-primary {
    width: 100%;
    padding: 14px;
    background: #6c5ce7;
    color: white;
    border: none;
    border-radius: 12px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
}

.btn-primary:active {
    background: #5a4bd1;
}

.btn-primary:disabled {
    background: #444;
    cursor: not-allowed;
}

.btn-secondary {
    width: 100%;
    padding: 12px;
    background: transparent;
    color: #6c5ce7;
    border: 1px solid #6c5ce7;
    border-radius: 12px;
    font-size: 15px;
    cursor: pointer;
}

.upload-link {
    color: #666;
    font-size: 13px;
    cursor: pointer;
}

.link {
    color: #6c5ce7;
    font-size: 14px;
    text-decoration: none;
}

/* Loading */
.spinner {
    width: 40px;
    height: 40px;
    border: 4px solid #333;
    border-top: 4px solid #6c5ce7;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 40px 0 16px;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

#loading-text {
    color: #888;
    font-size: 14px;
}

/* Book info */
.book-info {
    display: flex;
    gap: 14px;
    width: 100%;
    margin-bottom: 8px;
}

.book-cover {
    width: 80px;
    height: 110px;
    background: #1e1e2e;
    border-radius: 6px;
    flex-shrink: 0;
    overflow: hidden;
}

.book-cover img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.book-details h2 {
    font-size: 17px;
    font-weight: 600;
    line-height: 1.3;
}

.book-details p {
    color: #888;
    font-size: 13px;
    margin-top: 2px;
}

#rating-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}

.badge {
    font-size: 12px;
    padding: 3px 10px;
    border-radius: 12px;
    font-weight: 500;
}

.badge-goodreads {
    background: #2d5a2d;
    color: #7ddf7d;
}

.badge-google {
    background: #2d3a5a;
    color: #7db5df;
}

.badge-llm {
    background: #4a3a5a;
    color: #c09ddf;
}

/* Recommendation card */
.recommendation-card {
    width: 100%;
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 4px;
}

.recommendation-card.recommended {
    background: #1e3a1e;
    border: 1px solid #2d5a2d;
}

.recommendation-card.mixed {
    background: #3a3a1e;
    border: 1px solid #5a5a2d;
}

.recommendation-card.not-recommended {
    background: #3a1e1e;
    border: 1px solid #5a2d2d;
}

.recommendation-card.no-data {
    background: #1e1e2e;
    border: 1px solid #333;
}

.recommendation-card .verdict {
    font-weight: 600;
    font-size: 14px;
    margin-bottom: 4px;
}

.recommendation-card .summary {
    color: #aaa;
    font-size: 13px;
    line-height: 1.4;
}

/* Library section */
.library-section {
    width: 100%;
    background: #1e1e2e;
    border-radius: 12px;
    padding: 14px;
}

.library-section h3 {
    font-size: 14px;
    font-weight: 600;
    margin-bottom: 6px;
}

.library-section p {
    color: #888;
    font-size: 13px;
    line-height: 1.5;
}

/* Confirmation */
.confirm-icon {
    font-size: 56px;
    margin: 20px 0 12px;
}

#confirm-screen h2 {
    color: #7ddf7d;
    font-size: 22px;
    margin-bottom: 12px;
}

#confirm-details {
    color: #aaa;
    font-size: 14px;
    text-align: center;
    margin-bottom: 20px;
    line-height: 1.6;
}

/* Error */
.error-icon {
    font-size: 48px;
    margin: 20px 0 12px;
}

#error-text {
    color: #aaa;
    text-align: center;
    font-size: 14px;
    margin-bottom: 16px;
    line-height: 1.5;
}
```

- [ ] **Step 3: Create app.js**

```javascript
const screens = ['capture-screen', 'loading-screen', 'results-screen', 'confirm-screen', 'error-screen'];

function showScreen(id) {
    screens.forEach(s => {
        document.getElementById(s).classList.remove('active');
    });
    document.getElementById(id).classList.add('active');
}

function resetApp() {
    showScreen('capture-screen');
}

function setLoadingText(text) {
    document.getElementById('loading-text').textContent = text;
}

function showError(text) {
    document.getElementById('error-text').textContent = text;
    showScreen('error-screen');
}

// File input handlers
document.getElementById('camera-input').addEventListener('change', handleFile);
document.getElementById('upload-input').addEventListener('change', handleFile);

let scanResult = null;

async function handleFile(e) {
    const file = e.target.files[0];
    if (!file) return;

    showScreen('loading-screen');
    setLoadingText('Reading cover...');

    const formData = new FormData();
    formData.append('image', file);

    try {
        setLoadingText('Analyzing book...');
        const response = await fetch('/api/scan', {
            method: 'POST',
            body: formData,
        });

        if (!response.ok) {
            const err = await response.json();
            showError(err.detail || 'Something went wrong. Try again.');
            return;
        }

        scanResult = await response.json();
        displayResults(scanResult);
    } catch (err) {
        showError('Network error. Check your connection and try again.');
    }

    // Reset file inputs so the same file can be selected again
    e.target.value = '';
}

function displayResults(data) {
    // Title & author
    document.getElementById('book-title').textContent = data.title;
    document.getElementById('book-author').textContent = data.author;

    // Rating badges
    const badges = document.getElementById('rating-badges');
    badges.innerHTML = '';

    if (data.ratings.goodreads) {
        badges.innerHTML += `<span class="badge badge-goodreads">Goodreads ${data.ratings.goodreads.rating}</span>`;
    }
    if (data.ratings.google_books) {
        badges.innerHTML += `<span class="badge badge-google">Google ${data.ratings.google_books.rating}</span>`;
    }
    if (data.ratings.llm) {
        const tier = data.ratings.llm.quality_tier.replace('_', ' ');
        badges.innerHTML += `<span class="badge badge-llm">${tier}</span>`;
    }

    // Recommendation card
    const card = document.getElementById('recommendation-card');
    const verdict = data.recommendation.verdict;
    let cardClass = 'no-data';
    let icon = '';

    if (verdict === 'Recommended') { cardClass = 'recommended'; icon = '&#128077;'; }
    else if (verdict === 'Mixed Reviews' || verdict === 'Mixed Signals') { cardClass = 'mixed'; icon = '&#129300;'; }
    else if (verdict === 'Not Recommended') { cardClass = 'not-recommended'; icon = '&#128078;'; }

    card.className = `recommendation-card ${cardClass}`;
    card.innerHTML = `
        <div class="verdict">${icon} ${verdict}</div>
        <div class="summary">${data.recommendation.summary}</div>
    `;

    // Library section
    const libSection = document.getElementById('library-section');
    const holdBtn = document.getElementById('hold-btn');

    if (data.library && data.library.available) {
        const best = data.library.best_edition;
        let libHtml = '<h3>Burlingame Library</h3>';

        if (best) {
            const waitText = best.estimated_wait_days === 0 ? 'Available now' : `~${best.estimated_wait_days} day wait`;
            libHtml += `<p>${best.format} &middot; ${waitText}</p>`;
        }

        if (data.library.editions.length > 0) {
            libHtml += `<p>${data.library.editions.length} physical edition(s) found</p>`;
        }

        libSection.innerHTML = libHtml;
        holdBtn.style.display = 'block';
        holdBtn.onclick = () => placeHold(best.id, data.title);
    } else {
        libSection.innerHTML = '<h3>Burlingame Library</h3><p>Not available in catalog</p>';
        holdBtn.style.display = 'none';
    }

    showScreen('results-screen');
}

async function placeHold(editionId, title) {
    const holdBtn = document.getElementById('hold-btn');
    holdBtn.disabled = true;
    holdBtn.textContent = 'Placing hold...';

    try {
        const response = await fetch('/api/hold', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ edition_id: editionId, title: title }),
        });

        const result = await response.json();

        if (result.success) {
            const details = document.getElementById('confirm-details');
            details.innerHTML = `
                <div>${result.details.title}</div>
                <div>${result.details.format || ''} &middot; ${result.details.library}</div>
            `;
            const libLink = document.getElementById('library-link');
            libLink.href = `https://burlingame.bibliocommons.com${editionId}`;
            showScreen('confirm-screen');
        } else {
            showError(result.message);
        }
    } catch (err) {
        showError('Network error while placing hold. Try again.');
    }

    holdBtn.disabled = false;
    holdBtn.textContent = 'Place Hold';
}
```

- [ ] **Step 4: Manually test the UI locally**

```bash
cd /Users/deepak/AI/BookSearchApp
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Open `http://localhost:8000` in a mobile browser or Chrome DevTools mobile view. Verify:
- Capture screen renders with camera button
- File input triggers camera on mobile
- Layout is centered and readable on small screens

- [ ] **Step 5: Commit**

```bash
git add app/static/index.html app/static/style.css app/static/app.js
git commit -m "feat: mobile-first frontend UI with three-state flow"
```

---

### Task 10: Dockerfile + Deployment Config

**Files:**
- Create: `Dockerfile`
- Create: `.env.example` (already exists, verify)

- [ ] **Step 1: Create Dockerfile**

```dockerfile
FROM python:3.12-slim

# Install Tesseract OCR and system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium && playwright install-deps chromium

# Copy application code
COPY app/ ./app/

# Expose port (Railway sets PORT env var)
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
```

- [ ] **Step 2: Verify .env.example is correct**

Should contain:
```
LIBRARY_CARD_NUMBER=your_library_card_number
LIBRARY_PIN=your_library_pin
GOOGLE_BOOKS_API_KEY=your_google_books_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```

- [ ] **Step 3: Build and test Docker image locally**

```bash
docker build -t booksnap .
docker run --rm -p 8000:8000 --env-file .env booksnap
```

Verify app loads at `http://localhost:8000`.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: Dockerfile for Railway deployment"
```

---

### Task 11: Final Integration Test

- [ ] **Step 1: Run full test suite**

```bash
pytest -v
```

Expected: All tests pass.

- [ ] **Step 2: Run app locally and test end-to-end with a real book photo**

```bash
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

1. Open `http://localhost:8000` on your phone (same network) or in Chrome mobile view
2. Take a photo of a book cover
3. Verify: OCR extracts title/author, ratings load, recommendation shows
4. Tap "Place Hold" (test with real library credentials in `.env`)
5. Verify hold is placed or appropriate error is shown

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: ready for deployment"
```
