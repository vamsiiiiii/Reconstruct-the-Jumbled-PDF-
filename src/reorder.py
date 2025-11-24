"""
Simple PDF Reordering using LangChain and Gemini.

Straightforward workflow:
1. Check if PDF is scanned or digital
2. Extract text (OCR if scanned, direct extraction if digital)
3. Send all page texts to Gemini with detailed prompt
4. Gemini returns the correct page order
5. Reconstruct PDF with correct order
"""

import os
from typing import List, Tuple
from pypdf import PdfReader, PdfWriter
from google.cloud import documentai_v1 as documentai
import google.generativeai as genai
import logging

logger = logging.getLogger(__name__)


class SimplePDFReorderer:
    """Simple PDF reorderer using direct Gemini analysis."""
    
    def __init__(self, config):
        """Initialize with configuration."""
        self.config = config
        
        # Initialize Gemini
        genai.configure(api_key=config.gemini_api_key)
        self.model = genai.GenerativeModel(config.gemini_model)
        
        # Initialize Document AI for OCR
        self.docai_client = documentai.DocumentProcessorServiceClient()
        self.processor_name = self.docai_client.processor_path(
            config.google_project_id,
            config.google_location,
            config.document_ai_processor_id
        )
        
        logger.info("SimplePDFReorderer initialized")
    
    def is_scanned(self, pdf_path: str) -> bool:
        """
        Determine if PDF is scanned (image-based) or digital (text-based).
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            True if scanned, False if digital
        """
        reader = PdfReader(pdf_path)
        
        # Check first few pages for text content
        pages_to_check = min(3, len(reader.pages))
        text_found = False
        
        for i in range(pages_to_check):
            text = reader.pages[i].extract_text().strip()
            if len(text) > 100:  # If we find substantial text, it's digital
                text_found = True
                break
        
        is_scanned = not text_found
        logger.info(f"PDF is {'scanned (image-based)' if is_scanned else 'digital (text-based)'}")
        return is_scanned
    
    def extract_text_digital(self, pdf_path: str) -> List[Tuple[int, str]]:
        """
        Extract text from digital PDF directly.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of (page_number, text) tuples
        """
        logger.info("Extracting text from digital PDF")
        reader = PdfReader(pdf_path)
        pages = []
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            pages.append((i, text))
            logger.debug(f"Extracted {len(text)} characters from page {i}")
        
        logger.info(f"Extracted text from {len(pages)} pages")
        return pages
    
    def extract_text_scanned(self, pdf_path: str) -> List[Tuple[int, str]]:
        """
        Extract text from scanned PDF using Document AI OCR.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            List of (page_number, text) tuples
        """
        logger.info("Extracting text from scanned PDF using OCR")
        
        # Check page count
        reader = PdfReader(pdf_path)
        num_pages = len(reader.pages)
        
        # If more than 15 pages, use batch processing
        if num_pages > 15:
            logger.info(f"PDF has {num_pages} pages, using batch processing")
            return self._extract_text_batch(pdf_path)
        
        # For small PDFs, use synchronous processing
        with open(pdf_path, "rb") as pdf_file:
            pdf_content = pdf_file.read()
        
        # Use Document AI for OCR
        raw_document = documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )
        
        request = documentai.ProcessRequest(
            name=self.processor_name,
            raw_document=raw_document
        )
        
        result = self.docai_client.process_document(request=request)
        document = result.document
        
        # Extract text per page
        pages = []
        for i, page in enumerate(document.pages):
            # Get text for this page
            page_text = self._extract_page_text(document, page)
            pages.append((i, page_text))
            logger.debug(f"OCR extracted {len(page_text)} characters from page {i}")
        
        logger.info(f"OCR extracted text from {len(pages)} pages")
        return pages
    
    def _extract_text_batch(self, pdf_path: str) -> List[Tuple[int, str]]:
        """Extract text using batch processing for large PDFs."""
        from google.cloud import storage
        import uuid
        import json
        import time
        
        logger.info("Using batch processing for large PDF")
        
        # Upload to Cloud Storage
        storage_client = storage.Client(project=self.config.google_project_id)
        bucket_name = os.getenv("BUCKET_NAME", f"{self.config.google_project_id}-docai-temp")
        bucket = storage_client.bucket(bucket_name)
        
        batch_id = str(uuid.uuid4())
        input_blob_name = f"input/{batch_id}/{os.path.basename(pdf_path)}"
        output_prefix = f"output/{batch_id}/"
        
        # Upload PDF
        with open(pdf_path, "rb") as pdf_file:
            blob = bucket.blob(input_blob_name)
            blob.upload_from_string(pdf_file.read(), content_type="application/pdf")
        
        logger.info(f"Uploaded to gs://{bucket_name}/{input_blob_name}")
        
        # Create batch request
        input_config = documentai.BatchDocumentsInputConfig(
            gcs_documents=documentai.GcsDocuments(
                documents=[
                    documentai.GcsDocument(
                        gcs_uri=f"gs://{bucket_name}/{input_blob_name}",
                        mime_type="application/pdf"
                    )
                ]
            )
        )
        
        output_config = documentai.DocumentOutputConfig(
            gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(
                gcs_uri=f"gs://{bucket_name}/{output_prefix}"
            )
        )
        
        request = documentai.BatchProcessRequest(
            name=self.processor_name,
            input_documents=input_config,
            document_output_config=output_config
        )
        
        # Start batch operation
        logger.info("Starting batch OCR operation...")
        operation = self.docai_client.batch_process_documents(request=request)
        
        # Wait for completion
        logger.info("Waiting for batch operation to complete...")
        operation.result(timeout=300)
        
        # Download results
        logger.info("Downloading OCR results...")
        output_blobs = list(bucket.list_blobs(prefix=output_prefix))
        
        # Collect all JSON files (Document AI creates one per document/shard)
        json_blobs = [blob for blob in output_blobs if blob.name.endswith('.json')]
        
        if not json_blobs:
            raise Exception("No OCR results found")
        
        logger.info(f"Found {len(json_blobs)} result file(s)")
        
        # Parse all results and combine pages
        pages = []
        for json_blob in sorted(json_blobs, key=lambda b: b.name):
            json_content = json_blob.download_as_text()
            result_dict = json.loads(json_content)
            document = documentai.Document.from_json(json.dumps(result_dict.get('document', result_dict)))
            
            # Extract text per page from this document
            for i, page in enumerate(document.pages):
                page_text = self._extract_page_text(document, page)
                # Use global page index
                page_index = len(pages)
                pages.append((page_index, page_text))
        
        # Cleanup
        try:
            # Delete input file
            input_blob = bucket.blob(input_blob_name)
            input_blob.delete()
            # Delete all output files
            for output_blob in output_blobs:
                output_blob.delete()
        except Exception as e:
            logger.warning(f"Cleanup warning: {e}")
        
        logger.info(f"Batch OCR extracted text from {len(pages)} pages")
        return pages
    
    def _extract_page_text(self, document: documentai.Document, page: documentai.Document.Page) -> str:
        """Extract text from a single page."""
        text = document.text
        page_text_parts = []
        
        # Try paragraphs first
        if hasattr(page, 'paragraphs') and page.paragraphs:
            for paragraph in page.paragraphs:
                if hasattr(paragraph, 'layout') and paragraph.layout:
                    para_text = self._get_text_from_layout(paragraph.layout, text)
                    if para_text:
                        page_text_parts.append(para_text)
        
        # Fall back to tokens if no paragraphs
        if not page_text_parts and hasattr(page, 'tokens') and page.tokens:
            for token in page.tokens:
                if hasattr(token, 'layout') and token.layout:
                    token_text = self._get_text_from_layout(token.layout, text)
                    if token_text:
                        page_text_parts.append(token_text)
        
        return " ".join(page_text_parts) if page_text_parts else ""
    
    def _get_text_from_layout(self, layout: documentai.Document.Page.Layout, full_text: str) -> str:
        """Extract text from a layout element."""
        if not hasattr(layout, 'text_anchor') or not layout.text_anchor:
            return ""
        
        text_segments = []
        for segment in layout.text_anchor.text_segments:
            start_idx = int(segment.start_index) if hasattr(segment, 'start_index') else 0
            end_idx = int(segment.end_index) if hasattr(segment, 'end_index') else len(full_text)
            text_segments.append(full_text[start_idx:end_idx])
        
        return "".join(text_segments)
    
    def determine_order_with_gemini(self, pages: List[Tuple[int, str]]) -> List[int]:
        """
        Use Gemini to determine the correct page order.
        
        Args:
            pages: List of (page_number, text) tuples
            
        Returns:
            List of page indices in correct order
        """
        logger.info("Asking Gemini to determine correct page order")
        
        # Try up to 3 times to get a valid response
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                # Build detailed prompt with all page contents
                prompt = self._build_ordering_prompt(pages)
                
                # Ask Gemini with lower temperature for more consistent results
                generation_config = {
                    'temperature': 0.1,  # Lower temperature = more deterministic
                    'top_p': 0.8,
                    'top_k': 40
                }
                response = self.model.generate_content(prompt, generation_config=generation_config)
                
                # Log the response for debugging
                logger.debug(f"Gemini response (attempt {attempt + 1}): {response.text[:500]}")
                
                # Parse response to get page order
                order = self._parse_order_response(response.text, len(pages))
                
                # Check if we got a valid reordering (not just original order)
                if order != list(range(len(pages))):
                    logger.info(f"Gemini determined order: {order}")
                    return order
                else:
                    logger.warning(f"Attempt {attempt + 1}: Gemini returned original order, retrying...")
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                
            # Wait a bit before retrying
            if attempt < max_attempts - 1:
                import time
                time.sleep(2)
        
        # If all attempts failed, return original order
        logger.warning("All attempts failed, using original order")
        return list(range(len(pages)))
    
    def _build_ordering_prompt(self, pages: List[Tuple[int, str]]) -> str:
        """Build detailed prompt for Gemini to determine page order."""
        import json
        
        # Build structured JSON data
        pages_data = []
        for page_num, text in pages:
            # Send full page content without truncation
            pages_data.append({
                "page_id": page_num + 1,  # 1-based for human readability
                "content": text
            })
        
        pages_json = json.dumps(pages_data, indent=2)
        
        prompt = f"""You are an expert document analyst with deep expertise in legal contracts, loan agreements, and formal document structures.

TASK: Analyze the shuffled pages and determine their correct logical order by understanding the document's natural flow and structure.

CRITICAL: You MUST include ALL {len(pages)} pages in your response. Every page matters - do not skip any.

PAGES DATA (JSON format):
{pages_json}

YOUR ANALYSIS APPROACH:

1. IDENTIFY THE FIRST PAGE (MOST CRITICAL)
   **The first page is typically the MOST INTRODUCTORY page with the LEAST detail:**
   
   Priority order for identifying the first page:
   a) **Cover/Face Sheet**: Contains basic summary info like "Loan Agreement No.", borrower name, loan amount, date - usually minimal text, acts as a reference sheet
   b) **Title Page**: Has the main title "LOAN AGREEMENT" or "AGREEMENT" in large text, parties' names, date - more formal than cover sheet
   c) **Preamble/Introduction**: Starts with "THIS AGREEMENT made at..." or "BETWEEN" - begins the actual legal text
   
   **Key indicators of the FIRST page:**
   - Shortest/most concise page with summary information
   - Contains reference numbers, basic identifiers
   - Does NOT start mid-sentence or mid-section
   - Does NOT have "continued from" or reference to previous content
   - Does NOT start with "ARTICLE II" or "SECTION 2" (would indicate it's not first)
   - May have "Page 1 of X" or similar pagination
   
   **Common mistakes to avoid:**
   - Don't put a detailed article page first
   - Don't put a schedule/exhibit first
   - Don't put a continuation page first
   - The first page should introduce the document, not dive into details

2. IDENTIFY THE DOCUMENT TYPE
   - What kind of document is this? (Loan agreement, contract, legal document, etc.)
   - Who are the parties involved? (Look for names, roles like "Borrower", "Lender", "Party A", etc.)
   - What is the subject matter?

2. FIND STRUCTURAL MARKERS
   - **Page numbers**: Look for printed page numbers (e.g., "Page 5 of 25", "- 3 -", "p.7")
   - **Section numbers**: Articles, Sections, Clauses (I, II, III or 1, 2, 3 or 1.1, 1.2, etc.)
   - **Headings**: Bold or capitalized section titles
   - **Schedules/Annexures**: Usually labeled (Schedule A, Exhibit 1, Annexure I, etc.)

3. UNDERSTAND DOCUMENT FLOW
   - **Beginning**: Cover pages, title pages, introductions, preambles, "WHEREAS" clauses
   - **Definitions**: Terms are defined early and used throughout (e.g., "Borrower shall mean...")
   - **Main Content**: Sequential sections building on each other
   - **Supporting Material**: Schedules, exhibits, annexures that reference main content
   - **Ending**: Signatures, execution clauses, witness statements ("IN WITNESS WHEREOF")

4. LOOK FOR LOGICAL CONNECTIONS
   - **Forward references**: "as defined in Section 3", "pursuant to Article II"
   - **Backward references**: "as mentioned above", "in accordance with the foregoing"
   - **Continuation markers**: "(continued)", "continued on next page"
   - **Content dependencies**: Definitions used later, schedules referenced in main text

5. RECOGNIZE COMMON PATTERNS
   - Legal documents typically follow: **Cover/Summary Sheet → Title Page → Introduction → Definitions → Terms → Conditions → Schedules → Signatures**
   - Numbered sections should be sequential (don't jump from Section 2 to Section 5)
   - Schedules/Exhibits come after the main body but before signatures
   - Signature pages are always last
   - **The VERY FIRST page is usually the simplest/shortest with basic identifying information**
   
   **Example of correct first pages:**
   - "Loan Agreement No: 123, Dated: 01/01/2024, Borrower: ABC Ltd, Amount: Rs. 10 Cr"
   - "LOAN AGREEMENT between XYZ Bank and ABC Company dated January 1, 2024"
   - A page with just document title, parties, and date (minimal content)
   
   **Example of WRONG first pages (these come later):**
   - "ARTICLE II - LOAN TERMS: The Borrower shall repay..."
   - "SCHEDULE III - FINANCING PLAN: [detailed table]"
   - A page starting with "...continued from previous page"
   - A page with dense legal text and multiple clauses

6. HANDLE SPECIAL CASES
   - **Blank pages**: Often used as separators or appear at the end
   - **Tables/Charts**: Usually part of schedules or financial sections
   - **Multi-page sections**: Keep pages together if they're part of the same section
   - **Duplicate content**: If pages seem similar, check for version differences or continuation

QUALITY CHECKS (Validate your ordering):
✓ **First page check**: Is the first page truly introductory? Does it have minimal content and basic identifiers?
✓ **Sequential check**: Do numbered sections follow in order (I, II, III... or 1, 2, 3...)?
✓ **Cross-reference check**: Do references point correctly? ("as defined in Section 1" should come after Section 1)
✓ **Definition check**: Are terms defined before they're used extensively?
✓ **Signature check**: Are signatures at the very end?
✓ **Flow check**: Does reading page-by-page make logical sense?
✓ **No mid-sentence starts**: The first page should NOT start mid-sentence or mid-thought
✓ **Completeness check**: Did you include all {len(pages)} pages?

REQUIREMENTS:
✓ Include exactly {len(pages)} page_id numbers
✓ Each page_id from 1 to {len(pages)} must appear exactly once
✓ No skipping, no duplicates
✓ Maintain logical document flow
✓ Respect sequential numbering
✓ Place signatures last
✓ **CRITICAL**: The FIRST page in your array MUST be the most introductory/summary page (cover sheet, face sheet, or title page) - NOT a detailed article or schedule page

RESPONSE FORMAT:
Output ONLY a JSON array of page_id numbers in the correct order.
No explanations, no markdown, no code blocks - just the raw JSON array.

Example: [3, 1, 5, 2, 4]

YOUR RESPONSE (JSON array with all {len(pages)} pages):
"""
        
        return prompt
    
    def _parse_order_response(self, response: str, num_pages: int) -> List[int]:
        """
        Parse Gemini's response to extract page order.
        
        Args:
            response: Gemini's response text
            num_pages: Total number of pages
            
        Returns:
            List of page indices (0-based)
        """
        import re
        import json
        
        # Try to parse as JSON first
        try:
            # Extract JSON array from response (handle markdown code blocks)
            json_match = re.search(r'\[[\d,\s]+\]', response)
            if json_match:
                order_1based = json.loads(json_match.group())
                # Convert to 0-based indices
                order = [int(n) - 1 for n in order_1based if 0 < int(n) <= num_pages]
                
                # Validate we have all pages
                if len(order) == num_pages and set(order) == set(range(num_pages)):
                    logger.info("Successfully parsed JSON response from Gemini")
                    return order
        except (json.JSONDecodeError, ValueError) as e:
            logger.debug(f"JSON parsing failed: {e}")
        
        # Fallback: Extract comma-separated numbers
        numbers = re.findall(r'\d+', response.strip())
        
        if not numbers:
            logger.warning("Could not parse order from Gemini response, using original order")
            return list(range(num_pages))
        
        # Convert to 0-based indices
        order = [int(n) - 1 for n in numbers if 0 < int(n) <= num_pages]
        
        # Validate we have all pages
        if len(order) != num_pages or set(order) != set(range(num_pages)):
            logger.warning(f"Invalid order from Gemini (got {len(order)} pages, expected {num_pages}), using original order")
            return list(range(num_pages))
        
        return order
    
    def reorder_pdf(self, input_path: str, output_path: str) -> dict:
        """
        Main method to reorder a PDF.
        
        Args:
            input_path: Path to input PDF
            output_path: Path to output PDF
            
        Returns:
            Dictionary with results
        """
        import time
        start_time = time.time()
        
        logger.info(f"Starting PDF reordering: {input_path}")
        
        try:
            # Step 1: Determine if scanned or digital
            is_scanned = self.is_scanned(input_path)
            
            # Step 2: Extract text
            if is_scanned:
                pages = self.extract_text_scanned(input_path)
            else:
                pages = self.extract_text_digital(input_path)
            
            # Step 3: Identify blank pages (pages with very little text)
            blank_pages = []
            for page_num, text in pages:
                if len(text.strip()) < 50:  # Consider pages with < 50 chars as blank
                    blank_pages.append(page_num)
                    logger.info(f"Page {page_num + 1} appears to be blank or nearly blank ({len(text.strip())} chars)")
            
            # Step 4: Get correct order from Gemini (for all pages)
            correct_order = self.determine_order_with_gemini(pages)
            
            # Step 5: Move blank pages to the end
            if blank_pages:
                logger.info(f"Moving {len(blank_pages)} blank page(s) to the end")
                # Remove blank pages from their current position
                non_blank_order = [p for p in correct_order if p not in blank_pages]
                # Append blank pages at the end
                correct_order = non_blank_order + blank_pages
            
            # Step 6: Reconstruct PDF
            reader = PdfReader(input_path)
            writer = PdfWriter()
            
            for page_idx in correct_order:
                writer.add_page(reader.pages[page_idx])
            
            # Write output
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            processing_time = time.time() - start_time
            
            # Log detailed results
            logger.info(f"PDF reordering complete: {output_path}")
            logger.info(f"Pages processed: {len(pages)}")
            logger.info(f"Document type: {'Scanned (OCR used)' if is_scanned else 'Digital (direct text extraction)'}")
            logger.info(f"Original order: {[i+1 for i in range(len(pages))]}")
            logger.info(f"New order:      {[i+1 for i in correct_order]}")
            logger.info(f"Processing time: {processing_time:.2f}s")
            
            return {
                'success': True,
                'input_path': input_path,
                'output_path': output_path,
                'page_count': len(pages),
                'original_order': list(range(len(pages))),
                'new_order': correct_order,
                'is_scanned': is_scanned,
                'processing_time': processing_time,
                'error': None
            }
            
        except Exception as e:
            logger.error(f"Error reordering PDF: {e}", exc_info=True)
            return {
                'success': False,
                'input_path': input_path,
                'output_path': output_path,
                'page_count': 0,
                'error': str(e),
                'processing_time': time.time() - start_time
            }
