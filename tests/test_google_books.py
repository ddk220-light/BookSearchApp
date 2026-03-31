import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.ratings.google_books import fetch_google_books_rating


def _make_mock_client(response_data):
    """Create a mock httpx.AsyncClient with the given response data."""
    mock_response = MagicMock()
    mock_response.json.return_value = response_data
    mock_response.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = False
    mock_client.get = AsyncMock(return_value=mock_response)
    return mock_client


class TestGoogleBooksRating:
    @patch("app.ratings.google_books.httpx.AsyncClient")
    async def test_returns_rating_when_available(self, mock_client_cls):
        mock_client_cls.return_value = _make_mock_client({
            "items": [
                {
                    "volumeInfo": {
                        "averageRating": 4.1,
                        "ratingsCount": 350,
                    }
                }
            ]
        })

        result = await fetch_google_books_rating("The Midnight Library", "Matt Haig")

        assert result["rating"] == 4.1
        assert result["count"] == 350

    @patch("app.ratings.google_books.httpx.AsyncClient")
    async def test_returns_none_when_no_rating(self, mock_client_cls):
        mock_client_cls.return_value = _make_mock_client({
            "items": [{"volumeInfo": {"title": "Some Book"}}]
        })

        result = await fetch_google_books_rating("Unknown Book", "Unknown Author")

        assert result is None

    @patch("app.ratings.google_books.httpx.AsyncClient")
    async def test_returns_none_on_error(self, mock_client_cls):
        mock_client = AsyncMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))
        mock_client_cls.return_value = mock_client

        result = await fetch_google_books_rating("Any Book", "Any Author")

        assert result is None
