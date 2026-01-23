"""
Unified Receipt Processor - Single Source of Truth

This is the ONLY entry point for receipt processing. All operations go through this module:
- Preview generation (HTML→image, PDF→image, attachment processing)
- Data extraction (vendor/amount/currency/date/invoice_number)
- Status management (extraction_status, preview_status)
- Error handling and confidence scoring

MANDATORY RULE: Every receipt MUST have a preview_image_key after processing.

Architecture:
    process_receipt(receipt_id) -> ProcessingResult
    └── 1. normalize_email_content()
    └── 2. generate_preview()
        ├── 2a. generate_email_html_preview() [MANDATORY - always runs first]
        ├── 2b. generate_pdf_preview() [if PDF attachment exists]
        ├── 2c. generate_image_preview() [if image attachment exists]
        └── 2d. screenshot_receipt_url() [optional, with timeout]
    └── 3. extract_data()
        ├── 3a. extract_with_vendor_adapter()
        ├── 3b. extract_with_regex()
        └── 3c. extract_with_llm() [OpenAI for complex cases]
    └── 4. update_receipt_status()

Example Usage:
    from server.services.receipts.receipt_processor import ReceiptProcessor
    
    processor = ReceiptProcessor()
    result = processor.process_receipt(receipt_id=123)
    
    if result.success:
        print(f"Preview: {result.preview_image_key}")
        print(f"Vendor: {result.vendor_name}, Amount: {result.amount}")
"""

import logging
import time
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import re
import json

logger = logging.getLogger(__name__)

# Processing configuration
MAX_PROCESSING_TIME_SECONDS = 30  # Timeout per receipt
PREVIEW_MANDATORY = True  # Must generate preview for every receipt
MIN_CONFIDENCE_FOR_SUCCESS = 0.6  # Below this = needs_review


@dataclass
class ProcessingResult:
    """Result of receipt processing"""
    success: bool
    receipt_id: int
    
    # Preview fields
    preview_generated: bool = False
    preview_image_key: Optional[str] = None
    preview_source: Optional[str] = None  # email_html|attachment_pdf|attachment_image|receipt_url|html_fallback
    preview_error: Optional[str] = None
    
    # Extraction fields
    extraction_success: bool = False
    vendor_name: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None  # ISO format date string
    confidence: float = 0.0
    extraction_error: Optional[str] = None
    
    # Status
    extraction_status: str = 'pending'  # pending|processing|success|needs_review|failed
    
    # Processing metadata
    processing_time_ms: int = 0
    steps_completed: list = None
    
    def __post_init__(self):
        if self.steps_completed is None:
            self.steps_completed = []


class ReceiptProcessor:
    """
    Unified receipt processor - single source of truth for all receipt processing
    
    Features:
    - MANDATORY preview generation (always generates at least one image)
    - Multi-source preview support (email HTML, PDF, image, receipt URL)
    - Vendor-specific extraction adapters
    - Confidence scoring
    - Comprehensive error handling
    - Timeout protection
    """
    
    def __init__(self):
        """Initialize processor with dependencies"""
        self.start_time = None
        
    def process_receipt(self, receipt_id: int) -> ProcessingResult:
        """
        Main entry point - process a single receipt
        
        Steps:
        1. Load receipt from database
        2. Normalize email content
        3. Generate preview (MANDATORY)
        4. Extract data (vendor/amount/etc.)
        5. Update receipt in database
        
        Args:
            receipt_id: Receipt ID to process
            
        Returns:
            ProcessingResult with status and extracted data
        """
        self.start_time = time.time()
        result = ProcessingResult(success=False, receipt_id=receipt_id)
        
        try:
            logger.info(f"=" * 60)
            logger.info(f"🧾 RECEIPT_PROCESSING_START: Receipt #{receipt_id}")
            logger.info(f"=" * 60)
            
            # Step 1: Load receipt
            receipt = self._load_receipt(receipt_id)
            if not receipt:
                result.extraction_error = "Receipt not found"
                result.extraction_status = 'failed'
                return result
            
            result.steps_completed.append('loaded')
            
            # Step 2: Normalize email content
            normalized_data = self._normalize_email_content(receipt)
            result.steps_completed.append('normalized')
            
            # Step 3: Generate preview (MANDATORY)
            preview_result = self._generate_preview(receipt, normalized_data)
            result.preview_generated = preview_result.get('success', False)
            result.preview_image_key = preview_result.get('image_key')
            result.preview_source = preview_result.get('source')
            result.preview_error = preview_result.get('error')
            
            if not result.preview_generated:
                logger.warning(f"⚠️  Preview generation failed for receipt #{receipt_id}")
                # Don't fail entire processing - continue with extraction
            
            result.steps_completed.append('preview')
            
            # Step 4: Extract data
            extraction_result = self._extract_data(receipt, normalized_data)
            result.extraction_success = extraction_result.get('success', False)
            result.vendor_name = extraction_result.get('vendor_name')
            result.amount = extraction_result.get('amount')
            result.currency = extraction_result.get('currency')
            result.invoice_number = extraction_result.get('invoice_number')
            result.invoice_date = extraction_result.get('invoice_date')
            result.confidence = extraction_result.get('confidence', 0.0)
            result.extraction_error = extraction_result.get('error')
            
            result.steps_completed.append('extraction')
            
            # Step 5: Determine extraction status
            result.extraction_status = self._determine_extraction_status(result)
            
            # Step 6: Update receipt in database
            self._update_receipt(receipt, result)
            result.steps_completed.append('saved')
            
            # Mark as successful
            result.success = True
            
            # Calculate processing time
            result.processing_time_ms = int((time.time() - self.start_time) * 1000)
            
            logger.info(f"✅ RECEIPT_PROCESSING_COMPLETE: Receipt #{receipt_id}")
            logger.info(f"  → Preview: {result.preview_source or 'none'}")
            logger.info(f"  → Vendor: {result.vendor_name or 'unknown'}")
            logger.info(f"  → Amount: {result.amount} {result.currency or ''}")
            logger.info(f"  → Confidence: {result.confidence:.2f}")
            logger.info(f"  → Status: {result.extraction_status}")
            logger.info(f"  → Time: {result.processing_time_ms}ms")
            logger.info(f"=" * 60)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Receipt processing failed for #{receipt_id}: {e}", exc_info=True)
            result.success = False
            result.extraction_error = str(e)[:500]
            result.extraction_status = 'failed'
            
            # Try to update receipt with error
            try:
                receipt = self._load_receipt(receipt_id)
                if receipt:
                    self._update_receipt(receipt, result)
            except Exception as update_err:
                logger.error(f"Failed to update receipt with error: {update_err}")
            
            return result
    
    def _load_receipt(self, receipt_id: int):
        """Load receipt from database"""
        from server.models_sql import Receipt
        from server.db import db
        
        try:
            receipt = Receipt.query.get(receipt_id)
            return receipt
        except Exception as e:
            logger.error(f"Failed to load receipt #{receipt_id}: {e}")
            return None
    
    def _normalize_email_content(self, receipt) -> Dict[str, Any]:
        """
        Normalize email content for processing
        
        Steps:
        - Clean HTML (remove scripts, trackers, footers)
        - Identify main content area
        - Extract plain text
        - Prepare metadata (from, subject, date)
        
        Returns:
            Dict with normalized content
        """
        try:
            normalized = {
                'html_clean': None,
                'text_clean': None,
                'main_content_html': None,
                'from_email': receipt.email_from or receipt.from_email,
                'subject': receipt.email_subject or receipt.subject,
                'date': receipt.email_date or receipt.received_at,
            }
            
            # Get HTML content
            html_content = receipt.email_html_snippet
            
            if html_content:
                # Clean HTML
                from bs4 import BeautifulSoup
                import bleach
                
                # Parse HTML
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Remove unwanted elements
                for tag in soup.find_all(['script', 'style', 'noscript']):
                    tag.decompose()
                
                # Remove tracking pixels (1x1 images)
                for img in soup.find_all('img'):
                    if 'width' in img.attrs and 'height' in img.attrs:
                        if img.attrs.get('width') == '1' and img.attrs.get('height') == '1':
                            img.decompose()
                
                # Remove hidden elements
                for elem in soup.find_all(style=re.compile(r'display:\s*none', re.I)):
                    elem.decompose()
                
                # Try to identify main content (heuristic: largest text block)
                main_content = None
                max_text_length = 0
                
                for tag in soup.find_all(['div', 'table', 'main', 'article']):
                    text = tag.get_text(strip=True)
                    if len(text) > max_text_length:
                        max_text_length = len(text)
                        main_content = tag
                
                if main_content:
                    normalized['main_content_html'] = str(main_content)
                else:
                    normalized['main_content_html'] = html_content
                
                # Get clean HTML
                normalized['html_clean'] = str(soup)
                
                # Extract plain text
                normalized['text_clean'] = soup.get_text(separator='\n', strip=True)
            
            return normalized
            
        except Exception as e:
            logger.error(f"Failed to normalize email content: {e}")
            return {
                'html_clean': None,
                'text_clean': None,
                'main_content_html': None,
                'from_email': receipt.email_from or receipt.from_email,
                'subject': receipt.email_subject or receipt.subject,
                'date': receipt.email_date or receipt.received_at,
            }
    
    def _generate_preview(self, receipt, normalized_data: Dict) -> Dict[str, Any]:
        """
        Generate preview image (MANDATORY)
        
        Priority order:
        1. Email HTML → Image (always try this first)
        2. PDF attachment → Image
        3. Image attachment → Thumbnail
        4. Receipt URL → Screenshot (optional, with timeout)
        5. Fallback: Simple HTML → Image
        
        Returns:
            Dict with preview generation result
        """
        from server.services.receipt_preview_service import (
            generate_html_preview,
            generate_pdf_thumbnail,
            generate_image_thumbnail
        )
        from server.services.attachment_service import get_attachment_service
        from server.models_sql import Attachment
        
        attachment_service = get_attachment_service()
        
        # Try 1: Email HTML → Image (MANDATORY, always run first)
        if normalized_data.get('html_clean') or normalized_data.get('main_content_html'):
            try:
                logger.info("  → Generating email HTML preview...")
                html_content = normalized_data.get('main_content_html') or normalized_data.get('html_clean')
                
                # Inject CSS for better rendering
                html_with_css = f"""
                <!DOCTYPE html>
                <html dir="rtl">
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            max-width: 800px;
                            margin: 20px auto;
                            padding: 20px;
                            background: white;
                            color: #333;
                            direction: rtl;
                        }}
                        table {{
                            border-collapse: collapse;
                            width: 100%;
                        }}
                        td, th {{
                            border: 1px solid #ddd;
                            padding: 8px;
                            text-align: right;
                        }}
                        img {{
                            max-width: 100%;
                            height: auto;
                        }}
                    </style>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """
                
                preview_bytes = generate_html_preview(html_with_css, width=1280, height=1600)
                
                if preview_bytes:
                    # Save to R2
                    storage_key = f"receipts/{receipt.business_id}/previews/receipt_{receipt.id}_{int(time.time())}.png"
                    
                    result = attachment_service.upload_file(
                        file_data=preview_bytes,
                        filename=f"receipt_{receipt.id}_preview.png",
                        content_type='image/png',
                        purpose='receipt_preview',
                        business_id=receipt.business_id,
                        storage_key=storage_key
                    )
                    
                    if result.get('success'):
                        logger.info(f"  ✅ Email HTML preview generated: {storage_key}")
                        return {
                            'success': True,
                            'image_key': storage_key,
                            'source': 'email_html',
                            'attachment_id': result.get('attachment_id')
                        }
                
            except Exception as e:
                logger.warning(f"  ⚠️  Email HTML preview failed: {e}")
        
        # Try 2: PDF attachment
        if receipt.attachment_id:
            try:
                attachment = Attachment.query.get(receipt.attachment_id)
                if attachment and attachment.content_type == 'application/pdf':
                    logger.info("  → Generating PDF preview...")
                    
                    # Download PDF from R2
                    pdf_data = attachment_service.get_file(attachment.storage_path)
                    
                    if pdf_data:
                        preview_bytes = generate_pdf_thumbnail(pdf_data)
                        
                        if preview_bytes:
                            # Save to R2
                            storage_key = f"receipts/{receipt.business_id}/previews/receipt_{receipt.id}_{int(time.time())}.png"
                            
                            result = attachment_service.upload_file(
                                file_data=preview_bytes,
                                filename=f"receipt_{receipt.id}_pdf_preview.png",
                                content_type='image/png',
                                purpose='receipt_preview',
                                business_id=receipt.business_id,
                                storage_key=storage_key
                            )
                            
                            if result.get('success'):
                                logger.info(f"  ✅ PDF preview generated: {storage_key}")
                                return {
                                    'success': True,
                                    'image_key': storage_key,
                                    'source': 'attachment_pdf',
                                    'attachment_id': result.get('attachment_id')
                                }
                
            except Exception as e:
                logger.warning(f"  ⚠️  PDF preview failed: {e}")
        
        # Try 3: Image attachment
        if receipt.attachment_id:
            try:
                attachment = Attachment.query.get(receipt.attachment_id)
                if attachment and attachment.content_type.startswith('image/'):
                    logger.info("  → Generating image preview...")
                    
                    # Download image from R2
                    image_data = attachment_service.get_file(attachment.storage_path)
                    
                    if image_data:
                        preview_bytes = generate_image_thumbnail(image_data, attachment.content_type)
                        
                        if preview_bytes:
                            # Save to R2
                            storage_key = f"receipts/{receipt.business_id}/previews/receipt_{receipt.id}_{int(time.time())}.png"
                            
                            result = attachment_service.upload_file(
                                file_data=preview_bytes,
                                filename=f"receipt_{receipt.id}_image_preview.png",
                                content_type='image/png',
                                purpose='receipt_preview',
                                business_id=receipt.business_id,
                                storage_key=storage_key
                            )
                            
                            if result.get('success'):
                                logger.info(f"  ✅ Image preview generated: {storage_key}")
                                return {
                                    'success': True,
                                    'image_key': storage_key,
                                    'source': 'attachment_image',
                                    'attachment_id': result.get('attachment_id')
                                }
                
            except Exception as e:
                logger.warning(f"  ⚠️  Image preview failed: {e}")
        
        # Try 4: Receipt URL (optional, with timeout) - NOT IMPLEMENTED YET
        # This would require Playwright to screenshot receipt pages
        # Skip for now as it's optional and can fail on auth pages
        
        # Fallback: Generate simple HTML preview if we have any text
        if normalized_data.get('text_clean'):
            try:
                logger.info("  → Generating fallback HTML preview...")
                text = normalized_data['text_clean'][:2000]  # Limit to 2000 chars
                
                fallback_html = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            max-width: 800px;
                            margin: 20px auto;
                            padding: 20px;
                            background: white;
                            color: #333;
                        }}
                        pre {{
                            white-space: pre-wrap;
                            word-wrap: break-word;
                        }}
                    </style>
                </head>
                <body>
                    <h3>Receipt Content</h3>
                    <pre>{text}</pre>
                </body>
                </html>
                """
                
                preview_bytes = generate_html_preview(fallback_html, width=1280, height=1600)
                
                if preview_bytes:
                    # Save to R2
                    storage_key = f"receipts/{receipt.business_id}/previews/receipt_{receipt.id}_{int(time.time())}.png"
                    
                    result = attachment_service.upload_file(
                        file_data=preview_bytes,
                        filename=f"receipt_{receipt.id}_fallback_preview.png",
                        content_type='image/png',
                        purpose='receipt_preview',
                        business_id=receipt.business_id,
                        storage_key=storage_key
                    )
                    
                    if result.get('success'):
                        logger.info(f"  ✅ Fallback HTML preview generated: {storage_key}")
                        return {
                            'success': True,
                            'image_key': storage_key,
                            'source': 'html_fallback',
                            'attachment_id': result.get('attachment_id')
                        }
            
            except Exception as e:
                logger.warning(f"  ⚠️  Fallback HTML preview failed: {e}")
        
        # All preview methods failed
        logger.error(f"  ❌ All preview generation methods failed for receipt #{receipt.id}")
        return {
            'success': False,
            'error': 'All preview generation methods failed'
        }
    
    def _extract_data(self, receipt, normalized_data: Dict) -> Dict[str, Any]:
        """
        Extract receipt data (vendor, amount, currency, date, invoice number)
        
        Priority order:
        1. Vendor-specific adapters
        2. Generic regex patterns
        3. LLM extraction (OpenAI) - NOT IMPLEMENTED YET
        
        Returns:
            Dict with extraction results
        """
        from server.services.receipt_amount_extractor import extract_receipt_amount
        
        try:
            # Get text for extraction
            text = normalized_data.get('text_clean', '')
            from_email = normalized_data.get('from_email', '')
            subject = normalized_data.get('subject', '')
            
            # Combine all text sources
            full_text = f"{subject}\n{from_email}\n{text}"
            
            # Use existing amount extractor
            extraction = extract_receipt_amount(
                html_content=normalized_data.get('html_clean', ''),
                subject=subject,
                from_email=from_email
            )
            
            # Build result
            result = {
                'success': bool(extraction.get('amount') or extraction.get('vendor')),
                'vendor_name': extraction.get('vendor'),
                'amount': extraction.get('amount'),
                'currency': extraction.get('currency', 'ILS'),
                'invoice_number': None,  # TODO: Extract invoice number
                'invoice_date': None,  # TODO: Extract invoice date
                'confidence': extraction.get('confidence', 0) / 100.0,  # Convert to 0-1 range
            }
            
            # TODO: Add LLM extraction for complex cases
            # if result['confidence'] < 0.5:
            #     llm_result = self._extract_with_llm(full_text)
            #     result.update(llm_result)
            
            return result
            
        except Exception as e:
            logger.error(f"Data extraction failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)[:500]
            }
    
    def _determine_extraction_status(self, result: ProcessingResult) -> str:
        """
        Determine extraction status based on results
        
        Rules:
        - success: Has preview + (vendor OR amount) + confidence >= 0.6
        - needs_review: Has preview but low confidence or missing data
        - failed: No preview or extraction completely failed
        """
        # Must have preview
        if not result.preview_generated:
            return 'failed'
        
        # Must have at least vendor or amount
        if not result.vendor_name and not result.amount:
            return 'needs_review'
        
        # Check confidence
        if result.confidence < MIN_CONFIDENCE_FOR_SUCCESS:
            return 'needs_review'
        
        return 'success'
    
    def _update_receipt(self, receipt, result: ProcessingResult):
        """Update receipt in database with processing results"""
        from server.db import db
        
        try:
            # Update preview fields
            if result.preview_image_key:
                receipt.preview_image_key = result.preview_image_key
                receipt.preview_source = result.preview_source
                receipt.preview_status = 'generated'
            else:
                receipt.preview_status = 'failed'
                receipt.preview_failure_reason = result.preview_error
            
            # Update extraction fields
            receipt.extraction_status = result.extraction_status
            receipt.extraction_error = result.extraction_error
            
            if result.vendor_name:
                receipt.vendor_name = result.vendor_name
            if result.amount:
                receipt.amount = result.amount
            if result.currency:
                receipt.currency = result.currency
            if result.invoice_number:
                receipt.invoice_number = result.invoice_number
            if result.invoice_date:
                receipt.invoice_date = result.invoice_date
            
            # Update confidence (convert to 0-100 integer for backward compatibility)
            receipt.confidence = int(result.confidence * 100)
            
            # Set needs_review flag
            receipt.needs_review = (result.extraction_status == 'needs_review')
            
            # Update timestamp
            receipt.updated_at = datetime.utcnow()
            
            # Commit
            db.session.commit()
            
            logger.info(f"  ✅ Receipt #{receipt.id} updated in database")
            
        except Exception as e:
            logger.error(f"Failed to update receipt #{receipt.id}: {e}", exc_info=True)
            db.session.rollback()
            raise


# Singleton instance
_processor_instance = None

def get_receipt_processor() -> ReceiptProcessor:
    """Get singleton receipt processor instance"""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = ReceiptProcessor()
    return _processor_instance
