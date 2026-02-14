"""Screenshot capture for UI challenges.

Captures screenshots from HTML/CSS/JS code using headless browsers.
Supports both local execution and Modal sandbox execution.
"""

import base64
import tempfile
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


@dataclass
class ScreenshotOptions:
    """Options for screenshot capture."""
    width: int = 1280
    height: int = 720
    device_scale_factor: float = 1.0
    wait_timeout: int = 5000  # milliseconds to wait for page to load
    full_page: bool = False  # If True, captures full page, otherwise viewport only


class ScreenshotCapture:
    """Captures screenshots from HTML/CSS/JS code."""
    
    def __init__(self):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright is required for screenshot capture. "
                "Install it with: pip install playwright && playwright install chromium"
            )
        self.browser: Optional[Browser] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
    
    async def start(self):
        """Start the browser instance."""
        if self.browser is None:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
    
    async def close(self):
        """Close the browser instance."""
        if self.browser:
            await self.browser.close()
            self.browser = None
    
    async def capture_from_html(
        self,
        html_content: str,
        options: Optional[ScreenshotOptions] = None,
    ) -> bytes:
        """
        Capture screenshot from HTML content.
        
        Args:
            html_content: Complete HTML string (can include <style> and <script> tags)
            options: Screenshot options (width, height, etc.)
        
        Returns:
            PNG image bytes
        """
        if not self.browser:
            await self.start()
        
        options = options or ScreenshotOptions()
        
        # Create a new page
        page = await self.browser.new_page(
            viewport={'width': options.width, 'height': options.height},
            device_scale_factor=options.device_scale_factor,
        )
        
        try:
            # Set content and wait for it to load
            await page.set_content(html_content, wait_until='networkidle')
            
            # Wait additional time for any animations/JS to complete
            await asyncio.sleep(options.wait_timeout / 1000)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=options.full_page,
            )
            
            return screenshot_bytes
        finally:
            await page.close()
    
    async def capture_from_url(
        self,
        url: str,
        options: Optional[ScreenshotOptions] = None,
    ) -> bytes:
        """
        Capture screenshot from a URL.
        
        Args:
            url: URL to capture
            options: Screenshot options
        
        Returns:
            PNG image bytes
        """
        if not self.browser:
            await self.start()
        
        options = options or ScreenshotOptions()
        
        page = await self.browser.new_page(
            viewport={'width': options.width, 'height': options.height},
            device_scale_factor=options.device_scale_factor,
        )
        
        try:
            await page.goto(url, wait_until='networkidle')
            await asyncio.sleep(options.wait_timeout / 1000)
            
            screenshot_bytes = await page.screenshot(
                type='png',
                full_page=options.full_page,
            )
            
            return screenshot_bytes
        finally:
            await page.close()
    
    async def capture_to_base64(
        self,
        html_content: str,
        options: Optional[ScreenshotOptions] = None,
    ) -> str:
        """
        Capture screenshot and return as base64 data URL.
        
        Args:
            html_content: Complete HTML string
            options: Screenshot options
        
        Returns:
            Base64 data URL (data:image/png;base64,...)
        """
        screenshot_bytes = await self.capture_from_html(html_content, options)
        image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    async def capture_to_file(
        self,
        html_content: str,
        output_path: Optional[str] = None,
        options: Optional[ScreenshotOptions] = None,
    ) -> str:
        """
        Capture screenshot and save to file.
        
        Args:
            html_content: Complete HTML string
            output_path: Path to save screenshot (if None, uses temp file)
            options: Screenshot options
        
        Returns:
            Path to saved screenshot file
        """
        screenshot_bytes = await self.capture_from_html(html_content, options)
        
        if output_path is None:
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
                output_path = f.name
        
        # Ensure directory exists
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Write screenshot
        with open(output_path, 'wb') as f:
            f.write(screenshot_bytes)
        
        return output_path
    
    async def capture_element(
        self,
        html_content: str,
        selector: str,
        options: Optional[ScreenshotOptions] = None,
    ) -> bytes:
        """
        Capture screenshot of a specific element on the page.
        
        Args:
            html_content: Complete HTML string
            selector: CSS selector for the element (e.g., '#my-iframe', '.preview-container', 'iframe')
            options: Screenshot options
        
        Returns:
            PNG image bytes of the element
        """
        if not self.browser:
            await self.start()
        
        options = options or ScreenshotOptions()
        
        page = await self.browser.new_page(
            viewport={'width': options.width, 'height': options.height},
            device_scale_factor=options.device_scale_factor,
        )
        
        try:
            await page.set_content(html_content, wait_until='networkidle')
            await asyncio.sleep(options.wait_timeout / 1000)
            
            # Wait for the element to be visible
            await page.wait_for_selector(selector, state='visible', timeout=10000)
            
            # Get the element and take screenshot
            element = await page.query_selector(selector)
            if element is None:
                raise ValueError(f"Element with selector '{selector}' not found")
            
            screenshot_bytes = await element.screenshot(type='png')
            return screenshot_bytes
        finally:
            await page.close()
    
    async def capture_iframe(
        self,
        html_content: str,
        iframe_selector: str = 'iframe',
        options: Optional[ScreenshotOptions] = None,
    ) -> bytes:
        """
        Capture screenshot of an iframe's content.
        
        Note: This works for same-origin iframes. For cross-origin iframes,
        it will capture the iframe element itself (the frame, not the content).
        
        Args:
            html_content: Complete HTML string containing the iframe
            iframe_selector: CSS selector for the iframe (default: 'iframe')
            options: Screenshot options
        
        Returns:
            PNG image bytes of the iframe content
        """
        if not self.browser:
            await self.start()
        
        options = options or ScreenshotOptions()
        
        page = await self.browser.new_page(
            viewport={'width': options.width, 'height': options.height},
            device_scale_factor=options.device_scale_factor,
        )
        
        try:
            await page.set_content(html_content, wait_until='networkidle')
            await asyncio.sleep(options.wait_timeout / 1000)
            
            # Wait for iframe to load
            await page.wait_for_selector(iframe_selector, state='attached', timeout=10000)
            
            # Get the iframe element
            iframe_element = await page.query_selector(iframe_selector)
            if iframe_element is None:
                raise ValueError(f"Iframe with selector '{iframe_selector}' not found")
            
            # For iframes with srcdoc or same-origin content, we can screenshot the element directly
            # Playwright will capture the iframe's rendered content
            try:
                screenshot_bytes = await iframe_element.screenshot(type='png')
            except Exception as e:
                # If that fails, try to get the frame and screenshot its page
                iframe_frame = await iframe_element.content_frame()
                
                if iframe_frame is None:
                    # Cross-origin iframe - can't access content, just screenshot the frame element
                    screenshot_bytes = await iframe_element.screenshot(type='png')
                else:
                    # Same-origin iframe - get the frame's page and screenshot it
                    # Get bounding box to crop to iframe size
                    iframe_box = await iframe_element.bounding_box()
                    
                    if iframe_box:
                        # Screenshot the parent page, clipped to iframe bounds
                        screenshot_bytes = await page.screenshot(
                            type='png',
                            clip={
                                'x': iframe_box['x'],
                                'y': iframe_box['y'],
                                'width': iframe_box['width'],
                                'height': iframe_box['height'],
                            }
                        )
                    else:
                        # Fallback: screenshot the iframe element
                        screenshot_bytes = await iframe_element.screenshot(type='png')
            
            return screenshot_bytes
        finally:
            await page.close()
    
    async def capture_element_base64(
        self,
        html_content: str,
        selector: str,
        options: Optional[ScreenshotOptions] = None,
    ) -> str:
        """
        Capture screenshot of a specific element and return as base64.
        
        Args:
            html_content: Complete HTML string
            selector: CSS selector for the element
            options: Screenshot options
        
        Returns:
            Base64 data URL
        """
        screenshot_bytes = await self.capture_element(html_content, selector, options)
        image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"
    
    async def capture_iframe_base64(
        self,
        html_content: str,
        iframe_selector: str = 'iframe',
        options: Optional[ScreenshotOptions] = None,
    ) -> str:
        """
        Capture screenshot of an iframe and return as base64.
        
        Args:
            html_content: Complete HTML string containing the iframe
            iframe_selector: CSS selector for the iframe
            options: Screenshot options
        
        Returns:
            Base64 data URL
        """
        screenshot_bytes = await self.capture_iframe(html_content, iframe_selector, options)
        image_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return f"data:image/png;base64,{image_base64}"


async def capture_ui_screenshot(
    html_code: str,
    width: int = 1280,
    height: int = 720,
) -> bytes:
    """
    Convenience function to capture a screenshot from HTML.
    
    Args:
        html_code: HTML content to render
        width: Viewport width
        height: Viewport height
    
    Returns:
        PNG image bytes
    """
    options = ScreenshotOptions(width=width, height=height)
    
    async with ScreenshotCapture() as capture:
        return await capture.capture_from_html(html_code, options)


async def capture_ui_screenshot_base64(
    html_code: str,
    width: int = 1280,
    height: int = 720,
) -> str:
    """
    Convenience function to capture a screenshot and return as base64.
    
    Args:
        html_code: HTML content to render
        width: Viewport width
        height: Viewport height
    
    Returns:
        Base64 data URL
    """
    options = ScreenshotOptions(width=width, height=height)
    
    async with ScreenshotCapture() as capture:
        return await capture.capture_to_base64(html_code, options)

