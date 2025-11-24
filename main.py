"""
PDF Page Reordering - CLI and API Server
"""

import sys
import os
import logging
import tempfile
from pathlib import Path
from src.config import load_config
from src.reorder import SimplePDFReorderer

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def cli_mode():
    """CLI mode for PDF reordering."""
    if len(sys.argv) < 2:
        print("Usage: python main.py <input_pdf> [output_pdf]")
        print("\nExample:")
        print("  python main.py input.pdf")
        print("  python main.py input.pdf output.pdf")
        print("\nOr run as API server:")
        print("  python main.py --api")
        sys.exit(1)
    
    input_pdf = sys.argv[1]
    
    if len(sys.argv) > 2:
        output_pdf = sys.argv[2]
    else:
        # Auto-generate output filename
        input_path = Path(input_pdf)
        output_pdf = str(input_path.parent / f"{input_path.stem}_reordered.pdf")
    
    print("="*80)
    print("PDF Page Reordering - Simple Direct Approach")
    print("="*80)
    print(f"Input:  {input_pdf}")
    print(f"Output: {output_pdf}")
    print()
    
    try:
        # Load configuration
        print("Loading configuration...")
        config = load_config()
        
        # Initialize reorderer
        print("Initializing PDF reorderer...")
        reorderer = SimplePDFReorderer(config)
        
        # Process PDF
        print("\nProcessing PDF...")
        print("-"*80)
        result = reorderer.reorder_pdf(input_pdf, output_pdf)
        print("-"*80)
        
        # Display results
        print("\n" + "="*80)
        if result['success']:
            print("✓ SUCCESS!")
            print("="*80)
            print(f"Pages processed: {result['page_count']}")
            print(f"Document type: {'Scanned (OCR used)' if result['is_scanned'] else 'Digital (direct text extraction)'}")
            print(f"Original order: {[i+1 for i in result['original_order']]}")
            print(f"New order:      {[i+1 for i in result['new_order']]}")
            print(f"Processing time: {result['processing_time']:.2f}s")
            print(f"\nOutput saved to: {output_pdf}")
        else:
            print("✗ FAILED!")
            print("="*80)
            print(f"Error: {result['error']}")
            sys.exit(1)
            
    except Exception as e:
        print(f"\n✗ Error: {e}")
        logger.error("Fatal error", exc_info=True)
        sys.exit(1)


def api_mode():
    """API server mode."""
    try:
        from fastapi import FastAPI, File, UploadFile, HTTPException
        from fastapi.responses import FileResponse
        from fastapi.middleware.cors import CORSMiddleware
        import uvicorn
    except ImportError:
        print("Error: FastAPI not installed. Install with:")
        print("  pip install fastapi uvicorn[standard] python-multipart")
        sys.exit(1)
    
    # Initialize FastAPI app
    app = FastAPI(
        title="PDF Page Reordering API",
        description="Automatically reorder shuffled PDF pages using AI",
        version="1.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Load configuration
    config = load_config()
    reorderer = SimplePDFReorderer(config)
    
    @app.get("/")
    async def root():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "PDF Page Reordering API",
            "version": "1.0.0"
        }
    
    @app.get("/health")
    async def health():
        """Detailed health check."""
        return {
            "status": "healthy",
            "config": {
                "gemini_model": config.gemini_model,
                "google_project": config.google_project_id,
                "google_location": config.google_location
            }
        }
    
    @app.post("/reorder")
    async def reorder_pdf(file: UploadFile = File(...)):
        """
        Reorder pages in a shuffled PDF.
        
        Args:
            file: PDF file to reorder
            
        Returns:
            Reordered PDF file
        """
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as input_temp:
            with tempfile.NamedTemporaryFile(delete=False, suffix='_reordered.pdf') as output_temp:
                try:
                    # Save uploaded file
                    content = await file.read()
                    input_temp.write(content)
                    input_temp.flush()
                    
                    input_path = input_temp.name
                    output_path = output_temp.name
                    
                    logger.info(f"Processing PDF: {file.filename}")
                    
                    # Process PDF
                    result = reorderer.reorder_pdf(input_path, output_path)
                    
                    if not result['success']:
                        raise HTTPException(status_code=500, detail=result['error'])
                    
                    logger.info(f"Successfully reordered PDF: {file.filename}")
                    
                    # Return the reordered PDF
                    return FileResponse(
                        output_path,
                        media_type='application/pdf',
                        filename=f"reordered_{file.filename}",
                        headers={
                            "X-Page-Count": str(result['page_count']),
                            "X-Processing-Time": str(result['processing_time']),
                            "X-Document-Type": "scanned" if result['is_scanned'] else "digital",
                            "X-Original-Order": str([i+1 for i in result['original_order']]),
                            "X-New-Order": str([i+1 for i in result['new_order']])
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing PDF: {e}", exc_info=True)
                    raise HTTPException(status_code=500, detail=str(e))
                
                finally:
                    # Cleanup input file only (output file will be cleaned up by FastAPI after sending)
                    try:
                        if os.path.exists(input_path):
                            os.unlink(input_path)
                    except Exception:
                        pass  # Silently ignore cleanup errors - files will be cleaned by OS temp cleanup
    

    # Run server
    print("="*80)
    print("PDF Page Reordering API Server")
    print("="*80)
    print("Starting server at http://0.0.0.0:8000")
    print("API Documentation: http://localhost:8000/docs")
    print("="*80)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    # Check if API mode is requested
    if len(sys.argv) > 1 and sys.argv[1] == "--api":
        api_mode()
    else:
        cli_mode()
