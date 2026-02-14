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
    options = ScreenshotOptions(width=width, height=height)
    
    # Capture iframe screenshots
    async with ScreenshotCapture() as capture:
        reference_screenshot = await capture.capture_iframe_base64(
            reference_page_html,
            iframe_selector=iframe_selector,
            options=options,
        )
        
        generated_screenshot = await capture.capture_iframe_base64(
            generated_page_html,
            iframe_selector=iframe_selector,
            options=options,
        )
    
    # Compare using vision comparison
    comparator = VisionComparator()
    result = await comparator.compare_base64_images(
        reference_image_base64=reference_screenshot,
        generated_image_base64=generated_screenshot,
        challenge_description=challenge.description if challenge else None,
    )
    
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
    if not challenge.image_url:
        raise ValueError(f"Challenge '{challenge.id}' does not have an image_url")
    
    options = ScreenshotOptions(width=width, height=height)
    
    # Capture generated screenshot
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
    
    # Compare with challenge reference image
    comparator = VisionComparator()
    result = await comparator.compare_images(
        reference_image_url=challenge.image_url,
        generated_image_url=generated_screenshot,  # Base64 data URL
        challenge_description=challenge.description,
    )
    
    return result

