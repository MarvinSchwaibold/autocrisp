import base64
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from app.config import OUTPUT_DIR


class WebsiteScreenshotter:
    """Captures full-page screenshots of websites."""

    def __init__(self):
        self.screenshots_dir = OUTPUT_DIR / "screenshots"
        self.screenshots_dir.mkdir(exist_ok=True)

    def _get_site_id(self, url: str) -> str:
        """Generate a simple ID from URL."""
        parsed = urlparse(url)
        return parsed.netloc.replace(".", "_").replace(":", "_")

    async def capture_full_page(
        self,
        url: str,
        output_name: str,
        image_replacements: Optional[Dict[str, str]] = None
    ) -> Path:
        """
        Capture a full-page screenshot of a website.

        Args:
            url: The website URL to screenshot
            output_name: Name for the output file (without extension)
            image_replacements: Optional dict mapping original image URLs to local enhanced paths

        Returns:
            Path to the saved screenshot
        """
        output_path = self.screenshots_dir / f"{output_name}.png"

        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page(viewport={"width": 1920, "height": 1080})

            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Wait for images to load
            await page.wait_for_timeout(2000)

            # If we have image replacements, inject them
            if image_replacements:
                await self._inject_enhanced_images(page, image_replacements)
                await page.wait_for_timeout(1000)

            # Get full page height
            full_height = await page.evaluate("document.documentElement.scrollHeight")

            # Set viewport to full height for complete screenshot
            await page.set_viewport_size({"width": 1920, "height": full_height})
            await page.wait_for_timeout(500)

            # Take full page screenshot
            await page.screenshot(path=str(output_path), full_page=True)

            await browser.close()

        return output_path

    async def _inject_enhanced_images(self, page, replacements: Dict[str, str]):
        """
        Inject enhanced images into the page by replacing src attributes.

        Args:
            page: Playwright page object
            replacements: Dict mapping original URLs to base64 data URIs or local paths
        """
        for original_url, enhanced_path in replacements.items():
            # Read enhanced image and convert to base64
            if Path(enhanced_path).exists():
                with open(enhanced_path, "rb") as f:
                    img_data = f.read()

                # Detect format
                if enhanced_path.endswith(".webp"):
                    mime = "image/webp"
                elif enhanced_path.endswith(".png"):
                    mime = "image/png"
                else:
                    mime = "image/jpeg"

                data_uri = f"data:{mime};base64,{base64.b64encode(img_data).decode()}"

                # Replace in page using JavaScript
                await page.evaluate(f"""
                    (function() {{
                        // Replace img src
                        document.querySelectorAll('img').forEach(img => {{
                            if (img.src === '{original_url}' ||
                                img.dataset.src === '{original_url}' ||
                                img.dataset.lazySrc === '{original_url}') {{
                                img.src = '{data_uri}';
                            }}
                        }});

                        // Replace srcset
                        document.querySelectorAll('source').forEach(source => {{
                            if (source.srcset && source.srcset.includes('{original_url}')) {{
                                source.srcset = '{data_uri}';
                            }}
                        }});

                        // Replace background images
                        document.querySelectorAll('*').forEach(el => {{
                            const style = window.getComputedStyle(el);
                            if (style.backgroundImage.includes('{original_url}')) {{
                                el.style.backgroundImage = 'url({data_uri})';
                            }}
                        }});
                    }})();
                """)

    async def capture_before_after(
        self,
        url: str,
        image_replacements: Dict[str, str]
    ) -> Dict[str, Path]:
        """
        Capture both before and after screenshots.

        Args:
            url: Website URL
            image_replacements: Dict mapping original URLs to enhanced image paths

        Returns:
            Dict with 'before' and 'after' screenshot paths
        """
        site_id = self._get_site_id(url)

        # Capture before (original)
        before_path = await self.capture_full_page(
            url,
            f"{site_id}_before",
            image_replacements=None
        )

        # Capture after (with enhanced images)
        after_path = await self.capture_full_page(
            url,
            f"{site_id}_after",
            image_replacements=image_replacements
        )

        return {
            "before": before_path,
            "after": after_path
        }
