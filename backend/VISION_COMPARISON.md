# Claude Vision API Integration for Image Comparison

This document explains how to use Claude's Vision API to compare challenge reference images with generated screenshots.

## Overview

The vision comparison system allows you to:
1. Compare a challenge's ground truth image (`image_url`) with a generated screenshot from the sandbox
2. Get a similarity score (0.0 to 1.0) indicating how well the generated UI matches the reference
3. Receive detailed feedback about visual differences (layout, colors, typography, etc.)

## How It Works

### 1. Vision Comparator (`vision_comparison.py`)

The `VisionComparator` class handles:
- Fetching images from URLs
- Converting images to base64 format
- Calling Claude Vision API with both images
- Parsing Claude's response to extract similarity scores and feedback

### 2. Integration with Evaluator

The `ChallengeEvaluator` automatically uses vision comparison when:
- The challenge has an `image_url` (reference image)
- The sandbox execution returns a `screenshot_url` (generated image)
- `ANTHROPIC_API_KEY` is configured

### 3. Evaluation Flow

For UI challenges, the evaluator:
1. Executes code in sandbox (Modal placeholder)
2. Extracts screenshot URL from execution result
3. If both images are available, calls `VisionComparator.compare_images()`
4. Uses the similarity score as the primary accuracy metric
5. Falls back to code-based analysis if vision comparison isn't available

## Usage Example

```python
from vision_comparison import VisionComparator
from evaluator import ChallengeEvaluator

# Initialize
evaluator = ChallengeEvaluator()  # Automatically creates VisionComparator if API key is set

# Evaluate UI challenge
result = await evaluator.evaluate(
    challenge=challenge,  # Must have image_url
    generated_code=html_code,
    generated_test_suite=test_suite,
)

# Check if vision comparison was used
if result.details.get("vision_comparison_used"):
    similarity = result.details["vision_similarity_score"]
    feedback = result.details["vision_feedback"]
    print(f"Similarity: {similarity:.2%}")
    print(f"Feedback: {feedback}")
```

## Configuration

### Required Environment Variable

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

The vision comparison will only work if this is set. If not available, the evaluator falls back to code-based analysis.

## API Details

### Claude Vision API Format

The system sends both images to Claude in a single message:

```json
{
  "model": "claude-opus-4-6",
  "messages": [
    {
      "role": "user",
      "content": [
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "<base64_encoded_image>"
          }
        },
        {
          "type": "text",
          "text": "This is the reference image (ground truth)."
        },
        {
          "type": "image",
          "source": {
            "type": "base64",
            "media_type": "image/png",
            "data": "<base64_encoded_image>"
          }
        },
        {
          "type": "text",
          "text": "This is the generated image. [comparison prompt]"
        }
      ]
    }
  ]
}
```

### Response Format

Claude returns a JSON analysis with:
- `similarity_score`: 0.0 to 1.0
- `detailed_feedback`: Text description of differences
- `visual_elements_match`: Object with boolean flags for specific elements
- `overall_match`: Boolean indicating if similarity >= 0.7

## Integration with Modal Sandbox

When Modal sandbox execution is implemented:

1. `ModalExecutor.execute_ui_with_screenshot()` should return a `screenshot_url`
2. The evaluator extracts this URL from `execution_output`
3. Vision comparison automatically runs if both images are available

Example Modal integration:

```python
# In modal_execution.py
async def execute_ui_with_screenshot(...) -> ExecutionResult:
    # ... execute code in browser ...
    screenshot_url = await take_screenshot()  # Returns URL to screenshot
    return ExecutionResult(
        success=True,
        screenshot_url=screenshot_url,  # This triggers vision comparison
        ...
    )
```

## Accuracy Scoring

When vision comparison is used:
- **Primary score**: `similarity_score` from Claude (0.0 to 1.0)
- **Details**: Includes feedback and element-by-element matching

When vision comparison is not available:
- Falls back to code-based analysis (HTML/CSS/JS presence, DOM checks, etc.)

## Error Handling

- If image fetching fails: Falls back to code analysis
- If Claude API fails: Falls back to code analysis
- If API key not set: Vision comparison is disabled, uses code analysis

## Future Enhancements

- Support for animated GIFs (extract frames for comparison)
- Batch comparison for multiple screenshots
- Caching of comparison results
- More granular element-level scoring



