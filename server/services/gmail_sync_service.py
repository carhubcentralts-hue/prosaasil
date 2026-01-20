"""
Gmail Sync Service - Fetches and processes receipts from Gmail

Features:
- OAuth token management with automatic refresh
- Email fetching with receipt detection
- PDF text extraction for confidence scoring
- Integration with unified attachment service
- Rate limiting and error handling

Receipt Detection Algorithm:
1. Quick filter: Only emails with PDF/image attachments
2. Subject/sender keyword matching (קבלה, חשבונית, invoice, receipt)
3. Known vendor domain matching
4. PDF text extraction for confidence scoring

Security:
- Encrypted refresh tokens
- No raw token logging
- Multi-tenant isolation
"""

import logging
import base64
import os
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from email.utils import parsedate_to_datetime

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

# Minimum confidence to save as receipt
MIN_CONFIDENCE = 40
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
    
    # No attachments = not a receipt
    if not has_pdf and not has_image:
        return False, 0, metadata
    
    # PDF attachment is a strong indicator
    if has_pdf:
        confidence += 30
    elif has_image:
        confidence += 10
    
    # Check subject for keywords
    subject_lower = subject.lower()
    for keyword in RECEIPT_KEYWORDS:
        if keyword.lower() in subject_lower:
            confidence += 25
            break
    
    # Check sender domain
    if from_domain in KNOWN_RECEIPT_DOMAINS:
        confidence += 35
    
    # If confidence is too low, skip
    if confidence < MIN_CONFIDENCE:
        return False, confidence, metadata
    
    return True, confidence, metadata


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
    
    Args:
        pdf_text: Extracted PDF text
        metadata: Email metadata
        
    Returns:
        Extracted receipt data
    """
    data = {
        'vendor_name': None,
        'amount': None,
        'currency': 'ILS',
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
    
    # Extract amount (ILS first, then USD)
    ils_match = re.search(r'(?:סה"כ|total|לתשלום)[:\s]*₪?\s*([\d,]+\.?\d*)', pdf_text, re.IGNORECASE)
    if ils_match:
        try:
            data['amount'] = float(ils_match.group(1).replace(',', ''))
            data['currency'] = 'ILS'
        except ValueError:
            pass
    else:
        usd_match = re.search(r'(?:total|amount)[:\s]*\$?\s*([\d,]+\.?\d*)', pdf_text, re.IGNORECASE)
        if usd_match:
            try:
                data['amount'] = float(usd_match.group(1).replace(',', ''))
                data['currency'] = 'USD'
            except ValueError:
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


def sync_gmail_receipts(business_id: int, mode: str = 'incremental', max_messages: int = None) -> dict:
    """
    Sync receipts from Gmail for a business with full pagination support
    
    Args:
        business_id: Business ID to sync
        mode: 'full' for full sync (all history) or 'incremental' for new messages only
        max_messages: Maximum total messages to process (None = unlimited)
        
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
        
        # Build search query based on mode
        if mode == 'full':
            # Full sync - broader query, go back further
            query_parts = [
                'has:attachment',
                'newer_than:5y',  # Last 5 years
            ]
        else:
            # Incremental - check last sync time
            if connection and connection.last_sync_at:
                # Use last sync date
                from datetime import datetime, timedelta
                cutoff = connection.last_sync_at - timedelta(days=1)  # 1 day overlap for safety
                date_str = cutoff.strftime('%Y/%m/%d')
                query_parts = [
                    'has:attachment',
                    f'after:{date_str}',
                ]
            else:
                # No previous sync - default to last 30 days
                query_parts = [
                    'has:attachment',
                    'newer_than:30d',
                ]
        
        # Add keyword filters (broader for internal scoring)
        # Using OR for flexibility - we'll score internally
        keyword_filter = ' OR '.join([
            f'subject:"{kw}"' for kw in ['קבלה', 'חשבונית', 'invoice', 'receipt', 'payment']
        ])
        query = f"{' '.join(query_parts)} ({keyword_filter})"
        
        logger.info(f"Gmail query: {query}")
        
        attachment_service = get_attachment_service()
        page_token = None
        total_processed = 0
        
        # Pagination loop - continue until no more pages or max_messages reached
        while True:
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
                    
                    # Get email date
                    internal_date = int(message.get('internalDate', 0)) / 1000
                    received_at = datetime.fromtimestamp(internal_date) if internal_date else None
                    
                    # Extract email body/HTML for preview generation
                    email_html_snippet = extract_email_html(message)
                    
                    # Process first PDF or image attachment
                    attachment_id = None
                    pdf_text = ''
                    
                    for att in metadata.get('attachments', []):
                        if att['mime_type'] in ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']:
                            try:
                                # Download attachment
                                att_data = gmail.get_attachment(message_id, att['id'])
                                
                                # Extract text if PDF
                                if att['mime_type'] == 'application/pdf':
                                    pdf_text = extract_pdf_text(att_data)
                                    # Calculate additional confidence from PDF content
                                    pdf_confidence = calculate_pdf_confidence(pdf_text)
                                    confidence = min(confidence + pdf_confidence, 100)
                                
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
                                    channel_compatibility={'email': True, 'whatsapp': False, 'broadcast': False}
                                )
                                db.session.add(attachment)
                                db.session.flush()  # Get attachment ID
                                
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
                                
                                break  # Only process first attachment
                                
                            except Exception as e:
                                logger.warning(f"Failed to process attachment: {e}")
                                result['errors'] += 1
                    
                    # Skip if confidence too low after full analysis
                    if confidence < MIN_CONFIDENCE:
                        result['skipped'] += 1
                        continue
                    
                    # Extract structured data
                    extracted = extract_receipt_data(pdf_text, metadata)
                    
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
                    
                    logger.info(f"Created receipt: vendor={extracted.get('vendor_name')}, confidence={confidence}, status={status}")
                    
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
                        sync_run.updated_at = datetime.utcnow()
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
            sync_run.updated_at = datetime.utcnow()
            db.session.commit()
            
            logger.info(f"Progress: pages={result['pages_scanned']}, messages={result['messages_scanned']}, receipts={result['saved_receipts']}")
        
        # Final commit
        db.session.commit()
        
        # Update connection last sync time
        if connection:
            connection.last_sync_at = datetime.utcnow()
            db.session.commit()
        
        # Mark sync run as completed
        sync_run.status = 'completed'
        sync_run.finished_at = datetime.utcnow()
        db.session.commit()
        
        logger.info(f"Gmail sync complete: {result}")
        
        return result
        
    except Exception as e:
        logger.error(f"Gmail sync failed: {e}", exc_info=True)
        
        # Mark sync run as failed
        sync_run.status = 'failed'
        sync_run.error_message = str(e)[:500]
        sync_run.finished_at = datetime.utcnow()
        sync_run.errors_count = result['errors'] + 1
        db.session.commit()
        
        raise


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
