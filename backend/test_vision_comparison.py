"""Test script for vision_comparison.py

Tests the Claude Vision API integration for comparing images.

Usage:
    python backend/test_vision_comparison.py
"""

import asyncio
from vision_comparison import VisionComparator, VisionComparisonResult


async def test_vision_comparison():
    """Test vision comparison with placehold.co images."""
    
    print("="*70)
    print("VISION COMPARISON TEST")
    print("="*70)
    
    # Test images - use PNG format for placehold.co
    reference_image_url = "https://dummyimage.com/640x400/1a1a2e/eee.png&text=Landing+Page+Design"
    generated_image_url = "https://dummyimage.com/640x400/1a1a2e/eee.png&text=Landing+Page+De"
    
    print(f"\nReference Image: {reference_image_url}")
    print(f"Generated Image: {generated_image_url}")
    print()
    
    # Initialize comparator
    try:
        comparator = VisionComparator()
        print("✓ VisionComparator initialized successfully")
    except ValueError as e:
        print(f"✗ Failed to initialize VisionComparator: {e}")
        print("  Make sure ANTHROPIC_API_KEY is set in your .env file")
        return
    
    # Test 1: Compare identical images (should have high similarity)
    print("\n" + "-"*70)
    print("TEST 1: Comparing identical images (same URL)")
    print("-"*70)
    
    try:
        result = await comparator.compare_images(
            reference_image_url=reference_image_url,
            generated_image_url=reference_image_url,  # Same image
            challenge_description="Build a landing page with dark background and light text",
        )
        
        print(f"\n✓ Comparison successful!")
        print(f"  Similarity Score: {result.similarity_score:.2%}")
        print(f"  Overall Match: {result.overall_match}")
        print(f"  Visual Elements Match: {result.visual_elements_match}")
        print(f"\n  Detailed Feedback:")
        print(f"  {result.detailed_feedback[:200]}...")
        
        if result.similarity_score >= 0.9:
            print("\n  ✓ Expected: High similarity for identical images")
        else:
            print(f"\n  ⚠ Warning: Similarity lower than expected ({result.similarity_score:.2%})")
            
    except Exception as e:
        print(f"\n✗ Comparison failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Compare similar images (slightly different text)
    print("\n" + "-"*70)
    print("TEST 2: Comparing similar images (different text)")
    print("-"*70)
    
    try:
        result = await comparator.compare_images(
            reference_image_url=reference_image_url,
            generated_image_url=generated_image_url,  # Slightly different
            challenge_description="Build a landing page with dark background and light text",
        )
        
        print(f"\n✓ Comparison successful!")
        print(f"  Similarity Score: {result.similarity_score:.2%}")
        print(f"  Overall Match: {result.overall_match}")
        print(f"  Visual Elements Match: {result.visual_elements_match}")
        print(f"\n  Detailed Feedback:")
        print(f"  {result.detailed_feedback[:300]}...")
        
    except Exception as e:
        print(f"\n✗ Comparison failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Compare with very different image
    print("\n" + "-"*70)
    print("TEST 3: Comparing with different image (different colors)")
    print("-"*70)
    
    different_image_url = "https://dummyimage.com/640x400/1a1a2e/eee.png&text=Landing+Page+Design"
    
    try:
        result = await comparator.compare_images(
            reference_image_url=reference_image_url,
            generated_image_url=different_image_url,
            challenge_description="Build a landing page with dark background and light text",
        )
        
        print(f"\n✓ Comparison successful!")
        print(f"  Similarity Score: {result.similarity_score:.2%}")
        print(f"  Overall Match: {result.overall_match}")
        print(f"  Visual Elements Match: {result.visual_elements_match}")
        print(f"\n  Detailed Feedback:")
        print(f"  {result.detailed_feedback[:300]}...")
        
        if result.similarity_score < 0.5:
            print("\n  ✓ Expected: Low similarity for very different images")
        else:
            print(f"\n  ⚠ Warning: Similarity higher than expected ({result.similarity_score:.2%})")
            
    except Exception as e:
        print(f"\n✗ Comparison failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Test image fetching
    print("\n" + "-"*70)
    print("TEST 4: Testing image fetching and base64 conversion")
    print("-"*70)
    
    try:
        image_data = await comparator._fetch_image_as_base64(reference_image_url)
        print(f"✓ Image fetched and converted to base64")
        print(f"  Data URL length: {len(image_data)} characters")
        print(f"  Data URL preview: {image_data[:50]}...")
        
        # Verify it's a valid data URL
        if image_data.startswith("data:image/") and "base64," in image_data:
            print("  ✓ Valid data URL format")
        else:
            print("  ✗ Invalid data URL format")
            
    except Exception as e:
        print(f"\n✗ Image fetching failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)
    print("ALL TESTS COMPLETED")
    print("="*70)


async def test_with_challenge():
    """Test vision comparison in the context of a challenge."""
    from challenges import get_challenge_by_id
    
    print("\n" + "="*70)
    print("CHALLENGE INTEGRATION TEST")
    print("="*70)
    
    # Get a UI challenge
    challenge = get_challenge_by_id("build-landing-page")
    if not challenge:
        print("Challenge 'build-landing-page' not found")
        return
    
    print(f"\nChallenge: {challenge.title}")
    print(f"Reference Image URL: {challenge.image_url}")
    
    # Use placehold.co as generated screenshot (PNG format)
    generated_screenshot_url = "https://dummyimage.com/640x400/1a1a2e/eee.png&text=Landing+Page+De"
    
    try:
        comparator = VisionComparator()
        
        print(f"\nComparing challenge reference with generated screenshot...")
        result = await comparator.compare_images(
            reference_image_url=challenge.image_url or "",
            generated_image_url=generated_screenshot_url,
            challenge_description=challenge.description,
        )
        
        print(f"\n✓ Comparison Results:")
        print(f"  Similarity: {result.similarity_score:.2%}")
        print(f"  Match: {'✓ YES' if result.overall_match else '✗ NO'}")
        print(f"\n  Feedback:")
        print(f"  {result.detailed_feedback}")
        
        # Simulate how evaluator would use this
        accuracy = result.similarity_score
        print(f"\n  → Accuracy Score: {accuracy:.2%}")
        if accuracy >= 0.7:
            print("  → Challenge would PASS")
        else:
            print("  → Challenge would FAIL")
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    import os
    from config import settings
    
    # Check API key
    if not settings.anthropic_api_key:
        print("WARNING: ANTHROPIC_API_KEY not set in .env")
        print("Vision comparison tests will fail.")
        print()
    
    try:
        # Run basic tests
        await test_vision_comparison()
        
        # Run challenge integration test
        await test_with_challenge()
        
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

