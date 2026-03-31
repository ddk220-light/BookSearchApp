import pytest
from unittest.mock import patch, AsyncMock
from app.ratings.goodreads import scrape_goodreads_rating


class TestGoodreadsScraper:
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
