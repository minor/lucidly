"""Claude Vision API integration for comparing images.

This module provides functionality to compare challenge reference images
with generated screenshots using Claude's vision capabilities.
"""

import base64
import httpx
from typing import Any
from dataclasses import dataclass

import sys
from pathlib import Path

# Add parent directory to path for absolute imports
if str(Path(__file__).parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


@dataclass
class VisionComparisonResult:
    """Result of comparing two images using Claude Vision."""
    similarity_score: float  # 0.0 to 1.0
    detailed_feedback: str  # Detailed comparison feedback from Claude
    visual_elements_match: dict[str, bool]  # Specific visual elements checked
    overall_match: bool  # Whether images are considered a match


class VisionComparator:
    """Compares images using Claude Vision API."""
    
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be set to use vision comparison")
    
    async def compare_images(
        self,
        reference_image_url: str,
        generated_image_url: str,
        challenge_description: str | None = None,
    ) -> VisionComparisonResult:
        """
        Compare a reference image with a generated screenshot using Claude Vision.
        
        Args:
            reference_image_url: URL to the challenge's reference/ground truth image,
                                or base64 data URL (data:image/png;base64,...)
            generated_image_url: URL to the generated screenshot from sandbox,
                                or base64 data URL (data:image/png;base64,...)
            challenge_description: Optional description of what should match
        
        Returns:
            VisionComparisonResult with similarity score and detailed feedback
        """
        # Check if inputs are already base64 data URLs
        if reference_image_url.startswith("data:image/"):
            reference_image_data = reference_image_url
        else:
            # Fetch from URL and convert to base64
            reference_image_data = await self._fetch_image_as_base64(reference_image_url)
        
        if generated_image_url.startswith("data:image/"):
            generated_image_data = generated_image_url
        else:
            # Fetch from URL and convert to base64
            generated_image_data = await self._fetch_image_as_base64(generated_image_url)
        
        # Build the comparison prompt
        comparison_prompt = self._build_comparison_prompt(challenge_description)
        
        # Call Claude Vision API
        response = await self._call_vision_api(
            reference_image_data,
            generated_image_data,
            comparison_prompt,
        )
        
        # Parse response to extract similarity score and feedback
        return self._parse_vision_response(response)
    
    async def compare_base64_images(
        self,
        reference_image_base64: str,
        generated_image_base64: str,
        challenge_description: str | None = None,
    ) -> VisionComparisonResult:
        """
        Compare two base64-encoded images directly (no URL fetching).
        
        Args:
            reference_image_base64: Base64 data URL of reference image (data:image/png;base64,...)
            generated_image_base64: Base64 data URL of generated image (data:image/png;base64,...)
            challenge_description: Optional description of what should match
        
        Returns:
            VisionComparisonResult with similarity score and detailed feedback
        """
        # Build the comparison prompt
        comparison_prompt = self._build_comparison_prompt(challenge_description)
        
        # Call Claude Vision API directly with base64 data
        response = await self._call_vision_api(
            reference_image_base64,
            generated_image_base64,
            comparison_prompt,
        )
        
        # Parse response to extract similarity score and feedback
        return self._parse_vision_response(response)
    
    async def _fetch_image_as_base64(self, image_url: str) -> str:
        """Fetch an image from URL and convert to base64."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                # For placehold.co, request PNG format explicitly
                if "placehold.co" in image_url and "format=" not in image_url:
                    # Add format=png parameter
                    separator = "&" if "?" in image_url else "?"
                    image_url = f"{image_url}{separator}format=png"
                
                response = await client.get(image_url)
                response.raise_for_status()
                
                # Check if content is SVG
                content_type = response.headers.get("content-type", "").lower()
                content_preview = response.content[:100].decode("utf-8", errors="ignore")
                
                if "svg" in content_type or content_preview.strip().startswith("<svg"):
                    # SVG detected - convert to PNG
                    return await self._convert_svg_to_png_base64(response.content)
                
                # Determine media type for raster images
                if "jpeg" in content_type or "jpg" in content_type:
                    media_type = "image/jpeg"
                elif "gif" in content_type:
                    media_type = "image/gif"
                elif "webp" in content_type:
                    media_type = "image/webp"
                else:
                    media_type = "image/png"
                
                # Encode to base64
                image_base64 = base64.b64encode(response.content).decode("utf-8")
                return f"data:{media_type};base64,{image_base64}"
            except Exception as e:
                raise Exception(f"Failed to fetch image from {image_url}: {e}")
    
    async def _convert_svg_to_png_base64(self, svg_content: bytes) -> str:
        """Convert SVG content to PNG base64."""
        try:
            # Try using cairosvg if available
            try:
                import cairosvg
                from io import BytesIO
                
                png_data = cairosvg.svg2png(bytestring=svg_content)
                image_base64 = base64.b64encode(png_data).decode("utf-8")
                return f"data:image/png;base64,{image_base64}"
            except ImportError:
                # Fallback: Use PIL/Pillow with svglib if available
                try:
                    from svglib.svglib import svg2rlg
                    from reportlab.graphics import renderPM
                    from io import BytesIO
                    
                    drawing = svg2rlg(BytesIO(svg_content))
                    png_data = renderPM.drawToString(drawing, fmt="PNG")
                    image_base64 = base64.b64encode(png_data).decode("utf-8")
                    return f"data:image/png;base64,{image_base64}"
                except ImportError:
                    # Last resort: request PNG from placehold.co if it's a placehold URL
                    # For now, raise an error with helpful message
                    raise Exception(
                        "SVG images are not supported. Please install 'cairosvg' or 'svglib' "
                        "to convert SVG to PNG, or use PNG/JPEG image URLs. "
                        "For placehold.co, add '&format=png' to the URL."
                    )
        except Exception as e:
            raise Exception(f"Failed to convert SVG to PNG: {e}")
    
    def _build_comparison_prompt(self, challenge_description: str | None) -> str:
        """Build the prompt for image comparison."""
        base_prompt = """You are an expert at comparing UI designs and screenshots. Compare these two images:

1. Reference Image (ground truth): The expected design/UI
2. Generated Image: The implementation to evaluate

Analyze the following aspects:
- Layout and structure (positioning of elements)
- Colors and styling (background colors, text colors, borders)
- Typography (font sizes, weights, families)
- Visual elements (buttons, icons, images, spacing)
- Overall visual similarity

Provide your analysis in this JSON format:
{
  "similarity_score": 0.85,
  "detailed_feedback": "The layout matches well but colors are slightly off...",
  "visual_elements_match": {
    "layout": true,
    "colors": false,
    "typography": true,
    "spacing": true
  },
  "overall_match": true
}

Similarity score should be 0.0 (completely different) to 1.0 (identical).
Overall match should be true if similarity_score >= 0.7."""
        
        if challenge_description:
            base_prompt = f"""Challenge Description: {challenge_description}

{base_prompt}"""
        
        return base_prompt
    
    async def _call_vision_api(
        self,
        reference_image: str,
        generated_image: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Call Claude Vision API with two images."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            
            # Parse base64 data URLs
            def parse_data_url(data_url: str) -> tuple[str, str]:
                """Parse data URL into (media_type, base64_data)."""
                if "," not in data_url:
                    raise ValueError(f"Invalid data URL format: {data_url[:50]}...")
                
                header, data = data_url.split(",", 1)
                if ";" in header:
                    media_type = header.split(":")[1].split(";")[0]
                else:
                    media_type = header.split(":")[1] if ":" in header else "image/png"
                return media_type, data
            
            ref_media_type, ref_data = parse_data_url(reference_image)
            gen_media_type, gen_data = parse_data_url(generated_image)
            
            # Claude Vision API format: images are included in message content
            payload = {
                "model": "claude-opus-4-6",  # or claude-3-5-sonnet-20241022
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": ref_media_type,
                                    "data": ref_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": "This is the reference image (ground truth).",
                            },
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": gen_media_type,
                                    "data": gen_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": f"This is the generated image. {prompt}",
                            },
                        ],
                    }
                ],
            }
            
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            
            if response.status_code != 200:
                error_text = response.text
                raise Exception(f"Claude Vision API error ({response.status_code}): {error_text}")
            
            api_response = response.json()
            
            # Log the full Claude Vision API response
            import json
            import logging
            logger = logging.getLogger(__name__)
            logger.info("=" * 80)
            logger.info("[Claude Vision] Full API Response:")
            logger.info(json.dumps(api_response, indent=2))
            logger.info("=" * 80)
            
            return api_response
    
    def _parse_vision_response(self, api_response: dict[str, Any]) -> VisionComparisonResult:
        """Parse Claude's response to extract comparison results."""
        content = api_response.get("content", [])
        response_text = ""
        for block in content:
            if block.get("type") == "text":
                response_text += block.get("text", "")
        
        # Try to extract JSON from the response
        import json
        import re
        
        # Look for JSON in the response
        json_match = None
        try:
            # Try to find JSON block
            json_pattern = r'\{[^{}]*"similarity_score"[^{}]*\}'
            matches = re.findall(json_pattern, response_text, re.DOTALL)
            if matches:
                json_match = json.loads(matches[0])
        except:
            pass
        
        # If no JSON found, try to extract score from text
        if not json_match:
            # Look for similarity score in text (e.g., "0.85" or "85%")
            score_match = re.search(r"(\d+\.?\d*)", response_text)
            similarity_score = float(score_match.group(1)) if score_match else 0.5
            if similarity_score > 1.0:
                similarity_score = similarity_score / 100.0  # Convert percentage to decimal
            
            return VisionComparisonResult(
                similarity_score=similarity_score,
                detailed_feedback=response_text,
                visual_elements_match={},
                overall_match=similarity_score >= 0.7,
            )
        
        # Parse structured response
        similarity_score = json_match.get("similarity_score", 0.5)
        detailed_feedback = json_match.get("detailed_feedback", response_text)
        visual_elements_match = json_match.get("visual_elements_match", {})
        overall_match = json_match.get("overall_match", similarity_score >= 0.7)
        
        return VisionComparisonResult(
            similarity_score=float(similarity_score),
            detailed_feedback=detailed_feedback,
            visual_elements_match=visual_elements_match,
            overall_match=bool(overall_match),
        )

