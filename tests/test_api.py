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
