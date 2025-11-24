# PDF Page Reordering System

Automatically reorder shuffled PDF pages using Google Document AI OCR and Gemini AI analysis.

## Tech Stack

- **Python 3.12+**
- **Google Document AI** - OCR for scanned PDFs
- **Google Cloud Storage** - Batch processing for large PDFs
- **Gemini 2.5 Flash** - AI-powered page ordering
- **PyPDF** - PDF manipulation

## How It Works

1. **Detect PDF Type** - Identifies if PDF is scanned (image-based) or digital (text-based)
2. **Extract Text** - Uses Document AI OCR for scanned PDFs, direct extraction for digital PDFs
3. **Batch Processing** - Automatically uses batch processing for PDFs > 15 pages
4. **AI Analysis** - Sends full page content to Gemini AI in JSON format
5. **Smart Ordering** - Gemini analyzes document structure and determines correct page order
6. **Blank Page Handling** - Automatically detects and moves blank pages to the end
7. **PDF Reconstruction** - Creates new PDF with pages in correct order

## Prerequisites

1. **Google Cloud Project** with:
   - Document AI API enabled
   - Cloud Storage bucket created
   - Service account with permissions

2. **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Or using uv (recommended)
uv sync
```

## Configuration

Create a `.env` file:

```env
# Google Cloud
GOOGLE_PROJECT_ID=your-project-id
GOOGLE_LOCATION=us
DOCUMENT_AI_PROCESSOR_ID=your-processor-id
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# Gemini AI
GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=models/gemini-2.5-flash

# Cloud Storage
BUCKET_NAME=your-bucket-name
```

## Usage

### CLI Mode

```bash
# Basic usage
python main.py input.pdf output.pdf

# Using uv
uv run main.py input.pdf output.pdf
```

### API Server Mode

```bash
# Start the FastAPI server
python main.py --api

# Or using venv directly
.venv\Scripts\python.exe main.py --api
```

**API Endpoints:**

- `GET /` - Health check
- `GET /health` - Detailed health status
- `POST /reorder` - Upload PDF and get reordered PDF back

**Example API Usage:**

```bash
# Using curl
curl -X POST "http://localhost:8000/reorder" \
  -F "file=@input.pdf" \
  --output reordered.pdf
```

**Python Client Example:**

```python
import requests

# Upload and reorder PDF
with open('input.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/reorder',
        files={'file': f}
    )
    
with open('output.pdf', 'wb') as f:
    f.write(response.content)
```

## Features

✅ **Automatic OCR** - Handles scanned documents seamlessly  
✅ **Batch Processing** - Processes large PDFs (25+ pages) efficiently  
✅ **AI-Powered** - Uses Gemini AI for intelligent page ordering  
✅ **Full Content Analysis** - No truncation, complete page content sent to AI  
✅ **Blank Page Detection** - Automatically moves blank pages to end  
✅ **Legal Document Optimized** - Specialized for loan agreements and contracts  
✅ **Deterministic Results** - Low temperature (0.1) for consistent ordering  
✅ **Retry Logic** - Up to 3 attempts for reliability

## Project Structure

```
pdf-reorder/
├── src/
│   ├── config.py          # Configuration & SystemConfig
│   ├── logging_config.py  # Logging setup
│   └── reorder.py         # Core reordering logic
├── main.py                # CLI entry point
├── .env                   # Configuration (create this)
├── requirements.txt       # Dependencies
└── README.md             # This file
```

## Performance

- **Small PDFs (≤15 pages)**: ~60-90 seconds
- **Large PDFs (25 pages)**: ~90-140 seconds
- Processing time includes OCR, AI analysis, and PDF reconstruction

## Deployment

### Local Development

```bash
# Run API server
python api.py
# Server will be available at http://localhost:8000
# API docs at http://localhost:8000/docs
```

## API Documentation

Once the server is running, visit:
- **Swagger UI**: http://localhost:8000/docs

## License

MIT
