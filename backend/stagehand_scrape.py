"""
Optional Stagehand (Browserbase) integration for the Claude agent.
When configured, the agent can use view_reference_page to navigate to a URL
and extract structure/content.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# Schema for extract(): landing page structure and content useful for recreation
LANDING_PAGE_EXTRACT_SCHEMA = {
    "type": "object",
    "properties": {
        "page_title": {"type": "string", "description": "Document title or main heading"},
        "nav_items": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Navigation link labels (e.g. Research, Product, Pricing)",
        },
        "hero_heading": {"type": "string", "description": "Main hero/headline text"},
        "hero_subtext": {"type": "string", "description": "Subheading or description under the hero"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "body": {"type": "string"},
                    "cta_or_links": {"type": "array", "items": {"type": "string"}},
                },
            },
            "description": "Major sections with heading, body text, and links/CTAs",
        },
        "footer_links": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Footer link labels or groups",
        },
        "styling_notes": {
            "type": "string",
            "description": "Brief notes on colors, layout (e.g. dark header, gradient hero), fonts if obvious",
        },
    },
    "required": ["page_title"],
}


async def scrape_landing_page(url: str, *, model_api_key: str) -> dict[str, Any]:
    """
    Use Stagehand to navigate to url and extract landing-page structure/content.
    Returns a dict with extracted data or error info.
    Requires: stagehand-py, BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID, and model_api_key.
    """
    try:
        from stagehand import AsyncStagehand
    except ImportError as e:
        logger.warning("stagehand not installed: %s", e)
        return {"error": "Stagehand is not installed. Install with: uv add stagehand-py"}

    from config import settings

    api_key = getattr(settings, "browserbase_api_key", "") or ""
    project_id = getattr(settings, "browserbase_project_id", "") or ""
    if not api_key or not project_id:
        return {
            "error": "Browserbase is not configured. Set BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in .env to use view_reference_page.",
        }

    async with AsyncStagehand(
        browserbase_api_key=api_key,
        browserbase_project_id=project_id,
        model_api_key=model_api_key,
    ) as client:
        session = await client.sessions.start(model_name="openai/gpt-4o-mini")
        try:
            await session.navigate(url=url)
            extract_response = await session.extract(
                instruction=(
                    "Extract the structure and content of this landing page so it can be recreated. "
                    "Include: page title, main nav link labels, hero heading and subtext, "
                    "major sections (heading, body text, CTAs/links), footer links, "
                    "and brief styling notes (colors, layout style)."
                ),
                schema=LANDING_PAGE_EXTRACT_SCHEMA,
            )
            result = extract_response.data.result if extract_response.data else None
            if isinstance(result, dict):
                return {"url": url, "extracted": result}
            return {"url": url, "extracted": result, "raw": str(result)}
        except Exception as e:
            logger.exception("Stagehand scrape failed for %s: %s", url, e)
            return {"error": str(e), "url": url}
        finally:
            await session.end()
