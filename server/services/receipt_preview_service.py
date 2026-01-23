"""
Receipt Preview Service - Generate thumbnails and previews for receipts

Features:
- PDF thumbnail generation (first page as PNG)
- Image thumbnail generation (resize to thumbnail size)
- HTML→PNG rendering for emails without attachments using Playwright
- Integration with unified attachment service

Requirements:
- PyMuPDF (fitz) for PDF rendering
- Pillow (PIL) for image processing
- Playwright for HTML→PNG rendering
"""

import logging
import os
from typing import Optional, Tuple
from io import BytesIO

logger = logging.getLogger(__name__)

# Preview configuration
THUMBNAIL_MAX_WIDTH = 512  # Max width for thumbnails
THUMBNAIL_MAX_HEIGHT = 512  # Max height for thumbnails
THUMBNAIL_QUALITY = 85  # JPEG quality for thumbnails

# Content validation thresholds
MIN_CONTENT_VARIANCE = 50  # Minimum pixel variance for non-blank image (raised from 10)
MIN_UNIQUE_COLORS = 50  # Minimum unique colors for non-blank image (raised from 10)
MIN_EDGE_MEAN = 3.0  # Minimum edge detection mean (raised from 1.0)


def is_image_blank_or_white(image_data: bytes) -> bool:
    """
    Check if image is blank, white, or lacks meaningful content
    
    Uses multiple heuristics:
    1. Pixel variance - blank images have very low variance
    2. Unique colors - blank images have very few unique colors
    3. Edge detection - blank images have no edges
    
    Args:
        image_data: Raw image bytes
        
    Returns:
        True if image appears blank/empty, False if has content
    """
    try:
        from PIL import Image, ImageStat
        import numpy as np
        
        img = Image.open(BytesIO(image_data))
        
        # Convert to RGB if needed
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Check 1: Calculate pixel variance
        # Blank/white images have very low variance
        stat = ImageStat.Stat(img)
        variance = sum(stat.var) / len(stat.var) if hasattr(stat, 'var') else 0
        
        if variance < MIN_CONTENT_VARIANCE:
            logger.warning(f"Image appears blank - low variance: {variance:.2f}")
            return True
        
        # Check 2: Count unique colors
        # Blank images have very few unique colors
        img_small = img.resize((50, 50))  # Downscale for faster processing
        unique_colors = len(set(list(img_small.getdata())))
        
        if unique_colors < MIN_UNIQUE_COLORS:
            logger.warning(f"Image appears blank - few colors: {unique_colors}")
            return True
        
        # Check 3: Edge detection
        # Blank images have no edges
        try:
            from PIL import ImageFilter
            edges = img.convert('L').filter(ImageFilter.FIND_EDGES)
            edge_stat = ImageStat.Stat(edges)
            edge_mean = sum(edge_stat.mean) / len(edge_stat.mean)
            
            # If almost no edges detected, likely blank
            if edge_mean < MIN_EDGE_MEAN:
                logger.warning(f"Image appears blank - no edges: {edge_mean:.2f}")
                return True
        except Exception as e:
            logger.warning(f"Edge detection failed: {e}")
        
        # Image has content
        return False
        
    except Exception as e:
        logger.error(f"Failed to check if image is blank: {e}")
        # If check fails, assume image has content to avoid false positives
        return False


def generate_pdf_thumbnail(pdf_data: bytes) -> Optional[bytes]:
    """
    Generate thumbnail image from first page of PDF
    
    Args:
        pdf_data: Raw PDF bytes
        
    Returns:
        PNG thumbnail bytes or None if generation fails
    """
    try:
        import fitz  # PyMuPDF
        
        # Open PDF from bytes
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")
        
        if pdf_document.page_count == 0:
            logger.warning("PDF has no pages")
            return None
        
        # Get first page
        first_page = pdf_document[0]
        
        # Render page to pixmap (image)
        # Scale to get higher quality thumbnail
        zoom = 2.0  # 2x zoom for better quality
        mat = fitz.Matrix(zoom, zoom)
        pix = first_page.get_pixmap(matrix=mat)
        
        # Convert pixmap to PNG bytes
        png_bytes = pix.tobytes("png")
        
        pdf_document.close()
        
        # Resize to thumbnail size using PIL
        from PIL import Image
        
        img = Image.open(BytesIO(png_bytes))
        img.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_HEIGHT), Image.Resampling.LANCZOS)
        
        # Save as PNG
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        
        thumbnail_bytes = output.getvalue()
        
        # Validate thumbnail is not blank
        if is_image_blank_or_white(thumbnail_bytes):
            logger.warning("PDF thumbnail appears blank/white - may indicate empty PDF")
            return None
        
        logger.info(f"Generated PDF thumbnail: {img.size}")
        
        return thumbnail_bytes
        
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. Install with: pip install PyMuPDF")
        return None
    except Exception as e:
        logger.error(f"Failed to generate PDF thumbnail: {e}", exc_info=True)
        return None


def generate_image_thumbnail(image_data: bytes, mime_type: str) -> Optional[bytes]:
    """
    Generate thumbnail from image
    
    Args:
        image_data: Raw image bytes
        mime_type: Original image MIME type
        
    Returns:
        PNG thumbnail bytes or None if generation fails
    """
    try:
        from PIL import Image
        
        # Open image
        img = Image.open(BytesIO(image_data))
        
        # Convert to RGB if necessary (for PNG with transparency, etc.)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Create thumbnail
        img.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_HEIGHT), Image.Resampling.LANCZOS)
        
        # Save as PNG
        output = BytesIO()
        img.save(output, format='PNG', optimize=True)
        
        thumbnail_bytes = output.getvalue()
        
        # Validate thumbnail is not blank
        if is_image_blank_or_white(thumbnail_bytes):
            logger.warning("Image thumbnail appears blank/white - may indicate corrupt image")
            return None
        
        logger.info(f"Generated image thumbnail: {img.size}")
        
        return thumbnail_bytes
        
    except ImportError:
        logger.error("Pillow (PIL) not installed. Install with: pip install Pillow")
        return None
    except Exception as e:
        logger.error(f"Failed to generate image thumbnail: {e}", exc_info=True)
        return None


def generate_html_preview(html_content: str, width: int = 1280, height: int = 720) -> Optional[bytes]:
    """
    Render HTML content to PNG image using Playwright with proper waiting
    
    IMPROVEMENTS:
    - Waits for DOM, fonts, and images to fully load
    - Uses screen media emulation
    - Fixed viewport size (1280x720 for better quality)
    - Injects CSS for better rendering
    - Full-page screenshot
    
    Args:
        html_content: HTML string to render
        width: Viewport width in pixels (default 1280)
        height: Viewport height in pixels (default 720)
        
    Returns:
        PNG image bytes or None if rendering fails
    """
    try:
        from playwright.sync_api import sync_playwright
        
        with sync_playwright() as p:
            # Launch browser (headless)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-first-run',
                    '--no-default-browser-check',
                    '--disable-extensions'
                ]
            )
            
            # Create page with fixed viewport size for consistent rendering
            page = browser.new_page(viewport={'width': width, 'height': height})
            
            # CRITICAL: Emulate screen media (not print)
            page.emulate_media(media='screen')
            
            # Set HTML content and wait for network to be idle
            page.set_content(html_content, wait_until='networkidle', timeout=30000)
            
            # CRITICAL WAITING SEQUENCE - Let content fully load
            try:
                # Wait 1: Network idle
                page.wait_for_load_state('networkidle', timeout=20000)
            except Exception as e:
                logger.warning(f"networkidle timeout (continuing): {e}")
            
            try:
                # Wait 2: Fonts ready
                page.evaluate("document.fonts && document.fonts.ready")
            except Exception as e:
                logger.warning(f"fonts.ready failed (continuing): {e}")
            
            try:
                # Wait 3: All images loaded
                page.evaluate("""
                    async () => {
                        const imgs = Array.from(document.images || []);
                        await Promise.all(imgs.map(img => img.complete ? Promise.resolve() : new Promise(res => {
                            img.addEventListener('load', res);
                            img.addEventListener('error', res);
                        })));
                    }
                """)
            except Exception as e:
                logger.warning(f"Image loading wait failed (continuing): {e}")
            
            # Wait 4: Final buffer to ensure everything is settled
            try:
                page.wait_for_timeout(1200)
            except Exception as e:
                logger.warning(f"Final timeout failed (continuing): {e}")
            
            # Inject wrapper CSS for better rendering
            try:
                page.add_style_tag(content="""
                    body {
                        max-width: 100%;
                        background: white !important;
                        font-size: 14px;
                        padding: 20px;
                    }
                    img {
                        max-width: 100% !important;
                        height: auto !important;
                    }
                """)
            except Exception as e:
                logger.warning(f"CSS injection failed (continuing): {e}")
            
            # Take full-page screenshot
            screenshot_bytes = page.screenshot(type='png', full_page=True)
            
            # Close browser
            browser.close()
            
            # CRITICAL: Validate screenshot is not blank/white
            if is_image_blank_or_white(screenshot_bytes):
                logger.error("Screenshot validation failed - image appears blank/white")
                return None
            
            # Resize to thumbnail size using PIL
            from PIL import Image
            
            img = Image.open(BytesIO(screenshot_bytes))
            img.thumbnail((THUMBNAIL_MAX_WIDTH, THUMBNAIL_MAX_HEIGHT), Image.Resampling.LANCZOS)
            
            # Save as PNG
            output = BytesIO()
            img.save(output, format='PNG', optimize=True)
            
            logger.info(f"Generated HTML preview: {img.size}")
            
            return output.getvalue()
            
    except ImportError:
        logger.error("Playwright not installed. Install with: pip install playwright && playwright install chromium")
        return None
    except Exception as e:
        logger.error(f"Failed to generate HTML preview: {e}", exc_info=True)
        return None


def save_preview_attachment(preview_data: bytes, business_id: int, original_filename: str, purpose: str = 'receipt_preview') -> Optional[int]:
    """
    Save preview/thumbnail as attachment
    
    Args:
        preview_data: Preview image bytes (PNG)
        business_id: Business ID
        original_filename: Original filename (for reference)
        purpose: Attachment purpose
        
    Returns:
        Attachment ID or None if save fails
    """
    try:
        from server.db import db
        from server.models_sql import Attachment
        from server.services.attachment_service import get_attachment_service
        from werkzeug.datastructures import FileStorage
        
        attachment_service = get_attachment_service()
        
        # Generate preview filename
        preview_filename = f"preview_{original_filename}.png"
        
        # Create attachment record
        attachment = Attachment(
            business_id=business_id,
            filename_original=preview_filename,
            mime_type='image/png',
            file_size=0,  # Will be updated after save
            storage_path='',  # Will be updated after save
            purpose=purpose,
            channel_compatibility={'email': True, 'whatsapp': True, 'broadcast': True}
        )
        db.session.add(attachment)
        db.session.flush()  # Get attachment ID
        
        # Create FileStorage object for save_file
        file_storage = FileStorage(
            stream=BytesIO(preview_data),
            filename=preview_filename,
            content_type='image/png'
        )
        
        # Save file
        storage_key, file_size = attachment_service.save_file(
            file=file_storage,
            business_id=business_id,
            attachment_id=attachment.id,
            purpose=purpose
        )
        
        # Update attachment record
        attachment.storage_path = storage_key
        attachment.file_size = file_size
        
        db.session.commit()
        
        logger.info(f"Saved preview attachment: {attachment.id} ({file_size} bytes)")
        
        return attachment.id
        
    except Exception as e:
        logger.error(f"Failed to save preview attachment: {e}", exc_info=True)
        return None


def generate_receipt_preview(receipt_id: int) -> bool:
    """
    Generate preview for a receipt
    
    This function:
    1. Checks if receipt has an attachment (PDF/image)
    2. If yes, generates thumbnail from attachment
    3. If no, generates preview from email HTML content
    4. Saves preview as new attachment
    5. Links preview to receipt
    
    Args:
        receipt_id: Receipt ID
        
    Returns:
        True if preview generated successfully
    """
    try:
        from server.db import db
        from server.models_sql import Receipt, Attachment
        from server.services.attachment_service import get_attachment_service
        
        receipt = Receipt.query.get(receipt_id)
        if not receipt:
            logger.error(f"Receipt {receipt_id} not found")
            return False
        
        # Skip if preview already exists
        if receipt.preview_attachment_id:
            logger.info(f"Receipt {receipt_id} already has preview")
            return True
        
        attachment_service = get_attachment_service()
        preview_data = None
        original_filename = "receipt"
        
        # Case 1: Receipt has attachment (PDF or image)
        if receipt.attachment_id and receipt.attachment:
            att = receipt.attachment
            original_filename = att.filename_original
            
            logger.info(f"Generating preview from attachment: {att.mime_type}")
            
            # Download attachment data
            try:
                _, mime_type, file_bytes = attachment_service.open_file(
                    storage_key=att.storage_path,
                    filename=att.filename_original,
                    mime_type=att.mime_type
                )
                
                # Generate thumbnail based on type
                if mime_type == 'application/pdf':
                    preview_data = generate_pdf_thumbnail(file_bytes)
                elif mime_type.startswith('image/'):
                    preview_data = generate_image_thumbnail(file_bytes, mime_type)
                
            except Exception as e:
                logger.error(f"Failed to download attachment {att.id}: {e}")
        
        # Case 2: No attachment - generate from HTML
        if not preview_data and receipt.email_html_snippet:
            logger.info(f"Generating preview from email HTML")
            preview_data = generate_html_preview(receipt.email_html_snippet)
        
        # Save preview attachment if generated
        if preview_data:
            preview_attachment_id = save_preview_attachment(
                preview_data=preview_data,
                business_id=receipt.business_id,
                original_filename=original_filename,
                purpose='receipt_preview'
            )
            
            if preview_attachment_id:
                # Link preview to receipt
                receipt.preview_attachment_id = preview_attachment_id
                db.session.commit()
                
                logger.info(f"✅ Generated preview for receipt {receipt_id}")
                return True
        
        logger.warning(f"Failed to generate preview for receipt {receipt_id}")
        return False
        
    except Exception as e:
        logger.error(f"Error generating preview for receipt {receipt_id}: {e}", exc_info=True)
        return False


def batch_generate_previews(business_id: int, limit: int = 50) -> dict:
    """
    Generate previews for receipts that don't have them
    
    Args:
        business_id: Business ID
        limit: Maximum number of receipts to process
        
    Returns:
        Results dict with counts
    """
    try:
        from server.models_sql import Receipt
        
        # Find receipts without preview
        receipts = Receipt.query.filter_by(
            business_id=business_id,
            preview_attachment_id=None,
            is_deleted=False
        ).limit(limit).all()
        
        logger.info(f"Generating previews for {len(receipts)} receipts")
        
        result = {
            'total': len(receipts),
            'success': 0,
            'failed': 0
        }
        
        for receipt in receipts:
            if generate_receipt_preview(receipt.id):
                result['success'] += 1
            else:
                result['failed'] += 1
        
        logger.info(f"Preview generation complete: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Batch preview generation failed: {e}", exc_info=True)
        return {'total': 0, 'success': 0, 'failed': 0, 'error': str(e)}
