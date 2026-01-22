"""
Gmail Sync Service - Fetches and processes receipts from Gmail

Features:
- OAuth token management with automatic refresh
- Email fetching with receipt detection
- PDF text extraction for confidence scoring
- Integration with unified attachment service
- Rate limiting and error handling
- Screenshot generation for emails without attachments

Receipt Detection Algorithm:
1. Quick filter: Emails with OR without attachments
2. Subject/sender keyword matching (קבלה, חשבונית, invoice, receipt)
3. Known vendor domain matching
4. PDF text extraction for confidence scoring
5. Auto-screenshot generation if no attachment

Security:
- Encrypted refresh tokens
- No raw token logging
- Multi-tenant isolation
"""

import logging
import base64
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from email.utils import parsedate_to_datetime

# Try importing Playwright at module level for efficiency
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger(__name__)

# Environment configuration
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY', os.getenv('FERNET_KEY', ''))
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')

# Run-to-completion mode: If True, ignore time limits and run until done
RUN_TO_COMPLETION = os.getenv('RUN_TO_COMPLETION', 'false').lower() in ('true', '1', 'yes')

# Batch limits to prevent crashes on large syncs (only used when RUN_TO_COMPLETION=False)
MAX_MESSAGES_PER_RUN = 500  # Process max 500 messages per run
try:
    MAX_SECONDS_PER_RUN = int(os.getenv('MAX_SECONDS_PER_RUN', '120'))
    if MAX_SECONDS_PER_RUN < 10:
        logger.warning(f"MAX_SECONDS_PER_RUN ({MAX_SECONDS_PER_RUN}) too low, using 10")
        MAX_SECONDS_PER_RUN = 10
except (ValueError, TypeError):
    logger.warning(f"Invalid MAX_SECONDS_PER_RUN value, using default 120")
    MAX_SECONDS_PER_RUN = 120  # Default 2 minutes per run

# Semaphore to limit concurrent Playwright instances
playwright_semaphore = threading.Semaphore(2)  # Max 2 concurrent browsers


def strip_null_bytes(obj):
    """
    Recursively strip NULL bytes (\x00) from all strings
    
    This is CRITICAL - PostgreSQL cannot store \x00 in TEXT/JSON columns
    and will crash with: psycopg2.errors.UntranslatableCharacter
    
    Args:
        obj: Any Python object (dict, list, str, int, float, None, etc.)
        
    Returns:
        Cleaned version of the object with all \x00 removed
    """
    if obj is None:
        return None
    if isinstance(obj, str):
        # Remove NULL bytes and literal \u0000 sequences
        return obj.replace('\x00', '').replace('\\u0000', '').replace('\ufffd', '')
    if isinstance(obj, list):
        return [strip_null_bytes(x) for x in obj]
    if isinstance(obj, dict):
        return {strip_null_bytes(k): strip_null_bytes(v) for k, v in obj.items()}
    if isinstance(obj, (int, float, bool)):
        return obj
    # For other types, try to convert to string and clean
    try:
        return strip_null_bytes(str(obj))
    except Exception:
        return None

# Keep old name for compatibility but use new function
sanitize_for_postgres = strip_null_bytes

# Receipt detection keywords (Hebrew + English) - EXPANDED for better coverage
RECEIPT_KEYWORDS = [
    # Hebrew - expanded
    'קבלה', 'חשבונית', 'חשבונית מס', 'קבלת תשלום', 'אישור תשלום',
    'תשלום התקבל', 'תודה על ההזמנה', 'הזמנה מאושרת', 'חיוב',
    'סה"כ לתשלום', 'תשלום בוצע', 'עסקה מאושרת', 'קניה', 'רכישה',
    # English - expanded  
    'invoice', 'receipt', 'payment confirmation', 'tax invoice',
    'order confirmation', 'payment receipt', 'billing statement',
    'payment successful', 'thank you for your order', 'purchase',
    'transaction', 'your order', 'charge', 'payment received',
    'invoice number', 'receipt number', 'order number'
]

# Known receipt sender domains - EXPANDED
KNOWN_RECEIPT_DOMAINS = [
    # Payment processors
    'paypal.com', 'stripe.com', 'square.com', 'payoneer.com',
    # Israeli billing
    'greeninvoice.co.il', 'icount.co.il', 'invoice4u.co.il', 'meshulam.co.il',
    'meshulam-pay.co.il', 'tranzila.com', 'cardcom.co.il', 'payplus.co.il',
    # E-commerce
    'amazon.com', 'ebay.com', 'aliexpress.com', 'alibaba.com',
    'wish.com', 'etsy.com', 'shopify.com',
    # Tech companies
    'apple.com', 'google.com', 'microsoft.com', 'dropbox.com',
    'github.com', 'slack.com', 'zoom.us', 'notion.so',
    # Food delivery
    'uber.com', 'lyft.com', 'wolt.com', 'doordash.com', '10bis.co.il',
    'tenbis.co.il', 'deliveroo.com', 'foodora.com',
    # Israeli services
    'pelephone.co.il', 'partner.co.il', 'cellcom.co.il', 'golan.co.il',
    'bezeq.co.il', 'hot.net.il', 'yes.co.il', 'iec.co.il',
    # Israeli retail
    'zap.co.il', 'ksp.co.il', 'ivory.co.il', 'bug.co.il', 'shufersal.co.il',
    'rami-levy.co.il', 'victory.co.il', 'mega.co.il',
    # Travel
    'booking.com', 'airbnb.com', 'hotels.com', 'expedia.com',
    'elal.co.il', 'arkia.co.il', 'israir.co.il'
]

# PDF receipt indicators (for confidence scoring) - EXPANDED
PDF_RECEIPT_INDICATORS = [
    # Hebrew
    'סה"כ', "סה''כ", 'סהכ', 'מע"מ', "מע''מ", 'מעמ',
    'חשבונית מס', 'קבלה מס', 'תאריך', 'מספר חשבונית',
    'לתשלום', 'שולם', 'תודה על הקנייה', 'תודה על ההזמנה',
    'ח.פ', 'ע.מ', 'כתובת', 'טלפון', 'אתר',
    # English
    'total', 'subtotal', 'tax', 'vat', 'grand total',
    'invoice number', 'receipt number', 'order number',
    'amount due', 'paid', 'payment received',
    'thank you for your purchase', 'thank you for your order',
    'date', 'address', 'phone', 'email', 'website'
]

# Minimum confidence to save as receipt - LOWERED to catch more receipts!
MIN_CONFIDENCE = 5  # Super low threshold - catch everything that might be a receipt
AUTO_APPROVE_THRESHOLD = 50  # Above this = auto-approve, below = pending_review
REVIEW_THRESHOLD = 30  # Deprecated - using AUTO_APPROVE_THRESHOLD instead
ATTACHMENT_CONFIDENCE_BOOST = 10  # Increased boost for attachments
MAX_SNIPPET_MATCHES = 3  # Maximum number of snippet indicators to count

# Error message truncation (to fit in DB error_message column)
ERROR_MESSAGE_MAX_LENGTH = 450  # Leave room for message_id prefix


def encrypt_token(token: str) -> str:
    """
    Encrypt a token for storage using Fernet symmetric encryption.
    
    Security: In production, ENCRYPTION_KEY must be set to a valid Fernet key.
    In development, falls back to base64 with a warning.
    """
    if not ENCRYPTION_KEY:
        logger.warning("⚠️ SECURITY: No ENCRYPTION_KEY set - tokens stored with base64 encoding only!")
        return base64.b64encode(token.encode()).decode()
    
    try:
        from cryptography.fernet import Fernet, InvalidToken
        # Validate key format
        key = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
        f = Fernet(key)
        return f.encrypt(token.encode()).decode()
    except ImportError:
        logger.error("cryptography package not installed - falling back to base64 (NOT SECURE)")
        return base64.b64encode(token.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed (invalid key format?): {e}")
        raise ValueError("Invalid ENCRYPTION_KEY - must be a valid Fernet key")


def decrypt_token(encrypted: str) -> str:
    """
    Decrypt a stored token.
    
    Returns empty string if encrypted is empty.
    Raises ValueError if decryption fails with proper key.
    """
    if not encrypted:
        return ''
    
    if not ENCRYPTION_KEY:
        # No key set - assume base64 encoded
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except Exception:
            return ''
    
    try:
        from cryptography.fernet import Fernet, InvalidToken
        key = ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY
        f = Fernet(key)
        return f.decrypt(encrypted.encode()).decode()
    except ImportError:
        # cryptography not installed - try base64
        return base64.b64decode(encrypted.encode()).decode()
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        # Don't expose encrypted data, just return empty
        return ''


def mask_pii(text: str, mask_char: str = '*') -> str:
    """
    Mask PII (Personally Identifiable Information) in text for safe logging
    
    SECURITY: Never log full emails, phone numbers, or credit card numbers
    
    Args:
        text: Text that may contain PII
        mask_char: Character to use for masking
        
    Returns:
        Text with PII masked
    """
    if not text:
        return text
    
    # Mask email addresses (keep first 2 chars + domain)
    text = re.sub(r'\b([a-zA-Z0-9]{1,2})[a-zA-Z0-9._%+-]*@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
                  r'\1***@\2', text)
    
    # Mask phone numbers (keep country code if present)
    text = re.sub(r'\b(\+?\d{1,3})[- ]?\d{2,3}[- ]?\d{3,4}[- ]?\d{3,4}\b', 
                  r'\1-***-****', text)
    
    # Mask credit card numbers (keep first 4 and last 4)
    text = re.sub(r'\b(\d{4})[\s-]?\d{4}[\s-]?\d{4}[\s-]?(\d{4})\b', 
                  r'\1-****-****-\2', text)
    
    # Mask Israeli ID numbers (9 digits)
    text = re.sub(r'\b(\d{2})\d{5}(\d{2})\b', 
                  r'\1*****\2', text)
    
    return text


def get_safe_log_metadata(metadata: dict) -> dict:
    """
    Extract safe metadata for logging (no PII)
    
    Args:
        metadata: Full metadata dict
        
    Returns:
        Safe dict with PII masked
    """
    safe = {}
    
    # Safe fields (IDs, booleans, counts)
    for key in ['has_attachment', 'matched_keywords']:
        if key in metadata:
            safe[key] = metadata[key]
    
    # Mask PII in text fields
    if 'subject' in metadata:
        safe['subject'] = mask_pii(metadata['subject'][:50])
    
    if 'from_domain' in metadata:
        safe['from_domain'] = metadata['from_domain']  # Domain is safe
    
    if 'from_email' in metadata:
        safe['from_email'] = mask_pii(metadata['from_email'])
    
    return safe


def get_gmail_service(business_id: int):
    """
    Get authenticated Gmail API service for a business
    
    Args:
        business_id: Business ID to get Gmail connection for
        
    Returns:
        Google Gmail API service object
        
    Raises:
        ValueError: If no valid Gmail connection exists
    """
    from server.db import db
    from server.models_sql import GmailConnection
    
    connection = GmailConnection.query.filter_by(
        business_id=business_id,
        status='connected'
    ).first()
    
    if not connection:
        raise ValueError("No Gmail connection found")
    
    refresh_token = decrypt_token(connection.refresh_token_encrypted)
    if not refresh_token:
        raise ValueError("Invalid refresh token")
    
    try:
        import requests
        
        # Refresh access token
        token_response = requests.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': GOOGLE_CLIENT_ID,
                'client_secret': GOOGLE_CLIENT_SECRET,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            },
            timeout=30
        )
        
        if token_response.status_code != 200:
            logger.error(f"Token refresh failed: {token_response.status_code}")
            connection.status = 'error'
            connection.error_message = 'Token refresh failed'
            db.session.commit()
            raise ValueError("Token refresh failed")
        
        tokens = token_response.json()
        access_token = tokens.get('access_token')
        
        if not access_token:
            raise ValueError("No access token received")
        
        # Return a simple API wrapper instead of full Google client library
        return GmailApiClient(access_token)
        
    except Exception as e:
        logger.error(f"Failed to get Gmail service: {e}")
        raise


class GmailApiClient:
    """Simple Gmail API client using REST"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = 'https://gmail.googleapis.com/gmail/v1'
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make API request"""
        import requests
        
        url = f"{self.base_url}{endpoint}"
        kwargs['headers'] = self.headers
        kwargs['timeout'] = 30
        
        response = requests.request(method, url, **kwargs)
        
        if response.status_code >= 400:
            logger.error(f"Gmail API error: {response.status_code} - {response.text[:200]}")
            raise Exception(f"Gmail API error: {response.status_code}")
        
        return response.json()
    
    def list_messages(self, query: str = '', max_results: int = None, page_token: str = None) -> dict:
        """
        List messages matching query with pagination support
        
        Args:
            query: Gmail search query
            max_results: Maximum results per page (None = API default, usually 100)
            page_token: Page token for pagination
            
        Returns:
            Dict with 'messages' list and optional 'nextPageToken'
        """
        params = {'q': query}
        
        if max_results:
            params['maxResults'] = min(max_results, 500)  # Gmail API max is 500
        
        if page_token:
            params['pageToken'] = page_token
        
        result = self._request('GET', '/users/me/messages', params=params)
        return result
    
    def get_message(self, message_id: str, format: str = 'full') -> dict:
        """Get single message"""
        return self._request('GET', f'/users/me/messages/{message_id}', params={'format': format})
    
    def get_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Get attachment data"""
        result = self._request('GET', f'/users/me/messages/{message_id}/attachments/{attachment_id}')
        
        data = result.get('data', '')
        # Gmail uses URL-safe base64
        return base64.urlsafe_b64decode(data)


def extract_all_attachments(message: dict) -> list:
    """
    Recursively extract ALL attachments from Gmail message - IMPROVED!
    
    Gmail uses nested multipart structure. We recurse through ALL parts.
    CRITICAL: Must handle all Gmail attachment patterns correctly!
    
    SECURITY: Filters out inline images (tracking pixels, signatures, logos)
    to avoid bloating storage and processing.
    
    Args:
        message: Gmail message object
        
    Returns:
        List of attachment dicts with {id, filename, mime_type, size, disposition}
    """
    attachments = []
    
    def recurse_parts(parts):
        """Recursively process message parts"""
        if not parts:
            return
        
        for part in parts:
            mime_type = part.get('mimeType', '')
            filename = part.get('filename', '')
            body = part.get('body', {})
            attachment_id = body.get('attachmentId')
            size = body.get('size', 0)
            
            # Check Content-Disposition header to distinguish attachment from inline
            headers = part.get('headers', [])
            content_disposition = None
            for header in headers:
                if header.get('name', '').lower() == 'content-disposition':
                    content_disposition = header.get('value', '').lower()
                    break
            
            # IMPROVED: Check multiple conditions for attachments
            # 1. Has explicit attachmentId
            # 2. Has filename and size > 0
            # 3. Is PDF/image mime type (even without filename)
            is_attachment = False
            
            if attachment_id:
                is_attachment = True
            elif filename and size > 0:
                is_attachment = True
            elif mime_type in ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/gif']:
                # PDF or image without filename - still an attachment!
                is_attachment = True
                if not filename:
                    # Generate filename from mime type
                    ext = mime_type.split('/')[-1]
                    filename = f'attachment.{ext}'
            
            # SECURITY FILTER: Skip inline images that are likely tracking pixels/logos
            if is_attachment and content_disposition and 'inline' in content_disposition:
                # Skip small inline images (< 5KB) - likely tracking pixels or signatures
                if mime_type.startswith('image/') and size < 5120:  # 5KB threshold
                    logger.debug(f"🔒 Skipping small inline image: {filename} ({size} bytes)")
                    is_attachment = False
            
            if is_attachment:
                attachments.append({
                    'id': attachment_id,
                    'filename': filename or 'attachment',
                    'mime_type': mime_type,
                    'size': size,
                    'disposition': content_disposition or 'attachment'
                })
                logger.debug(f"📎 Found attachment: {filename} ({mime_type}, {size} bytes, disposition={content_disposition})")
            
            # Recurse into nested parts (multipart/alternative, etc.)
            if 'parts' in part:
                recurse_parts(part['parts'])
    
    # Start recursion from payload
    payload = message.get('payload', {})
    if 'parts' in payload:
        recurse_parts(payload['parts'])
    else:
        # Single-part message - check if it's an attachment
        mime_type = payload.get('mimeType', '')
        body = payload.get('body', {})
        attachment_id = body.get('attachmentId')
        size = body.get('size', 0)
        
        if attachment_id or mime_type in ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']:
            filename = payload.get('filename', f'attachment.{mime_type.split("/")[-1]}')
            attachments.append({
                'id': attachment_id,
                'filename': filename,
                'mime_type': mime_type,
                'size': size,
                'disposition': 'attachment'
            })
            logger.debug(f"📎 Found single-part attachment: {filename}")
    
    if attachments:
        logger.info(f"📎 Total attachments found: {len(attachments)}")
    
    return attachments


def check_is_receipt_email(message: dict) -> Tuple[bool, int, dict]:
    """
    Check if an email is likely to contain a receipt
    
    IMPROVED DETECTION LOGIC:
    - Lower thresholds to catch more receipts
    - Analyze full email content, not just subject
    - Give high weight to attachments
    - Look for amounts in snippet
    
    Args:
        message: Gmail message object
        
    Returns:
        (is_receipt, confidence, metadata)
    """
    confidence = 0
    metadata = {}
    
    # Extract headers
    headers = {h['name'].lower(): h['value'] for h in message.get('payload', {}).get('headers', [])}
    
    subject = headers.get('subject', '')
    from_header = headers.get('from', '')
    
    metadata['subject'] = subject
    metadata['from'] = from_header
    
    # Extract sender email/domain
    from_email_match = re.search(r'<([^>]+)>', from_header)
    from_email = from_email_match.group(1) if from_email_match else from_header
    from_domain = from_email.split('@')[-1].lower() if '@' in from_email else ''
    
    metadata['from_email'] = from_email
    metadata['from_domain'] = from_domain
    
    # Extract received date from email
    date_header = headers.get('date', '')
    metadata['date'] = date_header
    
    
    # Use recursive attachment extraction
    attachments_list = extract_all_attachments(message)
    attachments = []
    has_pdf = False
    has_image = False
    for att in attachments_list:
        if att['mime_type'] in ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']:
            attachments.append(att)
            if att['mime_type'] == 'application/pdf':
                has_pdf = True
            else:
                has_image = True
    
    metadata['attachments'] = attachments
    metadata['has_attachment'] = has_pdf or has_image
    
    # ==================================================================================
    # MASTER INSTRUCTION RULE 1: ANY ATTACHMENT = MUST PROCESS (NO EXCEPTIONS!)
    # ==================================================================================
    # If email has ANY attachment (PDF or image), it MUST be processed.
    # No keyword checks, no confidence thresholds - attachment presence is absolute.
    if has_pdf or has_image:
        logger.info(f"📎 RULE 1: Email has attachment - MUST PROCESS (confidence=100)")
        return True, 100, metadata  # Force processing with max confidence
    
    # If no attachment, use keyword-based detection for other receipt types
    # (e.g., plain text receipts, embedded HTML receipts)
    
    # Check for receipt keywords in subject/content
    subject_lower = subject.lower()
    matched_keywords = []
    
    # Check subject for keywords
    for keyword in RECEIPT_KEYWORDS:
        if keyword.lower() in subject_lower:
            matched_keywords.append(keyword)
    
    # If we have receipt keywords, it's likely a receipt even without attachment
    if matched_keywords:
        confidence += 40  # Strong indicator
        metadata['matched_keywords'] = matched_keywords
    
    # Check sender domain
    if from_domain in KNOWN_RECEIPT_DOMAINS:
        confidence += 40  # Increased from 35
    
    # Extract email snippet for additional analysis
    snippet = message.get('snippet', '').lower()
    metadata['snippet'] = snippet
    
    # IMPROVED: Check snippet for receipt indicators (amounts, payment terms)
    snippet_indicators = [
        ('total', 10), ('amount', 10), ('סכום', 10), ('סה"כ', 10),
        ('payment', 10), ('תשלום', 10), ('paid', 10), ('שולם', 10),
        ('₪', 15), ('$', 15), ('€', 15), ('USD', 12), ('ILS', 12), ('EUR', 12),  # Currency is STRONG indicator
        ('invoice', 15), ('חשבונית', 15), ('receipt', 15), ('קבלה', 15),
        ('order', 10), ('הזמנה', 10), ('purchase', 10), ('רכישה', 10),
        ('thank you', 12), ('תודה', 12), ('confirmation', 12), ('אישור', 12),
    ]
    snippet_matches = 0
    for indicator, points in snippet_indicators:
        if indicator in snippet:
            confidence += points
            snippet_matches += 1
            # Allow multiple matches for better detection
            if snippet_matches >= MAX_SNIPPET_MATCHES:
                break
    
    # Also give benefit of doubt if we have keywords
    if matched_keywords:
        if confidence < MIN_CONFIDENCE:
            confidence = MIN_CONFIDENCE + 5  # Small boost
            logger.info(f"🔑 Boosted confidence to {confidence} due to keywords: {matched_keywords}")
    
    # NEW: If snippet contains currency symbols, likely a receipt
    if any(symbol in snippet for symbol in ['₪', '$', '€', 'USD', 'ILS', 'EUR']):
        confidence += 15
        logger.info(f"💰 Found currency in snippet, confidence now {confidence}")
    
    # Lower threshold - accept almost anything that looks like a receipt
    # Philosophy: Better to let user review/reject than to miss receipts! (Rule 6)
    is_receipt = confidence >= MIN_CONFIDENCE
    
    logger.info(f"📧 Receipt detection: is_receipt={is_receipt}, confidence={confidence}, has_attachment=False, keywords={len(matched_keywords)}")
    
    return is_receipt, confidence, metadata


def extract_pdf_text(pdf_data: bytes, max_pages: int = 2) -> str:
    """
    Extract text from PDF for receipt validation
    
    Args:
        pdf_data: Raw PDF bytes
        max_pages: Maximum pages to extract (receipts are usually 1-2 pages)
        
    Returns:
        Extracted text
    """
    try:
        from io import BytesIO
        
        # Try PyPDF2 first
        try:
            import PyPDF2
            
            reader = PyPDF2.PdfReader(BytesIO(pdf_data))
            text = ''
            
            for i, page in enumerate(reader.pages[:max_pages]):
                text += page.extract_text() or ''
            
            return text.strip()
        except ImportError:
            pass
        
        # Try pdfminer as fallback
        try:
            from pdfminer.high_level import extract_text_to_fp
            from pdfminer.layout import LAParams
            from io import StringIO
            
            output = StringIO()
            extract_text_to_fp(BytesIO(pdf_data), output, laparams=LAParams())
            return output.getvalue().strip()
        except ImportError:
            pass
        
        logger.warning("No PDF library available - skipping text extraction")
        return ''
        
    except Exception as e:
        logger.warning(f"PDF text extraction failed: {e}")
        return ''


def calculate_pdf_confidence(pdf_text: str) -> int:
    """
    Calculate confidence score based on PDF content
    
    Args:
        pdf_text: Extracted PDF text
        
    Returns:
        Confidence score 0-100
    """
    if not pdf_text:
        return 0
    
    text_lower = pdf_text.lower()
    score = 0
    
    # Check for receipt indicators
    for indicator in PDF_RECEIPT_INDICATORS:
        if indicator.lower() in text_lower:
            score += 10
    
    # Check for amount patterns (₪, $, numbers)
    if re.search(r'₪\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*₪', pdf_text):
        score += 15
    if re.search(r'\$\s*[\d,]+\.?\d*|[\d,]+\.?\d*\s*\$', pdf_text):
        score += 10
    
    # Check for date patterns
    if re.search(r'\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}', pdf_text):
        score += 10
    
    # Check for invoice/receipt number patterns
    if re.search(r'(invoice|receipt|חשבונית|קבלה)\s*#?\s*:?\s*\d+', text_lower):
        score += 15
    
    return min(score, 100)


def extract_receipt_data(pdf_text: str, metadata: dict) -> dict:
    """
    Extract structured data from receipt
    
    IMPROVED: Detects currency FIRST by looking for symbols/keywords,
    then extracts amount based on detected currency.
    This prevents USD receipts from being incorrectly labeled as ILS.
    
    Args:
        pdf_text: Extracted PDF text
        metadata: Email metadata
        
    Returns:
        Extracted receipt data
    """
    data = {
        'vendor_name': None,
        'amount': None,
        'currency': None,  # Don't default to any currency - will be detected or left as None
        'invoice_number': None,
        'invoice_date': None
    }
    
    # Try to extract vendor from sender domain
    from_domain = metadata.get('from_domain', '')
    if from_domain:
        # Clean up domain to get vendor name
        vendor = from_domain.replace('.co.il', '').replace('.com', '').replace('.net', '')
        vendor = vendor.replace('.', ' ').title()
        data['vendor_name'] = vendor
    
    if not pdf_text:
        return data
    
    # NEW LOGIC: Detect currency FIRST by scanning for currency symbols/keywords
    # Count occurrences of each currency indicator
    currency_scores = {
        'ILS': 0,
        'USD': 0,
        'EUR': 0
    }
    
    # Check for currency symbols (most reliable)
    currency_scores['ILS'] += len(re.findall(r'₪', pdf_text)) * 10
    currency_scores['USD'] += len(re.findall(r'\$', pdf_text)) * 10
    currency_scores['EUR'] += len(re.findall(r'€', pdf_text)) * 10
    
    # Check for currency keywords
    currency_scores['ILS'] += len(re.findall(r'\b(?:ILS|ils|ש"ח|שקל|שקלים)\b', pdf_text, re.IGNORECASE)) * 5
    currency_scores['USD'] += len(re.findall(r'\b(?:USD|usd|dollar|dollars)\b', pdf_text, re.IGNORECASE)) * 5
    currency_scores['EUR'] += len(re.findall(r'\b(?:EUR|eur|euro|euros)\b', pdf_text, re.IGNORECASE)) * 5
    
    # Determine most likely currency
    detected_currency = None
    max_score = max(currency_scores.values())
    if max_score > 0:
        detected_currency = max(currency_scores, key=currency_scores.get)
        logger.debug(f"Currency detection scores: {currency_scores} -> detected: {detected_currency}")
    
    # Extract amount based on detected currency
    amount_found = False
    
    if detected_currency == 'USD' or (detected_currency is None and currency_scores['USD'] == max_score):
        # Try USD patterns first if USD detected or no clear currency
        # Priority 1: Total/Grand Total with $ (most reliable)
        usd_patterns_priority = [
            r'(?:total|grand total|amount due)[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100
        ]
        
        for pattern in usd_patterns_priority:
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    data['amount'] = float(amount_str)
                    data['currency'] = 'USD'
                    amount_found = True
                    break
                except (ValueError, IndexError):
                    pass
        
        # Priority 2: Other USD patterns
        if not amount_found:
            usd_patterns = [
                r'\$\s*([\d,]+\.?\d*)',  # $100 or $100.50
                r'([\d,]+\.?\d*)\s*\$',  # 100$ or 100.50$
                r'([\d,]+\.?\d*)\s+(?:USD|usd)',  # 100 USD or 100 usd
                r'(?:USD|usd)[:\s]*([\d,]+\.?\d*)',  # USD: 100 or USD 100
            ]
            
            for pattern in usd_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    try:
                        amount_str = match.group(1).replace(',', '')
                        data['amount'] = float(amount_str)
                        data['currency'] = 'USD'
                        amount_found = True
                        break
                    except (ValueError, IndexError):
                        pass
    
    if not amount_found and (detected_currency == 'ILS' or detected_currency is None):
        # Try ILS patterns
        # Priority 1: Total keywords with ₪
        ils_patterns_priority = [
            r'(?:סה"כ|סהכ|לתשלום|total|amount due)[:\s]*₪?\s*([\d,]+\.?\d*)\s*₪',  # Hebrew/English keywords with ₪
        ]
        
        for pattern in ils_patterns_priority:
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    data['amount'] = float(amount_str)
                    data['currency'] = 'ILS'
                    amount_found = True
                    break
                except (ValueError, IndexError):
                    pass
        
        # Priority 2: Other ILS patterns
        if not amount_found:
            ils_patterns = [
                r'₪\s*([\d,]+\.?\d*)',  # ₪100 or ₪100.50
                r'([\d,]+\.?\d*)\s*₪',  # 100₪ or 100.50₪
                r'(?:ILS|ils|ש"ח)[:\s]*([\d,]+\.?\d*)',  # ILS: 100 or ש"ח: 100
                r'(?:סה"כ|סהכ|לתשלום|סכום)[:\s]*([\d,]+\.?\d*)',  # Hebrew keywords without ₪
            ]
        
            for pattern in ils_patterns:
                match = re.search(pattern, pdf_text, re.IGNORECASE)
                if match:
                    try:
                        amount_str = match.group(1).replace(',', '')
                        data['amount'] = float(amount_str)
                        data['currency'] = 'ILS'
                        amount_found = True
                        break
                    except (ValueError, IndexError):
                        pass
    
    if not amount_found and detected_currency == 'EUR':
        # Try EUR patterns
        eur_patterns = [
            r'€\s*([\d,]+\.?\d*)',  # €100 or €100.50
            r'([\d,]+\.?\d*)\s*€',  # 100€ or 100.50€
            r'(?:EUR|eur)[:\s]+([\d,]+\.?\d*)',  # EUR: 100
            r'(?:total|amount|sum|subtotal|grand total)[:\s]*€\s*([\d,]+\.?\d*)',  # Total: €100
        ]
        
        for pattern in eur_patterns:
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    data['amount'] = float(amount_str)
                    data['currency'] = 'EUR'
                    amount_found = True
                    break
                except (ValueError, IndexError):
                    pass
    
    # Fallback: If no amount found but we have English keywords, try generic amount patterns
    if not amount_found and detected_currency is None:
        # Try generic patterns without currency symbol (only if no currency detected)
        generic_patterns = [
            r'(?:total|amount due|balance|subtotal|grand total)[:\s]+([\d,]+\.?\d*)',
        ]
        
        for pattern in generic_patterns:
            match = re.search(pattern, pdf_text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    # Only use if amount looks reasonable (> 0)
                    if amount_val > 0:
                        data['amount'] = amount_val
                        # Try to infer currency from domain
                        if from_domain and '.co.il' in from_domain:
                            data['currency'] = 'ILS'
                        else:
                            # Don't assume - leave as None
                            data['currency'] = None
                        amount_found = True
                        break
                except (ValueError, IndexError):
                    pass
    
    # Extract invoice number
    inv_match = re.search(r'(?:invoice|receipt|חשבונית|קבלה)\s*#?\s*:?\s*(\d+)', pdf_text, re.IGNORECASE)
    if inv_match:
        data['invoice_number'] = inv_match.group(1)
    
    # Extract date
    date_match = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', pdf_text)
    if date_match:
        day, month, year = date_match.groups()
        try:
            if len(year) == 2:
                year = '20' + year
            data['invoice_date'] = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except ValueError:
            pass
    
    return data


def extract_amount_from_html(html_content: str, metadata: dict) -> dict:
    """
    Extract amount and currency from HTML email content
    
    This function strips HTML tags and applies the same extraction logic as PDF extraction.
    Useful for emails without PDF attachments that contain receipt information in HTML.
    
    Args:
        html_content: HTML content from email
        metadata: Email metadata (for vendor detection)
        
    Returns:
        dict with amount, currency, vendor_name
    """
    data = {
        'vendor_name': None,
        'amount': None,
        'currency': None,
        'amount_raw': None
    }
    
    if not html_content:
        return data
    
    # Strip HTML tags to get plain text using BeautifulSoup (more secure than regex)
    try:
        from bs4 import BeautifulSoup
        # Use lxml parser for better security against malicious HTML
        soup = BeautifulSoup(html_content, 'lxml')
        # Remove script and style elements
        for script in soup(['script', 'style']):
            script.decompose()
        text = soup.get_text(separator=' ')
    except ImportError:
        # Fallback to regex if BeautifulSoup not available
        # Note: re is already imported at module level (line 28)
        # Best-effort regex to remove script/style tags with any whitespace in closing tag
        text = re.sub(r'<script[^>]*>.*?</script[^>]*>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style[^>]*>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Remove other HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
    
    # Decode HTML entities
    try:
        import html
        text = html.unescape(text)
    except Exception:
        pass
    
    # Try to extract vendor from sender domain
    from_domain = metadata.get('from_domain', '')
    if from_domain:
        # Clean up domain to get vendor name
        vendor = from_domain.replace('.co.il', '').replace('.com', '').replace('.net', '')
        vendor = vendor.replace('.', ' ').title()
        data['vendor_name'] = vendor
    
    # Detect currency FIRST
    currency_scores = {
        'ILS': 0,
        'USD': 0,
        'EUR': 0
    }
    
    # Check for currency symbols
    currency_scores['ILS'] += len(re.findall(r'₪', text)) * 10
    currency_scores['USD'] += len(re.findall(r'\$', text)) * 10
    currency_scores['EUR'] += len(re.findall(r'€', text)) * 10
    
    # Check for currency keywords
    currency_scores['ILS'] += len(re.findall(r'\b(?:ILS|ils|ש"ח|שקל|שקלים|NIS)\b', text, re.IGNORECASE)) * 5
    currency_scores['USD'] += len(re.findall(r'\b(?:USD|usd|dollar|dollars)\b', text, re.IGNORECASE)) * 5
    currency_scores['EUR'] += len(re.findall(r'\b(?:EUR|eur|euro|euros)\b', text, re.IGNORECASE)) * 5
    
    # Determine most likely currency
    detected_currency = None
    max_score = max(currency_scores.values())
    if max_score > 0:
        detected_currency = max(currency_scores, key=currency_scores.get)
    
    # Extract amount based on detected currency
    amount_found = False
    
    # Try USD patterns
    if detected_currency == 'USD' or (detected_currency is None and currency_scores['USD'] == max_score):
        usd_patterns = [
            r'(?:total|grand total|amount due|amount|subtotal)[:\s]*\$\s*([\d,]+\.?\d*)',  # Total: $100
            r'\$\s*([\d,]+\.?\d*)',  # $100
            r'([\d,]+\.?\d*)\s*\$',  # 100$
            r'([\d,]+\.?\d*)\s+(?:USD|usd)',  # 100 USD
            r'(?:USD|usd)[:\s]*([\d,]+\.?\d*)',  # USD: 100
        ]
        
        for pattern in usd_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    if amount_val > 0:
                        data['amount'] = amount_val
                        data['currency'] = 'USD'
                        data['amount_raw'] = match.group(0)
                        amount_found = True
                        break
                except (ValueError, IndexError):
                    pass
    
    # Try ILS patterns
    if not amount_found and (detected_currency == 'ILS' or detected_currency is None):
        ils_patterns = [
            r'(?:סה"כ|סהכ|לתשלום|total|amount due|amount)[:\s]*₪?\s*([\d,]+\.?\d*)\s*₪',  # Total: 100 ₪
            r'₪\s*([\d,]+\.?\d*)',  # ₪100
            r'([\d,]+\.?\d*)\s*₪',  # 100₪
            r'(?:ILS|ils|ש"ח|NIS)[:\s]*([\d,]+\.?\d*)',  # ILS: 100
            r'(?:סה"כ|סהכ|לתשלום|סכום)[:\s]*([\d,]+\.?\d*)',  # Hebrew keywords
        ]
        
        for pattern in ils_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    if amount_val > 0:
                        data['amount'] = amount_val
                        data['currency'] = 'ILS'
                        data['amount_raw'] = match.group(0)
                        amount_found = True
                        break
                except (ValueError, IndexError):
                    pass
    
    # Try EUR patterns
    if not amount_found and detected_currency == 'EUR':
        eur_patterns = [
            r'€\s*([\d,]+\.?\d*)',  # €100
            r'([\d,]+\.?\d*)\s*€',  # 100€
            r'(?:EUR|eur)[:\s]+([\d,]+\.?\d*)',  # EUR: 100
            r'(?:total|amount)[:\s]*€\s*([\d,]+\.?\d*)',  # Total: €100
        ]
        
        for pattern in eur_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    if amount_val > 0:
                        data['amount'] = amount_val
                        data['currency'] = 'EUR'
                        data['amount_raw'] = match.group(0)
                        amount_found = True
                        break
                except (ValueError, IndexError):
                    pass
    
    # Fallback: generic patterns without currency symbol
    if not amount_found:
        generic_patterns = [
            r'(?:total|amount due|balance|subtotal|grand total)[:\s]+([\d,]+\.?\d*)',
        ]
        
        for pattern in generic_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    if amount_val > 0:
                        data['amount'] = amount_val
                        data['amount_raw'] = match.group(0)
                        # Infer currency from domain
                        if from_domain and '.co.il' in from_domain:
                            data['currency'] = 'ILS'
                        elif detected_currency:
                            data['currency'] = detected_currency
                        # else leave as None
                        amount_found = True
                        break
                except (ValueError, IndexError):
                    pass
    
    return data


def extract_amount_merged(pdf_text: str, html_content: str, subject: str, metadata: dict) -> dict:
    """
    Merge amount extraction from multiple sources with priority order
    
    Priority:
    1. PDF text (most reliable)
    2. HTML body (Stripe, Replit, etc.)
    3. Subject line (fallback)
    
    Args:
        pdf_text: Extracted PDF text
        html_content: Full HTML email content
        subject: Email subject
        metadata: Email metadata
        
    Returns:
        dict with amount, currency, vendor_name, amount_raw
    """
    result = {
        'vendor_name': None,
        'amount': None,
        'currency': None,
        'amount_raw': None
    }
    
    # Try PDF first (most reliable)
    if pdf_text:
        pdf_data = extract_receipt_data(pdf_text, metadata)
        if pdf_data.get('amount'):
            result['amount'] = pdf_data['amount']
            result['currency'] = pdf_data.get('currency')
            result['vendor_name'] = pdf_data.get('vendor_name')
            result['amount_raw'] = f"PDF: {pdf_data.get('amount')} {pdf_data.get('currency', '')}"
            return result  # Found in PDF - done!
    
    # Try HTML if no PDF or PDF didn't have amount
    if html_content:
        html_data = extract_amount_from_html(html_content, metadata)
        if html_data.get('amount'):
            result['amount'] = html_data['amount']
            result['currency'] = html_data.get('currency')
            if not result['vendor_name']:
                result['vendor_name'] = html_data.get('vendor_name')
            result['amount_raw'] = html_data.get('amount_raw') or f"HTML: {html_data.get('amount')} {html_data.get('currency', '')}"
            return result  # Found in HTML - done!
    
    # Last resort: try subject line
    if subject:
        # Note: re is already imported at module level (line 28)
        # Try to find amount in subject
        patterns = [
            r'\$\s*([\d,]+\.?\d*)',  # $100
            r'₪\s*([\d,]+\.?\d*)',   # ₪100
            r'([\d,]+\.?\d*)\s*USD', # 100 USD
            r'([\d,]+\.?\d*)\s*ILS', # 100 ILS
        ]
        
        for pattern in patterns:
            match = re.search(pattern, subject, re.IGNORECASE)
            if match:
                try:
                    amount_str = match.group(1).replace(',', '')
                    amount_val = float(amount_str)
                    if amount_val > 0:
                        result['amount'] = amount_val
                        if '$' in pattern or 'USD' in pattern:
                            result['currency'] = 'USD'
                        elif '₪' in pattern or 'ILS' in pattern:
                            result['currency'] = 'ILS'
                        result['amount_raw'] = f"Subject: {match.group(0)}"
                        break
                except (ValueError, IndexError):
                    pass
    
    # If still no vendor, try domain
    if not result['vendor_name']:
        from_domain = metadata.get('from_domain', '')
        if from_domain:
            vendor = from_domain.replace('.co.il', '').replace('.com', '').replace('.net', '')
            vendor = vendor.replace('.', ' ').title()
            result['vendor_name'] = vendor
    
    return result


def process_single_receipt_message(
    message_id: str,
    gmail,
    business_id: int,
    attachment_service,
    result: dict,
    sync_run,
    message=None,
    is_receipt: bool = None,
    confidence: int = None,
    metadata: dict = None
) -> Optional['Receipt']:
    """
    Process a single Gmail message as a potential receipt
    
    This function extracts the complete receipt processing logic to avoid duplication.
    It handles:
    - Message fetching (if not provided)
    - Receipt detection (if not already done)
    - HTML extraction
    - Attachment processing (PDF/images)
    - Preview generation (with 100ms delay after Playwright)
    - Screenshot generation for emails without attachments
    - Amount extraction (PDF + HTML fallback)
    - Receipt object creation with validation
    - Enhanced logging with warnings
    
    Args:
        message_id: Gmail message ID
        gmail: Gmail service instance
        business_id: Business ID
        attachment_service: Attachment service instance
        result: Result dictionary for counters
        sync_run: Sync run record
        message: Optional pre-fetched message
        is_receipt: Optional pre-computed receipt flag
        confidence: Optional pre-computed confidence
        metadata: Optional pre-computed metadata
        
    Returns:
        Receipt object if successfully saved, None if skipped/failed
    """
    from server.db import db
    from server.models_sql import Receipt, Attachment
    import time
    
    # Fetch message if not provided
    if not message:
        message = gmail.get_message(message_id)
        result['processed'] += 1
    
    # Check if receipt if not already done
    if is_receipt is None or confidence is None or metadata is None:
        is_receipt, confidence, metadata = check_is_receipt_email(message)
        
        if is_receipt:
            result['candidate_receipts'] += 1
            sync_run.candidate_receipts = result['candidate_receipts']
    
    if not is_receipt:
        # Log why it was skipped for debugging - WITH PII MASKING
        safe_metadata = get_safe_log_metadata(metadata)
        logger.info(
            f"⏭️ SKIP: confidence={confidence}, "
            f"subject='{safe_metadata.get('subject', 'N/A')}', "
            f"from_domain={safe_metadata.get('from_domain', 'N/A')}, "
            f"has_attachment={metadata.get('has_attachment', False)}"
        )
        result['skipped'] += 1
        return None
    
    # Extract full HTML content
    email_html_snippet = extract_email_html(message)
    # CRITICAL: Strip NULL bytes to prevent PostgreSQL crashes
    if email_html_snippet:
        email_html_snippet = strip_null_bytes(email_html_snippet)
    attachment_id = None
    preview_attachment_id = None
    pdf_text = ''
    attachment_processed = False
    preview_generated = False
    
    # Use recursive attachment extraction
    all_attachments = extract_all_attachments(message)
    
    # Track preview failure reason if any
    preview_error_msg = None
    
    # ==================================================================================
    # MASTER INSTRUCTION RULE 5: SAVE ALL ATTACHMENTS (NO EXCEPTIONS!)
    # ==================================================================================
    # Extract, save, and link ALL attachments to records
    # Never skip, never decide "not relevant" - Rule 5
    
    saved_attachments = []  # Track all saved attachment IDs
    
    # Process ALL attachments (not just first one)
    for att_idx, att in enumerate(all_attachments):
        if att['mime_type'] in ['application/pdf', 'image/jpeg', 'image/png', 'image/webp', 'image/gif']:
            try:
                # CRITICAL: Skip if no attachment ID (can't download)
                if not att['id']:
                    logger.warning(f"⚠️ Attachment {att_idx+1} has no ID, skipping: {att['filename']}")
                    continue
                
                logger.info(f"📎 Downloading attachment {att_idx+1}/{len(all_attachments)}: {att['filename']} (ID: {att['id']})")
                att_data = gmail.get_attachment(message_id, att['id'])
                
                if not att_data:
                    logger.warning(f"⚠️ Empty attachment data for {att['filename']}")
                    continue
                
                logger.info(f"✅ Downloaded {len(att_data)} bytes for {att['filename']}")
                
                # Extract PDF text if applicable (only for first PDF for performance)
                if att['mime_type'] == 'application/pdf' and not pdf_text:
                    pdf_text = extract_pdf_text(att_data)
                    pdf_confidence = calculate_pdf_confidence(pdf_text)
                    confidence = min(confidence + pdf_confidence, 100)
                
                # Save source attachment to storage
                from werkzeug.datastructures import FileStorage
                from io import BytesIO
                
                file_storage = FileStorage(
                    stream=BytesIO(att_data),
                    filename=att['filename'] or f'attachment_{att_idx+1}.pdf',
                    content_type=att['mime_type']
                )
                
                attachment = Attachment(
                    business_id=business_id,
                    filename_original=att['filename'] or f'attachment_{att_idx+1}',
                    mime_type=att['mime_type'],
                    file_size=0,
                    storage_path='',
                    purpose='receipt_source',
                    origin_module='receipts',
                    channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                )
                db.session.add(attachment)
                db.session.flush()
                
                storage_key, file_size = attachment_service.save_file(
                    file=file_storage,
                    business_id=business_id,
                    attachment_id=attachment.id,
                    purpose='receipt_source'
                )
                
                attachment.storage_path = storage_key
                attachment.file_size = file_size
                saved_attachments.append(attachment.id)
                
                # Use first attachment as THE attachment for receipt record
                if not attachment_processed:
                    attachment_id = attachment.id
                    attachment_processed = True
                
                logger.info(f"✅ Saved attachment {att_idx+1}: ID={attachment.id}, size={file_size}")
                
                # Generate preview from FIRST attachment only (for performance)
                if att_idx == 0 and not preview_generated:
                    try:
                        from server.services.receipt_preview_service import generate_pdf_thumbnail, generate_image_thumbnail, save_preview_attachment
                        
                        # Acquire semaphore before heavy Playwright/PDF operations
                        with playwright_semaphore:
                            preview_data = None
                            if att['mime_type'] == 'application/pdf':
                                preview_data = generate_pdf_thumbnail(att_data)
                                time.sleep(0.1)  # Small delay after PDF processing
                            elif att['mime_type'].startswith('image/'):
                                preview_data = generate_image_thumbnail(att_data, att['mime_type'])
                            
                            if preview_data:
                                preview_attachment_id = save_preview_attachment(
                                    preview_data=preview_data,
                                    business_id=business_id,
                                    original_filename=att['filename'] or 'receipt',
                                    purpose='receipt_preview'
                                )
                                if preview_attachment_id:
                                    preview_generated = True
                                    logger.info(f"✅ Preview generated from first attachment")
                            else:
                                logger.warning(f"⚠️ Preview generation returned None for {att['mime_type']}")
                                preview_error_msg = f"Preview generation returned None for {att['mime_type']}"
                    except Exception as preview_err:
                        preview_error_msg = str(preview_err)[:ERROR_MESSAGE_MAX_LENGTH]
                        logger.warning(f"⚠️ Preview generation failed: {preview_err}", exc_info=True)
                
            except Exception as e:
                logger.error(f"❌ Failed to process attachment {att_idx+1}: {e}")
                result['errors'] += 1
                sync_run.errors_count = result['errors']
    
    # Log summary of saved attachments
    if saved_attachments:
        logger.info(f"✅ RULE 5: Saved {len(saved_attachments)} attachments: {saved_attachments}")
    
    # ==================================================================================
    # MASTER INSTRUCTION RULE 2: SCREENSHOT MANDATORY FOR ALL PROCESSED EMAILS
    # ==================================================================================
    # Every processed email MUST have a screenshot/snapshot PDF (Rule 2)
    # This is NON-NEGOTIABLE - if screenshot fails, email should NOT be marked as processed
    
    if email_html_snippet and not preview_generated:
        try:
            # Acquire semaphore before Playwright screenshot
            with playwright_semaphore:
                screenshot_attachment_id = generate_email_screenshot(
                    email_html=email_html_snippet,
                    business_id=business_id,
                    receipt_id=None
                )
                
                if screenshot_attachment_id:
                    if not attachment_processed:
                        # No attachment - screenshot IS the attachment
                        attachment_id = screenshot_attachment_id
                        attachment_processed = True
                    # Screenshot is always the preview (shows email context)
                    preview_attachment_id = screenshot_attachment_id
                    preview_generated = True
                    logger.info(f"✅ Email snapshot PDF generated successfully")
                    time.sleep(0.1)  # Small delay after Playwright
                else:
                    # CRITICAL: Screenshot generation failed - this violates Rule 2
                    logger.error(f"❌ RULE 2 VIOLATION: Screenshot mandatory but generation failed!")
                    preview_error_msg = "Screenshot generation failed - mandatory requirement not met"
        except Exception as e:
            preview_error_msg = str(e)[:ERROR_MESSAGE_MAX_LENGTH]
            logger.error(f"❌ RULE 2 VIOLATION: Screenshot generation exception: {e}")
    
    # ==================================================================================
    # MASTER INSTRUCTION RULE 8: VALIDATION CHECK
    # ==================================================================================
    # Before creating receipt record, validate:
    # 1. If email had HTML, screenshot PDF must exist
    # 2. If email had attachments, they must be saved
    
    validation_failed = False
    validation_errors = []
    
    # Check 1: If we had HTML content, we MUST have a screenshot
    if email_html_snippet and not preview_generated:
        validation_failed = True
        validation_errors.append("Screenshot PDF mandatory but not generated")
        logger.error(f"❌ VALIDATION FAILED: Email had HTML but no screenshot PDF")
    
    # Check 2: If original message had attachments, at least one must be processed
    # (all_attachments was already extracted above)
    if all_attachments and not attachment_processed:
        validation_failed = True
        validation_errors.append(f"Email had {len(all_attachments)} attachments but none were saved")
        logger.error(f"❌ VALIDATION FAILED: Attachments present but not saved")
    
    # If validation failed, do NOT create receipt - return None
    if validation_failed:
        logger.error(f"❌ CRITICAL: Receipt validation failed - will NOT create record")
        logger.error(f"❌ Validation errors: {', '.join(validation_errors)}")
        result['errors'] += 1
        return None
    
    # Don't skip receipts just because they lack attachments
    # If confidence check passed in check_is_receipt_email(), trust it
    # Only skip if BOTH no attachment AND no HTML content (empty email)
    if not attachment_processed and not email_html_snippet:
        logger.info(f"⏭️ Skipping email with no attachment and no HTML content")
        result['skipped'] += 1
        return None
    
    # Use merged extraction (PDF + HTML + Subject priority)
    extracted = extract_amount_merged(
        pdf_text=pdf_text,
        html_content=email_html_snippet,
        subject=metadata.get('subject', ''),
        metadata=metadata
    )
    
    # Parse received date
    received_at = None
    if metadata.get('date'):
        try:
            received_at = parsedate_to_datetime(metadata['date'])
        except Exception:
            received_at = datetime.now(timezone.utc)
    else:
        received_at = datetime.now(timezone.utc)
    
    # Determine status based on confidence with two-tier system
    # High confidence (>=50): Auto-approve
    # Medium/Low confidence (5-49): Pending review
    if confidence >= AUTO_APPROVE_THRESHOLD:
        status = 'approved'
        logger.debug(f"✅ Auto-approved (confidence={confidence} >= {AUTO_APPROVE_THRESHOLD})")
    else:
        status = 'pending_review'
        logger.debug(f"⏸️ Pending review (confidence={confidence} < {AUTO_APPROVE_THRESHOLD})")
    
    # Determine needs_review flag for low-confidence or missing data
    # This is SEPARATE from status - helps filter false positives from reports
    needs_review = False
    if confidence < 15:  # Very low confidence (5-14)
        needs_review = True
        logger.debug(f"🔍 Flagged for review: very low confidence ({confidence})")
    elif not extracted.get('amount'):
        needs_review = True
        logger.debug(f"🔍 Flagged for review: missing amount")
    elif not extracted.get('vendor_name'):
        needs_review = True
        logger.debug(f"🔍 Flagged for review: missing vendor")
    
    # Determine receipt_type based on keywords in subject/content
    receipt_type = None
    subject_lower = metadata.get('subject', '').lower()
    if any(kw in subject_lower for kw in ['confirmation', 'אישור', 'confirmed']):
        receipt_type = 'confirmation'
    elif any(kw in subject_lower for kw in ['invoice', 'חשבונית']):
        receipt_type = 'invoice'
    elif any(kw in subject_lower for kw in ['receipt', 'קבלה']):
        receipt_type = 'receipt'
    elif any(kw in subject_lower for kw in ['statement', 'דוח']):
        receipt_type = 'statement'
    else:
        receipt_type = 'other'
    
    # Parse invoice date
    invoice_date = None
    if extracted.get('invoice_date'):
        try:
            invoice_date = datetime.strptime(extracted['invoice_date'], '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # Create receipt record with sanitized JSON (no NUL characters for PostgreSQL)
    raw_json_data = {
        'metadata': metadata,
        'extracted': extracted,
        'pdf_text_preview': pdf_text[:500] if pdf_text else None,
        'html_extraction': extract_amount_from_html(email_html_snippet, metadata) if email_html_snippet else None
    }
    # CRITICAL: Use robust NULL byte stripping
    try:
        sanitized_json = strip_null_bytes(raw_json_data)
    except Exception as sanitize_err:
        logger.error(f"⚠️ JSON sanitization failed, using None: {sanitize_err}")
        sanitized_json = None
    
    # CRITICAL: Validation - track why extraction failed
    extraction_warnings = []
    
    # Check preview generation
    if attachment_id and not preview_generated:
        extraction_warnings.append('preview_generation_failed')
        logger.warning(f"⚠️ Receipt {message_id}: Preview generation failed despite having attachment")
    
    # Check amount extraction
    if (pdf_text or email_html_snippet) and not extracted.get('amount'):
        extraction_warnings.append('amount_not_extracted')
        logger.warning(f"⚠️ Receipt {message_id}: Amount not extracted despite having content")
        # Don't auto-approve if amount missing
        if status == 'approved':
            status = 'pending_review'
    
    # Check currency
    if extracted.get('amount') and not extracted.get('currency'):
        extraction_warnings.append('currency_not_detected')
        logger.warning(f"⚠️ Receipt {message_id}: Currency not detected")
    
    # Add warnings to raw_extraction_json
    if extraction_warnings and sanitized_json:
        sanitized_json['extraction_warnings'] = extraction_warnings
    elif extraction_warnings:
        sanitized_json = {'extraction_warnings': extraction_warnings}
    
    # Determine preview status based on generation result
    if preview_generated:
        preview_status_val = 'generated'
        preview_failure_reason_val = None
    elif attachment_processed:
        # Had attachment but preview failed
        preview_status_val = 'failed'
        preview_failure_reason_val = preview_error_msg or 'Preview generation failed for attachment'
    elif email_html_snippet:
        # Had HTML but screenshot failed
        preview_status_val = 'failed'
        preview_failure_reason_val = preview_error_msg or 'Email screenshot generation failed'
    else:
        # No attachment and no HTML
        preview_status_val = 'not_available'
        preview_failure_reason_val = 'No attachment or HTML content available'
    
    receipt = Receipt(
        business_id=business_id,
        source='gmail',
        gmail_message_id=message_id,
        gmail_thread_id=message.get('threadId'),
        from_email=metadata.get('from_email'),
        subject=metadata.get('subject', '')[:500],
        received_at=received_at,
        email_subject=metadata.get('subject', '')[:500],
        email_from=metadata.get('from_email'),
        email_date=received_at,
        email_html_snippet=email_html_snippet,
        vendor_name=extracted.get('vendor_name'),
        amount=extracted.get('amount'),
        currency=extracted.get('currency') or 'ILS',  # Default to ILS if None
        invoice_number=extracted.get('invoice_number'),
        invoice_date=invoice_date,
        confidence=confidence,
        raw_extraction_json=sanitized_json,
        status=status,
        needs_review=needs_review,  # NEW: Flag for low-confidence items
        receipt_type=receipt_type,  # NEW: Type classification
        attachment_id=attachment_id,
        preview_attachment_id=preview_attachment_id,
        preview_status=preview_status_val,
        preview_failure_reason=preview_failure_reason_val
    )
    
    db.session.add(receipt)
    db.session.flush()  # Get receipt ID
    result['new_count'] += 1
    result['saved_receipts'] += 1
    sync_run.saved_receipts = result['saved_receipts']
    
    # Enhanced logging per receipt with full details - PII MASKED
    safe_metadata = get_safe_log_metadata(metadata)
    logger.info(
        f"✅ RECEIPT_SAVED id={receipt.id}, "
        f"message_id={message_id[:20]}..., "
        f"subject='{safe_metadata.get('subject', '')}', "
        f"from_domain={safe_metadata.get('from_domain', '')}, "
        f"has_attachment={attachment_processed} (att_id={attachment_id}), "
        f"amount={extracted.get('amount')}, "
        f"currency={extracted.get('currency')}, "
        f"confidence={confidence}, "
        f"needs_review={needs_review}, "
        f"receipt_type={receipt_type}, "
        f"preview={'✓' if preview_generated else '✗'} (prev_id={preview_attachment_id}), "
        f"warnings={extraction_warnings if extraction_warnings else 'none'}"
    )
    
    return receipt


def sync_gmail_receipts(business_id: int, mode: str = 'incremental', max_messages: int = None, 
                       from_date: str = None, to_date: str = None, months_back: int = 36) -> dict:
    """
    Sync receipts from Gmail for a business with monthly backfill and full pagination
    
    📅 DATE RANGE PRIORITY:
    1. If from_date OR to_date specified → use exact date range (ignore mode)
    2. If mode='full_backfill' → use monthly backfill logic
    3. If mode='incremental' → use last_sync_at with 30-day overlap
    
    📅 GMAIL QUERY FORMAT:
    - after:YYYY/MM/DD (inclusive - messages ON or AFTER this date)
    - before:YYYY/MM/DD (exclusive - messages BEFORE this date)
    - To make to_date inclusive, we add 1 day to it
    
    Args:
        business_id: Business ID to sync
        mode: 'full_backfill' for monthly backfill or 'incremental' for recent messages
        max_messages: Maximum total messages to process (None = unlimited)
        from_date: Start date for sync in YYYY-MM-DD format (optional, ALWAYS overrides mode)
        to_date: End date for sync in YYYY-MM-DD format (optional, ALWAYS overrides mode)
        months_back: Number of months to go back for full_backfill (default 36 = 3 years)
        
    Returns:
        Sync results with detailed counters
    """
    from server.db import db
    from server.models_sql import GmailConnection, Receipt, Attachment, ReceiptSyncRun
    from server.services.attachment_service import get_attachment_service
    from dateutil.relativedelta import relativedelta
    import time
    
    # Start time tracking for MAX_SECONDS_PER_RUN
    start_time = time.time()
    
    # Log what we received from the API
    logger.info(f"🔍 RUN_START: Gmail sync requested - business_id={business_id}, mode={mode}, from_date={from_date}, to_date={to_date}, months_back={months_back}")
    
    # Determine if we should run to completion
    # Use global env var, or False if not set
    run_to_completion = RUN_TO_COMPLETION  # Global env var
    max_seconds = MAX_SECONDS_PER_RUN if not run_to_completion else None
    
    # Parse dates if provided
    from_date_obj = datetime.strptime(from_date, '%Y-%m-%d').date() if from_date else None
    to_date_obj = datetime.strptime(to_date, '%Y-%m-%d').date() if to_date else None
    
    # Create sync run record with initial heartbeat and full context
    now_utc = datetime.now(timezone.utc)
    sync_run = ReceiptSyncRun(
        business_id=business_id,
        mode=mode,
        from_date=from_date_obj,
        to_date=to_date_obj,
        months_back=months_back,
        run_to_completion=run_to_completion,  # Explicitly set (not None)
        max_seconds_per_run=max_seconds,
        status='running',
        last_heartbeat_at=now_utc  # Initialize heartbeat
    )
    db.session.add(sync_run)
    db.session.commit()
    
    logger.info(f"🔍 RUN_START: run_id={sync_run.id}, started_at={now_utc.isoformat()}, run_to_completion={run_to_completion}, max_seconds={max_seconds}")

    
    result = {
        'sync_run_id': sync_run.id,
        'new_count': 0,
        'processed': 0,
        'skipped': 0,
        'errors': 0,
        'pages_scanned': 0,
        'messages_scanned': 0,
        'candidate_receipts': 0,
        'saved_receipts': 0,
        'months_processed': 0,
        'total_months': 0
    }
    
    try:
        gmail = get_gmail_service(business_id)
        connection = GmailConnection.query.filter_by(business_id=business_id).first()
        
        # ========================================================================
        # PRIORITY 1: Custom date range ALWAYS wins (overrides mode)
        # ========================================================================
        use_custom_dates = from_date is not None or to_date is not None
        
        if use_custom_dates:
            logger.info(f"📅 Custom date range detected - will use exact dates (ignoring mode={mode})")
            
            # Parse and determine date range
            # Case 1: Both dates provided
            if from_date and to_date:
                start_dt = datetime.strptime(from_date, '%Y-%m-%d')
                end_dt = datetime.strptime(to_date, '%Y-%m-%d')
                logger.info(f"📅 Date range: {from_date} to {to_date}")
            # Case 2: Only from_date - go to today
            elif from_date:
                start_dt = datetime.strptime(from_date, '%Y-%m-%d')
                end_dt = datetime.now()
                logger.info(f"📅 From {from_date} to now")
            # Case 3: Only to_date - go back based on months_back parameter
            else:  # only to_date
                end_dt = datetime.strptime(to_date, '%Y-%m-%d')
                # Use months_back parameter to determine how far back to go
                # Default: 12 months if not specified
                # Note: When only to_date is specified, we use months_back to determine start
                # to avoid accidentally syncing the entire Gmail history. 
                # For full control, specify both from_date and to_date explicitly.
                months_to_go_back = months_back if months_back else 12
                start_dt = end_dt - relativedelta(months=months_to_go_back)
                logger.info(f"📅 Last {months_to_go_back} months up to {to_date} (only to_date specified, using months_back={months_to_go_back})")
            
            # Build Gmail query with custom dates
            query_parts = []
            query_parts.append(f'after:{start_dt.strftime("%Y/%m/%d")}')
            
            # Gmail's "before" is EXCLUSIVE, so add 1 day to make to_date inclusive
            end_dt_inclusive = end_dt + timedelta(days=1)
            query_parts.append(f'before:{end_dt_inclusive.strftime("%Y/%m/%d")}')
            
            # Add broad keyword filters to reduce noise but not miss receipts
            # Include common receipt keywords in subject OR body
            keyword_filter = ' OR '.join([
                f'subject:"{kw}"' for kw in ['קבלה', 'חשבונית', 'invoice', 'receipt', 'payment', 'bill', 'order']
            ] + [
                f'"{kw}"' for kw in ['קבלת תשלום', 'חשבונית מס', 'tax invoice', 'סה"כ', 'total', 'amount', 'סכום']
            ])
            
            # CRITICAL FIX: Make keyword filter optional to catch ALL potential receipts
            # Filter by attachment presence instead of strict keywords
            attachment_filter = 'has:attachment'
            
            # Combine: (date range) AND (keywords OR attachments)
            # This catches receipts without exact keywords but with attachments
            query = f"{' '.join(query_parts)} ({keyword_filter} OR {attachment_filter})"
            logger.info(f"📧 Gmail query built: {query}")
            logger.info(f"📧 This will fetch emails from {start_dt.strftime('%Y/%m/%d')} up to AND INCLUDING {end_dt.strftime('%Y/%m/%d')}")
            logger.info(f"📧 Query includes keyword filter OR attachments to maximize receipt detection")
            
            # Use simple pagination (not monthly chunks) for custom date range
            attachment_service = get_attachment_service()
            page_token = None
            
            while True:
                # Check for cancellation
                db.session.refresh(sync_run)
                if sync_run.status == 'cancelled':
                    logger.info(f"⛔ Sync {sync_run.id} cancelled by user")
                    result['cancelled'] = True
                    break
                
                result['pages_scanned'] += 1
                sync_run.pages_scanned = result['pages_scanned']
                
                try:
                    page_result = gmail.list_messages(
                        query=query,
                        max_results=100,
                        page_token=page_token
                    )
                except Exception as api_error:
                    if '429' in str(api_error) or 'rate' in str(api_error).lower():
                        logger.warning(f"⚠️ Rate limit hit, sleeping 10 seconds...")
                        time.sleep(10)
                        continue
                    else:
                        raise
                
                messages = page_result.get('messages', [])
                page_token = page_result.get('nextPageToken')
                
                logger.info(f"📄 PAGE_FETCH: page={result['pages_scanned']}, messages={len(messages)}, has_next={bool(page_token)}")
                
                # Update heartbeat at page boundary
                sync_run.last_heartbeat_at = datetime.now(timezone.utc)
                sync_run.pages_scanned = result['pages_scanned']
                sync_run.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                
                if not messages:
                    break
                
                # Process messages
                for msg_info in messages:
                    message_id = msg_info['id']
                    result['messages_scanned'] += 1
                    sync_run.messages_scanned = result['messages_scanned']
                    
                    # CHECK 1: Max messages limit (skip if run_to_completion mode)
                    if not run_to_completion and result['messages_scanned'] >= MAX_MESSAGES_PER_RUN:
                        logger.info(f"⏸️ Reached MAX_MESSAGES_PER_RUN ({MAX_MESSAGES_PER_RUN}), pausing for resume")
                        sync_run.status = 'paused'
                        sync_run.last_page_token = page_token
                        sync_run.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                        page_token = None
                        break
                    
                    # CHECK 2: Max time limit (skip if run_to_completion mode)
                    if not run_to_completion:
                        elapsed_seconds = time.time() - start_time
                        if elapsed_seconds >= MAX_SECONDS_PER_RUN:
                            logger.info(f"⏸️ Reached MAX_SECONDS_PER_RUN ({MAX_SECONDS_PER_RUN}s), pausing for auto-resume")
                            logger.info(f"   Progress: {result['messages_scanned']} messages, {result['saved_receipts']} receipts")
                            sync_run.status = 'paused'
                            sync_run.last_page_token = page_token
                            sync_run.updated_at = datetime.now(timezone.utc)
                            db.session.commit()
                            page_token = None
                            break
                    
                    if max_messages and result['messages_scanned'] >= max_messages:
                        logger.info(f"Reached max_messages limit ({max_messages})")
                        page_token = None
                        break
                    
                    # Check for cancellation and update heartbeat every 20 messages
                    if result['messages_scanned'] % 20 == 0:
                        # Update heartbeat for stale run detection
                        sync_run.last_heartbeat_at = datetime.now(timezone.utc)
                        sync_run.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                        
                        # Check for cancellation
                        db.session.refresh(sync_run)
                        if sync_run.status == 'cancelled':
                            logger.info(f"⛔ Sync {sync_run.id} cancelled")
                            result['cancelled'] = True
                            page_token = None
                            break
                        
                        # Log progress every 50 messages
                        if result['messages_scanned'] % 50 == 0:
                            logger.info(
                                f"📊 RUN_PROGRESS: run_id={sync_run.id}, "
                                f"messages_scanned={result['messages_scanned']}, "
                                f"saved={result['saved_receipts']}, "
                                f"skipped={result['skipped']}, "
                                f"errors={result['errors']}"
                            )
                    
                    # Check if already exists (with no_autoflush to prevent SQLAlchemy warnings)
                    with db.session.no_autoflush:
                        existing = Receipt.query.filter_by(
                            business_id=business_id,
                            gmail_message_id=message_id
                        ).first()
                    
                    if existing:
                        result['skipped'] += 1
                        # Batch update skipped_count every 50 skips to reduce DB writes
                        if result['skipped'] % 50 == 0:
                            sync_run.skipped_count = result['skipped']
                        continue
                    
                    try:
                        # Process receipt using extracted helper function
                        receipt = process_single_receipt_message(
                            message_id=message_id,
                            gmail=gmail,
                            business_id=business_id,
                            attachment_service=attachment_service,
                            result=result,
                            sync_run=sync_run
                        )
                        
                        # Commit every 10 receipts (no sleep)
                        if receipt and result['saved_receipts'] % 20 == 0:
                            sync_run.updated_at = datetime.now(timezone.utc)
                            db.session.commit()
                        
                    except Exception as e:
                        # Per-message error handling: rollback and continue to next message
                        logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
                        try:
                            db.session.rollback()  # Rollback failed transaction
                        except Exception as rollback_err:
                            logger.error(f"❌ Rollback failed: {rollback_err}")
                        result['errors'] += 1
                        sync_run.errors_count = result['errors']
                        sync_run.error_message = f"{message_id}: {str(e)[:ERROR_MESSAGE_MAX_LENGTH]}"  # Track last error
                        # Continue to next message - don't fail entire sync
                
                if not page_token:
                    break
                
                time.sleep(0.2)  # 200ms between pages
                
                sync_run.last_page_token = page_token
                sync_run.updated_at = datetime.now(timezone.utc)
                db.session.commit()
            
            # Check if cancelled
            if result.get('cancelled'):
                sync_run.status = 'cancelled'
                sync_run.finished_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"Gmail sync cancelled: {result}")
                return result
        
        # ========================================================================
        # PRIORITY 2: Mode-based logic (only if no custom dates)
        # ========================================================================
        elif mode == 'full_backfill':
            # Monthly backfill mode without custom dates - use months_back
            logger.info(f"📅 Full backfill mode: going back {months_back} months")
            
            end_dt = datetime.now()
            start_dt = end_dt - relativedelta(months=months_back)
            logger.info(f"📅 Date range: {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}")
            
            # Generate list of months to process (from oldest to newest)
            months_to_process = []
            current_month_dt = start_dt.replace(day=1)  # Start at first day of month
            
            while current_month_dt <= end_dt:
                # Calculate month boundaries
                month_start = current_month_dt
                month_end = (current_month_dt + relativedelta(months=1)) - relativedelta(days=1)
                
                # Don't go past end_dt
                if month_end > end_dt:
                    month_end = end_dt
                
                months_to_process.append({
                    'start': month_start,
                    'end': month_end,
                    'label': current_month_dt.strftime('%Y-%m')
                })
                
                current_month_dt = current_month_dt + relativedelta(months=1)
            
            result['total_months'] = len(months_to_process)
            logger.info(f"📅 Processing {len(months_to_process)} months: {months_to_process[0]['label']} to {months_to_process[-1]['label']}")
            
            # Process each month sequentially
            attachment_service = get_attachment_service()
            
            for month_info in months_to_process:
                # Check for cancellation at start of each month
                db.session.refresh(sync_run)
                if sync_run.status == 'cancelled':
                    logger.info(f"⛔ Sync {sync_run.id} cancelled by user")
                    result['cancelled'] = True
                    break
                
                month_label = month_info['label']
                month_start = month_info['start']
                month_end = month_info['end']
                
                logger.info(f"📅 Processing month: {month_label} ({month_start.strftime('%Y/%m/%d')} to {month_end.strftime('%Y/%m/%d')})")
                
                # Update current_month in sync_run for checkpoint
                sync_run.current_month = month_label
                sync_run.updated_at = datetime.now(timezone.utc)
                db.session.commit()
                
                # Build Gmail query for this specific month
                query_parts = []
                query_parts.append(f'after:{month_start.strftime("%Y/%m/%d")}')
                query_parts.append(f'before:{month_end.strftime("%Y/%m/%d")}')
                
                # Add keyword filters for receipt/invoice detection
                keyword_filter = ' OR '.join([
                    f'subject:"{kw}"' for kw in ['קבלה', 'חשבונית', 'invoice', 'receipt', 'payment', 'bill']
                ] + [
                    f'"{kw}"' for kw in ['קבלת תשלום', 'חשבונית מס', 'tax invoice']
                ])
                
                query = f"{' '.join(query_parts)} ({keyword_filter})"
                logger.info(f"  Query: {query}")
                
                # Paginate through all messages for this month
                page_token = None
                month_messages = 0
                month_receipts = 0
                
                while True:
                    # Check for cancellation every page
                    db.session.refresh(sync_run)
                    if sync_run.status == 'cancelled':
                        logger.info(f"⛔ Sync {sync_run.id} cancelled during month {month_label}")
                        result['cancelled'] = True
                        break
                    
                    result['pages_scanned'] += 1
                    sync_run.pages_scanned = result['pages_scanned']
                    
                    # Get page of messages
                    try:
                        page_result = gmail.list_messages(
                            query=query,
                            max_results=100,  # Max per page
                            page_token=page_token
                        )
                    except Exception as api_error:
                        # Handle rate limiting with exponential backoff
                        if '429' in str(api_error) or 'rate' in str(api_error).lower():
                            logger.warning(f"⚠️ Rate limit hit, sleeping 10 seconds...")
                            time.sleep(10)
                            continue
                        else:
                            raise
                    
                    messages = page_result.get('messages', [])
                    page_token = page_result.get('nextPageToken')
                    
                    logger.info(f"  Page {result['pages_scanned']}: {len(messages)} messages")
                    month_messages += len(messages)
                    
                    if not messages:
                        break
                    
                    # Process messages in this page
                    for msg_info in messages:
                        message_id = msg_info['id']
                        result['messages_scanned'] += 1
                        sync_run.messages_scanned = result['messages_scanned']
                        
                        # CHECK 1: Max messages limit (skip if run_to_completion mode)
                        if not run_to_completion and result['messages_scanned'] >= MAX_MESSAGES_PER_RUN:
                            logger.info(f"⏸️ Reached MAX_MESSAGES_PER_RUN ({MAX_MESSAGES_PER_RUN}), pausing for resume")
                            sync_run.status = 'paused'
                            sync_run.last_page_token = page_token
                            sync_run.current_month = month_label
                            sync_run.updated_at = datetime.now(timezone.utc)
                            db.session.commit()
                            page_token = None
                            break
                        
                        # CHECK 2: Max time limit (skip if run_to_completion mode)
                        if not run_to_completion:
                            elapsed_seconds = time.time() - start_time
                            if elapsed_seconds >= MAX_SECONDS_PER_RUN:
                                logger.info(f"⏸️ Reached MAX_SECONDS_PER_RUN ({MAX_SECONDS_PER_RUN}s), pausing for auto-resume")
                                logger.info(f"   Progress: {result['messages_scanned']} messages, {result['saved_receipts']} receipts")
                                sync_run.status = 'paused'
                                sync_run.last_page_token = page_token
                                sync_run.current_month = month_label
                                sync_run.updated_at = datetime.now(timezone.utc)
                                db.session.commit()
                                page_token = None
                                break
                        
                        # Check max_messages limit
                        if max_messages and result['messages_scanned'] >= max_messages:
                            logger.info(f"Reached max_messages limit ({max_messages})")
                            page_token = None  # Stop pagination
                            break
                        
                        # Check for cancellation every 10 messages
                        if result['messages_scanned'] % 20 == 0:
                            db.session.refresh(sync_run)
                            if sync_run.status == 'cancelled':
                                logger.info(f"⛔ Sync {sync_run.id} cancelled")
                                result['cancelled'] = True
                                page_token = None
                                break
                        
                        # Check if already processed (with no_autoflush to prevent SQLAlchemy warnings)
                        with db.session.no_autoflush:
                            existing = Receipt.query.filter_by(
                                business_id=business_id,
                                gmail_message_id=message_id
                            ).first()
                        
                        if existing:
                            result['skipped'] += 1
                            # Batch update skipped_count every 50 skips to reduce DB writes
                            if result['skipped'] % 50 == 0:
                                sync_run.skipped_count = result['skipped']
                            continue
                        
                        try:
                            # Process receipt using extracted helper function
                            receipt = process_single_receipt_message(
                                message_id=message_id,
                                gmail=gmail,
                                business_id=business_id,
                                attachment_service=attachment_service,
                                result=result,
                                sync_run=sync_run
                            )
                            
                            if receipt:
                                month_receipts += 1
                            
                            # Commit every 10 receipts (no sleep)
                            if result['saved_receipts'] % 20 == 0:
                                sync_run.updated_at = datetime.now(timezone.utc)
                                db.session.commit()
                            
                        except Exception as e:
                            # Per-message error handling: rollback and continue to next message
                            logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
                            try:
                                db.session.rollback()  # Rollback failed transaction
                            except Exception as rollback_err:
                                logger.error(f"❌ Rollback failed: {rollback_err}")
                            result['errors'] += 1
                            sync_run.errors_count = result['errors']
                            sync_run.error_message = f"{message_id}: {str(e)[:ERROR_MESSAGE_MAX_LENGTH]}"  # Track last error
                            # Continue to next message - don't fail entire sync
                    
                    # Check if should continue to next page
                    if not page_token:
                        break
                    
                    # Sleep between pages to avoid rate limits
                    time.sleep(0.2)  # 200ms between pages
                    
                    # Update checkpoint including final skipped_count
                    sync_run.last_page_token = page_token
                    sync_run.current_month = month_label  # Add this
                    sync_run.updated_at = datetime.now(timezone.utc)
                    sync_run.skipped_count = result['skipped']  # Ensure final count is saved
                    db.session.commit()
                
                # Month complete - commit all changes for this month
                result['months_processed'] += 1
                logger.info(f"✅ Month {month_label} complete: {month_messages} messages, {month_receipts} receipts")
                db.session.commit()
                
                # Check if cancelled after month completion
                if result.get('cancelled'):
                    break
            
            # All months processed or cancelled
            if result.get('cancelled'):
                sync_run.status = 'cancelled'
                sync_run.finished_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"Gmail sync cancelled: {result}")
                return result
        
        else:
            # Incremental mode - use original logic (single query with pagination)
            # Build search query based on last sync time
            query_parts = []
            
            if connection and connection.last_sync_at:
                cutoff = connection.last_sync_at - timedelta(days=30)
                date_str = cutoff.strftime('%Y/%m/%d')
                query_parts.append(f'after:{date_str}')
                logger.info(f"📅 Incremental sync from: {date_str}")
            else:
                query_parts.append('newer_than:1y')
                logger.info("📅 First sync - going back 1 year")
            
            # Add keyword filters
            keyword_filter = ' OR '.join([
                f'subject:"{kw}"' for kw in ['קבלה', 'חשבונית', 'invoice', 'receipt', 'payment', 'bill']
            ] + [
                f'"{kw}"' for kw in ['קבלת תשלום', 'חשבונית מס', 'tax invoice']
            ])
            
            query = f"{' '.join(query_parts)} ({keyword_filter})"
            logger.info(f"Gmail query: {query}")
            
            attachment_service = get_attachment_service()
            page_token = None
            
            # Pagination loop - same logic as before but without monthly division
            while True:
                db.session.refresh(sync_run)
                if sync_run.status == 'cancelled':
                    logger.info(f"⛔ Sync {sync_run.id} cancelled")
                    result['cancelled'] = True
                    break
                
                result['pages_scanned'] += 1
                sync_run.pages_scanned = result['pages_scanned']
                
                try:
                    page_result = gmail.list_messages(
                        query=query,
                        max_results=100,
                        page_token=page_token
                    )
                except Exception as api_error:
                    if '429' in str(api_error) or 'rate' in str(api_error).lower():
                        logger.warning(f"⚠️ Rate limit hit, sleeping 10 seconds...")
                        time.sleep(10)
                        continue
                    else:
                        raise
                
                messages = page_result.get('messages', [])
                page_token = page_result.get('nextPageToken')
                
                logger.info(f"Page {result['pages_scanned']}: {len(messages)} messages")
                
                if not messages:
                    break
                
                # Process messages (same logic as monthly mode)
                for msg_info in messages:
                    message_id = msg_info['id']
                    result['messages_scanned'] += 1
                    sync_run.messages_scanned = result['messages_scanned']
                    
                    if max_messages and result['messages_scanned'] >= max_messages:
                        logger.info(f"Reached max_messages limit ({max_messages})")
                        page_token = None
                        break
                    
                    if result['messages_scanned'] % 20 == 0:
                        db.session.refresh(sync_run)
                        if sync_run.status == 'cancelled':
                            logger.info(f"⛔ Sync {sync_run.id} cancelled")
                            result['cancelled'] = True
                            page_token = None
                            break
                    
                    # Check if already processed (with no_autoflush to prevent SQLAlchemy warnings)
                    with db.session.no_autoflush:
                        existing = Receipt.query.filter_by(
                            business_id=business_id,
                            gmail_message_id=message_id
                        ).first()
                    
                    if existing:
                        result['skipped'] += 1
                        continue
                    
                    try:
                        message = gmail.get_message(message_id)
                        result['processed'] += 1
                        
                        is_receipt, confidence, metadata = check_is_receipt_email(message)
                        
                        if is_receipt:
                            result['candidate_receipts'] += 1
                            sync_run.candidate_receipts = result['candidate_receipts']
                        
                        if not is_receipt:
                            result['skipped'] += 1
                            continue
                        
                        # Process receipt (same logic as before - extracted for brevity)
                        email_html_snippet = extract_email_html(message)
                        attachment_id = None
                        pdf_text = ''
                        
                        # ... (same attachment processing as in monthly mode)
                        
                        # Extract and save receipt
                        extracted = extract_receipt_data(pdf_text, metadata)
                        
                        received_at = None
                        if metadata.get('date'):
                            try:
                                received_at = parsedate_to_datetime(metadata['date'])
                            except Exception:
                                received_at = datetime.now(timezone.utc)
                        else:
                            received_at = datetime.now(timezone.utc)
                        
                        status = 'approved' if confidence >= REVIEW_THRESHOLD else 'pending_review'
                        
                        invoice_date = None
                        if extracted.get('invoice_date'):
                            try:
                                invoice_date = datetime.strptime(extracted['invoice_date'], '%Y-%m-%d').date()
                            except ValueError:
                                pass
                        
                        # Create receipt record with sanitized JSON (no NUL characters for PostgreSQL)
                        raw_json_data = {
                            'metadata': metadata,
                            'extracted': extracted,
                            'pdf_text_preview': pdf_text[:500] if pdf_text else None
                        }
                        # Sanitize to remove \x00 and other PostgreSQL-incompatible characters
                        sanitized_json = sanitize_for_postgres(raw_json_data)
                        
                        receipt = Receipt(
                            business_id=business_id,
                            source='gmail',
                            gmail_message_id=message_id,
                            gmail_thread_id=message.get('threadId'),
                            from_email=metadata.get('from_email'),
                            subject=metadata.get('subject', '')[:500],
                            received_at=received_at,
                            email_subject=metadata.get('subject', '')[:500],
                            email_from=metadata.get('from_email'),
                            email_date=received_at,
                            email_html_snippet=email_html_snippet,
                            vendor_name=extracted.get('vendor_name'),
                            amount=extracted.get('amount'),
                            currency=extracted.get('currency', 'ILS'),
                            invoice_number=extracted.get('invoice_number'),
                            invoice_date=invoice_date,
                            confidence=confidence,
                            raw_extraction_json=sanitized_json,
                            status=status,
                            attachment_id=attachment_id
                        )
                        
                        db.session.add(receipt)
                        result['new_count'] += 1
                        result['saved_receipts'] += 1
                        sync_run.saved_receipts = result['saved_receipts']
                        
                        if result['new_count'] % 20 == 0:
                            sync_run.updated_at = datetime.now(timezone.utc)
                            db.session.commit()
                        
                    except Exception as e:
                        # Per-message error handling: rollback and continue to next message
                        logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
                        db.session.rollback()  # Rollback failed transaction
                        result['errors'] += 1
                        sync_run.errors_count = result['errors']
                        sync_run.error_message = f"{message_id}: {str(e)[:ERROR_MESSAGE_MAX_LENGTH]}"  # Track last error
                        # Continue to next message - don't fail entire sync
                
                if not page_token:
                    break
                
                time.sleep(0.2)  # 200ms between pages
                
                sync_run.last_page_token = page_token
                sync_run.updated_at = datetime.now(timezone.utc)
                db.session.commit()
            
            # Check if cancelled
            if result.get('cancelled'):
                sync_run.status = 'cancelled'
                sync_run.finished_at = datetime.now(timezone.utc)
                db.session.commit()
                logger.info(f"Gmail sync cancelled: {result}")
                return result
        
        # Final commit
        db.session.commit()
        
        # Update connection last sync time
        if connection:
            connection.last_sync_at = datetime.now(timezone.utc)
            db.session.commit()
        
        # Mark sync run as completed (even if there were errors)
        # The UI will check errors_count to determine if there were issues
        if sync_run.status not in ('paused', 'cancelled'):
            sync_run.status = 'completed'
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.pages_scanned = result['pages_scanned']
        sync_run.messages_scanned = result['messages_scanned']
        sync_run.candidate_receipts = result.get('candidate_receipts', 0)
        sync_run.saved_receipts = result['saved_receipts']
        sync_run.errors_count = result['errors']
        sync_run.last_heartbeat_at = datetime.now(timezone.utc)  # Final heartbeat
        sync_run.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        
        duration = (sync_run.finished_at - sync_run.started_at).total_seconds()
        
        # SUMMARY LOGGING: Show key metrics for verification
        total_emails_scanned = result['messages_scanned']
        total_receipts_saved = result['saved_receipts']
        total_skipped = result['skipped']
        receipts_to_emails_ratio = (total_receipts_saved / total_emails_scanned * 100) if total_emails_scanned > 0 else 0
        
        logger.info("=" * 80)
        logger.info(f"📊 SYNC SUMMARY (run_id={sync_run.id}, duration={duration:.1f}s)")
        logger.info(f"   Emails scanned: {total_emails_scanned}")
        logger.info(f"   Receipts saved: {total_receipts_saved}")
        logger.info(f"   Skipped (duplicates): {total_skipped}")
        logger.info(f"   Pages scanned: {result['pages_scanned']}")
        logger.info(f"   Candidate receipts: {result.get('candidate_receipts', 0)}")
        logger.info(f"   Errors: {result.get('errors', 0)}")
        logger.info(f"   Receipts/Emails ratio: {receipts_to_emails_ratio:.1f}%")
        if receipts_to_emails_ratio > 60:
            logger.warning(f"⚠️ High ratio ({receipts_to_emails_ratio:.1f}%) - possible false positives!")
        logger.info("=" * 80)
        
        if result['errors'] > 0:
            logger.warning(
                f"🏁 RUN_DONE: run_id={sync_run.id}, status=completed_with_errors, "
                f"duration={duration:.1f}s, saved={result['saved_receipts']}, "
                f"errors={result['errors']}"
            )
        else:
            logger.info(
                f"🏁 RUN_DONE: run_id={sync_run.id}, status=completed, "
                f"duration={duration:.1f}s, saved={result['saved_receipts']}, "
                f"messages={result['messages_scanned']}, pages={result['pages_scanned']}"
            )
        
        return result
        
    except Exception as e:
        logger.error(f"❌ RUN_FAIL: Gmail sync failed with exception: {e}", exc_info=True)
        
        # Mark sync run as failed
        try:
            db.session.rollback()  # Rollback first to clear any pending transactions
            sync_run.status = 'failed'
            sync_run.error_message = str(e)[:500]
            sync_run.finished_at = datetime.now(timezone.utc)
            sync_run.errors_count = result.get('errors', 0) + 1
            sync_run.last_heartbeat_at = datetime.now(timezone.utc)  # Mark failure time
            sync_run.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            logger.error(
                f"❌ RUN_FAIL: run_id={sync_run.id}, status=failed, "
                f"error={sync_run.error_message}"
            )
        except Exception as commit_error:
            logger.error(f"Failed to update sync_run status: {commit_error}")
        
        raise
    """
    Sync receipts from Gmail for a business with full pagination support
    
    Args:
        business_id: Business ID to sync
        mode: 'full' for full sync (all history) or 'incremental' for new messages only
        max_messages: Maximum total messages to process (None = unlimited)
        from_date: Start date for sync in YYYY-MM-DD format (optional, overrides mode)
        to_date: End date for sync in YYYY-MM-DD format (optional)
        
    Returns:
        Sync results with detailed counters
    """
    from server.db import db
    from server.models_sql import GmailConnection, Receipt, Attachment, ReceiptSyncRun
    from server.services.attachment_service import get_attachment_service
    
    logger.info(f"Starting Gmail sync for business {business_id}, mode={mode}")
    
    # Create sync run record
    sync_run = ReceiptSyncRun(
        business_id=business_id,
        mode=mode,
        status='running'
    )
    db.session.add(sync_run)
    db.session.commit()
    
    result = {
        'sync_run_id': sync_run.id,
        'new_count': 0,
        'processed': 0,
        'skipped': 0,
        'errors': 0,
        'pages_scanned': 0,
        'messages_scanned': 0,
        'candidate_receipts': 0,
        'saved_receipts': 0
    }
    
    try:
        gmail = get_gmail_service(business_id)
        connection = GmailConnection.query.filter_by(business_id=business_id).first()
        
        # Build search query based on date parameters or mode
        query_parts = []
        
        # Priority 1: Use explicit date range if provided
        if from_date or to_date:
            if from_date:
                try:
                    # Convert YYYY-MM-DD to Gmail format YYYY/MM/DD
                    from_dt = datetime.strptime(from_date, '%Y-%m-%d')
                    date_str = from_dt.strftime('%Y/%m/%d')
                    query_parts.append(f'after:{date_str}')
                    logger.info(f"📅 Using custom from_date: {date_str}")
                except ValueError:
                    logger.warning(f"Invalid from_date format: {from_date}, ignoring")
            
            if to_date:
                try:
                    # Convert YYYY-MM-DD to Gmail format YYYY/MM/DD
                    to_dt = datetime.strptime(to_date, '%Y-%m-%d')
                    date_str = to_dt.strftime('%Y/%m/%d')
                    query_parts.append(f'before:{date_str}')
                    logger.info(f"📅 Using custom to_date: {date_str}")
                except ValueError:
                    logger.warning(f"Invalid to_date format: {to_date}, ignoring")
        
        # Priority 2: Use mode if no explicit dates
        elif mode == 'full':
            # Full sync - broader query, go back as far as possible
            # Don't use date filter - get ALL emails
            logger.info("📅 Full sync mode - no date restrictions")
        else:
            # Incremental - check last sync time
            if connection and connection.last_sync_at:
                # Use last sync date with 30-day overlap to catch missed emails
                cutoff = connection.last_sync_at - timedelta(days=30)  # 30 days overlap for safety
                date_str = cutoff.strftime('%Y/%m/%d')
                query_parts.append(f'after:{date_str}')
                logger.info(f"📅 Incremental sync from: {date_str}")
            else:
                # No previous sync - go back 1 year to catch historical receipts
                query_parts.append('newer_than:1y')
                logger.info("📅 First sync - going back 1 year")
        
        # Add keyword filters for receipt/invoice detection
        # Match in subject OR body for flexibility
        keyword_filter = ' OR '.join([
            f'subject:"{kw}"' for kw in ['קבלה', 'חשבונית', 'invoice', 'receipt', 'payment', 'bill', 'billing']
        ] + [
            f'"{kw}"' for kw in ['קבלת תשלום', 'חשבונית מס', 'tax invoice', 'receipt of payment']
        ])
        
        # Build final query - include emails WITH or WITHOUT attachments
        # We'll detect receipts based on content, not just attachments
        if query_parts:
            query = f"{' '.join(query_parts)} ({keyword_filter})"
        else:
            query = f"({keyword_filter})"
        
        logger.info(f"Gmail query: {query}")
        
        attachment_service = get_attachment_service()
        page_token = None
        total_processed = 0
        
        # Pagination loop - continue until no more pages or max_messages reached or cancelled
        while True:
            # Check for cancellation at start of each page
            db.session.refresh(sync_run)
            if sync_run.status == 'cancelled':
                logger.info(f"⛔ Sync {sync_run.id} cancelled by user")
                result['cancelled'] = True
                break
            
            result['pages_scanned'] += 1
            sync_run.pages_scanned = result['pages_scanned']
            
            # Get page of messages
            page_result = gmail.list_messages(
                query=query, 
                max_results=100,  # Max per page
                page_token=page_token
            )
            
            messages = page_result.get('messages', [])
            page_token = page_result.get('nextPageToken')
            
            logger.info(f"Page {result['pages_scanned']}: {len(messages)} messages, has_next={bool(page_token)}")
            
            if not messages:
                break
            
            # Process messages in this page
            for msg_info in messages:
                message_id = msg_info['id']
                result['messages_scanned'] += 1
                sync_run.messages_scanned = result['messages_scanned']
                
                # Check max_messages limit
                if max_messages and result['messages_scanned'] >= max_messages:
                    logger.info(f"Reached max_messages limit ({max_messages})")
                    page_token = None  # Stop pagination
                    break
                
                # Check for cancellation every 10 messages to avoid excessive DB queries
                if result['messages_scanned'] % 20 == 0:
                    db.session.refresh(sync_run)
                    if sync_run.status == 'cancelled':
                        logger.info(f"⛔ Sync {sync_run.id} cancelled by user (during message processing)")
                        result['cancelled'] = True
                        page_token = None  # Stop pagination
                        break
                
                # Check if already processed (with no_autoflush to prevent SQLAlchemy warnings)
                with db.session.no_autoflush:
                    existing = Receipt.query.filter_by(
                        business_id=business_id,
                        gmail_message_id=message_id
                    ).first()
                
                if existing:
                    result['skipped'] += 1
                    continue
                
                try:
                    # Process receipt using extracted helper function
                    receipt = process_single_receipt_message(
                        message_id=message_id,
                        gmail=gmail,
                        business_id=business_id,
                        attachment_service=attachment_service,
                        result=result,
                        sync_run=sync_run
                    )
                    
                    # Commit every 10 receipts (no sleep)
                    if receipt and result['saved_receipts'] % 20 == 0:
                        sync_run.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                    
                except Exception as e:
                    # Per-message error handling: rollback and continue to next message
                    logger.error(f"❌ Error processing message {message_id}: {e}", exc_info=True)
                    try:
                        db.session.rollback()  # Rollback failed transaction
                    except Exception as rollback_err:
                        logger.error(f"❌ Rollback failed: {rollback_err}")
                    result['errors'] += 1
                    sync_run.errors_count = result['errors']
                    sync_run.error_message = f"{message_id}: {str(e)[:ERROR_MESSAGE_MAX_LENGTH]}"  # Track last error
                    # Continue to next message - don't fail entire sync
            
            # Check if we should continue to next page
            if not page_token:
                break
            
            # Update sync run with progress
            sync_run.last_page_token = page_token
            sync_run.updated_at = datetime.now(timezone.utc)
            db.session.commit()
            
            logger.info(f"Progress: pages={result['pages_scanned']}, messages={result['messages_scanned']}, receipts={result['saved_receipts']}")
        
        # Final commit
        db.session.commit()
        
        # Check if sync was cancelled
        if result.get('cancelled'):
            # Mark sync run as cancelled (don't override with 'completed')
            sync_run.status = 'cancelled'
            sync_run.finished_at = datetime.now(timezone.utc)
            db.session.commit()
            logger.info(f"Gmail sync cancelled by user: {result}")
            return result
        
        # Update connection last sync time
        if connection:
            connection.last_sync_at = datetime.now(timezone.utc)
            db.session.commit()
        
        # Mark sync run as completed (even if there were errors)
        # The UI will check errors_count to determine if there were issues
        if sync_run.status not in ('paused', 'cancelled'):
            sync_run.status = 'completed'
        sync_run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        
        if result['errors'] > 0:
            logger.warning(f"Gmail sync completed with {result['errors']} errors: {result}")
        else:
            logger.info(f"Gmail sync completed successfully: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Gmail sync failed: {e}", exc_info=True)
        
        # Mark sync run as failed
        sync_run.status = 'failed'
        sync_run.error_message = str(e)[:500]
        sync_run.finished_at = datetime.now(timezone.utc)
        sync_run.errors_count = result['errors'] + 1
        db.session.commit()
        
        raise


def _convert_png_to_pdf(png_path: str) -> bytes:
    """
    Helper function to convert PNG image to PDF format
    
    Args:
        png_path: Path to PNG file
        
    Returns:
        PDF bytes
        
    Raises:
        Exception if conversion fails
    """
    import tempfile
    import os
    from PIL import Image
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_pdf:
        pdf_path = tmp_pdf.name
    
    try:
        img = Image.open(png_path)
        # Convert to RGB if necessary (PDF doesn't support RGBA)
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        img.save(pdf_path, 'PDF', resolution=100.0)
        
        # Read the PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        return pdf_data
    finally:
        # Always clean up temp PDF file
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)


def generate_email_screenshot(email_html: str, business_id: int, receipt_id: int = None) -> Optional[int]:
    """
    Generate a PDF screenshot from email HTML content
    
    MASTER INSTRUCTION COMPLIANCE:
    - ALWAYS generates PDF (not PNG) - Rule 3
    - Filename: email_snapshot.pdf - Rule 3
    - Contains email body only (HTML rendered) - Rule 4
    - Used for ALL processed emails - Rule 2
    
    Args:
        email_html: HTML content of the email
        business_id: Business ID for storage
        receipt_id: Receipt ID for logging (optional)
        
    Returns:
        Attachment ID if successful, None otherwise
    """
    try:
        # Method 1: Try using Playwright to generate PDF directly
        if PLAYWRIGHT_AVAILABLE:
            try:
                import tempfile
                import os
                
                logger.info(f"📄 Generating HTML snapshot as PDF with Playwright for receipt {receipt_id or 'unknown'}")
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 800, 'height': 1200})
                    
                    # Set HTML content
                    page.set_content(email_html)
                    
                    # Wait for content to load
                    page.wait_for_load_state('networkidle')
                    
                    # Create temp PDF file - CRITICAL: Must be PDF, not PNG (Rule 3)
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
                        pdf_path = tmp.name
                    
                    # Generate PDF directly (not screenshot)
                    page.pdf(
                        path=pdf_path,
                        format='A4',
                        print_background=True,
                        display_header_footer=False
                    )
                    browser.close()
                    
                    # Read the PDF
                    with open(pdf_path, 'rb') as f:
                        pdf_data = f.read()
                    
                    # Clean up temp file
                    os.unlink(pdf_path)
                    
                    if pdf_data:
                        # Save to storage
                        from server.services.attachment_service import get_attachment_service
                        from server.models_sql import Attachment
                        from server.db import db
                        from werkzeug.datastructures import FileStorage
                        from io import BytesIO
                        
                        attachment_service = get_attachment_service()
                        
                        # CRITICAL: Filename must be email_snapshot.pdf (Rule 3)
                        file_storage = FileStorage(
                            stream=BytesIO(pdf_data),
                            filename='email_snapshot.pdf',
                            content_type='application/pdf'
                        )
                        
                        # Create attachment record
                        attachment = Attachment(
                            business_id=business_id,
                            filename_original='email_snapshot.pdf',
                            mime_type='application/pdf',
                            file_size=0,
                            storage_path='',
                            purpose='receipt_source',
                            origin_module='receipts',
                            channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                        )
                        db.session.add(attachment)
                        db.session.flush()
                        
                        # Save file
                        storage_key, file_size = attachment_service.save_file(
                            file=file_storage,
                            business_id=business_id,
                            attachment_id=attachment.id,
                            purpose='receipt_source'
                        )
                        
                        attachment.storage_path = storage_key
                        attachment.file_size = file_size
                        db.session.commit()
                        
                        logger.info(f"✅ Email snapshot PDF generated with Playwright: attachment_id={attachment.id}, size={file_size}")
                        return attachment.id
                        
            except Exception as e:
                logger.warning(f"Playwright PDF generation failed: {e}, trying PNG-to-PDF fallback")
                # Fallback: Generate PNG then convert to PDF
                try:
                    import tempfile
                    import os
                    
                    logger.info(f"📄 Fallback: Generating PNG then converting to PDF")
                    
                    with sync_playwright() as p:
                        browser = p.chromium.launch(headless=True)
                        page = browser.new_page(viewport={'width': 800, 'height': 1200})
                        page.set_content(email_html)
                        page.wait_for_load_state('networkidle')
                        
                        # Take PNG screenshot
                        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                            screenshot_path = tmp.name
                        page.screenshot(path=screenshot_path, full_page=True)
                        browser.close()
                        
                        # Convert PNG to PDF using helper function
                        pdf_data = _convert_png_to_pdf(screenshot_path)
                        
                        # Clean up temp PNG file
                        os.unlink(screenshot_path)
                        
                        if pdf_data:
                            from server.services.attachment_service import get_attachment_service
                            from server.models_sql import Attachment
                            from server.db import db
                            from werkzeug.datastructures import FileStorage
                            from io import BytesIO
                            
                            attachment_service = get_attachment_service()
                            
                            file_storage = FileStorage(
                                stream=BytesIO(pdf_data),
                                filename='email_snapshot.pdf',
                                content_type='application/pdf'
                            )
                            
                            attachment = Attachment(
                                business_id=business_id,
                                filename_original='email_snapshot.pdf',
                                mime_type='application/pdf',
                                file_size=0,
                                storage_path='',
                                purpose='receipt_source',
                                origin_module='receipts',
                                channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                            )
                            db.session.add(attachment)
                            db.session.flush()
                            
                            storage_key, file_size = attachment_service.save_file(
                                file=file_storage,
                                business_id=business_id,
                                attachment_id=attachment.id,
                                purpose='receipt_source'
                            )
                            
                            attachment.storage_path = storage_key
                            attachment.file_size = file_size
                            db.session.commit()
                            
                            logger.info(f"✅ Email snapshot PDF generated via PNG conversion: attachment_id={attachment.id}, size={file_size}")
                            return attachment.id
                except Exception as fallback_err:
                    logger.error(f"PNG-to-PDF fallback failed: {fallback_err}")
        else:
            logger.debug("Playwright not available, trying alternative methods")
        
        # Method 2: Try using html2image (convert PNG to PDF)
        try:
            from html2image import Html2Image
            import tempfile
            import os
            
            logger.info(f"📄 Method 2: Generating PDF via html2image for receipt {receipt_id or 'unknown'}")
            
            hti = Html2Image()
            
            # Create temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Generate PNG screenshot
                output_file = hti.screenshot(
                    html_str=email_html,
                    save_as='receipt_screenshot.png',
                    size=(800, 1200)
                )
                
                if output_file and len(output_file) > 0:
                    png_path = output_file[0]
                    
                    # Convert PNG to PDF using helper function
                    pdf_data = _convert_png_to_pdf(png_path)
                    
                    # Save to storage
                    from server.services.attachment_service import get_attachment_service
                    from server.models_sql import Attachment
                    from server.db import db
                    from werkzeug.datastructures import FileStorage
                    from io import BytesIO
                    
                    attachment_service = get_attachment_service()
                    
                    file_storage = FileStorage(
                        stream=BytesIO(pdf_data),
                        filename='email_snapshot.pdf',
                        content_type='application/pdf'
                    )
                    
                    # Create attachment record
                    attachment = Attachment(
                        business_id=business_id,
                        filename_original='email_snapshot.pdf',
                        mime_type='application/pdf',
                        file_size=0,
                        storage_path='',
                        purpose='receipt_source',
                        origin_module='receipts',
                        channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                    )
                    db.session.add(attachment)
                    db.session.flush()
                    
                    # Save file
                    storage_key, file_size = attachment_service.save_file(
                        file=file_storage,
                        business_id=business_id,
                        attachment_id=attachment.id,
                        purpose='receipt_source'
                    )
                    
                    attachment.storage_path = storage_key
                    attachment.file_size = file_size
                    db.session.commit()
                    
                    logger.info(f"✅ Email snapshot PDF generated with html2image: attachment_id={attachment.id}")
                    return attachment.id
                    
        except ImportError:
            logger.debug("html2image not available")
        except Exception as e:
            logger.warning(f"html2image PDF generation failed: {e}")
        
        # Method 3: Try using weasyprint (generates PDF directly)
        try:
            from weasyprint import HTML as WeasyprintHTML
            
            logger.info(f"📄 Method 3: Generating PDF with weasyprint for receipt {receipt_id or 'unknown'}")
            
            # Generate PDF directly from HTML (weasyprint's native format)
            html_obj = WeasyprintHTML(string=email_html)
            pdf_bytes = html_obj.write_pdf()
            
            if pdf_bytes:
                # Save to storage
                from server.services.attachment_service import get_attachment_service
                from server.models_sql import Attachment
                from server.db import db
                from werkzeug.datastructures import FileStorage
                from io import BytesIO
                
                attachment_service = get_attachment_service()
                
                file_storage = FileStorage(
                    stream=BytesIO(pdf_bytes),
                    filename='email_snapshot.pdf',
                    content_type='application/pdf'
                )
                
                # Create attachment record
                attachment = Attachment(
                    business_id=business_id,
                    filename_original='email_snapshot.pdf',
                    mime_type='application/pdf',
                    file_size=0,
                    storage_path='',
                    purpose='receipt_source',
                    origin_module='receipts',
                    channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                )
                db.session.add(attachment)
                db.session.flush()
                
                # Save file
                storage_key, file_size = attachment_service.save_file(
                    file=file_storage,
                    business_id=business_id,
                    attachment_id=attachment.id,
                    purpose='receipt_source'
                )
                
                attachment.storage_path = storage_key
                attachment.file_size = file_size
                db.session.commit()
                
                logger.info(f"✅ Email snapshot PDF generated with weasyprint: attachment_id={attachment.id}")
                return attachment.id
                
        except ImportError:
            logger.debug("weasyprint not available")
        except Exception as e:
            logger.warning(f"weasyprint PDF generation failed: {e}")
        
        # If all methods fail, log critical error (Rule 2: Screenshot mandatory!)
        logger.error(f"❌ CRITICAL: Could not generate email snapshot PDF - no suitable library available")
        logger.error(f"❌ This violates Rule 2: Screenshot mandatory for ALL processed emails")
        return None
        
    except Exception as e:
        logger.error(f"❌ Email snapshot PDF generation failed: {e}", exc_info=True)
        return None


def extract_email_html(message: dict) -> str:
    """
    Extract HTML content from Gmail message for preview generation
    
    Args:
        message: Gmail message object
        
    Returns:
        HTML snippet (first 10KB for database efficiency)
    """
    def find_html_part(parts):
        """Recursively find HTML part"""
        for part in parts:
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/html':
                # Found HTML part
                body = part.get('body', {})
                data = body.get('data', '')
                if data:
                    # Decode from base64
                    import base64
                    try:
                        html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                        return html
                    except Exception:
                        pass
            
            # Recurse into multipart
            if 'parts' in part:
                html = find_html_part(part['parts'])
                if html:
                    return html
        
        return None
    
    payload = message.get('payload', {})
    
    # Try to find HTML part
    if 'parts' in payload:
        html = find_html_part(payload['parts'])
        if html:
            # Limit to 10KB for database efficiency
            return html[:10000]
    
    # Fallback to plain text or snippet
    snippet = message.get('snippet', '')
    return f"<div>{snippet}</div>"[:10000] if snippet else ""
