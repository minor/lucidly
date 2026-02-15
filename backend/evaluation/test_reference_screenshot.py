"""
Example usage of capture_url_iframe for your challenge embed_url iframe.

This demonstrates how to capture screenshots of the iframe shown in your React component.
"""

import asyncio
from screenshot_capture import ScreenshotCapture, ScreenshotOptions

async def example_basic_iframe_capture():
    """Basic example: Capture just the iframe element."""
    async with ScreenshotCapture() as capture:
        # URL of your page that contains the iframe
        page_url = "http://localhost:3000/play/build-landing-page"  # Replace with your actual URL
        
        # Capture the iframe (it will find the first iframe on the page)
        screenshot_bytes = await capture.capture_url_iframe(
            page_url=page_url,
            iframe_selector='iframe',  # Or be more specific: 'iframe[title*="Challenge reference"]'
            wait_time=3.0  # Wait 3 seconds for embed_url content to load
        )
        
        # Save to file
        with open('iframe_screenshot_new.png', 'wb') as f:
            f.write(screenshot_bytes)
        
        print("Screenshot saved to iframe_screenshot_new.png")


async def example_container_capture():
    """Capture the container div instead (for the 680px clipped view)."""
    async with ScreenshotCapture() as capture:
        page_url = "http://localhost:3000/challenge/123"
        
        # Capture the container div that clips to 680px height
        screenshot_bytes = await capture.capture_url_iframe(
            page_url=page_url,
            iframe_selector='iframe',
            container_selector='div.rounded-lg.border.border-border',  # The container div
            wait_time=3.0
        )
        
        with open('container_screenshot.png', 'wb') as f:
            f.write(screenshot_bytes)
        
        print("Screenshot saved to container_screenshot.png")


async def example_base64_capture():
    """Get screenshot as base64 data URL (useful for APIs)."""
    async with ScreenshotCapture() as capture:
        page_url = "http://localhost:3000/challenge/123"
        
        # Get as base64
        base64_image = await capture.capture_url_iframe_base64(
            page_url=page_url,
            iframe_selector='iframe',
            wait_time=3.0
        )
        
        # Now you can use this in HTML: <img src="{base64_image}" />
        # Or send it via API
        print(f"Base64 image (first 100 chars): {base64_image[:100]}...")


async def example_custom_viewport():
    """Capture with custom viewport size."""
    async with ScreenshotCapture() as capture:
        page_url = "http://localhost:3000/challenge/123"
        
        # Custom options to match your design
        options = ScreenshotOptions(
            width=1920,  # Wider viewport
            height=1080,
            device_scale_factor=2.0  # Retina/high DPI screenshot
        )
        
        screenshot_bytes = await capture.capture_url_iframe(
            page_url=page_url,
            iframe_selector='iframe',
            options=options,
            wait_time=4.0  # Wait a bit longer for complex embeds
        )
        
        with open('high_res_screenshot.png', 'wb') as f:
            f.write(screenshot_bytes)
        
        print("High-resolution screenshot saved")


async def example_multiple_iframes():
    """If you have multiple iframes, target specific ones."""
    async with ScreenshotCapture() as capture:
        page_url = "http://localhost:3000/challenge/123"
        
        # Use a more specific selector based on your React component
        screenshot_bytes = await capture.capture_url_iframe(
            page_url=page_url,
            # Target by title attribute
            iframe_selector='iframe[title="Challenge reference (top of page only)"]',
            wait_time=3.0
        )
        
        with open('specific_iframe.png', 'wb') as f:
            f.write(screenshot_bytes)
        
        print("Specific iframe screenshot saved")


async def example_error_handling():
    """Example with proper error handling."""
    async with ScreenshotCapture() as capture:
        try:
            page_url = "http://localhost:3000/challenge/123"
            
            screenshot_bytes = await capture.capture_url_iframe(
                page_url=page_url,
                iframe_selector='iframe',
                wait_time=3.0
            )
            
            with open('screenshot.png', 'wb') as f:
                f.write(screenshot_bytes)
            
            print("✓ Screenshot captured successfully")
            
        except ValueError as e:
            print(f"✗ Element not found: {e}")
        except Exception as e:
            print(f"✗ Error capturing screenshot: {e}")


if __name__ == "__main__":
    # Run any of the examples
    print("Running basic iframe capture example...")
    asyncio.run(example_basic_iframe_capture())
    
    # Uncomment to run other examples:
    # asyncio.run(example_container_capture())
    # asyncio.run(example_base64_capture())
    # asyncio.run(example_custom_viewport())
    # asyncio.run(example_multiple_iframes())
    # asyncio.run(example_error_handling())