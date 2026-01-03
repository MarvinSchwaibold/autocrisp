# Image Enhancer POC

AI-powered image enhancement service that scrapes images from websites and upscales them using Real-ESRGAN.

## Features

- Web scraping to discover images from any URL
- AI upscaling using Real-ESRGAN (via Replicate API)
- WebP optimization with configurable quality
- REST API for integration

## Setup

1. Clone the repository:
```bash
git clone https://github.com/MarvinSchwaibold/image-enhancer-poc.git
cd image-enhancer-poc
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your Replicate API token
```

5. Run the server:
```bash
uvicorn app.main:app --reload
```

6. Open http://localhost:8000/docs for API documentation

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/scan` | Scan a URL for images |
| GET | `/api/scan/{scan_id}` | Get scan results |
| POST | `/api/enhance` | Enhance a single image |
| POST | `/api/enhance-batch` | Enhance all images from a scan |
| GET | `/api/status/{job_id}` | Check enhancement job status |
| GET | `/api/results` | List all enhanced images |
| DELETE | `/api/clear` | Clear temp and output files |

## Example Usage

```bash
# Scan a website for images
curl -X POST "http://localhost:8000/api/scan" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}'

# Enhance a specific image
curl -X POST "http://localhost:8000/api/enhance" \
  -H "Content-Type: application/json" \
  -d '{"image_id": "abc123", "scale": 2}'
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REPLICATE_API_TOKEN` | - | Your Replicate API token (required) |
| `OUTPUT_FORMAT` | webp | Output format (webp, jpg, png) |
| `OUTPUT_QUALITY` | 85 | Compression quality (1-100) |
| `UPSCALE_FACTOR` | 2 | Upscale factor (2 or 4) |

## License

MIT
