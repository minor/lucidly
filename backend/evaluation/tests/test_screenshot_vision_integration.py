"""Test script for screenshot capture + vision comparison integration.

Usage:
    python backend/evaluation/tests/test_screenshot_vision_integration.py
    # OR from backend directory:
    python -m evaluation.tests.test_screenshot_vision_integration
"""

import asyncio
import sys
from pathlib import Path

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from evaluation import (
    capture_and_compare,
    capture_iframe_and_compare,
    compare_with_challenge_reference,
)
from challenges import get_challenge_by_id


async def test_basic_integration():
    """Test basic screenshot + vision comparison."""
    
    print("="*70)
    print("SCREENSHOT + VISION COMPARISON INTEGRATION TEST")
    print("="*70)
    
    # Reference HTML (ground truth)
    reference_html = """<!DOCTYPE html>
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
    <div class="hero">
        <h1>Landing Page</h1>
        <p>Reference design</p>
    </div>
</body>
</html>"""
    
    # Generated HTML (to compare)
    generated_html = """<!DOCTYPE html>
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
    <div class="hero">
        <h1>Landing Page</h1>
        <p>Generated design</p>
    </div>
</body>
</html>"""
    
    try:
        print("\n" + "-"*70)
        print("TEST 1: Basic HTML Comparison")
        print("-"*70)
        
        result = await capture_and_compare(
            reference_html=reference_html,
            generated_html=generated_html,
            challenge_description="Build a landing page with dark background",
            width=1280,
            height=720,
        )
        
        print(f"\n✓ Comparison successful!")
        print(f"  Similarity Score: {result.similarity_score:.2%}")
        print(f"  Overall Match: {result.overall_match}")
        print(f"  Visual Elements: {result.visual_elements_match}")
        print(f"\n  Feedback:")
        print(f"  {result.detailed_feedback[:200]}...")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def test_iframe_integration():
    """Test iframe screenshot + vision comparison."""
    
    print("\n" + "-"*70)
    print("TEST 2: Iframe Comparison")
    print("-"*70)
    
    # Page with iframe containing reference
    reference_page = """<!DOCTYPE html>
<html>
<head>
    <style>body { padding: 20px; background: #f0f0f0; }</style>
</head>
<body>
    <h1>Challenge Preview</h1>
    <iframe id="preview" srcdoc="
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { background: #1a1a2e; color: #eee; padding: 2rem; }
                h1 { font-size: 3rem; text-align: center; }
            </style>
        </head>
        <body>
            <h1>Reference Design</h1>
        </body>
        </html>
    "></iframe>
</body>
</html>"""
    
    # Page with iframe containing generated preview
    generated_page = """<!DOCTYPE html>
<html>
<head>
    <style>body { padding: 20px; background: #f0f0f0; }</style>
</head>
<body>
    <h1>Your Preview</h1>
    <iframe id="preview" srcdoc="
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body { background: #1a1a2e; color: #eee; padding: 2rem; }
                h1 { font-size: 3rem; text-align: center; }
            </style>
        </head>
        <body>
            <h1>Generated Design</h1>
        </body>
        </html>
    "></iframe>
</body>
</html>"""
    
    try:
        result = await capture_iframe_and_compare(
            reference_page_html=reference_page,
            generated_page_html=generated_page,
            iframe_selector='#preview',
            width=1280,
            height=720,
        )
        
        print(f"\n✓ Iframe comparison successful!")
        print(f"  Similarity Score: {result.similarity_score:.2%}")
        print(f"  Overall Match: {result.overall_match}")
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()

# DOESN'T WORK IF NO REFERENCE IMAGE IS PROVIDED

# async def test_challenge_integration():
#     """Test comparing generated HTML against challenge reference."""
    
#     print("\n" + "-"*70)
#     print("TEST 3: Challenge Reference Comparison")
#     print("-"*70)
    
#     challenge = get_challenge_by_id("build-landing-page")
#     if not challenge:
#         print("Challenge 'build-landing-page' not found")
#         return
    
#     # Generated HTML to compare
#     generated_html = """<!DOCTYPE html>
# <html>
# <head>
#     <style>
#         body {
#             background: #1a1a2e;
#             color: #eee;
#             font-family: Arial;
#             padding: 2rem;
#             margin: 0;
#         }
#         .hero {
#             text-align: center;
#             padding: 4rem 2rem;
#         }
#         h1 { font-size: 3rem; margin-bottom: 1rem; }
#     </style>
# </head>
# <body>
#     <div class="hero">
#         <h1>Welcome to Our Landing Page</h1>
#         <p>This is the generated preview</p>
#     </div>
# </body>
# </html>"""
    
#     try:
#         result = await compare_with_challenge_reference(
#             generated_html=generated_html,
#             challenge=challenge,
#             width=1280,
#             height=720,
#         )
        
#         print(f"\n✓ Challenge comparison successful!")
#         print(f"  Challenge: {challenge.title}")
#         print(f"  Similarity Score: {result.similarity_score:.2%}")
#         print(f"  Overall Match: {'✓ YES' if result.overall_match else '✗ NO'}")
#         print(f"\n  Feedback:")
#         print(f"  {result.detailed_feedback[:300]}...")
        
#     except Exception as e:
#         print(f"\n✗ Test failed: {e}")
#         import traceback
#         traceback.print_exc()


async def main():
    """Run all integration tests."""
    import os
    from config import settings
    
    if not settings.anthropic_api_key:
        print("WARNING: ANTHROPIC_API_KEY not set in .env")
        print("Vision comparison tests will fail.")
        print()
    
    try:
        await test_basic_integration()
        await test_iframe_integration()
        # await test_challenge_integration()
        
        print("\n" + "="*70)
        print("ALL INTEGRATION TESTS COMPLETED")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

