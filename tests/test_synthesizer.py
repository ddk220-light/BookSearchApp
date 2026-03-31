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
