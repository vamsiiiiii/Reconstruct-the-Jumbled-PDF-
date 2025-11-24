# Technical Documentation

## What I Built

An AI-powered PDF page reordering system that automatically fixes shuffled document pages using Google Document AI (OCR) and Gemini AI (intelligent ordering). Supports both scanned and digital PDFs with dual CLI/API interfaces.

**Core Components:**
- `SimplePDFReorderer` - Main orchestration (OCR + AI ordering + PDF reconstruction)
- `SystemConfig` - Environment-based configuration management
- `main.py` - Dual interface (CLI for direct processing, FastAPI for web integration)
- `logging_config.py` - Structured JSON logging

## Why This Approach

**AI-Driven Ordering**: Legal documents have complex structures (schedules, cross-references, non-linear sections). Gemini AI understands context better than rule-based systems, reducing development complexity.

**Hybrid OCR Strategy**: Auto-detects scanned vs digital PDFs. Digital PDFs use fast PyPDF extraction; scanned PDFs use Document AI OCR. Optimizes for speed and cost.

**Batch Processing**: Automatically switches to GCS batch processing for PDFs >15 pages (Document AI sync limit). Handles unlimited pages with increased latency (90-140s).

**Low Temperature (0.1)**: Ensures deterministic, consistent ordering for legal documents. Reduces AI randomness.

**Full Content Analysis**: Sends complete page text to Gemini (no truncation). Legal documents need all details (dates, amounts, clause numbers) for accurate ordering.

**Retry Logic**: Up to 3 attempts with validation (correct page count, no duplicates, not original order). Improves reliability.

**Blank Page Handling**: Pages with <50 characters automatically moved to end. Common in scanned documents.

**FastAPI**: Modern async support, auto-generated docs (Swagger), better performance than Flask for I/O-bound operations.

## Assumptions

**Document Structure:**
- Optimized for legal/formal documents (loan agreements, contracts)
- English language (prompts are English-based)
- Pages have sufficient text for analysis

**Technical Requirements:**
- Active GCP project with Document AI API enabled
- Cloud Storage bucket for batch processing
- Service account with appropriate permissions
- Stable internet connection
- Python 3.12+ environment

## Limitations

1. **Processing Time**: 60-140 seconds per document (OCR + AI analysis + batch overhead)
2. **Cost**: ~$0.04-0.06 per 25-page scanned PDF (Document AI + Gemini API)
3. **Document Type**: Optimized for legal documents; may underperform on academic papers, books, informal docs
4. **Blank Page Detection**: Fixed 50-char threshold may misclassify sparse signature pages
5. **Text-Only Analysis**: No visual/layout understanding (logos, formatting, images)
6. **Single Document CLI**: Processes one PDF at a time (API mode supports concurrent requests)
7. **No Confidence Scoring**: Cannot flag uncertain orderings for manual review
8. **Memory Constraints**: Entire PDF loaded into memory (may struggle with >500 pages)

## Key Trade-offs

**Accuracy vs Speed**: Prioritized accuracy (full content, low temperature, retries) over speed. Result: 60-140s processing but high accuracy.

**Cost vs Simplicity**: Used managed services (Document AI, Gemini) instead of open-source (Tesseract, self-hosted LLMs). Higher per-document cost (~$0.05) but no infrastructure maintenance.

**Flexibility vs Optimization**: Generic approach handles various document types vs specialized systems per type. Single codebase but not perfectly optimized for each format.

**Validation Strictness**: Strict validation (all pages present, no duplicates) prevents data loss but may fail on edge cases where AI response is partially correct.

## Architecture

**Modular Design**: Separation of concerns (config, logging, business logic, entry points) enables independent testing and easy maintenance.

**Dependency Injection**: Config passed to SimplePDFReorderer constructor for testability and flexibility.

**Error Handling**: Structured results with `success`/`error` fields for consistent error checking.

**Logging**: Structured JSON logs at key decision points (INFO for major steps, DEBUG for details, WARNING for retries, ERROR for failures).

## What We'd Improve With More Time

**Confidence Scoring & Visual Analysis**: Add heuristic validation (sequential section numbers, cross-reference consistency) to flag uncertain orderings for manual review. Integrate vision models to analyze page layouts, logos, and formatting patterns for better ordering accuracy beyond text-only analysis.

---

**Version**: 1.0.0

