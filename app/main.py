import asyncio
import os
import tempfile

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
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


@app.get("/api/goodreads")
async def goodreads_rating(
    title: str = Query(..., description="Book title"),
    author: str = Query("", description="Book author (optional)"),
):
    """Fetch Goodreads rating for a book by title and optional author.
    Returns JSON with rating, count, and url, or an error message."""
    result = await scrape_goodreads_rating(title, author)
    if result is None:
        return {"error": "Could not fetch Goodreads rating", "rating": None, "count": None, "url": None}
    return result


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
        goodreads, google_books, llm, library = await asyncio.gather(
            scrape_goodreads_rating(title, author),
            fetch_google_books_rating(title, author),
            assess_book(title, author),
            search_library(title, author),
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
