"""
FastAPI Application for PDF to Vault Markdown Converter
High-performance API optimized for M3 Pro with ProcessPoolExecutor.
"""

import os
import sys
import uuid
import asyncio
import zipfile
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from concurrent.futures import ProcessPoolExecutor
from urllib.parse import unquote

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from loguru import logger

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pdf_to_markdown import PDFToMarkdownConverter
from markdown_cleanup import MarkdownCleanup

# Initialize FastAPI app
app = FastAPI(
    title="PDF to Vault Markdown Converter",
    description="High-performance PDF conversion API optimized for large files",
    version="2.0.0"
)

# CORS middleware for web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
BASE_DIR = Path(__file__).parent.parent
UPLOAD_FOLDER = BASE_DIR / 'uploads'
OUTPUT_FOLDER = BASE_DIR / 'outputs'
LOG_FOLDER = BASE_DIR / 'logs'
STATIC_FOLDER = BASE_DIR / 'static'
API_PORT = 9234  # Uncommon port to avoid conflicts
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max file size
ALLOWED_EXTENSIONS = {'pdf'}
FILE_CLEANUP_HOURS = 1

# Create necessary directories
for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER, LOG_FOLDER, STATIC_FOLDER]:
    folder.mkdir(parents=True, exist_ok=True)

# Configure logging
log_file = LOG_FOLDER / 'app.log'
logger.add(
    log_file,
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Optimize for M3 Pro: Use 4-6 performance cores for the pool
# This prevents heavy conversions from blocking the web server
executor = ProcessPoolExecutor(max_workers=4)
logger.info("Initialized ProcessPoolExecutor with 4 workers for M3 Pro optimization")


# Pydantic models
class ConversionResponse(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
    original_filename: Optional[str] = None
    output_size: Optional[int] = None
    source_type: Optional[str] = None
    processing_time: Optional[float] = None


class BatchConversionItem(BaseModel):
    success: bool
    message: str
    download_url: Optional[str] = None
    filename: Optional[str] = None
    original_filename: str
    output_size: Optional[int] = None
    processing_time: Optional[float] = None
    error: Optional[str] = None


class BatchConversionResponse(BaseModel):
    status: str
    total_files: int
    successful: int
    failed: int
    conversions: List[BatchConversionItem]
    total_processing_time: float
    zip_download_url: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    upload_folder: str
    output_folder: str
    executor_workers: int


# Helper functions
def allowed_file(filename: str) -> bool:
    """Check if file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename using UUID to prevent collisions."""
    unique_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    name, ext = os.path.splitext(original_filename)
    # Sanitize filename - replace spaces with underscores
    name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in name).strip('_')
    return f"{unique_id}_{timestamp}_{name}{ext}"


def convert_pdf_worker(pdf_path: str, output_path: str, source_type: str) -> Dict[str, Any]:
    """
    Worker function for PDF conversion - runs in separate process.
    
    Args:
        pdf_path: Path to PDF file
        output_path: Path for output markdown file
        source_type: Type of PDF source
        
    Returns:
        Dictionary with conversion results
    """
    try:
        start_time = datetime.now()
        
        # Initialize converter
        converter = PDFToMarkdownConverter(
            source_type=source_type,
            preserve_images=True,
            add_frontmatter=True,
            verbose=False
        )
        
        # Convert PDF to Markdown
        success, message = converter.convert_file(Path(pdf_path), Path(output_path))
        
        if not success:
            return {
                'success': False,
                'message': message,
                'processing_time': (datetime.now() - start_time).total_seconds()
            }
        
        # Run cleanup on the output
        cleanup = MarkdownCleanup(
            remove_duplicate_lines=True,
            standardize_headings=True,
            fix_lists=True,
            normalize_spacing=True,
            add_metadata=True,
            verbose=False
        )
        
        cleanup.cleanup_file(Path(output_path))
        
        # Get output file size
        output_size = Path(output_path).stat().st_size
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return {
            'success': True,
            'message': 'Conversion completed successfully',
            'output_size': output_size,
            'processing_time': processing_time
        }
        
    except Exception as e:
        return {
            'success': False,
            'message': f"Error during conversion: {str(e)}",
            'processing_time': (datetime.now() - start_time).total_seconds()
        }


async def run_in_pool(func, *args):
    """Run a function in the process pool asynchronously."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, func, *args)


async def cleanup_old_files():
    """Background task to clean up old files."""
    while True:
        try:
            cutoff_time = datetime.now() - timedelta(hours=FILE_CLEANUP_HOURS)
            
            # Clean uploads
            for file_path in UPLOAD_FOLDER.glob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        logger.info(f"Cleaned up old upload: {file_path.name}")
            
            # Clean outputs
            for file_path in OUTPUT_FOLDER.glob('*'):
                if file_path.is_file():
                    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_time < cutoff_time:
                        file_path.unlink()
                        logger.info(f"Cleaned up old output: {file_path.name}")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        # Sleep for 30 minutes before next cleanup
        await asyncio.sleep(1800)


# API Routes
@app.on_event("startup")
async def startup_event():
    """Initialize background tasks on startup."""
    asyncio.create_task(cleanup_old_files())
    logger.info("Started background cleanup task")
    logger.info(f"API server starting on port {API_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    executor.shutdown(wait=True)
    logger.info("Executor shutdown complete")


@app.get("/")
async def root():
    """Serve the main HTML interface."""
    html_file = STATIC_FOLDER / 'index.html'
    if html_file.exists():
        return FileResponse(html_file)
    return {
        "message": "PDF to Vault Markdown Converter API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.post("/convert", response_model=ConversionResponse)
async def convert_pdf(
    file: UploadFile = File(...),
    source_type: str = "auto"
):
    """
    Convert PDF to Markdown.
    
    Args:
        file: PDF file to convert
        source_type: Type of PDF source ('auto', 'ppt', 'word')
        
    Returns:
        Conversion response with download URL
    """
    start_time = datetime.now()
    
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file selected")
        
        if not allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF files are allowed."
            )
        
        # Validate source type
        if source_type not in ['auto', 'ppt', 'word']:
            source_type = 'auto'
        
        logger.info(f"Received upload: {file.filename} (source_type: {source_type})")
        
        # Generate unique filename and save
        unique_filename = generate_unique_filename(file.filename)
        upload_path = UPLOAD_FOLDER / unique_filename
        
        # Save uploaded file
        content = await file.read()
        
        # Check file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB."
            )
        
        with open(upload_path, 'wb') as f:
            f.write(content)
        
        file_size_mb = len(content) / (1024 * 1024)
        logger.info(f"Saved upload to: {upload_path} ({file_size_mb:.2f} MB)")
        
        # Generate output path
        output_filename = upload_path.stem + '.md'
        output_path = OUTPUT_FOLDER / output_filename
        
        # Run conversion in process pool to avoid blocking
        logger.info("Starting conversion in process pool...")
        result = await run_in_pool(
            convert_pdf_worker,
            str(upload_path),
            str(output_path),
            source_type
        )
        
        if not result['success']:
            # Clean up uploaded file
            if upload_path.exists():
                upload_path.unlink()
            
            raise HTTPException(status_code=500, detail=result['message'])
        
        # Verify output file exists (race condition protection)
        max_retries = 3
        for i in range(max_retries):
            if output_path.exists():
                break
            logger.warning(f"Output file not found, retry {i+1}/{max_retries}")
            await asyncio.sleep(0.5)
        
        if not output_path.exists():
            logger.error(f"Output file not created: {output_path}")
            raise HTTPException(
                status_code=500,
                detail="Conversion completed but output file not found. Check logs."
            )
        
        total_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Conversion complete in {total_time:.2f}s. Output: {output_filename}")
        logger.info(f"Output file verified at: {output_path}")
        
        return ConversionResponse(
            success=True,
            message="File converted successfully",
            download_url=f"/download/{output_filename}",
            filename=output_filename,
            original_filename=file.filename,
            output_size=result['output_size'],
            source_type=source_type,
            processing_time=total_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred during processing: {str(e)}"
        )


@app.post("/convert/batch", response_model=BatchConversionResponse)
async def convert_multiple_pdfs(
    files: List[UploadFile] = File(...),
    source_type: str = "auto"
):
    """
    Convert multiple PDF files to Markdown in parallel.
    
    Args:
        files: List of PDF files to convert
        source_type: Type of PDF source ('auto', 'ppt', 'word')
        
    Returns:
        Batch conversion response with individual results and zip download
    """
    batch_start_time = datetime.now()
    
    try:
        # Validate source type
        if source_type not in ['auto', 'ppt', 'word']:
            source_type = 'auto'
        
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        
        if len(files) > 10:
            raise HTTPException(
                status_code=400,
                detail="Maximum 10 files allowed per batch"
            )
        
        logger.info(f"Batch conversion started: {len(files)} files (source_type: {source_type})")
        
        # Process all files
        tasks = []
        file_info = []
        
        for file in files:
            # Validate file
            if not file.filename:
                file_info.append({
                    'original_filename': 'unknown',
                    'error': 'No filename provided'
                })
                continue
            
            if not allowed_file(file.filename):
                file_info.append({
                    'original_filename': file.filename,
                    'error': 'Invalid file type. Only PDF files are allowed.'
                })
                continue
            
            # Generate unique filename and save
            unique_filename = generate_unique_filename(file.filename)
            upload_path = UPLOAD_FOLDER / unique_filename
            
            # Save uploaded file
            content = await file.read()
            
            # Check file size
            if len(content) > MAX_FILE_SIZE:
                file_info.append({
                    'original_filename': file.filename,
                    'error': f'File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB.'
                })
                continue
            
            with open(upload_path, 'wb') as f:
                f.write(content)
            
            file_size_mb = len(content) / (1024 * 1024)
            logger.info(f"Saved: {file.filename} -> {upload_path} ({file_size_mb:.2f} MB)")
            
            # Generate output path
            output_filename = upload_path.stem + '.md'
            output_path = OUTPUT_FOLDER / output_filename
            
            # Store file info for processing
            file_info.append({
                'original_filename': file.filename,
                'upload_path': str(upload_path),
                'output_path': str(output_path),
                'output_filename': output_filename
            })
            
            # Create conversion task
            task = run_in_pool(
                convert_pdf_worker,
                str(upload_path),
                str(output_path),
                source_type
            )
            tasks.append(task)
        
        # Wait for all conversions to complete in parallel
        logger.info(f"Processing {len(tasks)} files in parallel...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Compile results
        conversions = []
        successful_files = []
        successful = 0
        failed = 0
        
        for i, result in enumerate(results):
            info = file_info[i]
            
            # Handle errors from file_info (validation errors)
            if 'error' in info:
                conversions.append(BatchConversionItem(
                    success=False,
                    message="Validation failed",
                    original_filename=info['original_filename'],
                    error=info['error']
                ))
                failed += 1
                continue
            
            # Handle exceptions from conversion
            if isinstance(result, Exception):
                conversions.append(BatchConversionItem(
                    success=False,
                    message="Conversion failed",
                    original_filename=info['original_filename'],
                    error=str(result)
                ))
                failed += 1
                continue
            
            # Handle conversion results
            if result['success']:
                # Verify output file exists (race condition protection)
                output_path = Path(info['output_path'])
                max_retries = 3
                for retry in range(max_retries):
                    if output_path.exists():
                        break
                    logger.warning(f"Output file not found, retry {retry+1}/{max_retries}")
                    await asyncio.sleep(0.5)
                
                if output_path.exists():
                    conversions.append(BatchConversionItem(
                        success=True,
                        message="Conversion successful",
                        download_url=f"/download/{info['output_filename']}",
                        filename=info['output_filename'],
                        original_filename=info['original_filename'],
                        output_size=result.get('output_size'),
                        processing_time=result.get('processing_time')
                    ))
                    successful_files.append(info['output_filename'])
                    successful += 1
                else:
                    conversions.append(BatchConversionItem(
                        success=False,
                        message="Output file not created",
                        original_filename=info['original_filename'],
                        error="Conversion completed but output file not found"
                    ))
                    failed += 1
            else:
                conversions.append(BatchConversionItem(
                    success=False,
                    message="Conversion failed",
                    original_filename=info['original_filename'],
                    error=result.get('message', 'Unknown error')
                ))
                failed += 1
        
        total_time = (datetime.now() - batch_start_time).total_seconds()
        
        # Create zip file if there are successful conversions
        zip_url = None
        if successful_files:
            zip_filename = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            zip_path = OUTPUT_FOLDER / zip_filename
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for filename in successful_files:
                    file_path = OUTPUT_FOLDER / filename
                    if file_path.exists():
                        zipf.write(file_path, filename)
            
            zip_url = f"/download/{zip_filename}"
            logger.info(f"Created zip archive: {zip_filename}")
        
        logger.info(f"Batch conversion complete: {successful} successful, {failed} failed in {total_time:.2f}s")
        
        return BatchConversionResponse(
            status="success",
            total_files=len(files),
            successful=successful,
            failed=failed,
            conversions=conversions,
            total_processing_time=total_time,
            zip_download_url=zip_url
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch conversion error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch conversion failed: {str(e)}"
        )


@app.post("/download/batch")
async def download_batch_zip(filenames: List[str]):
    """
    Create and download a ZIP file containing multiple converted Markdown files.
    
    This endpoint accepts a list of filenames and creates a ZIP archive on-the-fly.
    Useful for downloading selected files from the staging queue.
    
    Args:
        filenames: List of output filenames to include in the ZIP
        
    Returns:
        StreamingResponse with application/zip content
        
    Raises:
        HTTPException: If no valid files found or ZIP creation fails
    """
    try:
        if not filenames:
            raise HTTPException(status_code=400, detail="No filenames provided")
        
        logger.info(f"Batch ZIP download requested for {len(filenames)} files")
        
        # Validate and collect existing files
        valid_files = []
        missing_files = []
        
        for filename in filenames:
            # Sanitize filename
            safe_filename = "".join(c if c.isalnum() or c in ('.', '-', '_') else '_' for c in filename).strip('_')
            file_path = OUTPUT_FOLDER / safe_filename
            
            if file_path.exists():
                valid_files.append((safe_filename, file_path))
            else:
                missing_files.append(safe_filename)
                logger.warning(f"File not found for ZIP: {safe_filename}")
        
        if not valid_files:
            raise HTTPException(
                status_code=404,
                detail=f"No valid files found. Missing: {', '.join(missing_files)}"
            )
        
        # Create ZIP in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filename, file_path in valid_files:
                zipf.write(file_path, filename)
        
        zip_buffer.seek(0)
        
        # Generate ZIP filename with timestamp
        zip_filename = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        
        logger.info(f"Created ZIP with {len(valid_files)} files: {zip_filename}")
        
        if missing_files:
            logger.warning(f"ZIP created with {len(missing_files)} missing files: {', '.join(missing_files)}")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={zip_filename}",
                "X-Files-Included": str(len(valid_files)),
                "X-Files-Missing": str(len(missing_files))
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"ZIP creation error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create ZIP file: {str(e)}"
        )


@app.get("/download/{filename}")
async def download_file(filename: str):
    """
    Download converted Markdown file.
    
    Args:
        filename: Name of the file to download (may be URL-encoded)
        
    Returns:
        File download response
    """
    try:
        # URL decode the filename first (handles %20 for spaces, etc.)
        decoded_filename = unquote(filename)
        
        # Sanitize filename - replace spaces with underscores to match generation
        safe_filename = "".join(c if c.isalnum() or c in ('.', '-', '_') else '_' for c in decoded_filename).strip('_')
        file_path = OUTPUT_FOLDER / safe_filename
        
        # Debug logging
        logger.info(f"Download request - Original: {filename}, Decoded: {decoded_filename}, Safe: {safe_filename}")
        logger.info(f"Looking for file at: {file_path}")
        logger.info(f"File exists: {file_path.exists()}")
        
        if not file_path.exists():
            # List available files for debugging
            available_files = list(OUTPUT_FOLDER.glob('*.md'))
            logger.error(f"File not found. Available files: {[f.name for f in available_files]}")
            raise HTTPException(
                status_code=404,
                detail=f"File not found: {safe_filename}. Check logs for available files."
            )
        
        logger.info(f"Serving download: {safe_filename}")
        
        return FileResponse(
            path=file_path,
            filename=safe_filename,
            media_type='text/markdown'
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error downloading file: {str(e)}")


@app.get("/")
async def root():
    """Redirect root to web interface."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/index.html")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint for monitoring."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        upload_folder=str(UPLOAD_FOLDER),
        output_folder=str(OUTPUT_FOLDER),
        executor_workers=executor._max_workers
    )


# Mount static files for frontend
if STATIC_FOLDER.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_FOLDER)), name="static")


if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting PDF to Markdown Converter API")
    logger.info(f"Upload folder: {UPLOAD_FOLDER}")
    logger.info(f"Output folder: {OUTPUT_FOLDER}")
    logger.info(f"Log folder: {LOG_FOLDER}")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=API_PORT,
        reload=False,
        workers=1  # Single worker, parallelism handled by ProcessPoolExecutor
    )


# Made with Bob