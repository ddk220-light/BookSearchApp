import pytest
from unittest.mock import patch, AsyncMock
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
