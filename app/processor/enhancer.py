import base64
from pathlib import Path
from typing import Optional

import replicate
import requests

from app.config import REPLICATE_API_TOKEN, ESRGAN_MODEL, UPSCALE_FACTOR


class ImageEnhancer:
    """Enhances images using Replicate's Real-ESRGAN model."""

    def __init__(self):
        if not REPLICATE_API_TOKEN:
            raise ValueError("REPLICATE_API_TOKEN is not set. Please add it to your .env file.")
        self.client = replicate.Client(api_token=REPLICATE_API_TOKEN)

    def enhance(self, image_path: Path, scale: int = UPSCALE_FACTOR) -> bytes:
        """
        Enhance an image using Real-ESRGAN.

        Args:
            image_path: Path to the input image
            scale: Upscale factor (2 or 4)

        Returns:
            Enhanced image as bytes
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Read and encode image
        with open(image_path, "rb") as f:
            image_data = f.read()

        # Run the model
        output = self.client.run(
            ESRGAN_MODEL,
            input={
                "image": f"data:image/png;base64,{base64.b64encode(image_data).decode()}",
                "scale": scale,
                "face_enhance": False
            }
        )

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
