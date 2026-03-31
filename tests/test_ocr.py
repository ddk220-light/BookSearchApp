import pytest
from unittest.mock import patch, MagicMock
from app.ocr import extract_book_info


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
