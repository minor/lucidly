"""Test script for screenshot capture functionality.

Usage:
    python backend/test_screenshot_capture.py
"""

import asyncio
from screenshot_capture import (
    ScreenshotCapture,
    ScreenshotOptions,
    capture_ui_screenshot_base64,
)
from modal_execution import ModalExecutor


async def test_screenshot_capture():
    """Test screenshot capture from HTML."""
    
    print("="*70)
    print("SCREENSHOT CAPTURE TEST")
    print("="*70)
    
    # Sample HTML for landing page
    landing_page_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Landing Page</title>
    <style>
        body {
            background-color: #1a1a2e;
            color: #eee;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 2rem;
        }
        .hero {
            text-align: center;
            padding: 4rem 2rem;
        }
        h1 {
            font-size: 3rem;
            margin-bottom: 1rem;
        }
        .features {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 2rem;
            margin-top: 4rem;
        }
        .feature {
            background: rgba(255, 255, 255, 0.1);
            padding: 2rem;
            border-radius: 8px;
        }
    </style>
</head>
<body>
    <header class="hero">
        <h1>Welcome to Our Landing Page</h1>
        <p>This is a test landing page design</p>
    </header>
    <main>
        <section class="features">
            <div class="feature">
                <h2>Feature 1</h2>
                <p>Description of feature 1</p>
            </div>
            <div class="feature">
                <h2>Feature 2</h2>
                <p>Description of feature 2</p>
            </div>
            <div class="feature">
                <h2>Feature 3</h2>
                <p>Description of feature 3</p>
            </div>
        </section>
    </main>
</body>
</html>"""
    
    try:
        # Test 1: Basic screenshot capture
        print("\n" + "-"*70)
        print("TEST 1: Basic Screenshot Capture")
        print("-"*70)
        
        async with ScreenshotCapture() as capture:
            screenshot_base64 = await capture.capture_to_base64(
                landing_page_html,
                options=ScreenshotOptions(width=1280, height=720)
            )
            
            print(f"✓ Screenshot captured successfully")
            print(f"  Base64 length: {len(screenshot_base64)} characters")
            print(f"  Format: {screenshot_base64[:30]}...")
            
            # Save to file for inspection
            file_path = await capture.capture_to_file(
                landing_page_html,
                output_path="test_screenshot.png",
                options=ScreenshotOptions(width=1280, height=720)
            )
            print(f"  Saved to: {file_path}")
        
        # Test 2: Convenience function
        print("\n" + "-"*70)
        print("TEST 2: Convenience Function")
        print("-"*70)
        
        screenshot_base64 = await capture_ui_screenshot_base64(
            landing_page_html,
            width=640,
            height=400,
        )
        
        print(f"✓ Screenshot captured using convenience function")
        print(f"  Base64 length: {len(screenshot_base64)} characters")
        
        # Test 3: Modal executor integration
        print("\n" + "-"*70)
        print("TEST 3: Modal Executor Integration")
        print("-"*70)
        
        executor = ModalExecutor()
        result = await executor.execute_ui_with_screenshot(
            html_code=landing_page_html,
            width=1280,
            height=720,
        )
        
        if result.success:
            print(f"✓ Modal executor screenshot capture successful")
            if result.screenshot_url:
                if result.screenshot_url.startswith("data:image"):
                    print(f"  Screenshot URL (base64): {result.screenshot_url[:50]}...")
                else:
                    print(f"  Screenshot URL: {result.screenshot_url}")
        else:
            print(f"✗ Modal executor failed: {result.error}")
        
        print("\n" + "="*70)
        print("ALL TESTS COMPLETED")
        print("="*70)
        
    except ImportError as e:
        print(f"\n✗ Playwright not installed: {e}")
        print("\nTo install Playwright:")
        print("  pip install playwright")
        print("  playwright install chromium")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_screenshot_capture())

