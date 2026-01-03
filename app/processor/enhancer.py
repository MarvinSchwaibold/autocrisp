import base64
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import replicate
import requests
from PIL import Image

from app.config import REPLICATE_API_TOKEN, ESRGAN_MODEL, UPSCALE_FACTOR

MAX_PIXELS = 2000000  # ~2 million pixels max for Real-ESRGAN


class ImageEnhancer:
    """Enhances images using Replicate's Real-ESRGAN model."""

    def __init__(self):
        if not REPLICATE_API_TOKEN:
            raise ValueError("REPLICATE_API_TOKEN is not set. Please add it to your .env file.")
        self.client = replicate.Client(api_token=REPLICATE_API_TOKEN)

    def _resize_if_needed(self, image_path: Path) -> bytes:
        """Resize image if it exceeds max pixel count."""
        with Image.open(image_path) as img:
            width, height = img.size
            pixels = width * height

            if pixels > MAX_PIXELS:
                # Calculate new size maintaining aspect ratio
                ratio = (MAX_PIXELS / pixels) ** 0.5
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to bytes
            buffer = BytesIO()
            img_format = 'PNG' if image_path.suffix.lower() == '.png' else 'JPEG'
            img.save(buffer, format=img_format)
            return buffer.getvalue()

    def enhance(self, image_path: Path, scale: int = UPSCALE_FACTOR, max_retries: int = 3) -> bytes:
        """
        Enhance an image using Real-ESRGAN.

        Args:
            image_path: Path to the input image
            scale: Upscale factor (2 or 4)
            max_retries: Max retries for rate limits

        Returns:
            Enhanced image as bytes
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Resize if needed and encode
        image_data = self._resize_if_needed(image_path)
        img_format = 'png' if image_path.suffix.lower() == '.png' else 'jpeg'

        for attempt in range(max_retries):
            try:
                output = self.client.run(
                    ESRGAN_MODEL,
                    input={
                        "image": f"data:image/{img_format};base64,{base64.b64encode(image_data).decode()}",
                        "scale": scale,
                        "face_enhance": False
                    }
                )
                break
            except Exception as e:
                if '429' in str(e) and attempt < max_retries - 1:
                    time.sleep(10)  # Wait for rate limit
                    continue
                raise

        # Output is a URL to the enhanced image
        if isinstance(output, str):
            response = requests.get(output, timeout=60)
            response.raise_for_status()
            return response.content
        elif hasattr(output, 'read'):
            return output.read()
        else:
            raise ValueError(f"Unexpected output type from Replicate: {type(output)}")

    def enhance_to_file(self, image_path: Path, output_path: Path, scale: int = UPSCALE_FACTOR) -> Path:
        """
        Enhance an image and save to a file.

        Args:
            image_path: Path to the input image
            output_path: Path to save the enhanced image
            scale: Upscale factor (2 or 4)

        Returns:
            Path to the enhanced image
        """
        enhanced_data = self.enhance(image_path, scale)
        output_path.write_bytes(enhanced_data)
        return output_path
