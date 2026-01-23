"""
Receipt Amount Extractor - Enhanced extraction with vendor-specific adapters

This module provides enhanced amount extraction from receipts with:
- Vendor-specific extraction patterns (Stripe, GitHub, AliExpress, PayPal, etc.)
- Multi-currency support (ILS, USD, EUR)
- Confidence scoring for extraction quality
- Fallback to generic patterns when vendor-specific fails

Priority order:
1. Vendor-specific adapters (highest confidence)
2. Generic currency-based patterns (medium confidence)
3. Fallback to any number (low confidence)
"""

import re
import logging
from typing import Dict, Optional, Tuple
from decimal import Decimal

logger = logging.getLogger(__name__)


# Vendor-specific extraction patterns
VENDOR_ADAPTERS = {
    'stripe.com': {
        'patterns': [
            r'Amount\s+paid[:\s]*\$\s*([\d,]+\.?\d*)',  # Amount paid: $100.00
            r'Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100.00
            r'\$\s*([\d,]+\.?\d*)\s+USD',  # $100.00 USD
        ],
        'currency': 'USD',
        'confidence_boost': 30
    },
    'github.com': {
        'patterns': [
            r'Amount[:\s]*\$\s*([\d,]+\.?\d*)',  # Amount: $100.00
            r'Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100.00
            r'\$\s*([\d,]+\.?\d*)\s+USD',  # $100.00 USD
        ],
        'currency': 'USD',
        'confidence_boost': 30
    },
    'aliexpress.com': {
        'patterns': [
            r'Order\s+Total[:\s]*US\s*\$\s*([\d,]+\.?\d*)',  # Order Total: US $100.00
            r'Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100.00
            r'\$\s*([\d,]+\.?\d*)',  # $100.00
        ],
        'currency': 'USD',
        'confidence_boost': 25
    },
    'paypal.com': {
        'patterns': [
            r'Amount[:\s]*\$\s*([\d,]+\.?\d*)\s+USD',  # Amount: $100.00 USD
            r'Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100.00
            r'\$\s*([\d,]+\.?\d*)',  # $100.00
        ],
        'currency': 'USD',
        'confidence_boost': 30
    },
    'amazon.com': {
        'patterns': [
            r'Order\s+Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Order Total: $100.00
            r'Grand\s+Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Grand Total: $100.00
            r'\$\s*([\d,]+\.?\d*)',  # $100.00
        ],
        'currency': 'USD',
        'confidence_boost': 25
    },
    'apple.com': {
        'patterns': [
            r'Amount[:\s]*\$\s*([\d,]+\.?\d*)',  # Amount: $100.00
            r'Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100.00
        ],
        'currency': 'USD',
        'confidence_boost': 30
    },
    'google.com': {
        'patterns': [
            r'Amount[:\s]*\$\s*([\d,]+\.?\d*)',  # Amount: $100.00
            r'Total[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100.00
        ],
        'currency': 'USD',
        'confidence_boost': 30
    },
    # Israeli vendors
    'greeninvoice.co.il': {
        'patterns': [
            r'(?:סה"כ|סהכ|לתשלום)[:\s]*₪?\s*([\d,]+\.?\d*)\s*₪',  # סה"כ: ₪100.00
            r'₪\s*([\d,]+\.?\d*)',  # ₪100.00
        ],
        'currency': 'ILS',
        'confidence_boost': 30
    },
    'icount.co.il': {
        'patterns': [
            r'(?:סה"כ|סהכ|לתשלום)[:\s]*₪?\s*([\d,]+\.?\d*)\s*₪',
            r'₪\s*([\d,]+\.?\d*)',
        ],
        'currency': 'ILS',
        'confidence_boost': 30
    },
}


def extract_amount_with_vendor_adapter(
    text: str,
    vendor_domain: Optional[str],
    subject: Optional[str] = None
) -> Dict:
    """
    Extract amount using vendor-specific adapter if available
    
    Args:
        text: Text content (from PDF, HTML, or email body)
        vendor_domain: Vendor domain (e.g., 'stripe.com', 'github.com')
        subject: Email subject line (optional, for fallback)
        
    Returns:
        Dict with keys:
        - amount: Decimal or None
        - currency: str or None
        - confidence: int (0-100)
        - source: str (vendor_adapter, generic, subject, none)
    """
    result = {
        'amount': None,
        'currency': None,
        'confidence': 0,
        'source': 'none'
    }
    
    if not text and not subject:
        return result
    
    # Try vendor-specific adapter first
    if vendor_domain:
        for domain_key, adapter in VENDOR_ADAPTERS.items():
            if domain_key in vendor_domain.lower():
                logger.debug(f"Trying vendor adapter for: {domain_key}")
                
                for pattern in adapter['patterns']:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        try:
                            amount_str = match.group(1).replace(',', '')
                            amount = Decimal(amount_str)
                            
                            result['amount'] = amount
                            result['currency'] = adapter['currency']
                            result['confidence'] = 70 + adapter['confidence_boost']
                            result['source'] = 'vendor_adapter'
                            
                            logger.info(
                                f"✓ Vendor adapter extracted: {amount} {adapter['currency']} "
                                f"from {domain_key} (confidence: {result['confidence']})"
                            )
                            return result
                        except ValueError as e:
                            logger.debug(f"Failed to parse amount from vendor pattern: {e}")
                            continue
    
    # Fallback to generic currency detection (existing logic from gmail_sync_service)
    generic_result = _extract_amount_generic(text)
    if generic_result['amount']:
        result.update(generic_result)
        return result
    
    # Last resort: try subject line
    if subject:
        subject_result = _extract_amount_from_subject(subject)
        if subject_result['amount']:
            result.update(subject_result)
            return result
    
    return result


def _extract_amount_generic(text: str) -> Dict:
    """
    Generic amount extraction using currency symbols
    
    This is the existing logic from gmail_sync_service.py
    """
    result = {
        'amount': None,
        'currency': None,
        'confidence': 50,
        'source': 'generic'
    }
    
    if not text:
        return result
    
    # Detect currency by counting symbols
    currency_scores = {
        'ILS': len(re.findall(r'₪', text)) * 10 + len(re.findall(r'\b(?:ILS|ils|ש"ח)\b', text, re.IGNORECASE)) * 5,
        'USD': len(re.findall(r'\$', text)) * 10 + len(re.findall(r'\b(?:USD|usd|dollar)\b', text, re.IGNORECASE)) * 5,
        'EUR': len(re.findall(r'€', text)) * 10 + len(re.findall(r'\b(?:EUR|eur|euro)\b', text, re.IGNORECASE)) * 5,
    }
    
    detected_currency = max(currency_scores, key=currency_scores.get) if max(currency_scores.values()) > 0 else None
    
    # Try currency-specific patterns
    patterns_by_currency = {
        'USD': [
            r'(?:total|grand total|amount due)[:\s]*\$\s*([\d,]+\.?\d*)',
            r'\$\s*([\d,]+\.?\d*)',
        ],
        'ILS': [
            r'(?:סה"כ|סהכ|לתשלום|total)[:\s]*₪?\s*([\d,]+\.?\d*)\s*₪',
            r'₪\s*([\d,]+\.?\d*)',
        ],
        'EUR': [
            r'(?:total|amount)[:\s]*€\s*([\d,]+\.?\d*)',
            r'€\s*([\d,]+\.?\d*)',
        ],
    }
    
    if detected_currency:
        for pattern in patterns_by_currency.get(detected_currency, []):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    result['amount'] = Decimal(amount_str)
                    result['currency'] = detected_currency
                    logger.debug(f"Generic extraction: {result['amount']} {result['currency']}")
                    return result
                except ValueError:
                    continue
    
    return result


def _extract_amount_from_subject(subject: str) -> Dict:
    """
    Last resort: extract from subject line
    """
    result = {
        'amount': None,
        'currency': None,
        'confidence': 30,
        'source': 'subject'
    }
    
    # Try common subject patterns
    patterns = [
        (r'\$\s*([\d,]+\.?\d*)', 'USD'),
        (r'₪\s*([\d,]+\.?\d*)', 'ILS'),
        (r'€\s*([\d,]+\.?\d*)', 'EUR'),
    ]
    
    for pattern, currency in patterns:
        match = re.search(pattern, subject)
        if match:
            try:
                amount_str = match.group(1).replace(',', '')
                result['amount'] = Decimal(amount_str)
                result['currency'] = currency
                logger.debug(f"Subject extraction: {result['amount']} {result['currency']}")
                return result
            except ValueError:
                continue
    
    return result


def extract_receipt_amount(
    pdf_text: Optional[str] = None,
    html_content: Optional[str] = None,
    subject: Optional[str] = None,
    vendor_domain: Optional[str] = None
) -> Dict:
    """
    Main extraction function with priority order
    
    Priority:
    1. PDF text with vendor adapter
    2. HTML with vendor adapter  
    3. PDF text with generic patterns
    4. HTML with generic patterns
    5. Subject line
    
    Args:
        pdf_text: Text extracted from PDF attachment
        html_content: HTML email content
        subject: Email subject
        vendor_domain: Sender domain for vendor-specific extraction
        
    Returns:
        Dict with amount, currency, confidence, source
    """
    # Priority 1 & 2: Try vendor adapter on PDF and HTML
    if pdf_text:
        result = extract_amount_with_vendor_adapter(pdf_text, vendor_domain, subject)
        if result['amount']:
            return result
    
    if html_content:
        # Strip HTML tags for text extraction
        html_text = re.sub(r'<[^>]+>', ' ', html_content)
        result = extract_amount_with_vendor_adapter(html_text, vendor_domain, subject)
        if result['amount']:
            return result
    
    # If no result yet, return the last attempt (which includes fallbacks)
    return {
        'amount': None,
        'currency': None,
        'confidence': 0,
        'source': 'none'
    }
