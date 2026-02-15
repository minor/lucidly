"""Integration between screenshot capture and vision comparison.

This module provides helper functions to capture screenshots and compare them
using Claude Vision API in a single workflow.
"""

from typing import Optional
import sys
from pathlib import Path

# Add parent directory to path for absolute imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from screenshot_capture import ScreenshotCapture, ScreenshotOptions
from .vision_comparison import VisionComparator, VisionComparisonResult
from challenges import Challenge


async def capture_and_compare(
    reference_html: str,
    generated_html: str,
    challenge_description: Optional[str] = None,
    reference_selector: Optional[str] = None,
    generated_selector: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
) -> VisionComparisonResult:
    """
    Capture screenshots from HTML and compare them using Claude Vision.
    
    Args:
        reference_html: HTML content of the reference/ground truth
        generated_html: HTML content of the generated preview
        challenge_description: Optional description of what should match
        reference_selector: Optional CSS selector to capture specific element from reference
                          (e.g., 'iframe', '#preview-container')
        generated_selector: Optional CSS selector to capture specific element from generated
                           (e.g., 'iframe', '#preview-container')
        width: Viewport width for screenshots
        height: Viewport height for screenshots
    
    Returns:
        VisionComparisonResult with similarity score and feedback
    """
    options = ScreenshotOptions(width=width, height=height)
    
    # Capture screenshots
    async with ScreenshotCapture() as capture:
        if reference_selector:
            reference_screenshot = await capture.capture_element_base64(
                reference_html,
                selector=reference_selector,
                options=options,
            )
        else:
            reference_screenshot = await capture.capture_to_base64(
                reference_html,
                options=options,
            )
        
        if generated_selector:
            generated_screenshot = await capture.capture_element_base64(
                generated_html,
                selector=generated_selector,
                options=options,
            )
        else:
            generated_screenshot = await capture.capture_to_base64(
                generated_html,
                options=options,
            )
    
    # Compare using vision comparison
    comparator = VisionComparator()
    result = await comparator.compare_base64_images(
        reference_image_base64=reference_screenshot,
        generated_image_base64=generated_screenshot,
        challenge_description=challenge_description,
    )
    
    return result


async def capture_iframe_and_compare(
    reference_page_html: str,
    generated_page_html: str,
    challenge: Optional[Challenge] = None,
    iframe_selector: str = 'iframe',
    width: int = 1280,
    height: int = 720,
) -> VisionComparisonResult:
    """
    Capture iframe screenshots from pages and compare them.
    
    Useful when you have a page with an iframe containing the preview.
    
    Args:
        reference_page_html: HTML of the page containing reference iframe
        generated_page_html: HTML of the page containing generated preview iframe
        challenge: Optional Challenge object (uses its description if provided)
        iframe_selector: CSS selector for the iframe (default: 'iframe')
        width: Viewport width
        height: Viewport height
    
    Returns:
        VisionComparisonResult with similarity score and feedback
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"[Screenshot] Starting iframe capture (viewport: {width}x{height})")
    options = ScreenshotOptions(width=width, height=height)
    
    # Capture iframe screenshots
    logger.info("[Screenshot] Capturing reference iframe screenshot...")
    async with ScreenshotCapture() as capture:
        reference_screenshot = await capture.capture_iframe_base64(
            reference_page_html,
            iframe_selector=iframe_selector,
            options=options,
        )
        logger.info(f"[Screenshot] Reference screenshot captured ({len(reference_screenshot)} chars)")
        
        # Save reference screenshot to file
        import base64
        import os
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs("screenshots", exist_ok=True)
        ref_path = f"screenshots/reference_{timestamp}.png"
        if reference_screenshot.startswith("data:image"):
            # Extract base64 data
            base64_data = reference_screenshot.split(",")[1]
            with open(ref_path, "wb") as f:
                f.write(base64.b64decode(base64_data))
            logger.info(f"[Screenshot] Reference screenshot saved to: {ref_path}")
        
        logger.info("[Screenshot] Capturing generated iframe screenshot...")
        generated_screenshot = await capture.capture_iframe_base64(
            generated_page_html,
            iframe_selector=iframe_selector,
            options=options,
        )
        logger.info(f"[Screenshot] Generated screenshot captured ({len(generated_screenshot)} chars)")
        
        # Save generated screenshot to file
        gen_path = f"screenshots/generated_{timestamp}.png"
        if generated_screenshot.startswith("data:image"):
            # Extract base64 data
            base64_data = generated_screenshot.split(",")[1]
            with open(gen_path, "wb") as f:
                f.write(base64.b64decode(base64_data))
            logger.info(f"[Screenshot] Generated screenshot saved to: {gen_path}")
    
    # Compare using vision comparison
    logger.info("[Vision] Starting Claude Vision comparison...")
    comparator = VisionComparator()
    result = await comparator.compare_base64_images(
        reference_image_base64=reference_screenshot,
        generated_image_base64=generated_screenshot,
        challenge_description=challenge.description if challenge else None,
    )
    logger.info(f"[Vision] Comparison complete. Similarity: {result.similarity_score:.4f}, Match: {result.overall_match}")
    
    return result

## not really relevant if we don't use reference images.
async def compare_with_challenge_reference(
    generated_html: str,
    challenge: Challenge,
    generated_selector: Optional[str] = None,
    width: int = 1280,
    height: int = 720,
) -> VisionComparisonResult:
    """
    Compare generated HTML against a challenge's reference image.
    
    This function:
    1. Fetches the challenge's reference image (from image_url)
    2. Captures screenshot from generated HTML
    3. Compares them using Claude Vision
    
    Args:
        generated_html: HTML content of the generated preview
        challenge: Challenge object with image_url
        generated_selector: Optional CSS selector to capture specific element
                          (e.g., 'iframe', '#preview-container')
        width: Viewport width
        height: Viewport height
    
    Returns:
        VisionComparisonResult with similarity score and feedback
    """
    import logging
    logger = logging.getLogger(__name__)
    
    if not challenge.image_url:
        raise ValueError(f"Challenge '{challenge.id}' does not have an image_url")
    
    logger.info(f"[Screenshot] Starting screenshot capture (viewport: {width}x{height})")
    logger.info(f"[Screenshot] Reference image URL: {challenge.image_url}")
    logger.info(f"[Screenshot] Generated HTML length: {len(generated_html)} chars")
    
    options = ScreenshotOptions(width=width, height=height)
    
    # Capture generated screenshot
    logger.info("[Screenshot] Capturing generated HTML screenshot...")
    async with ScreenshotCapture() as capture:
        if generated_selector:
            if 'iframe' in generated_selector.lower():
                generated_screenshot = await capture.capture_iframe_base64(
                    generated_html,
                    iframe_selector=generated_selector,
                    options=options,
                )
            else:
                generated_screenshot = await capture.capture_element_base64(
                    generated_html,
                    selector=generated_selector,
                    options=options,
                )
        else:
            generated_screenshot = await capture.capture_to_base64(
                generated_html,
                options=options,
            )
    
    logger.info(f"[Screenshot] Generated screenshot captured ({len(generated_screenshot)} chars)")
    
    # Save screenshots to files
    import base64
    import os
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("screenshots", exist_ok=True)
    
    # Save reference image (from URL)
    if challenge.image_url:
        ref_path = f"screenshots/reference_{timestamp}.png"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(challenge.image_url)
                response.raise_for_status()
                with open(ref_path, "wb") as f:
                    f.write(response.content)
                logger.info(f"[Screenshot] Reference image saved to: {ref_path}")
        except Exception as e:
            logger.warning(f"[Screenshot] Failed to save reference image: {e}")
    
    # Save generated screenshot
    gen_path = f"screenshots/generated_{timestamp}.png"
    if generated_screenshot.startswith("data:image"):
        # Extract base64 data
        base64_data = generated_screenshot.split(",")[1]
        with open(gen_path, "wb") as f:
            f.write(base64.b64decode(base64_data))
        logger.info(f"[Screenshot] Generated screenshot saved to: {gen_path}")
    
    # Compare with challenge reference image
    logger.info("[Vision] Starting Claude Vision comparison with reference image...")
    comparator = VisionComparator()
    result = await comparator.compare_images(
        reference_image_url=challenge.image_url,
        generated_image_url=generated_screenshot,  # Base64 data URL
        challenge_description=challenge.description,
    )
    logger.info(f"[Vision] Comparison complete. Similarity: {result.similarity_score:.4f}, Match: {result.overall_match}")
    
    return result

