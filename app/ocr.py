import pytesseract
from PIL import Image
from anthropic import AsyncAnthropic
from app.config import settings


async def extract_book_info(image_path: str) -> dict | None:
    """Extract title and author from a book cover image.

    Uses Tesseract OCR with heuristic parsing. Falls back to Claude
    if the extraction is ambiguous (e.g., only one text block found).
    """
    img = Image.open(image_path)
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    # Filter to lines with actual text and reasonable confidence
    lines = []
    for i, text in enumerate(data["text"]):
        text = text.strip()
        if text and data["conf"][i] > 0:
            lines.append({"text": text, "height": data["height"][i]})

    if not lines:
        return None

    # Sort by text height descending — largest text is likely the title
    lines.sort(key=lambda x: x["height"], reverse=True)

    title = lines[0]["text"]
    author = lines[1]["text"] if len(lines) > 1 else None

    # If we only found one line or author looks suspicious, ask the LLM
    if author is None or len(lines) < 2:
        raw_text = " ".join(line["text"] for line in lines)
        llm_result = await parse_with_llm(raw_text)
        if llm_result:
            return llm_result
        return None

    return {"title": title, "author": author}


async def parse_with_llm(raw_text: str) -> dict | None:
    """Use Claude to parse title/author from ambiguous OCR text."""
    if not settings.anthropic_api_key:
        return None

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    message = await client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Extract the book title and author from this OCR text: '{raw_text}'. "
                    "Respond with ONLY JSON: {\"title\": \"...\", \"author\": \"...\"}"
                ),
            }
        ],
    )
    import json

    try:
        return json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError):
        return None
