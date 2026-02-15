"""Quick test script for the test generator pipeline.

This is a simpler version that tests one challenge at a time.
Useful for debugging or quick validation.

Usage:
    python backend/test_pipeline_quick.py [challenge_id]
    
Examples:
    python backend/test_pipeline_quick.py build-landing-page
    python backend/test_pipeline_quick.py nyt-front-page-scraper
"""

import asyncio
import sys
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from challenges import get_challenge_by_id, get_all_challenges
from evaluation import TestGenerator, ChallengeEvaluator


async def quick_test(challenge_id: str | None = None):
    """Quick test of test generation and evaluation."""
    
    # Get challenge
    if challenge_id:
        challenge = get_challenge_by_id(challenge_id)
        if not challenge:
            print(f"Challenge '{challenge_id}' not found")
            print(f"Available challenges: {[c.id for c in get_all_challenges()]}")
            return
    else:
        # Use first challenge
        challenges = get_all_challenges()
        if not challenges:
            print("No challenges found")
            return
        challenge = challenges[0]
        print(f"No challenge ID provided, using: {challenge.id}")
    
    print(f"\n{'='*60}")
    print(f"Testing: {challenge.title}")
    print(f"Category: {challenge.category}")
    print(f"Description: {challenge.description[:80]}...")
    print(f"{'='*60}\n")
    
    # Step 1: Generate tests
    print("Step 1: Generating tests...")
    generator = TestGenerator()
    try:
        test_suite = await generator.generate_tests(challenge)
        print(f"✓ Generated {len(test_suite.test_cases)} test cases")
        print(f"  Execution type: {test_suite.execution_type}")
        print(f"  Test suite: {test_suite}")

        if test_suite.test_cases:
            print(f"\n  Sample test cases:")
            for i, tc in enumerate(test_suite.test_cases[:], 1):
                print(f"    {i}. {tc.input[:100]}...")
    except Exception as e:
        print(f"✗ Failed: {e}")
        import traceback
        traceback.print_exc()
        return

    # Step 2: Test evaluation with placeholder code
    print(f"\nStep 2: Testing evaluation...")
    evaluator = ChallengeEvaluator()
    
    # Create sample code based on challenge type
    sample_code = ""
    if challenge.category == "ui":
        sample_code = """<!DOCTYPE html>
<html><head><style>body{background:#1a1a2e;color:#eee}</style></head>
<body><header class="hero"><h1>Test</h1></header></body></html>"""
    elif challenge.category == "data":
        sample_code = """import requests
from bs4 import BeautifulSoup
def scrape(): return [{'title': 'Test', 'url': 'http://test.com'}]"""
    else:
        sample_code = "# Sample code for testing"
    
    try:
        eval_result = await evaluator.evaluate(challenge, sample_code, test_suite)
        print(f"✓ Evaluation complete")
        print(f"  Accuracy: {eval_result.accuracy:.2%}")
        print(f"  Details: {len(eval_result.details)} items")
        
        if eval_result.details:
            print(f"\n  Key details:")
            for key in list(eval_result.details.keys())[:5]:
                value = eval_result.details[key]
                if isinstance(value, bool):
                    print(f"    {key}: {value}")
                elif isinstance(value, (int, float)):
                    print(f"    {key}: {value}")
                else:
                    print(f"    {key}: {type(value).__name__}")
    except Exception as e:
        print(f"✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"\n{'='*60}")
    print("✓ Quick test completed successfully!")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    challenge_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    try:
        asyncio.run(quick_test(challenge_id))
    except KeyboardInterrupt:
        print("\n\nTest interrupted")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()

