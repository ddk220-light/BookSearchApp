POSITIVE_TIERS = {"classic", "highly_acclaimed"}
NEGATIVE_TIERS = {"poorly_received"}


def synthesize(
    goodreads: dict | None,
    google_books: dict | None,
    llm: dict | None,
) -> dict:
    """Combine all rating signals into a single recommendation."""
    sources = []

    gr_rating = goodreads["rating"] if goodreads else None
    gb_rating = google_books["rating"] if google_books else None
    llm_tier = llm["quality_tier"] if llm else None
    llm_confidence = llm.get("confidence", "low") if llm else "low"

    # Rule 1: Not enough data
    if gr_rating is None and gb_rating is None and llm is None:
        return {
            "verdict": "Not Enough Data",
            "summary": "Couldn't find ratings from any source.",
        }

    # Collect source descriptions
    if gr_rating is not None:
        sources.append(f"Goodreads: {gr_rating}/5")
    if gb_rating is not None:
        sources.append(f"Google Books: {gb_rating}/5")
    if llm:
        sources.append(f"AI assessment: {llm_tier}")

    # Rule 2: Conflicting signals
    best_numeric = max(
        r for r in [gr_rating, gb_rating] if r is not None
    ) if any(r is not None for r in [gr_rating, gb_rating]) else None

    if best_numeric is not None and best_numeric >= 4.0 and llm_tier in NEGATIVE_TIERS and llm_confidence == "high":
        summary = f"Mixed signals — check reviews. {'. '.join(sources)}."
        if llm and llm.get("brief_rationale"):
            summary += f" AI says: {llm['brief_rationale']}"
        return {"verdict": "Mixed Signals", "summary": summary}

    if best_numeric is not None and best_numeric < 3.0 and llm_tier in POSITIVE_TIERS and llm_confidence == "high":
        summary = f"Mixed signals — check reviews. {'. '.join(sources)}."
        return {"verdict": "Mixed Signals", "summary": summary}

    # Rule 3: Recommended
    numeric_recommended = (gr_rating is not None and gr_rating >= 4.0) or (
        gb_rating is not None and gb_rating >= 4.0
    )
    llm_recommended = llm_tier in POSITIVE_TIERS and llm_confidence == "high"

    if numeric_recommended or llm_recommended:
        summary = f"{'. '.join(sources)}."
        if llm and llm.get("notable_awards"):
            summary += f" Awards: {', '.join(llm['notable_awards'])}."
        if llm and llm.get("brief_rationale"):
            summary += f" {llm['brief_rationale']}"
        return {"verdict": "Recommended", "summary": summary}

    # Rule 4: Mixed reviews
    numeric_mixed = (gr_rating is not None and 3.0 <= gr_rating < 4.0) or (
        gb_rating is not None and 3.0 <= gb_rating < 4.0
    )
    llm_mixed = llm_tier in {"mixed", "well_received"}

    if numeric_mixed or llm_mixed:
        summary = f"{'. '.join(sources)}."
        if llm and llm.get("brief_rationale"):
            summary += f" {llm['brief_rationale']}"
        return {"verdict": "Mixed Reviews", "summary": summary}

    # Rule 5: Not recommended
    numeric_low = (gr_rating is not None and gr_rating < 3.0) or (
        gb_rating is not None and gb_rating < 3.0
    )
    llm_low = llm_tier in NEGATIVE_TIERS and llm_confidence == "high"

    if numeric_low or llm_low:
        summary = f"{'. '.join(sources)}."
        if llm and llm.get("brief_rationale"):
            summary += f" {llm['brief_rationale']}"
        return {"verdict": "Not Recommended", "summary": summary}

    # Fallback
    summary = f"{'. '.join(sources)}."
    return {"verdict": "Not Enough Data", "summary": summary}
