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

# Receipt detection keywords (Hebrew + English)
RECEIPT_KEYWORDS = [
    # Hebrew
    'קבלה', 'חשבונית', 'חשבונית מס', 'קבלת תשלום',
    # English
    'invoice', 'receipt', 'payment confirmation', 'tax invoice',
    'order confirmation', 'payment receipt', 'billing statement'
]

# Known receipt sender domains
KNOWN_RECEIPT_DOMAINS = [
    'paypal.com', 'stripe.com', 'square.com',
    'greeninvoice.co.il', 'icount.co.il', 'invoice4u.co.il',
    'amazon.com', 'ebay.com', 'aliexpress.com',
    'apple.com', 'google.com', 'microsoft.com',
    'uber.com', 'lyft.com', 'wolt.com', 'doordash.com',
    # Israeli services
    'pelephone.co.il', 'partner.co.il', 'cellcom.co.il',
    'bezeq.co.il', 'hot.net.il', 'yes.co.il'
]

# PDF receipt indicators (for confidence scoring)
PDF_RECEIPT_INDICATORS = [
    # Hebrew
    'סה"כ', "סה''כ", 'סהכ', 'מע"מ', "מע''מ",
    'חשבונית מס', 'קבלה מס', 'תאריך',
    'לתשלום', 'שולם', 'תודה על הקנייה',
    # English
    'total', 'subtotal', 'tax', 'vat',
    'invoice number', 'receipt number',
    'amount due', 'paid', 'payment received',
    'thank you for your purchase'
]

# Minimum confidence to save as receipt (lowered to catch more receipts)
MIN_CONFIDENCE = 20  # Lower threshold to catch more potential receipts
REVIEW_THRESHOLD = 60  # Below this goes to pending_review


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


def check_is_receipt_email(message: dict) -> Tuple[bool, int, dict]:
    """
    Check if an email is likely to contain a receipt
    
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
    
    # Check for attachments
    has_pdf = False
    has_image = False
    attachments = []
    
    def check_parts(parts):
        nonlocal has_pdf, has_image
        for part in parts:
            mime_type = part.get('mimeType', '')
            filename = part.get('filename', '')
            
            if part.get('body', {}).get('attachmentId'):
                attachments.append({
                    'id': part['body']['attachmentId'],
                    'filename': filename,
                    'mime_type': mime_type,
                    'size': part.get('body', {}).get('size', 0)
                })
            
            if mime_type == 'application/pdf':
                has_pdf = True
            elif mime_type.startswith('image/'):
                has_image = True
            
            # Recurse into multipart
            if 'parts' in part:
                check_parts(part['parts'])
    
    payload = message.get('payload', {})
    if 'parts' in payload:
        check_parts(payload['parts'])
    
    metadata['attachments'] = attachments
    metadata['has_attachment'] = has_pdf or has_image
    
    # NEW LOGIC: Check for receipt keywords in subject/content first
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
    
    # PDF attachment is a strong indicator
    if has_pdf:
        confidence += 40  # Increased from 30 - PDFs are strong receipt indicators
    elif has_image:
        confidence += 20  # Increased from 10 - images can be receipt photos
    
    # Check sender domain
    if from_domain in KNOWN_RECEIPT_DOMAINS:
        confidence += 40  # Increased from 35
    
    # Extract email snippet for additional analysis
    snippet = message.get('snippet', '').lower()
    metadata['snippet'] = snippet
    
    # Check snippet for receipt indicators
    snippet_indicators = ['total', 'amount', 'סכום', 'סה"כ', 'payment', 'תשלום', '₪', '$', 'paid', 'שולם']
    for indicator in snippet_indicators:
        if indicator in snippet:
            confidence += 5
            break
    
    # Even with low confidence, if we have keywords or attachment, it's worth reviewing
    # The worst case is user marks it as "not a receipt"
    if confidence < MIN_CONFIDENCE and (matched_keywords or has_pdf or has_image):
        # Give minimum confidence if we have indicators
        confidence = MIN_CONFIDENCE
    
    # Must have at least SOME indicator to be considered a receipt
    is_receipt = confidence >= MIN_CONFIDENCE
    
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


def sync_gmail_receipts(business_id: int, mode: str = 'incremental', max_messages: int = None, 
                       from_date: str = None, to_date: str = None) -> dict:
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
                from datetime import datetime, timedelta
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
                if result['messages_scanned'] % 10 == 0:
                    db.session.refresh(sync_run)
                    if sync_run.status == 'cancelled':
                        logger.info(f"⛔ Sync {sync_run.id} cancelled by user (during message processing)")
                        result['cancelled'] = True
                        page_token = None  # Stop pagination
                        break
                
                # Check if already processed
                existing = Receipt.query.filter_by(
                    business_id=business_id,
                    gmail_message_id=message_id
                ).first()
                
                if existing:
                    result['skipped'] += 1
                    continue
                
                try:
                    # Get full message
                    message = gmail.get_message(message_id)
                    result['processed'] += 1
                    
                    # Check if it's a receipt with internal scoring
                    is_receipt, confidence, metadata = check_is_receipt_email(message)
                    
                    if is_receipt:
                        result['candidate_receipts'] += 1
                        sync_run.candidate_receipts = result['candidate_receipts']
                    
                    if not is_receipt:
                        result['skipped'] += 1
                        continue
                    
                    # Extract email body/HTML for preview generation and screenshots
                    email_html_snippet = extract_email_html(message)
                    
                    # Process first PDF or image attachment
                    attachment_id = None
                    pdf_text = ''
                    attachment_processed = False
                    
                    for att in metadata.get('attachments', []):
                        if att['mime_type'] in ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']:
                            try:
                                logger.info(f"📎 Downloading attachment: {att['filename']} ({att['mime_type']}, {att['size']} bytes)")
                                
                                # Download attachment
                                att_data = gmail.get_attachment(message_id, att['id'])
                                
                                if not att_data:
                                    logger.warning(f"⚠️ Empty attachment data for {att['filename']}")
                                    continue
                                
                                logger.info(f"✅ Downloaded {len(att_data)} bytes")
                                
                                # Extract text if PDF
                                if att['mime_type'] == 'application/pdf':
                                    pdf_text = extract_pdf_text(att_data)
                                    logger.info(f"📄 Extracted {len(pdf_text)} chars from PDF")
                                    
                                    # Calculate additional confidence from PDF content
                                    pdf_confidence = calculate_pdf_confidence(pdf_text)
                                    confidence = min(confidence + pdf_confidence, 100)
                                    logger.info(f"📊 PDF confidence boost: +{pdf_confidence} -> total {confidence}")
                                
                                # Save to storage with purpose
                                from werkzeug.datastructures import FileStorage
                                from io import BytesIO
                                
                                file_storage = FileStorage(
                                    stream=BytesIO(att_data),
                                    filename=att['filename'] or 'receipt.pdf',
                                    content_type=att['mime_type']
                                )
                                
                                # Create attachment record
                                attachment = Attachment(
                                    business_id=business_id,
                                    filename_original=att['filename'] or 'receipt',
                                    mime_type=att['mime_type'],
                                    file_size=0,  # Will be updated after save
                                    storage_path='',  # Will be updated after save
                                    purpose='receipt_source',  # Mark as receipt source
                                    origin_module='receipts',  # Set origin
                                    channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                                )
                                db.session.add(attachment)
                                db.session.flush()  # Get attachment ID
                                
                                logger.info(f"💾 Saving attachment to storage (attachment_id={attachment.id})")
                                
                                # Save file via attachment service
                                storage_key, file_size = attachment_service.save_file(
                                    file=file_storage,
                                    business_id=business_id,
                                    attachment_id=attachment.id,
                                    purpose='receipt_source'
                                )
                                
                                # Update attachment record
                                attachment.storage_path = storage_key
                                attachment.file_size = file_size
                                attachment_id = attachment.id
                                attachment_processed = True
                                
                                logger.info(f"✅ Attachment saved: storage_key={storage_key}, size={file_size}")
                                
                                break  # Only process first attachment
                                
                            except Exception as e:
                                logger.error(f"❌ Failed to process attachment {att['filename']}: {e}", exc_info=True)
                                result['errors'] += 1
                    
                    if not attachment_processed:
                        logger.info(f"📧 No file attachments found, will generate email screenshot")
                        
                        # NEW: Generate screenshot from email HTML if we have content
                        if email_html_snippet:
                            try:
                                screenshot_attachment_id = generate_email_screenshot(
                                    email_html=email_html_snippet,
                                    business_id=business_id,
                                    receipt_id=None  # Will be set after receipt creation
                                )
                                
                                if screenshot_attachment_id:
                                    attachment_id = screenshot_attachment_id
                                    attachment_processed = True
                                    logger.info(f"✅ Generated email screenshot as attachment: {screenshot_attachment_id}")
                                else:
                                    logger.warning(f"⚠️ Failed to generate email screenshot")
                            except Exception as e:
                                logger.error(f"❌ Error generating email screenshot: {e}", exc_info=True)
                    
                    # Don't skip if we have no attachment but good confidence from keywords
                    # User wants to see ALL receipts, even without images
                    if not attachment_processed and confidence < MIN_CONFIDENCE:
                        logger.info(f"⏭️ Skipping: no attachment and low confidence ({confidence})")
                        result['skipped'] += 1
                        continue
                    
                    # Extract structured data
                    extracted = extract_receipt_data(pdf_text, metadata)
                    
                    # Parse received date from email header
                    received_at = None
                    if metadata.get('date'):
                        try:
                            received_at = parsedate_to_datetime(metadata['date'])
                        except Exception as e:
                            logger.warning(f"Failed to parse email date '{metadata.get('date')}': {e}")
                            received_at = datetime.now(timezone.utc)
                    else:
                        # Fallback to current time if no date header
                        received_at = datetime.now(timezone.utc)
                    
                    # Determine status based on confidence
                    status = 'approved' if confidence >= REVIEW_THRESHOLD else 'pending_review'
                    
                    # Parse invoice date safely
                    invoice_date = None
                    if extracted.get('invoice_date'):
                        try:
                            invoice_date = datetime.strptime(extracted['invoice_date'], '%Y-%m-%d').date()
                        except ValueError:
                            logger.warning(f"Invalid invoice date format: {extracted['invoice_date']}")
                    
                    # Create receipt record with email content
                    receipt = Receipt(
                        business_id=business_id,
                        source='gmail',
                        gmail_message_id=message_id,
                        gmail_thread_id=message.get('threadId'),
                        from_email=metadata.get('from_email'),
                        subject=metadata.get('subject', '')[:500],
                        received_at=received_at,
                        # Email content for preview
                        email_subject=metadata.get('subject', '')[:500],
                        email_from=metadata.get('from_email'),
                        email_date=received_at,
                        email_html_snippet=email_html_snippet,
                        # Extracted data
                        vendor_name=extracted.get('vendor_name'),
                        amount=extracted.get('amount'),
                        currency=extracted.get('currency', 'ILS'),
                        invoice_number=extracted.get('invoice_number'),
                        invoice_date=invoice_date,
                        confidence=confidence,
                        raw_extraction_json={
                            'metadata': metadata,
                            'extracted': extracted,
                            'pdf_text_preview': pdf_text[:500] if pdf_text else None
                        },
                        status=status,
                        attachment_id=attachment_id
                    )
                    
                    db.session.add(receipt)
                    result['new_count'] += 1
                    result['saved_receipts'] += 1
                    sync_run.saved_receipts = result['saved_receipts']
                    
                    logger.info(
                        f"✅ Created receipt: id={message_id[:10]}..., "
                        f"vendor={extracted.get('vendor_name')}, "
                        f"amount={extracted.get('amount')} {extracted.get('currency', 'ILS')}, "
                        f"invoice_num={extracted.get('invoice_number')}, "
                        f"confidence={confidence}, "
                        f"status={status}, "
                        f"has_attachment={bool(attachment_id)}"
                    )
                    
                    # Commit to get receipt ID
                    db.session.flush()
                    
                    # Generate preview asynchronously (don't fail sync if preview fails)
                    try:
                        from server.services.receipt_preview_service import generate_receipt_preview
                        if generate_receipt_preview(receipt.id):
                            sync_run.preview_generated_count += 1
                            logger.info(f"✅ Generated preview for receipt {receipt.id}")
                    except Exception as preview_error:
                        logger.warning(f"Preview generation failed for receipt {receipt.id}: {preview_error}")
                    
                    # Commit periodically (every 10 receipts)
                    if result['new_count'] % 10 == 0:
                        sync_run.updated_at = datetime.now(timezone.utc)
                        db.session.commit()
                    
                except Exception as e:
                    logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
                    result['errors'] += 1
                    sync_run.errors_count = result['errors']
            
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
        
        # Mark sync run as completed
        sync_run.status = 'completed'
        sync_run.finished_at = datetime.now(timezone.utc)
        db.session.commit()
        
        logger.info(f"Gmail sync complete: {result}")
        
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


def generate_email_screenshot(email_html: str, business_id: int, receipt_id: int = None) -> Optional[int]:
    """
    Generate a screenshot/image from email HTML content
    Used when receipt has no PDF/image attachment
    
    Args:
        email_html: HTML content of the email
        business_id: Business ID for storage
        receipt_id: Receipt ID for logging (optional)
        
    Returns:
        Attachment ID if successful, None otherwise
    """
    try:
        # Method 1: Try using Playwright (already available in dependencies)
        if PLAYWRIGHT_AVAILABLE:
            try:
                import tempfile
                import os
                
                logger.info(f"🖼️ Generating HTML screenshot with Playwright for receipt {receipt_id or 'unknown'}")
                
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page(viewport={'width': 800, 'height': 1200})
                    
                    # Set HTML content
                    page.set_content(email_html)
                    
                    # Wait for content to load
                    page.wait_for_load_state('networkidle')
                    
                    # Create temp file
                    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                        screenshot_path = tmp.name
                    
                    # Take screenshot
                    page.screenshot(path=screenshot_path, full_page=True)
                    browser.close()
                    
                    # Read the screenshot
                    with open(screenshot_path, 'rb') as f:
                        screenshot_data = f.read()
                    
                    # Clean up temp file
                    os.unlink(screenshot_path)
                    
                    if screenshot_data:
                        # Save to storage
                        from server.services.attachment_service import get_attachment_service
                        from server.models_sql import Attachment
                        from server.db import db
                        from werkzeug.datastructures import FileStorage
                        from io import BytesIO
                        
                        attachment_service = get_attachment_service()
                        
                        file_storage = FileStorage(
                            stream=BytesIO(screenshot_data),
                            filename='email_screenshot.png',
                            content_type='image/png'
                        )
                        
                        # Create attachment record
                        attachment = Attachment(
                            business_id=business_id,
                            filename_original='email_screenshot.png',
                            mime_type='image/png',
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
                        
                        logger.info(f"✅ Email screenshot generated with Playwright: attachment_id={attachment.id}, size={file_size}")
                        return attachment.id
                        
            except Exception as e:
                logger.warning(f"Playwright screenshot failed: {e}")
        else:
            logger.debug("Playwright not available, trying alternative methods")
        
        # Method 2: Try using html2image
        try:
            from html2image import Html2Image
            import tempfile
            
            logger.info(f"🖼️ Generating HTML screenshot with html2image for receipt {receipt_id or 'unknown'}")
            
            hti = Html2Image()
            
            # Create temp directory
            with tempfile.TemporaryDirectory() as tmpdir:
                # Generate screenshot
                output_file = hti.screenshot(
                    html_str=email_html,
                    save_as='receipt_screenshot.png',
                    size=(800, 1200)
                )
                
                if output_file and len(output_file) > 0:
                    screenshot_path = output_file[0]
                    
                    # Read the file
                    with open(screenshot_path, 'rb') as f:
                        screenshot_data = f.read()
                    
                    # Save to storage
                    from server.services.attachment_service import get_attachment_service
                    from server.models_sql import Attachment
                    from server.db import db
                    from werkzeug.datastructures import FileStorage
                    from io import BytesIO
                    
                    attachment_service = get_attachment_service()
                    
                    file_storage = FileStorage(
                        stream=BytesIO(screenshot_data),
                        filename='email_screenshot.png',
                        content_type='image/png'
                    )
                    
                    # Create attachment record
                    attachment = Attachment(
                        business_id=business_id,
                        filename_original='email_screenshot.png',
                        mime_type='image/png',
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
                    
                    logger.info(f"✅ Email screenshot generated with html2image: attachment_id={attachment.id}")
                    return attachment.id
                    
        except ImportError:
            logger.debug("html2image not available")
        except Exception as e:
            logger.warning(f"html2image screenshot failed: {e}")
        
        # Method 3: Try using weasyprint for HTML to PNG
        try:
            from weasyprint import HTML as WeasyprintHTML
            
            logger.info(f"🖼️ Generating HTML screenshot with weasyprint for receipt {receipt_id or 'unknown'}")
            
            # Generate PNG from HTML
            html_obj = WeasyprintHTML(string=email_html)
            png_bytes = html_obj.write_png()
            
            if png_bytes:
                # Save to storage
                from server.services.attachment_service import get_attachment_service
                from server.models_sql import Attachment
                from server.db import db
                from werkzeug.datastructures import FileStorage
                from io import BytesIO
                
                attachment_service = get_attachment_service()
                
                file_storage = FileStorage(
                    stream=BytesIO(png_bytes),
                    filename='email_screenshot.png',
                    content_type='image/png'
                )
                
                # Create attachment record
                attachment = Attachment(
                    business_id=business_id,
                    filename_original='email_screenshot.png',
                    mime_type='image/png',
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
                
                logger.info(f"✅ Email screenshot generated with weasyprint: attachment_id={attachment.id}")
                return attachment.id
                
        except ImportError:
            logger.debug("weasyprint not available")
        except Exception as e:
            logger.warning(f"weasyprint screenshot failed: {e}")
        
        # If all methods fail, return None
        logger.warning(f"⚠️ Could not generate email screenshot - no suitable library available")
        return None
        
    except Exception as e:
        logger.error(f"❌ Email screenshot generation failed: {e}", exc_info=True)
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
