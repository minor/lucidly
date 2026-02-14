"""Test script for the test generator and evaluator pipeline.

This script tests:
1. Test generation for different challenge types
2. Evaluation of generated code against challenges
3. End-to-end pipeline functionality

Usage:
    python backend/evaluation/tests/test_pipeline.py
    # OR from backend directory:
    python -m evaluation.tests.test_pipeline
"""

import asyncio
import json
from typing import Any

import sys
from pathlib import Path

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from challenges import Challenge, get_challenge_by_id, get_all_challenges
from evaluation import TestGenerator, ChallengeEvaluator
from llm import LLM


# Sample generated code for testing
SAMPLE_CODE = {
    "ui": """<!DOCTYPE html>
<html>
<head>
    <style>
        body { background-color: #1a1a2e; color: #eee; }
        .hero { padding: 2rem; text-align: center; }
    </style>
</head>
<body>
    <header class="hero">
        <h1>Welcome to Our Landing Page</h1>
    </header>
    <main>
        <section class="features">
            <h2>Features</h2>
        </section>
    </main>
</body>
</html>""",
    
    "scraping": """import requests
from bs4 import BeautifulSoup
import json

def scrape_nyt():
    url = "https://www.nytimes.com"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    articles = []
    for article in soup.find_all('article', limit=10):
        title = article.find('h2')
        link = article.find('a')
        if title and link:
            articles.append({
                'title': title.get_text().strip(),
                'url': link.get('href', '')
            })
    return articles

if __name__ == "__main__":
    result = scrape_nyt()
    print(json.dumps(result, indent=2))
""",
    
    "function": """def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
""",
    
    "api": """import requests

def fetch_user_data(user_id):
    response = requests.get(f"https://api.example.com/users/{user_id}")
    if response.status_code == 200:
        return response.json()
    return None
""",
}


async def test_test_generation(challenge: Challenge) -> dict[str, Any]:
    """Test test generation for a challenge."""
    print(f"\n{'='*60}")
    print(f"Testing Test Generation: {challenge.title}")
    print(f"Category: {challenge.category}")
    print(f"{'='*60}")
    
    generator = TestGenerator()
    
    try:
        test_suite = await generator.generate_tests(challenge)
        
        print(f"\n✓ Test generation successful!")
        print(f"  Execution type: {test_suite.execution_type}")
        print(f"  Number of test cases: {len(test_suite.test_cases)}")
        print(f"  Metadata keys: {list(test_suite.test_metadata.keys())}")
        
        if test_suite.test_cases:
            print(f"\n  Test cases:")
            for i, tc in enumerate(test_suite.test_cases[:3], 1):  # Show first 3
                print(f"    {i}. Input: {tc.input[:60]}...")
                print(f"       Expected: {tc.expected_output[:60]}...")
        
        if test_suite.test_metadata:
            print(f"\n  Metadata:")
            for key, value in list(test_suite.test_metadata.items())[:3]:
                if isinstance(value, list):
                    print(f"    {key}: {len(value)} items")
                else:
                    print(f"    {key}: {str(value)[:60]}...")
        
        return {
            "success": True,
            "test_suite": test_suite,
            "challenge": challenge,
        }
    except Exception as e:
        print(f"\n✗ Test generation failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "challenge": challenge,
        }


async def test_evaluation(
    challenge: Challenge,
    generated_code: str,
    test_suite: Any = None,
) -> dict[str, Any]:
    """Test evaluation of generated code."""
    print(f"\n{'='*60}")
    print(f"Testing Evaluation: {challenge.title}")
    print(f"{'='*60}")
    
    evaluator = ChallengeEvaluator()
    
    try:
        eval_result = await evaluator.evaluate(
            challenge,
            generated_code,
            test_suite,
        )
        
        print(f"\n✓ Evaluation successful!")
        print(f"  Accuracy: {eval_result.accuracy:.2%}")
        print(f"  Test results: {eval_result.test_results}")
        
        if eval_result.details:
            print(f"\n  Details:")
            for key, value in eval_result.details.items():
                if isinstance(value, (dict, list)):
                    print(f"    {key}: {type(value).__name__} ({len(value) if hasattr(value, '__len__') else 'N/A'} items)")
                else:
                    print(f"    {key}: {value}")
        
        if eval_result.execution_output:
            output_preview = str(eval_result.execution_output)[:100]
            print(f"\n  Execution output: {output_preview}...")
        
        return {
            "success": True,
            "eval_result": eval_result,
            "challenge": challenge,
        }
    except Exception as e:
        print(f"\n✗ Evaluation failed: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
            "challenge": challenge,
        }


async def test_full_pipeline(challenge: Challenge, sample_code: str | None = None) -> dict[str, Any]:
    """Test the full pipeline: generation -> evaluation."""
    print(f"\n{'='*70}")
    print(f"FULL PIPELINE TEST: {challenge.title}")
    print(f"{'='*70}")
    
    # Step 1: Generate tests
    generator = TestGenerator()
    test_suite = None
    
    try:
        print("\n[Step 1] Generating tests...")
        test_suite = await generator.generate_tests(challenge)
        print(f"✓ Generated {len(test_suite.test_cases)} test cases")
    except Exception as e:
        print(f"✗ Test generation failed: {e}")
        return {"success": False, "error": f"Test generation: {e}"}
    
    # Step 2: Evaluate with sample code
    if sample_code:
        print("\n[Step 2] Evaluating sample code...")
        evaluator = ChallengeEvaluator()
        try:
            eval_result = await evaluator.evaluate(
                challenge,
                sample_code,
                test_suite,
            )
            print(f"✓ Evaluation complete - Accuracy: {eval_result.accuracy:.2%}")
            
            return {
                "success": True,
                "test_suite": test_suite,
                "eval_result": eval_result,
            }
        except Exception as e:
            print(f"✗ Evaluation failed: {e}")
            return {"success": False, "error": f"Evaluation: {e}"}
    else:
        print("\n[Step 2] Skipping evaluation (no sample code provided)")
        return {
            "success": True,
            "test_suite": test_suite,
        }


async def main():
    """Run all tests."""
    print("="*70)
    print("TEST GENERATOR PIPELINE TEST SUITE")
    print("="*70)
    
    # Get all challenges
    challenges = get_all_challenges()
    print(f"\nFound {len(challenges)} challenges to test")
    
    results = {
        "test_generation": [],
        "evaluation": [],
        "full_pipeline": [],
    }
    
    # Test 1: Test generation for each challenge
    print("\n" + "="*70)
    print("TEST 1: Test Generation")
    print("="*70)
    
    for challenge in challenges:
        result = await test_test_generation(challenge)
        results["test_generation"].append(result)
    
    # Test 2: Evaluation with sample code
    print("\n" + "="*70)
    print("TEST 2: Evaluation with Sample Code")
    print("="*70)
    
    for challenge in challenges:
        # Get appropriate sample code
        sample_code = None
        if challenge.category == "ui":
            sample_code = SAMPLE_CODE.get("ui")
        elif challenge.category == "data" or "scraper" in challenge.description.lower():
            sample_code = SAMPLE_CODE.get("scraping")
        elif challenge.category == "function":
            sample_code = SAMPLE_CODE.get("function")
        elif "api" in challenge.description.lower():
            sample_code = SAMPLE_CODE.get("api")
        
        if sample_code:
            result = await test_evaluation(challenge, sample_code)
            results["evaluation"].append(result)
        else:
            print(f"\nSkipping evaluation for {challenge.title} (no sample code)")
    
    # Test 3: Full pipeline
    print("\n" + "="*70)
    print("TEST 3: Full Pipeline (Generation + Evaluation)")
    print("="*70)
    
    for challenge in challenges:
        sample_code = None
        if challenge.category == "ui":
            sample_code = SAMPLE_CODE.get("ui")
        elif challenge.category == "data" or "scraper" in challenge.description.lower():
            sample_code = SAMPLE_CODE.get("scraping")
        elif challenge.category == "function":
            sample_code = SAMPLE_CODE.get("function")
        
        result = await test_full_pipeline(challenge, sample_code)
        results["full_pipeline"].append(result)
    
    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)
    
    def count_success(results_list):
        return sum(1 for r in results_list if r.get("success", False))
    
    print(f"\nTest Generation:")
    print(f"  Success: {count_success(results['test_generation'])}/{len(results['test_generation'])}")
    
    print(f"\nEvaluation:")
    print(f"  Success: {count_success(results['evaluation'])}/{len(results['evaluation'])}")
    
    print(f"\nFull Pipeline:")
    print(f"  Success: {count_success(results['full_pipeline'])}/{len(results['full_pipeline'])}")
    
    # Show accuracy scores if available
    print(f"\nAccuracy Scores:")
    for result in results["evaluation"]:
        if result.get("success") and "eval_result" in result:
            challenge = result.get("challenge")
            accuracy = result["eval_result"].accuracy
            print(f"  {challenge.title if challenge else 'Unknown'}: {accuracy:.2%}")
    
    print("\n" + "="*70)
    print("All tests completed!")
    print("="*70)
    
    return results


if __name__ == "__main__":
    # Check if we have required environment variables
    import os
    from config import settings
    
    if not settings.openai_api_key and not settings.anthropic_api_key:
        print("WARNING: No API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY in .env")
        print("The test will attempt to run but may fail on LLM calls.")
        print()
    
    # Run tests
    try:
        results = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nTests interrupted by user")
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        import traceback
        traceback.print_exc()

