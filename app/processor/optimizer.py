from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image

from app.config import OUTPUT_DIR, OUTPUT_FORMAT, OUTPUT_QUALITY


@dataclass
class OptimizationResult:
    """Result of image optimization."""
    input_path: Path
    output_path: Path
    original_size: int
    optimized_size: int
    original_dimensions: Tuple[int, int]
    optimized_dimensions: Tuple[int, int]

    @property
    def size_reduction_percent(self) -> float:
        """Calculate percentage of size reduction."""
        if self.original_size == 0:
            return 0
        return (1 - self.optimized_size / self.original_size) * 100


class ImageOptimizer:
    """Optimizes images for web delivery."""

    def __init__(
        self,
        output_format: str = OUTPUT_FORMAT,
        quality: int = OUTPUT_QUALITY,
        max_dimension: Optional[int] = None
    ):
        self.output_format = output_format.lower()
        self.quality = quality
        self.max_dimension = max_dimension

    def optimize(self, image_path: Path, output_name: Optional[str] = None) -> OptimizationResult:
        """
        Optimize an image for web delivery.

        Args:
            image_path: Path to the input image
            output_name: Optional custom output filename (without extension)

        Returns:
            OptimizationResult with before/after stats
        """
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        original_size = image_path.stat().st_size

        with Image.open(image_path) as img:
            original_dimensions = img.size

            # Convert to RGB if necessary (for formats that don't support alpha)
            if self.output_format in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            elif self.output_format == "webp" and img.mode == "P":
                img = img.convert("RGBA")

            # Resize if max dimension is set
            if self.max_dimension:
                img.thumbnail((self.max_dimension, self.max_dimension), Image.Resampling.LANCZOS)

            optimized_dimensions = img.size

            # Determine output path
            name = output_name or image_path.stem
            ext = "jpg" if self.output_format == "jpeg" else self.output_format
            output_path = OUTPUT_DIR / f"{name}.{ext}"

            # Save with optimization
            save_kwargs = {"quality": self.quality, "optimize": True}

            if self.output_format == "webp":
                save_kwargs["method"] = 6  # Best compression
            elif self.output_format in ("jpg", "jpeg"):
                save_kwargs["progressive"] = True

            img.save(output_path, **save_kwargs)

        optimized_size = output_path.stat().st_size

        return OptimizationResult(
            input_path=image_path,
            output_path=output_path,
            original_size=original_size,
            optimized_size=optimized_size,
            original_dimensions=original_dimensions,
            optimized_dimensions=optimized_dimensions
        )

    def optimize_bytes(self, image_data: bytes, output_name: str) -> OptimizationResult:
        """
        Optimize image from bytes.

        Args:
            image_data: Raw image bytes
            output_name: Output filename (without extension)

        Returns:
            OptimizationResult with before/after stats
        """
        from io import BytesIO

        original_size = len(image_data)

        with Image.open(BytesIO(image_data)) as img:
            original_dimensions = img.size

            # Convert to RGB if necessary
            if self.output_format in ("jpg", "jpeg") and img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            elif self.output_format == "webp" and img.mode == "P":
                img = img.convert("RGBA")

            # Resize if max dimension is set
            if self.max_dimension:
                img.thumbnail((self.max_dimension, self.max_dimension), Image.Resampling.LANCZOS)

            optimized_dimensions = img.size

            # Determine output path
            ext = "jpg" if self.output_format == "jpeg" else self.output_format
            output_path = OUTPUT_DIR / f"{output_name}.{ext}"

            # Save with optimization
            save_kwargs = {"quality": self.quality, "optimize": True}

            if self.output_format == "webp":
                save_kwargs["method"] = 6
            elif self.output_format in ("jpg", "jpeg"):
                save_kwargs["progressive"] = True

            img.save(output_path, **save_kwargs)

        optimized_size = output_path.stat().st_size

        return OptimizationResult(
            input_path=output_path,  # No original path for bytes input
            output_path=output_path,
            original_size=original_size,
            optimized_size=optimized_size,
            original_dimensions=original_dimensions,
            optimized_dimensions=optimized_dimensions
        )
