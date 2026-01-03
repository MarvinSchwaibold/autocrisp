from pathlib import Path
from typing import Optional, List, Dict

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from app.scraper import WebScraper
from app.processor import ImageEnhancer, ImageOptimizer
from app.config import TEMP_DIR, OUTPUT_DIR

router = APIRouter()

# In-memory storage for POC (would use a database in production)
scan_results: Dict[str, List[dict]] = {}
job_status: Dict[str, dict] = {}


class ScanRequest(BaseModel):
    url: HttpUrl


class ScanResponse(BaseModel):
    scan_id: str
    url: str
    image_count: int
    images: List[dict]


class EnhanceRequest(BaseModel):
    image_id: str
    scale: int = 2


class EnhanceBatchRequest(BaseModel):
    scan_id: str
    scale: int = 2


class EnhanceResponse(BaseModel):
    image_id: str
    status: str
    output_path: Optional[str] = None
    original_size: Optional[int] = None
    enhanced_size: Optional[int] = None


@router.post("/scan", response_model=ScanResponse)
async def scan_url(request: ScanRequest):
    """Scan a URL for images."""
    url = str(request.url)

    try:
        scraper = WebScraper(url)
        images = scraper.scan()

        # Download all images
        downloaded = scraper.download_all()

        # Generate scan ID
        scan_id = f"scan_{hash(url) % 100000:05d}"

        # Store results
        scan_results[scan_id] = [
            {
                "id": img.id,
                "original_url": img.original_url,
                "local_path": str(img.local_path) if img.local_path else None,
                "width": img.width,
                "height": img.height,
                "file_size": img.file_size,
                "alt_text": img.alt_text,
                "source_element": img.source_element
            }
            for img in downloaded
        ]

        return ScanResponse(
            scan_id=scan_id,
            url=url,
            image_count=len(downloaded),
            images=scan_results[scan_id]
        )

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/scan/{scan_id}")
async def get_scan_results(scan_id: str):
    """Get results of a previous scan."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    return {"scan_id": scan_id, "images": scan_results[scan_id]}


def process_enhancement(job_id: str, image_path: Path, image_id: str, scale: int):
    """Background task to enhance a single image."""
    try:
        job_status[job_id] = {"status": "processing", "image_id": image_id}

        # Enhance with Real-ESRGAN
        enhancer = ImageEnhancer()
        enhanced_data = enhancer.enhance(image_path, scale=scale)

        # Optimize the enhanced image
        optimizer = ImageOptimizer()
        result = optimizer.optimize_bytes(enhanced_data, f"enhanced_{image_id}")

        job_status[job_id] = {
            "status": "completed",
            "image_id": image_id,
            "output_path": str(result.output_path),
            "original_size": result.original_size,
            "optimized_size": result.optimized_size,
            "size_reduction": f"{result.size_reduction_percent:.1f}%"
        }

    except Exception as e:
        job_status[job_id] = {
            "status": "failed",
            "image_id": image_id,
            "error": str(e)
        }


@router.post("/enhance", response_model=EnhanceResponse)
async def enhance_image(request: EnhanceRequest, background_tasks: BackgroundTasks):
    """Enhance a single image by ID."""
    image_id = request.image_id

    # Find the image in scan results
    image_data = None
    for scan_images in scan_results.values():
        for img in scan_images:
            if img["id"] == image_id:
                image_data = img
                break
        if image_data:
            break

    if not image_data or not image_data.get("local_path"):
        raise HTTPException(status_code=404, detail="Image not found or not downloaded")

    job_id = f"job_{image_id}"
    image_path = Path(image_data["local_path"])

    # Start background processing
    background_tasks.add_task(process_enhancement, job_id, image_path, image_id, request.scale)

    return EnhanceResponse(
        image_id=image_id,
        status="processing"
    )


@router.post("/enhance-batch")
async def enhance_batch(request: EnhanceBatchRequest, background_tasks: BackgroundTasks):
    """Enhance all images from a scan."""
    if request.scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")

    images = scan_results[request.scan_id]
    jobs = []

    for img in images:
        if img.get("local_path"):
            job_id = f"job_{img['id']}"
            image_path = Path(img["local_path"])
            background_tasks.add_task(
                process_enhancement, job_id, image_path, img["id"], request.scale
            )
            jobs.append({"job_id": job_id, "image_id": img["id"]})

    return {
        "scan_id": request.scan_id,
        "jobs_started": len(jobs),
        "jobs": jobs
    }


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Check the status of an enhancement job."""
    if job_id not in job_status:
        return {"job_id": job_id, "status": "pending"}

    return {"job_id": job_id, **job_status[job_id]}


@router.get("/results")
async def get_results():
    """List all enhanced images."""
    output_files = list(OUTPUT_DIR.glob("enhanced_*.*"))

    results = []
    for f in output_files:
        results.append({
            "filename": f.name,
            "path": str(f),
            "size": f.stat().st_size
        })

    return {"count": len(results), "files": results}


@router.get("/enhanced/{image_id}")
async def get_enhanced_image(image_id: str):
    """Serve an enhanced image by ID."""
    # Look for the enhanced image in output directory
    for ext in ['.png', '.webp', '.jpg', '.jpeg']:
        image_path = OUTPUT_DIR / f"enhanced_{image_id}{ext}"
        if image_path.exists():
            return FileResponse(
                path=str(image_path),
                media_type=f"image/{ext[1:]}",
                filename=f"enhanced_{image_id}{ext}"
            )

    raise HTTPException(status_code=404, detail="Enhanced image not found")


@router.delete("/clear")
async def clear_data():
    """Clear all temporary and output files."""
    import shutil

    # Clear temp directory
    for f in TEMP_DIR.glob("*"):
        if f.is_file():
            f.unlink()

    # Clear output directory
    for f in OUTPUT_DIR.glob("*"):
        if f.is_file():
            f.unlink()

    # Clear in-memory data
    scan_results.clear()
    job_status.clear()

    return {"status": "cleared"}
