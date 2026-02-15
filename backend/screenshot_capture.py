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

def _check_playwright_available():
    """Check if playwright is available by trying to import it."""
    try:
        from playwright.async_api import async_playwright, Browser, Page
        return True, None
    except ImportError as e:
        return False, str(e)

# Try to import at module load time
try:
    from playwright.async_api import async_playwright, Browser, Page
    PLAYWRIGHT_AVAILABLE = True
    PLAYWRIGHT_IMPORT_ERROR = None
except ImportError as e:
    PLAYWRIGHT_AVAILABLE = False
    PLAYWRIGHT_IMPORT_ERROR = str(e)


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
        # Re-check at runtime in case import was cached incorrectly
        available, error = _check_playwright_available()
        if not available:
            error_msg = (
                "Playwright is required for screenshot capture. "
                "Install it with: pip install playwright && playwright install chromium"
            )
            if error:
                error_msg += f"\n\nImport error: {error}"
            raise ImportError(error_msg)
        # Re-import at runtime to ensure it's available
        from playwright.async_api import async_playwright, Browser, Page
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
            frames = await page.locator("iframe").all()
            print("Total iframes found:", len(frames))

            for i, frame in enumerate(frames):
                title = await frame.get_attribute("title")
                src = await frame.get_attribute("src")
                print(i, "title:", title, "src:", src)
                
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
            
            # Wait for iframe to be fully loaded
            # For cross-origin iframes, we need to wait longer
            await asyncio.sleep(2)  # Additional wait for iframe content to load
            
            # For iframes with srcdoc or same-origin content, we can screenshot the element directly
            # Playwright will capture the iframe's rendered content
            try:
                # First try to get the frame content (works for same-origin and srcdoc)
                iframe_frame = await iframe_element.content_frame()
                
                if iframe_frame is not None:
                    # Same-origin or srcdoc iframe - screenshot the frame's page directly
                    # This captures the actual iframe content, not just the frame element
                    # Wait for the frame to be ready
                    try:
                        await iframe_frame.wait_for_load_state('networkidle', timeout=10000)
                    except:
                        pass  # Continue even if networkidle times out
                    screenshot_bytes = await iframe_frame.screenshot(type='png', full_page=False)
                else:
                    # Cross-origin iframe - we need to capture the iframe element itself
                    # Wait a bit more for cross-origin content to render
                    await asyncio.sleep(1)
                    # For cross-origin iframes, screenshot the element (captures what's visible)
                    screenshot_bytes = await iframe_element.screenshot(type='png')
            except Exception as e:
                # If that fails, try alternative method
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
    
    async def capture_url_iframe(
        self,
        page_url: str,
        iframe_selector: str = 'iframe',
        container_selector: Optional[str] = None,
        options: Optional[ScreenshotOptions] = None,
        wait_time: float = 3.0,
    ) -> bytes:
        """
        Capture screenshot of an iframe from a live URL.
        
        This is useful when you need to screenshot an iframe that's embedded in a webpage,
        especially when the iframe loads external content (like challenge.embed_url).
        
        Args:
            page_url: URL of the page containing the iframe
            iframe_selector: CSS selector for the iframe (default: 'iframe')
            container_selector: Optional CSS selector for the container div to screenshot
                               instead of the iframe itself. Useful when the container
                               has overflow/clipping (like your 680px height container).
            options: Screenshot options
            wait_time: Additional time to wait for iframe content to load (seconds)
        
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
            # Navigate to the page
            await page.goto(page_url, wait_until='networkidle', timeout=30000)
            
            # Wait for iframe to be present
            await page.wait_for_selector(iframe_selector, state='attached', timeout=10000)
            
            # Wait additional time for iframe content to load
            # This is important for external embed URLs
            await asyncio.sleep(wait_time)
            
            # Determine what to screenshot
            if container_selector:
                # Screenshot the container (useful for clipped/overflow containers)
                element = await page.query_selector(container_selector)
                if element is None:
                    raise ValueError(f"Container with selector '{container_selector}' not found")
                screenshot_bytes = await element.screenshot(type='png')
            else:
                # Screenshot the iframe element itself
                iframe_element = await page.query_selector(iframe_selector)
                if iframe_element is None:
                    raise ValueError(f"Iframe with selector '{iframe_selector}' not found")
                
                # Try to access iframe content if same-origin
                try:
                    iframe_frame = await iframe_element.content_frame()
                    
                    if iframe_frame is not None:
                        # Same-origin iframe - can screenshot the frame content
                        try:
                            await iframe_frame.wait_for_load_state('networkidle', timeout=5000)
                        except:
                            pass  # Continue even if timeout
                        screenshot_bytes = await iframe_frame.screenshot(type='png', full_page=False)
                    else:
                        # Cross-origin iframe - screenshot the element
                        screenshot_bytes = await iframe_element.screenshot(type='png')
                except Exception:
                    # Fallback: just screenshot the iframe element
                    screenshot_bytes = await iframe_element.screenshot(type='png')
            
            return screenshot_bytes
        finally:
            await page.close()
    
    async def capture_url_iframe_base64(
        self,
        page_url: str,
        iframe_selector: str = 'iframe',
        container_selector: Optional[str] = None,
        options: Optional[ScreenshotOptions] = None,
        wait_time: float = 3.0,
    ) -> str:
        """
        Capture screenshot of an iframe from a live URL and return as base64.
        
        Args:
            page_url: URL of the page containing the iframe
            iframe_selector: CSS selector for the iframe
            container_selector: Optional CSS selector for the container div
            options: Screenshot options
            wait_time: Additional wait time for iframe content (seconds)
        
        Returns:
            Base64 data URL
        """
        screenshot_bytes = await self.capture_url_iframe(
            page_url, iframe_selector, container_selector, options, wait_time
        )
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