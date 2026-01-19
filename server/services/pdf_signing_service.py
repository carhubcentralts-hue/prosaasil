"""
PDF Signing Service - Embeds digital signatures onto PDF documents

Features:
- Place signature images at specific coordinates on PDF pages
- Support multiple signatures per document
- Support multi-page PDFs
- Generate signed PDF with embedded signatures
"""

import io
import logging
from typing import List, Dict, Tuple, Optional
from PIL import Image
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

logger = logging.getLogger(__name__)


class SignaturePlacement:
    """Represents a signature placement on a PDF"""
    def __init__(
        self,
        page_number: int,  # 0-indexed
        x: float,  # X coordinate (from left)
        y: float,  # Y coordinate (from bottom in PDF coords)
        width: float,
        height: float,
        signature_image: bytes,  # PNG image data
        signer_name: Optional[str] = None
    ):
        self.page_number = page_number
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.signature_image = signature_image
        self.signer_name = signer_name


def create_signature_overlay(
    page_width: float,
    page_height: float,
    signature: SignaturePlacement
) -> io.BytesIO:
    """
    Create a PDF overlay with the signature at the specified position
    
    Args:
        page_width: Width of the PDF page
        page_height: Height of the PDF page
        signature: SignaturePlacement object with position and image data
        
    Returns:
        BytesIO object containing the signature overlay PDF
    """
    packet = io.BytesIO()
    c = canvas.Canvas(packet, pagesize=(page_width, page_height))
    
    try:
        # Load signature image from bytes
        sig_image = Image.open(io.BytesIO(signature.signature_image))
        
        # Convert RGBA to RGB if needed (for PDF compatibility)
        if sig_image.mode == 'RGBA':
            # Create white background and paste the image
            background = Image.new('RGB', sig_image.size, (255, 255, 255))
            background.paste(sig_image, mask=sig_image.split()[3])
            sig_image = background
        elif sig_image.mode != 'RGB':
            sig_image = sig_image.convert('RGB')
        
        # Save to buffer
        img_buffer = io.BytesIO()
        sig_image.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        # Draw the signature on the canvas
        img_reader = ImageReader(img_buffer)
        c.drawImage(
            img_reader,
            signature.x,
            signature.y,
            width=signature.width,
            height=signature.height,
            preserveAspectRatio=True,
            mask='auto'
        )
        
        # Optionally add signer name below the signature
        if signature.signer_name:
            c.setFont("Helvetica", 8)
            c.drawString(
                signature.x,
                signature.y - 12,
                signature.signer_name
            )
        
    except Exception as e:
        logger.error(f"[PDF_SIGN] Error creating signature overlay: {e}")
        raise
    
    c.save()
    packet.seek(0)
    return packet


def embed_signatures_in_pdf(
    pdf_data: bytes,
    signatures: List[SignaturePlacement]
) -> bytes:
    """
    Embed one or more signatures into a PDF document
    
    Args:
        pdf_data: Original PDF as bytes
        signatures: List of SignaturePlacement objects
        
    Returns:
        Signed PDF as bytes
    """
    try:
        # Read the original PDF
        original_pdf = PdfReader(io.BytesIO(pdf_data))
        output_pdf = PdfWriter()
        
        # Group signatures by page
        signatures_by_page: Dict[int, List[SignaturePlacement]] = {}
        for sig in signatures:
            if sig.page_number not in signatures_by_page:
                signatures_by_page[sig.page_number] = []
            signatures_by_page[sig.page_number].append(sig)
        
        # Process each page
        for page_num in range(len(original_pdf.pages)):
            page = original_pdf.pages[page_num]
            
            # Get page dimensions
            media_box = page.mediabox
            page_width = float(media_box.width)
            page_height = float(media_box.height)
            
            # Check if this page has signatures
            if page_num in signatures_by_page:
                for signature in signatures_by_page[page_num]:
                    # Create overlay with signature
                    overlay_pdf = create_signature_overlay(
                        page_width,
                        page_height,
                        signature
                    )
                    
                    # Read overlay and merge with page
                    overlay_reader = PdfReader(overlay_pdf)
                    overlay_page = overlay_reader.pages[0]
                    page.merge_page(overlay_page)
            
            output_pdf.add_page(page)
        
        # Write output to bytes
        output_buffer = io.BytesIO()
        output_pdf.write(output_buffer)
        output_buffer.seek(0)
        
        logger.info(f"[PDF_SIGN] Successfully embedded {len(signatures)} signatures")
        return output_buffer.read()
        
    except Exception as e:
        logger.error(f"[PDF_SIGN] Error embedding signatures: {e}", exc_info=True)
        raise


def get_pdf_info(pdf_data: bytes) -> Dict:
    """
    Get information about a PDF document
    
    Args:
        pdf_data: PDF as bytes
        
    Returns:
        Dictionary with PDF info including page count and dimensions
    """
    try:
        pdf = PdfReader(io.BytesIO(pdf_data))
        pages = []
        
        for i, page in enumerate(pdf.pages):
            media_box = page.mediabox
            pages.append({
                'page_number': i,
                'width': float(media_box.width),
                'height': float(media_box.height),
            })
        
        return {
            'page_count': len(pdf.pages),
            'pages': pages,
            'metadata': pdf.metadata if pdf.metadata else {}
        }
        
    except Exception as e:
        logger.error(f"[PDF_SIGN] Error getting PDF info: {e}")
        raise
