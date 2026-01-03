import re
import hashlib
from pathlib import Path
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass, field
from typing import Optional

import requests
from bs4 import BeautifulSoup
from PIL import Image

from app.config import TEMP_DIR


@dataclass
class ImageInfo:
    """Metadata for a discovered image."""
    id: str
    original_url: str
    local_path: Optional[Path] = None
    width: Optional[int] = None
    height: Optional[int] = None
    file_size: Optional[int] = None
    alt_text: str = ""
    source_element: str = ""  # img, background-image, source, etc.


class WebScraper:
    """Scrapes images from a website."""

    SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (compatible; ImageEnhancerBot/1.0)"
        })
        self.images: list[ImageInfo] = []

    def _generate_id(self, url: str) -> str:
        """Generate a unique ID for an image URL."""
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _is_valid_image_url(self, url: str) -> bool:
        """Check if URL points to a supported image format."""
        parsed = urlparse(url)
        path = parsed.path.lower()
        return any(path.endswith(ext) for ext in self.SUPPORTED_EXTENSIONS)

    def _resolve_url(self, url: str) -> str:
        """Convert relative URL to absolute."""
        return urljoin(self.base_url, url)

    def _extract_background_images(self, soup: BeautifulSoup) -> list[str]:
        """Extract background-image URLs from inline styles."""
        urls = []
        pattern = re.compile(r'background(?:-image)?\s*:\s*url\(["\']?([^"\')\s]+)["\']?\)')

        for element in soup.find_all(style=True):
            style = element.get("style", "")
            matches = pattern.findall(style)
            urls.extend(matches)

        # Also check <style> tags
        for style_tag in soup.find_all("style"):
            if style_tag.string:
                matches = pattern.findall(style_tag.string)
                urls.extend(matches)

        return urls

    def scan(self) -> list[ImageInfo]:
        """Scan the website for all images."""
        try:
            response = self.session.get(self.base_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch {self.base_url}: {e}")

        soup = BeautifulSoup(response.text, "lxml")
        seen_urls = set()

        # Find <img> tags
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
            if not src:
                continue

            url = self._resolve_url(src)
            if url in seen_urls or not self._is_valid_image_url(url):
                continue

            seen_urls.add(url)
            self.images.append(ImageInfo(
                id=self._generate_id(url),
                original_url=url,
                alt_text=img.get("alt", ""),
                source_element="img"
            ))

        # Find <source> in <picture> elements
        for source in soup.find_all("source"):
            srcset = source.get("srcset", "")
            # Parse srcset (may contain multiple URLs with sizes)
            for part in srcset.split(","):
                url_part = part.strip().split()[0] if part.strip() else ""
                if url_part:
                    url = self._resolve_url(url_part)
                    if url in seen_urls or not self._is_valid_image_url(url):
                        continue
                    seen_urls.add(url)
                    self.images.append(ImageInfo(
                        id=self._generate_id(url),
                        original_url=url,
                        source_element="source"
                    ))

        # Find background images
        for bg_url in self._extract_background_images(soup):
            url = self._resolve_url(bg_url)
            if url in seen_urls or not self._is_valid_image_url(url):
                continue
            seen_urls.add(url)
            self.images.append(ImageInfo(
                id=self._generate_id(url),
                original_url=url,
                source_element="background-image"
            ))

        return self.images

    def download_image(self, image: ImageInfo) -> ImageInfo:
        """Download a single image to temp directory."""
        try:
            response = self.session.get(image.original_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            raise Exception(f"Failed to download {image.original_url}: {e}")

        # Determine file extension
        parsed = urlparse(image.original_url)
        ext = Path(parsed.path).suffix.lower() or ".jpg"

        # Save to temp directory
        local_path = TEMP_DIR / f"{image.id}{ext}"
        local_path.write_bytes(response.content)

        # Get image dimensions
        try:
            with Image.open(local_path) as img:
                image.width, image.height = img.size
        except Exception:
            pass

        image.local_path = local_path
        image.file_size = len(response.content)

        return image

    def download_all(self) -> list[ImageInfo]:
        """Download all discovered images."""
        for image in self.images:
            try:
                self.download_image(image)
            except Exception as e:
                print(f"Warning: Failed to download {image.original_url}: {e}")

        return [img for img in self.images if img.local_path is not None]
