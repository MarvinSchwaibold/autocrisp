import base64
import time
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image

from app.config import (
    REPLICATE_API_TOKEN, OPENAI_API_KEY, ESRGAN_MODEL,
    UPSCALE_FACTOR, ENHANCEMENT_PROVIDER
)

MAX_PIXELS = 2000000  # ~2 million pixels max for Real-ESRGAN


class ImageEnhancer:
    """Enhances images using OpenAI or Replicate API."""

    def __init__(self):
        self.provider = ENHANCEMENT_PROVIDER

        if self.provider == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is not set. Please add it to your .env file.")
            from openai import OpenAI
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            if not REPLICATE_API_TOKEN:
                raise ValueError("REPLICATE_API_TOKEN is not set. Please add it to your .env file.")
            import replicate
            self.client = replicate.Client(api_token=REPLICATE_API_TOKEN)

    def _prepare_image_for_openai(self, image_path: Path) -> bytes:
        """Prepare image for OpenAI API (must be PNG, max 4MB, square for best results)."""
        with Image.open(image_path) as img:
            # Convert to RGB if needed (remove alpha)
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            # Resize if too large (OpenAI has 4MB limit)
            max_size = 1024
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # Save as PNG
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            return buffer.getvalue()

    def _resize_if_needed(self, image_path: Path) -> bytes:
        """Resize image if it exceeds max pixel count (for Replicate)."""
        with Image.open(image_path) as img:
            width, height = img.size
            pixels = width * height

            if pixels > MAX_PIXELS:
                ratio = (MAX_PIXELS / pixels) ** 0.5
                new_width = int(width * ratio)
                new_height = int(height * ratio)
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            buffer = BytesIO()
            img_format = 'PNG' if image_path.suffix.lower() == '.png' else 'JPEG'
            img.save(buffer, format=img_format)
            return buffer.getvalue()

    def enhance_with_openai(self, image_path: Path) -> bytes:
        """Enhance image using OpenAI's DALL-E 2 variation API."""
        # Read and prepare image
        image_data = self._prepare_image_for_openai(image_path)

        # Save to a temporary file with proper extension for OpenAI
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            tmp.write(image_data)
            tmp_path = tmp.name

        try:
            # Open file for OpenAI API - use create_variation for enhancement
            with open(tmp_path, 'rb') as img_file:
                response = self.client.images.create_variation(
                    model="dall-e-2",
                    image=img_file,
                    n=1,
                    size="1024x1024"
                )
        finally:
            # Clean up temp file
            import os
            os.unlink(tmp_path)

        # Get the result URL and download
        image_url = response.data[0].url
        if image_url:
            img_response = requests.get(image_url, timeout=60)
            img_response.raise_for_status()
            return img_response.content
        elif response.data[0].b64_json:
            return base64.b64decode(response.data[0].b64_json)
        else:
            raise ValueError("No image returned from OpenAI")

    def enhance_with_replicate(self, image_path: Path, scale: int = UPSCALE_FACTOR) -> bytes:
        """Enhance image using Replicate's Real-ESRGAN."""
        image_data = self._resize_if_needed(image_path)
        img_format = 'png' if image_path.suffix.lower() == '.png' else 'jpeg'

        for attempt in range(3):
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
                if '429' in str(e) and attempt < 2:
                    time.sleep(10)
                    continue
                raise

        if isinstance(output, str):
            response = requests.get(output, timeout=60)
            response.raise_for_status()
            return response.content
        elif hasattr(output, 'read'):
            return output.read()
        else:
            raise ValueError(f"Unexpected output type from Replicate: {type(output)}")

    def enhance(self, image_path: Path, scale: int = UPSCALE_FACTOR) -> bytes:
        """
        Enhance an image using the configured provider.

        Args:
            image_path: Path to the input image
            scale: Upscale factor (only used for Replicate)

        Returns:
            Enhanced image as bytes
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        if self.provider == "openai":
            return self.enhance_with_openai(image_path)
        else:
            return self.enhance_with_replicate(image_path, scale)

    def enhance_to_file(self, image_path: Path, output_path: Path, scale: int = UPSCALE_FACTOR) -> Path:
        """
        Enhance an image and save to a file.

        Args:
            image_path: Path to the input image
            output_path: Path to save the enhanced image
            scale: Upscale factor (only used for Replicate)

        Returns:
            Path to the enhanced image
        """
        enhanced_data = self.enhance(image_path, scale)
        output_path.write_bytes(enhanced_data)
        return output_path
