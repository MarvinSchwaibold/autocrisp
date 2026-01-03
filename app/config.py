import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "output"

# Ensure directories exist
TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Replicate API
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")

# Image processing settings
MAX_IMAGE_SIZE_MB = int(os.getenv("MAX_IMAGE_SIZE_MB", "10"))
OUTPUT_FORMAT = os.getenv("OUTPUT_FORMAT", "webp")
OUTPUT_QUALITY = int(os.getenv("OUTPUT_QUALITY", "85"))
UPSCALE_FACTOR = int(os.getenv("UPSCALE_FACTOR", "2"))

# Real-ESRGAN model on Replicate
ESRGAN_MODEL = "nightmareai/real-esrgan:f121d640bd286e1fdc67f9799164c1d5be36ff74576ee11c803ae5b665dd46aa"
