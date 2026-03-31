import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from app.ratings.llm import assess_book


class TestLLMAssessment:
    @patch("app.ratings.llm.settings")
    @patch("app.ratings.llm.AsyncAnthropic")
    async def test_returns_assessment(self, mock_anthropic_cls, mock_settings):
        mock_settings.anthropic_api_key = "test-key"
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
