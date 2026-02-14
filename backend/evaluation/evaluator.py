"""Evaluation system for challenge responses with different strategies per challenge type."""

import json
from typing import Any
from dataclasses import dataclass

import sys
from pathlib import Path

# Add parent directory to path for absolute imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from challenges import Challenge, TestCase
from modal_execution import ModalExecutor, ExecutionType
from .test_generator import GeneratedTestSuite
from .vision_comparison import VisionComparator
from .screenshot_vision_integration import compare_with_challenge_reference


@dataclass
class EvaluationResult:
    """Result of evaluating a generated response against a challenge."""
    accuracy: float  # 0.0 to 1.0
    test_results: list[bool] | None
    details: dict[str, Any]  # Additional evaluation details
    execution_output: str | None = None  # Output from code execution (placeholder)


class ChallengeEvaluator:
    """Evaluates generated code/responses against challenge requirements."""

    def __init__(self):
        # Placeholder for Modal sandbox execution
        self.modal_executor = ModalExecutor()
        self.use_modal_execution = False  # Set to True when Modal is configured
        
        # Vision comparator for UI image comparison
        try:
            self.vision_comparator = VisionComparator()
        except ValueError:
            # ANTHROPIC_API_KEY not set, vision comparison won't be available
            self.vision_comparator = None

    async def evaluate(
        self,
        challenge: Challenge,
        generated_code: str,
        generated_test_suite: GeneratedTestSuite | None = None,
    ) -> EvaluationResult:
        """
        Evaluate generated code against challenge requirements.
        
        Uses different evaluation strategies based on challenge category.
        """
        if challenge.category == "ui":
            return await self._evaluate_ui(challenge, generated_code, generated_test_suite)
        elif challenge.category == "data" or "scraper" in challenge.description.lower():
            return await self._evaluate_scraping(challenge, generated_code, generated_test_suite)
        elif challenge.category == "function":
            return await self._evaluate_function(challenge, generated_code, generated_test_suite)
        elif "api" in challenge.description.lower() or challenge.category == "api":
            return await self._evaluate_api(challenge, generated_code, generated_test_suite)
        else:
            return await self._evaluate_generic(challenge, generated_code, generated_test_suite)

    async def _evaluate_ui(
        self,
        challenge: Challenge,
        generated_code: str,
        test_suite: GeneratedTestSuite | None,
    ) -> EvaluationResult:
        """
        Evaluate UI challenges by:
        1. Executing code in sandbox (placeholder)
        2. Taking screenshot/rendering
        3. Comparing visual elements and DOM structure
        4. Using Claude Vision API to compare reference image with generated screenshot
        """
        # Execute code in sandbox (placeholder for now)
        execution_output = await self._execute_code_placeholder(generated_code, "ui")
        
        # Use vision comparison if reference image is available
        # Capture screenshot directly from generated HTML (no persistence needed)
        vision_comparison_result = None
        if self.vision_comparator and challenge.image_url:
            try:
                # Use the integrated screenshot + vision comparison function
                vision_comparison_result = await compare_with_challenge_reference(
                    generated_html=generated_code,
                    challenge=challenge,
                    generated_selector=None,  # Can specify 'iframe' or other selector if needed
                    width=1280,
                    height=720,
                )
            except Exception as e:
                # Vision comparison failed, fall back to code analysis
                print(f"Vision comparison failed: {e}")
                import traceback
                traceback.print_exc()
                vision_comparison_result = None
        
        # Analyze code structure (fallback or supplement to vision comparison)
        code_lower = generated_code.lower()
        details = {
            "has_html": "<html" in code_lower or "<!doctype" in code_lower or "<div" in code_lower,
            "has_css": "<style" in code_lower or "css" in code_lower or ".css" in code_lower,
            "has_js": "<script" in code_lower or "javascript" in code_lower or ".js" in code_lower,
            "code_length": len(generated_code),
            "execution_successful": execution_output is not None and "Placeholder" not in str(execution_output),
            "vision_comparison_used": vision_comparison_result is not None,
        }
        
        # If vision comparison was successful, use it as primary accuracy score
        if vision_comparison_result:
            accuracy = vision_comparison_result.similarity_score
            details.update({
                "vision_similarity_score": vision_comparison_result.similarity_score,
                "vision_feedback": vision_comparison_result.detailed_feedback,
                "vision_elements_match": vision_comparison_result.visual_elements_match,
                "vision_overall_match": vision_comparison_result.overall_match,
            })
        else:
            # Fall back to code-based analysis
            # Check DOM structure if test suite provides checks
            dom_checks_passed = 0
            total_dom_checks = 0
            visual_checks_passed = 0
            total_visual_checks = 0
            
            if test_suite:
                # DOM structure checks
                if test_suite.test_metadata.get("dom_checks"):
                    dom_checks = test_suite.test_metadata.get("dom_checks", [])
                    total_dom_checks = len(dom_checks)
                    for check in dom_checks:
                        # Simple keyword matching for now
                        # In real implementation, would parse DOM from execution
                        check_lower = check.lower()
                        keywords = [kw for kw in check_lower.split() if len(kw) > 3]  # Filter out small words
                        if keywords and any(kw in code_lower for kw in keywords):
                            dom_checks_passed += 1
                
                # Visual checks (would compare screenshots in real implementation)
                if test_suite.test_metadata.get("visual_checks"):
                    visual_checks = test_suite.test_metadata.get("visual_checks", [])
                    total_visual_checks = len(visual_checks)
                    # For now, check if code mentions visual elements
                    for check in visual_checks:
                        check_lower = check.lower()
                        if any(word in code_lower for word in check_lower.split() if len(word) > 3):
                            visual_checks_passed += 1
            
            # Calculate accuracy from code analysis
            base_score = 0.2 if details["has_html"] else 0.0
            if details["has_css"]:
                base_score += 0.15
            if details["has_js"]:
                base_score += 0.15
            
            # Weight DOM and visual checks
            if total_dom_checks > 0:
                dom_score = dom_checks_passed / total_dom_checks
                base_score = base_score * 0.4 + dom_score * 0.3
            
            if total_visual_checks > 0:
                visual_score = visual_checks_passed / total_visual_checks
                base_score = base_score * 0.7 + visual_score * 0.3
            
            # Bonus for successful execution (when Modal is implemented)
            if details["execution_successful"]:
                base_score = min(base_score + 0.1, 1.0)
            
            accuracy = min(base_score, 1.0)
            
            details.update({
                "dom_checks_passed": dom_checks_passed,
                "total_dom_checks": total_dom_checks,
                "visual_checks_passed": visual_checks_passed,
                "total_visual_checks": total_visual_checks,
            })
        
        return EvaluationResult(
            accuracy=accuracy,
            test_results=None,  # UI tests are more visual, not pass/fail
            details=details,
            execution_output=execution_output,
        )

    async def _evaluate_scraping(
        self,
        challenge: Challenge,
        generated_code: str,
        test_suite: GeneratedTestSuite | None,
    ) -> EvaluationResult:
        """
        Evaluate web scraping challenges by:
        1. Executing code in sandbox
        2. Validating output structure
        3. Checking required fields
        """
        execution_output = await self._execute_code_placeholder(generated_code, "scraping")
        
        details = {
            "has_requests": "requests" in generated_code.lower() or "httpx" in generated_code.lower(),
            "has_parser": "beautifulsoup" in generated_code.lower() or "lxml" in generated_code.lower() or "html.parser" in generated_code.lower(),
            "code_length": len(generated_code),
        }
        
        # Try to parse output if execution returned something
        output_valid = False
        required_fields_present = []
        if execution_output:
            try:
                parsed = json.loads(execution_output)
                if isinstance(parsed, list):
                    output_valid = True
                    if parsed and isinstance(parsed[0], dict):
                        required_fields = test_suite.test_metadata.get("required_fields", []) if test_suite else []
                        for field in required_fields:
                            if field in parsed[0]:
                                required_fields_present.append(field)
            except:
                pass
        
        # Calculate accuracy
        base_score = 0.2 if details["has_requests"] else 0.0
        if details["has_parser"]:
            base_score += 0.2
        if output_valid:
            base_score += 0.4
        
        if test_suite and test_suite.test_metadata.get("required_fields"):
            required_fields = test_suite.test_metadata.get("required_fields", [])
            if required_fields:
                fields_score = len(required_fields_present) / len(required_fields)
                base_score = base_score * 0.6 + fields_score * 0.4
        
        accuracy = min(base_score, 1.0)
        
        return EvaluationResult(
            accuracy=accuracy,
            test_results=None,
            details=details,
            execution_output=execution_output,
        )

    async def _evaluate_function(
        self,
        challenge: Challenge,
        generated_code: str,
        test_suite: GeneratedTestSuite | None,
    ) -> EvaluationResult:
        """
        Evaluate function challenges by running test cases.
        Uses existing run_function_tests logic.
        Prioritizes challenge.test_suite if available, otherwise uses generated test suite.
        """
        from .scoring import run_function_tests
        
        # Prioritize challenge's test_suite if available
        if challenge.test_suite:
            test_dicts = [t.model_dump() for t in challenge.test_suite]
            test_results = run_function_tests(generated_code, test_dicts)
            accuracy = sum(test_results) / len(test_results) if test_results else 0.0
            return EvaluationResult(
                accuracy=accuracy,
                test_results=test_results,
                details={"test_count": len(test_results), "source": "challenge_test_suite"},
                execution_output=None,
            )
        
        # Fall back to generated test suite
        if test_suite and test_suite.test_cases:
            test_dicts = [t.model_dump() for t in test_suite.test_cases]
            test_results = run_function_tests(generated_code, test_dicts)
            accuracy = sum(test_results) / len(test_results) if test_results else 0.0
            return EvaluationResult(
                accuracy=accuracy,
                test_results=test_results,
                details={"test_count": len(test_results), "source": "generated_test_suite"},
                execution_output=None,
            )
        
        # No test cases available
        return EvaluationResult(
            accuracy=0.0,
            test_results=None,
            details={"error": "No test cases available"},
            execution_output=None,
        )

    async def _evaluate_api(
        self,
        challenge: Challenge,
        generated_code: str,
        test_suite: GeneratedTestSuite | None,
    ) -> EvaluationResult:
        """Evaluate API challenges."""
        execution_output = await self._execute_code_placeholder(generated_code, "api")
        
        details = {
            "has_http_client": any(lib in generated_code.lower() for lib in ["requests", "httpx", "fetch", "axios"]),
            "code_length": len(generated_code),
        }
        
        # Basic accuracy based on code structure
        accuracy = 0.3 if details["has_http_client"] else 0.0
        
        return EvaluationResult(
            accuracy=accuracy,
            test_results=None,
            details=details,
            execution_output=execution_output,
        )

    async def _evaluate_generic(
        self,
        challenge: Challenge,
        generated_code: str,
        test_suite: GeneratedTestSuite | None,
    ) -> EvaluationResult:
        """Generic evaluation fallback."""
        execution_output = await self._execute_code_placeholder(generated_code, "generic")
        
        # Very basic evaluation
        accuracy = 0.5 if len(generated_code) > 50 else 0.0
        
        return EvaluationResult(
            accuracy=accuracy,
            test_results=None,
            details={"code_length": len(generated_code)},
            execution_output=execution_output,
        )

    async def _execute_code_placeholder(
        self,
        code: str,
        execution_type: str,
    ) -> str | None:
        """
        Execute code using Modal sandbox (placeholder for now).
        
        In the real implementation, this will:
        1. Send code to Modal sandbox
        2. Execute in appropriate environment (browser for UI, Python for scraping, etc.)
        3. Return execution output (screenshot URL, JSON output, etc.)
        """
        if self.use_modal_execution:
            result = await self.modal_executor.execute(
                code,
                execution_type=execution_type,  # type: ignore
            )
            if result.success:
                return result.output or result.screenshot_url
            return None
        else:
            # Placeholder mode
            return f"[Placeholder: Code would be executed in Modal sandbox for {execution_type} challenge]"

