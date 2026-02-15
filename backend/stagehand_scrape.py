"""
Optional Stagehand (Browserbase) integration for the Claude agent.
When configured, the agent can use view_reference_page to navigate to a URL
and extract structure/content, and use generate_landing_page with a Browserbase
screenshot of the reference URL (no local Playwright).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def capture_url_screenshot_base64_browserbase(
    url: str,
    *,
    api_key: str,
    project_id: str,
    full_page: bool = True,
    wait_after_load: float = 2.0,
    viewport_width: int = 1280,
    viewport_height: int = 900,
) -> str:
    """
    Capture a screenshot of a live URL using Browserbase (no local Playwright).
    Returns a data URL (data:image/png;base64,...) for use with vision models.
    """
    try:
        from browserbase import Browserbase
    except ImportError as e:
        raise RuntimeError(
            "Browserbase SDK is required for URL screenshots. Install with: pip install browserbase"
        ) from e
    try:
        from playwright.async_api import async_playwright
    except ImportError as e:
        raise RuntimeError(
            "Playwright is required to connect to Browserbase and capture screenshots. "
            "Install with: pip install playwright && playwright install chromium"
        ) from e

    def _create_session() -> Any:
        bb = Browserbase(api_key=api_key)
        return bb.sessions.create(
            project_id=project_id,
            browser_settings={
                "viewport": {"width": viewport_width, "height": viewport_height},
            },
        )

    # #region agent log
    try:
        import json as _json
        _lp = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".cursor", "debug.log"))
        with open(_lp, "a") as _f:
            _f.write(_json.dumps({"id": "screenshot_browserbase_before_session_create", "timestamp": __import__("time").time() * 1000, "location": "stagehand_scrape.py:capture_url_screenshot_base64_browserbase", "message": "before Browserbase session create", "data": {"url_preview": url[:60], "has_api_key": bool(api_key), "has_project_id": bool(project_id)}, "hypothesisId": "H1"}) + "\n")
    except Exception:
        pass
    # #endregion
    logger.info("[Browserbase screenshot] Creating session for url=%s", url[:80])
    try:
        session = await asyncio.to_thread(_create_session)
    except Exception as e_create:
        # #region agent log
        try:
            import json as _json
            _lp = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".cursor", "debug.log"))
            with open(_lp, "a") as _f:
                _f.write(_json.dumps({"id": "screenshot_browserbase_error_at_session_create", "timestamp": __import__("time").time() * 1000, "location": "stagehand_scrape.py:capture_url_screenshot_base64_browserbase", "message": "exception at session create", "data": {"error_type": type(e_create).__name__, "error_msg": str(e_create)[:500]}, "hypothesisId": "H1"}) + "\n")
        except Exception:
            pass
        # #endregion
        raise
    connect_url = getattr(session, "connect_url", None) or getattr(session, "connectUrl", None)
    # #region agent log
    try:
        import json as _json
        _lp = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".cursor", "debug.log"))
        with open(_lp, "a") as _f:
            _f.write(_json.dumps({"id": "screenshot_browserbase_after_session_create", "timestamp": __import__("time").time() * 1000, "location": "stagehand_scrape.py:capture_url_screenshot_base64_browserbase", "message": "after session create", "data": {"has_connect_url": bool(connect_url)}, "hypothesisId": "H1"}) + "\n")
    except Exception:
        pass
    # #endregion
    if not connect_url:
        raise RuntimeError("Browserbase session did not return connect_url")
    logger.info("[Browserbase screenshot] Session created, connecting via CDP")

    async with async_playwright() as p:
        # #region agent log
        try:
            import json as _json
            _lp = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".cursor", "debug.log"))
            with open(_lp, "a") as _f:
                _f.write(_json.dumps({"id": "screenshot_browserbase_before_cdp_connect", "timestamp": __import__("time").time() * 1000, "location": "stagehand_scrape.py:capture_url_screenshot_base64_browserbase", "message": "before CDP connect", "data": {}, "hypothesisId": "H2"}) + "\n")
        except Exception:
            pass
        # #endregion
        try:
            browser = await p.chromium.connect_over_cdp(connect_url)
        except Exception as e_cdp:
            # #region agent log
            try:
                import json as _json
                _lp = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "..", ".cursor", "debug.log"))
                with open(_lp, "a") as _f:
                    _f.write(_json.dumps({"id": "screenshot_browserbase_error_at_cdp_connect", "timestamp": __import__("time").time() * 1000, "location": "stagehand_scrape.py:capture_url_screenshot_base64_browserbase", "message": "exception at CDP connect", "data": {"error_type": type(e_cdp).__name__, "error_msg": str(e_cdp)[:500]}, "hypothesisId": "H2"}) + "\n")
            except Exception:
                pass
            # #endregion
            raise
        try:
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            logger.info("[Browserbase screenshot] Navigating to %s", url[:80])
            await page.goto(url, wait_until="load", timeout=30000)
            await asyncio.sleep(wait_after_load)
            logger.info("[Browserbase screenshot] Taking CDP screenshot (full_page=%s)", full_page)
            cdp = await context.new_cdp_session(page)
            screenshot_payload = await cdp.send(
                "Page.captureScreenshot",
                {"format": "png", "captureBeyondViewport": full_page},
            )
            data_b64 = screenshot_payload.get("data") if isinstance(screenshot_payload, dict) else None
            if not data_b64:
                raise RuntimeError("Page.captureScreenshot did not return data")
            data_url = f"data:image/png;base64,{data_b64}"
            logger.info("[Browserbase screenshot] Success, data_url len=%d", len(data_url))
            return data_url
        finally:
            await browser.close()

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
