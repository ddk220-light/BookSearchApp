import json
from anthropic import AsyncAnthropic
from app.config import settings


async def assess_book(title: str, author: str) -> dict | None:
    """Use Claude to assess how well-regarded a book is."""
    if not settings.anthropic_api_key:
        return None

    try:
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        message = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f'Given the book "{title}" by {author}, assess how well-regarded this book is. '
                        "Respond with ONLY JSON: "
                        '{"quality_tier": "<classic|highly_acclaimed|well_received|mixed|poorly_received|unknown>", '
                        '"confidence": "<high|medium|low>", '
                        '"notable_awards": ["..."], '
                        '"brief_rationale": "one sentence"}'
                    ),
                }
            ],
        )
        return json.loads(message.content[0].text)
    except (json.JSONDecodeError, IndexError, KeyError, Exception):
        return None
