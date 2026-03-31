# BookSnap — Design Spec

Snap a book cover, get a recommendation, place a library hold in one tap.

## Overview

A mobile-first web app for personal use (with clean architecture for future multi-user support). The user photographs a book cover in a bookstore, the app identifies the book via OCR, fetches ratings from multiple sources, synthesizes a recommendation, and can place a hold at the Burlingame Public Library on the physical edition with the shortest wait.

## Tech Stack

- **Backend:** Python 3.12 + FastAPI (async)
- **OCR:** Tesseract via `pytesseract`, with Claude API fallback for ambiguous extractions
- **Browser Automation:** Playwright (Goodreads scraping + BiblioCommons library automation)
- **Frontend:** Vanilla HTML/CSS/JS (single-page, mobile-first)
- **Deployment:** Docker on Railway

## System Architecture

```
[Mobile Browser]
    → POST /api/scan (photo)
    → [FastAPI Server]
        → Tesseract OCR → extract title/author
        → Rating Pipeline (cascading):
            1. Playwright → scrape Goodreads rating
            2. Google Books API (parallel with #3)
            3. Claude API → LLM assessment (parallel with #2)
            → Synthesize into recommendation
        → Return recommendation to user
    → User taps "Place Hold"
    → POST /api/hold
        → Playwright → BiblioCommons login → search →
          filter physical books → pick shortest queue → place hold
        → Return confirmation
```

## API Endpoints

### `POST /api/scan`

**Input:** Multipart form with image file.

**Processing:**
1. Save uploaded image to temp file
2. Run Tesseract OCR to extract text
3. Parse title/author from extracted text (heuristic: largest text = title, smaller text = author). If ambiguous, send raw text to Claude to parse.
4. Run rating pipeline (details below)
5. Return results

**Response:**
```json
{
  "title": "The Midnight Library",
  "author": "Matt Haig",
  "ratings": {
    "goodreads": { "rating": 4.02, "count": 1200000, "url": "..." },
    "google_books": { "rating": 4.1, "count": 350 },
    "llm": {
      "quality_tier": "highly_acclaimed",
      "confidence": "high",
      "notable_awards": ["Goodreads Choice Award 2020"],
      "brief_rationale": "Widely praised for its uplifting exploration of parallel lives..."
    }
  },
  "recommendation": {
    "verdict": "Recommended",
    "summary": "Highly rated across sources. NYT bestseller. Praised for its uplifting take on parallel lives."
  },
  "library": {
    "available": true,
    "editions": [
      {
        "format": "Paperback",
        "copies": 3,
        "available": 2,
        "hold_queue": 0,
        "id": "..."
      },
      {
        "format": "Hardcover",
        "copies": 1,
        "available": 0,
        "hold_queue": 4,
        "id": "..."
      }
    ],
    "best_edition": {
      "format": "Paperback",
      "estimated_wait_days": 0,
      "id": "..."
    }
  }
}
```

### `POST /api/hold`

**Input:**
```json
{
  "edition_id": "...",
  "title": "The Midnight Library"
}
```

**Processing:**
1. Launch Playwright browser
2. Navigate to BiblioCommons Burlingame catalog
3. Log in with credentials from environment variables
4. Navigate to the specified edition
5. Place hold

**Response:**
```json
{
  "success": true,
  "message": "Hold placed successfully",
  "details": {
    "title": "The Midnight Library",
    "format": "Paperback",
    "estimated_wait_days": 0,
    "library": "Burlingame Public Library"
  }
}
```

## Rating Pipeline Detail

### 1. Goodreads Scraper (Primary)

- Playwright navigates to `goodreads.com/search?q={title}+{author}`
- Scrapes from first result: average rating, rating count, genres, book URL
- Timeout: 15 seconds. On failure (blocked, timeout, parse error), returns `null` and pipeline continues.

### 2. Google Books API (Secondary, runs in parallel with #3)

- `GET https://www.googleapis.com/books/v1/volumes?q={title}+inauthor:{author}&key={API_KEY}`
- Extracts: `averageRating`, `ratingsCount` from first result
- Fast and reliable; returns `null` for rating fields if no rating data exists

### 3. Claude LLM Assessment (runs in parallel with #2)

- Sends prompt to Claude API:
  ```
  Given the book "{title}" by {author}, assess how well-regarded this book is.
  Respond with JSON: quality_tier (classic/highly_acclaimed/well_received/mixed/poorly_received/unknown),
  confidence (high/medium/low), notable_awards (list), brief_rationale (one sentence).
  ```
- Provides broad coverage for books where APIs return sparse data
- Timeout: 10 seconds

### 4. Synthesizer

Combines all available signals into a final recommendation:

- **"Recommended"** — Goodreads >= 4.0, OR Google Books >= 4.0, OR LLM says highly_acclaimed/classic with high confidence
- **"Mixed Reviews"** — ratings between 3.0-4.0, OR LLM says mixed/well_received
- **"Not Recommended"** — ratings below 3.0, OR LLM says poorly_received with high confidence
- **"Not Enough Data"** — all sources failed or returned insufficient data

The summary text explains which sources contributed and highlights notable awards or context from the LLM.

## Library Automation Detail

### BiblioCommons Integration

1. **Search:** Navigate to Burlingame library catalog, search by title + author
2. **Filter:** Exclude audiobooks and ebooks from results. Identify physical editions (hardcover, paperback, large print).
3. **Select Best Edition:** Among physical editions, pick the one with the shortest hold queue. Prefer available copies (0 wait) over any hold queue.
4. **Login:** Use library card number + PIN from environment variables
5. **Place Hold:** Click through the hold placement flow on BiblioCommons
6. **Confirm:** Return success/failure with details

### Edition Selection Logic

```
For each physical edition:
  if copies_available > 0: wait_days = 0
  else: wait_days = (hold_queue_length / total_copies) * 14  # rough estimate

Sort by wait_days ascending → pick first
```

## UI Design

Single-page app with three states:

### State 1: Capture
- App header ("BookSnap")
- Large camera capture area (uses `<input type="file" accept="image/*" capture="environment">` for mobile camera)
- "Take Photo" button + "or upload an image" text link
- Clean, centered layout

### State 2: Results + Recommendation
- Book info (cover thumbnail from Google Books, title, author)
- Rating badges (Goodreads, Google Books scores as colored pills)
- Recommendation card (green for Recommended, yellow for Mixed, gray for Not Enough Data)
- Library availability section (copies, hold queue, estimated wait)
- "Place Hold" button (prominent, primary action)

### State 3: Confirmation
- Success checkmark
- Hold details (title, format, library, estimated wait)
- "Scan Another Book" button
- "View on Library Site" link

### Loading States
- After photo capture: "Reading cover..." → "Checking Goodreads..." → "Getting recommendation..."
- After Place Hold tap: "Logging into library..." → "Placing hold..."

## Error Handling

### OCR Failures
- Blurry/unreadable: "Couldn't read the cover. Try again with better lighting?" + retry button
- Ambiguous text: fall back to Claude API to parse title/author from raw OCR output

### Rating Pipeline Failures
- Goodreads blocked/down: silently fall through to Google Books + LLM
- Google Books no rating: show "No Google rating available" in that slot
- Claude API down: skip LLM assessment, show only available ratings
- All sources fail: "Couldn't find ratings" + manual search links

### Library Automation Failures
- Book not in catalog: "Not available at Burlingame Library" + manual search link
- No physical copies: "Only available as audiobook/ebook"
- Login fails: "Library login failed. Check your credentials."
- Hold placement fails: show error + direct link to book page for manual hold
- Already on hold: "You already have a hold on this book"

## Configuration

### Environment Variables (`.env`)
```
LIBRARY_CARD_NUMBER=...
LIBRARY_PIN=...
GOOGLE_BOOKS_API_KEY=...
ANTHROPIC_API_KEY=...
```

### Railway Deployment
- Dockerfile: Python 3.12 + Playwright browsers + Tesseract OCR
- Single web service, `PORT` from Railway environment
- Environment variables configured in Railway dashboard

## Project Structure

```
BookSearchApp/
├── app/
│   ├── main.py              # FastAPI app, routes
│   ├── ocr.py               # Tesseract + Claude fallback
│   ├── ratings/
│   │   ├── goodreads.py     # Playwright scraper
│   │   ├── google_books.py  # Google Books API client
│   │   ├── llm.py           # Claude assessment
│   │   └── synthesizer.py   # Combine ratings → recommendation
│   ├── library/
│   │   └── bibliocommons.py # Playwright automation for holds
│   └── static/
│       ├── index.html        # Single-page mobile UI
│       ├── style.css
│       └── app.js
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Future Considerations (Not In Scope)

- Multi-user auth (design keeps credentials server-side, would need per-user credential storage)
- Scan history / reading list
- Notifications when holds are ready
- Support for other library systems beyond BiblioCommons
