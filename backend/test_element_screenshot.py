"""Test script for element and iframe screenshot capture.

Usage:
    python backend/test_element_screenshot.py
"""

import asyncio
from screenshot_capture import ScreenshotCapture, ScreenshotOptions


async def test_element_screenshot():
    """Test screenshot capture of specific elements and iframes."""
    
    print("="*70)
    print("ELEMENT & IFRAME SCREENSHOT TEST")
    print("="*70)
    
    # HTML page with an iframe containing the preview
    page_with_iframe = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page with Preview Iframe</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            padding: 2rem;
            background: #f5f5f5;
        }
        .header {
            background: #333;
            color: white;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        .preview-container {
            border: 2px solid #ccc;
            border-radius: 8px;
            padding: 1rem;
            background: white;
        }
        iframe {
            width: 100%;
            height: 600px;
            border: 1px solid #ddd;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Challenge Preview</h1>
    </div>
    <div class="preview-container" id="preview-wrapper">
        <h2>Generated Preview:</h2>
        <iframe 
            id="preview-iframe"
            sandbox="allow-scripts"
            srcdoc="
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body { 
                            background: #1a1a2e; 
                            color: #eee; 
                            font-family: Arial; 
                            padding: 2rem; 
                            margin: 0;
                        }
                        .hero {
                            text-align: center;
                            padding: 4rem 2rem;
                        }
                        h1 { font-size: 3rem; margin-bottom: 1rem; }
                    </style>
                </head>
                <body>
                    <div class='hero'>
                        <h1>Landing Page Preview</h1>
                        <p>This is the rendered preview inside the iframe</p>
                    </div>
                </body>
                </html>
            ">
        </iframe>
    </div>
    <div class="sidebar">
        <p>Some sidebar content</p>
    </div>
</body>
</html>"""
    
    try:
        async with ScreenshotCapture() as capture:
            # Test 1: Screenshot entire page
            print("\n" + "-"*70)
            print("TEST 1: Screenshot Entire Page")
            print("-"*70)
            
            full_page = await capture.capture_to_base64(
                page_with_iframe,
                options=ScreenshotOptions(width=1280, height=800)
            )
            print(f"✓ Full page screenshot captured")
            print(f"  Base64 length: {len(full_page)} characters")
            
            # Test 2: Screenshot specific element (preview container)
            print("\n" + "-"*70)
            print("TEST 2: Screenshot Preview Container Element")
            print("-"*70)
            
            container_screenshot = await capture.capture_element_base64(
                page_with_iframe,
                selector='#preview-wrapper',
                options=ScreenshotOptions(width=1280, height=800)
            )
            print(f"✓ Preview container screenshot captured")
            print(f"  Base64 length: {len(container_screenshot)} characters")
            
            # Save to file for comparison
            container_bytes = await capture.capture_element(
                page_with_iframe,
                selector='#preview-wrapper',
                options=ScreenshotOptions(width=1280, height=800)
            )
            with open('test_container_screenshot.png', 'wb') as f:
                f.write(container_bytes)
            print(f"  Saved to: test_container_screenshot.png")
            
            # Test 3: Screenshot iframe element itself
            print("\n" + "-"*70)
            print("TEST 3: Screenshot Iframe Element")
            print("-"*70)
            
            iframe_screenshot = await capture.capture_iframe_base64(
                page_with_iframe,
                iframe_selector='#preview-iframe',
                options=ScreenshotOptions(width=1280, height=800)
            )
            print(f"✓ Iframe screenshot captured")
            print(f"  Base64 length: {len(iframe_screenshot)} characters")
            
            # Save to file
            iframe_bytes = await capture.capture_iframe(
                page_with_iframe,
                iframe_selector='#preview-iframe',
                options=ScreenshotOptions(width=1280, height=800)
            )
            with open('test_iframe_screenshot.png', 'wb') as f:
                f.write(iframe_bytes)
            print(f"  Saved to: test_iframe_screenshot.png")
            
            # Test 4: Screenshot using class selector
            print("\n" + "-"*70)
            print("TEST 4: Screenshot Using Class Selector")
            print("-"*70)
            
            preview_class = await capture.capture_element_base64(
                page_with_iframe,
                selector='.preview-container',
                options=ScreenshotOptions(width=1280, height=800)
            )
            print(f"✓ Preview container (class selector) screenshot captured")
            print(f"  Base64 length: {len(preview_class)} characters")
            
        print("\n" + "="*70)
        print("ALL TESTS COMPLETED")
        print("="*70)
        print("\nGenerated files:")
        print("  - test_container_screenshot.png (preview container only)")
        print("  - test_iframe_screenshot.png (iframe content only)")
        
    except ImportError as e:
        print(f"\n✗ Playwright not installed: {e}")
        print("\nTo install Playwright:")
        print("  pip install playwright")
        print("  playwright install chromium")
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_real_world_example():
    """Example of capturing iframe from a real page structure."""
    
    print("\n" + "="*70)
    print("REAL-WORLD EXAMPLE: Capturing Preview Iframe")
    print("="*70)
    
    # Simulate your actual page structure
    actual_page = """<!DOCTYPE html>
<html>
<head>
    <style>
        body { margin: 0; padding: 20px; background: #f0f0f0; }
        .challenge-container { max-width: 1200px; margin: 0 auto; }
        .preview-section {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-top: 20px;
        }
        #preview-frame {
            width: 100%;
            height: 600px;
            border: 2px solid #ddd;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="challenge-container">
        <h1>Challenge: Build Landing Page</h1>
        <div class="preview-section">
            <h2>Your Preview:</h2>
            <iframe 
                id="preview-frame"
                sandbox="allow-scripts"
                srcdoc="
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <style>
                            body { 
                                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                                color: white;
                                font-family: 'Arial', sans-serif;
                                margin: 0;
                                padding: 0;
                                display: flex;
                                align-items: center;
                                justify-content: center;
                                min-height: 100vh;
                            }
                            .hero {
                                text-align: center;
                                padding: 2rem;
                            }
                            h1 { font-size: 4rem; margin: 0; }
                            p { font-size: 1.5rem; opacity: 0.9; }
                        </style>
                    </head>
                    <body>
                        <div class='hero'>
                            <h1>Welcome</h1>
                            <p>This is the generated preview</p>
                        </div>
                    </body>
                    </html>
                ">
            </iframe>
        </div>
    </div>
</body>
</html>"""
    
    try:
        async with ScreenshotCapture() as capture:
            # Capture just the iframe content
            iframe_screenshot = await capture.capture_iframe_base64(
                actual_page,
                iframe_selector='#preview-frame',
                options=ScreenshotOptions(width=1200, height=600)
            )
            
            print(f"\n✓ Captured iframe screenshot")
            print(f"  Ready for vision comparison!")
            print(f"  Base64 length: {len(iframe_screenshot)} characters")
            
            # This can now be used with vision comparison
            print(f"\n  You can use this with VisionComparator:")
            print(f"    comparator.compare_images(")
            print(f"      reference_image_url=reference_screenshot,")
            print(f"      generated_image_url='{iframe_screenshot[:50]}...',")
            print(f"    )")
            
    except Exception as e:
        print(f"\n✗ Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_element_screenshot())
    asyncio.run(test_real_world_example())


