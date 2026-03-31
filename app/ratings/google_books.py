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
