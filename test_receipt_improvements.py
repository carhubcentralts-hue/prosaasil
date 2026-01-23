"""
Test the receipt improvements made for the issue.

This test verifies:
1. Blank image detection works correctly
2. Amount extraction with fallback patterns works
3. Screenshot validation is applied
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO


def test_blank_image_detection():
    """Test that blank/white images are detected correctly"""
    from server.services.receipt_preview_service import is_image_blank_or_white
    from PIL import Image
    
    # Create a white image
    white_img = Image.new('RGB', (100, 100), color='white')
    white_bytes = BytesIO()
    white_img.save(white_bytes, format='PNG')
    white_bytes.seek(0)
    
    # Should detect as blank
    assert is_image_blank_or_white(white_bytes.getvalue()) is True
    
    # Create an image with content
    content_img = Image.new('RGB', (100, 100), color='white')
    # Add some colored pixels
    pixels = content_img.load()
    for i in range(10):
        for j in range(10):
            pixels[i, j] = (255, 0, 0)  # Red square
    
    content_bytes = BytesIO()
    content_img.save(content_bytes, format='PNG')
    content_bytes.seek(0)
    
    # Should NOT detect as blank
    assert is_image_blank_or_white(content_bytes.getvalue()) is False
    
    print("✅ Blank image detection works correctly")


def test_amount_extraction_fallback():
    """Test that amount extraction with fallback patterns works"""
    from server.services.gmail_sync_service import extract_receipt_data
    
    # Test 1: Amount with clear currency
    pdf_text_usd = "Total: $123.45 Thank you for your purchase"
    metadata = {'from_domain': 'stripe.com'}
    result = extract_receipt_data(pdf_text_usd, metadata)
    assert result['amount'] == 123.45
    assert result['currency'] == 'USD'
    print(f"✅ Extracted USD amount: {result['amount']} {result['currency']}")
    
    # Test 2: Amount with ILS
    pdf_text_ils = "סה״כ לתשלום: 456.78 ₪"
    result = extract_receipt_data(pdf_text_ils, metadata)
    assert result['amount'] == 456.78
    assert result['currency'] == 'ILS'
    print(f"✅ Extracted ILS amount: {result['amount']} {result['currency']}")
    
    # Test 3: Amount without clear keywords but with currency symbol
    # This should be caught by the new fallback pattern
    pdf_text_fallback = "Your payment receipt. $ Invoice #123. Amount 99.99"
    result = extract_receipt_data(pdf_text_fallback, metadata)
    # Should extract the amount with fallback
    assert result['amount'] is not None
    assert result['amount'] > 0
    print(f"✅ Extracted amount with fallback: {result['amount']} {result.get('currency')}")


def test_html_amount_extraction_fallback():
    """Test HTML amount extraction with fallback"""
    from server.services.gmail_sync_service import extract_amount_from_html
    
    # Test with HTML containing amount but no clear format
    html_content = """
    <html>
        <body>
            <p>Thank you for your purchase!</p>
            <p>Payment received: $75.50</p>
        </body>
    </html>
    """
    metadata = {'from_domain': 'example.com'}
    result = extract_amount_from_html(html_content, metadata)
    assert result['amount'] == 75.50
    assert result['currency'] == 'USD'
    print(f"✅ Extracted HTML amount: {result['amount']} {result['currency']}")
    
    # Test with fallback - amount appears without keywords
    html_with_currency_only = """
    <html><body>Invoice 123. Dollar amount below. 89.99 Thanks!</body></html>
    """
    result = extract_amount_from_html(html_with_currency_only, metadata)
    # With "dollar" keyword, should detect USD
    assert result['amount'] is not None
    print(f"✅ Extracted HTML amount with fallback: {result['amount']} {result.get('currency')}")


def test_pdf_thumbnail_validation():
    """Test that PDF thumbnails are validated for blank content"""
    from server.services.receipt_preview_service import generate_pdf_thumbnail
    from PIL import Image
    import fitz  # PyMuPDF
    
    # Create a blank PDF
    blank_pdf = fitz.open()
    blank_page = blank_pdf.new_page(width=200, height=200)
    # Leave page white
    blank_pdf_bytes = blank_pdf.tobytes()
    blank_pdf.close()
    
    # Try to generate thumbnail from blank PDF
    thumbnail = generate_pdf_thumbnail(blank_pdf_bytes)
    
    # Should return None because it's blank
    assert thumbnail is None
    print("✅ Blank PDF thumbnail correctly rejected")
    
    # Create a PDF with content
    content_pdf = fitz.open()
    content_page = content_pdf.new_page(width=200, height=200)
    # Add some text
    content_page.insert_text((50, 50), "Receipt #123\nTotal: $100.00", fontsize=12)
    content_pdf_bytes = content_pdf.tobytes()
    content_pdf.close()
    
    # Generate thumbnail
    thumbnail = generate_pdf_thumbnail(content_pdf_bytes)
    
    # Should generate thumbnail successfully
    assert thumbnail is not None
    assert len(thumbnail) > 0
    print("✅ PDF with content generates valid thumbnail")


def test_image_thumbnail_validation():
    """Test that image thumbnails are validated"""
    from server.services.receipt_preview_service import generate_image_thumbnail
    from PIL import Image
    
    # Create white image
    white_img = Image.new('RGB', (200, 200), color='white')
    white_bytes = BytesIO()
    white_img.save(white_bytes, format='PNG')
    
    # Try to generate thumbnail
    thumbnail = generate_image_thumbnail(white_bytes.getvalue(), 'image/png')
    
    # Should return None because it's blank
    assert thumbnail is None
    print("✅ Blank image thumbnail correctly rejected")
    
    # Create image with content
    content_img = Image.new('RGB', (200, 200), color='white')
    pixels = content_img.load()
    for i in range(50, 150):
        for j in range(50, 150):
            pixels[i, j] = (100, 100, 200)  # Blue square
    
    content_bytes = BytesIO()
    content_img.save(content_bytes, format='PNG')
    
    # Generate thumbnail
    thumbnail = generate_image_thumbnail(content_bytes.getvalue(), 'image/png')
    
    # Should generate thumbnail successfully
    assert thumbnail is not None
    assert len(thumbnail) > 0
    print("✅ Image with content generates valid thumbnail")


if __name__ == '__main__':
    print("Testing receipt improvements...")
    print()
    
    print("1. Testing blank image detection...")
    test_blank_image_detection()
    print()
    
    print("2. Testing amount extraction from PDF...")
    test_amount_extraction_fallback()
    print()
    
    print("3. Testing amount extraction from HTML...")
    test_html_amount_extraction_fallback()
    print()
    
    print("4. Testing PDF thumbnail validation...")
    test_pdf_thumbnail_validation()
    print()
    
    print("5. Testing image thumbnail validation...")
    test_image_thumbnail_validation()
    print()
    
    print("=" * 60)
    print("✅ ALL TESTS PASSED!")
    print("=" * 60)
