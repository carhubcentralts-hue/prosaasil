"""
Email service using SendGrid for sending transactional emails
Production-grade implementation with proper error handling and logging

✅ SINGLE SOURCE OF TRUTH: One EmailService for ALL email needs
   - Password reset emails (global config)
   - CRM emails (per-business config from email_settings table)
   - Complete logging to email_messages table
"""
import os
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
import bleach

logger = logging.getLogger(__name__)

# SendGrid configuration from environment
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
MAIL_FROM_EMAIL = os.getenv('MAIL_FROM_EMAIL', 'noreply@prosaas.pro')
MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'PROSAAS')
MAIL_REPLY_TO = os.getenv('MAIL_REPLY_TO', 'support@prosaas.pro')

# 🔒 ENFORCED FROM EMAIL - Only SendGrid-verified addresses allowed
# Business can customize from_name and reply_to ONLY
ALLOWED_FROM_EMAILS = ['noreply@prosaas.pro', 'info@prosaas.pro']

# Regex for stripping HTML tags (simple but effective for our use case)
HTML_TAG_REGEX = re.compile('<[^<]+?>')

# Allowed HTML tags and attributes for sanitization
ALLOWED_TAGS = [
    'a', 'b', 'blockquote', 'br', 'div', 'em', 'i', 'li', 'ol', 'p', 
    'strong', 'ul', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'table',
    'tbody', 'td', 'th', 'thead', 'tr'
]
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'div': ['style'],
    'span': ['style'],
    'p': ['style'],
    'td': ['style'],
    'th': ['style']
}

def strip_html(html: str) -> str:
    """Strip HTML tags from string for plain text version"""
    return HTML_TAG_REGEX.sub('', html)

def sanitize_html(html: str) -> str:
    """Sanitize HTML to prevent XSS attacks"""
    return bleach.clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        strip=True
    )

class EmailService:
    """SendGrid email service for transactional emails"""
    
    def __init__(self):
        """Initialize SendGrid client"""
        if not SENDGRID_API_KEY:
            logger.warning("[EMAIL] SENDGRID_API_KEY not configured - emails will not be sent")
            self.client = None
        else:
            self.client = SendGridAPIClient(SENDGRID_API_KEY)
            logger.info(f"[EMAIL] SendGrid client initialized with from_email={MAIL_FROM_EMAIL}")
    
    def send_email(
        self, 
        to_email: str, 
        subject: str, 
        html_content: str,
        plain_content: Optional[str] = None
    ) -> bool:
        """
        Send an email via SendGrid
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            html_content: HTML email body
            plain_content: Plain text email body (optional, defaults to stripped HTML)
            
        Returns:
            bool: True if email was sent successfully, False otherwise
        """
        if not self.client:
            logger.error(f"[EMAIL] Cannot send email - SendGrid not configured")
            return False
        
        try:
            # Create email message
            from_email = Email(MAIL_FROM_EMAIL, MAIL_FROM_NAME)
            to_email_obj = To(to_email)
            
            # Use plain content if provided, otherwise strip HTML
            if not plain_content:
                plain_content = strip_html(html_content)
            
            message = Mail(
                from_email=from_email,
                to_emails=to_email_obj,
                subject=subject,
                html_content=html_content,
                plain_text_content=plain_content
            )
            
            # Set reply-to
            message.reply_to = Email(MAIL_REPLY_TO)
            
            # Send email
            response = self.client.send(message)
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"[EMAIL] Email sent successfully to {to_email} - subject: {subject}")
                return True
            else:
                logger.error(f"[EMAIL] Failed to send email to {to_email} - status: {response.status_code}, body: {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"[EMAIL] Exception sending email to {to_email}: {e}")
            return False
    
    def send_password_reset_email(self, to_email: str, reset_url: str, user_name: Optional[str] = None) -> bool:
        """
        Send password reset email
        
        Args:
            to_email: User's email address
            reset_url: Password reset URL with token
            user_name: User's name (optional)
            
        Returns:
            bool: True if email was sent successfully (or if SendGrid not configured)
        """
        if not self.client:
            # No SendGrid configured - log but return True for anti-enumeration
            logger.warning(f"[AUTH] password_reset_email_failed reason=missing_api_key email={to_email}")
            return True  # Return success to maintain anti-enumeration protection
        
        subject = "איפוס סיסמה - PROSAAS"
        
        # HTML content with proper Hebrew support
        html_content = f"""
<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            direction: rtl;
            text-align: right;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .button {{
            display: inline-block;
            padding: 12px 24px;
            background-color: #007bff;
            color: white !important;
            text-decoration: none;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="content">
            <h2>שלום{' ' + user_name if user_name else ''},</h2>
            
            <p>קיבלנו בקשה לאיפוס הסיסמה שלך במערכת PROSAAS.</p>
            
            <p>כדי לאפס את הסיסמה, לחץ על הכפתור למטה:</p>
            
            <a href="{reset_url}" class="button">איפוס סיסמה</a>
            
            <p>או העתק את הקישור הבא לדפדפן:</p>
            <p style="word-break: break-all; color: #007bff; text-decoration: underline;">{reset_url}</p>
            
            <p><strong>חשוב:</strong> הקישור תקף ל-60 דקות בלבד ומיועד לשימוש חד-פעמי.</p>
            
            <p>אם לא ביקשת לאפס את הסיסמה, אנא התעלם ממייל זה. הסיסמה שלך תישאר ללא שינוי.</p>
            
            <div class="footer">
                <p>בברכה,<br>צוות PROSAAS</p>
                <p>מייל זה נשלח אוטומטית, אנא אל תשיב אליו.<br>
                לתמיכה, פנה אל: {MAIL_REPLY_TO}</p>
            </div>
        </div>
    </div>
</body>
</html>
"""
        
        # Plain text version
        plain_content = f"""
שלום{' ' + user_name if user_name else ''},

קיבלנו בקשה לאיפוס הסיסמה שלך במערכת PROSAAS.

כדי לאפס את הסיסמה, לחץ על הקישור הבא:
{reset_url}

חשוב: הקישור תקף ל-60 דקות בלבד ומיועד לשימוש חד-פעמי.

אם לא ביקשת לאפס את הסיסמה, אנא התעלם ממייל זה.

בברכה,
צוות PROSAAS

לתמיכה: {MAIL_REPLY_TO}
"""
        
        return self.send_email(to_email, subject, html_content, plain_content)
    
    # ========================================================================
    # CRM EMAIL FUNCTIONS - Per-business email system with DB logging
    # ========================================================================
    
    def get_email_settings(self, business_id: int) -> Optional[Dict[str, Any]]:
        """
        Get email settings for a business
        
        Args:
            business_id: Business ID
            
        Returns:
            dict with settings or None if not configured
        """
        try:
            from server.db import db
            from sqlalchemy import text
            
            result = db.session.execute(
                text("""
                    SELECT id, business_id, provider, from_email, from_name, 
                           reply_to, is_enabled, created_at, updated_at
                    FROM email_settings
                    WHERE business_id = :business_id
                """),
                {"business_id": business_id}
            ).fetchone()
            
            if not result:
                return None
            
            return {
                'id': result[0],
                'business_id': result[1],
                'provider': result[2],
                'from_email': result[3],
                'from_name': result[4],
                'reply_to': result[5],
                'is_enabled': result[6],
                'created_at': result[7],
                'updated_at': result[8]
            }
        except Exception as e:
            logger.error(f"[EMAIL] Failed to get email settings for business {business_id}: {e}")
            return None
    
    def upsert_email_settings(
        self,
        business_id: int,
        from_name: str,
        reply_to: Optional[str] = None,
        is_enabled: bool = True
    ) -> bool:
        """
        Create or update email settings for a business
        
        🔒 CRITICAL: from_email is ENFORCED to noreply@prosaas.pro
        Business can only customize from_name and reply_to
        
        Args:
            business_id: Business ID
            from_name: Display name (what customer sees)
            reply_to: Reply-to address (where replies go - can be any email)
            is_enabled: Enable/disable email sending
            
        Returns:
            bool: True if successful
        """
        try:
            from server.db import db
            from sqlalchemy import text
            
            # 🔒 ENFORCED: Always use verified SendGrid address
            from_email = ALLOWED_FROM_EMAILS[0]  # noreply@prosaas.pro
            
            # Check if settings exist
            existing = self.get_email_settings(business_id)
            
            now = datetime.utcnow()
            
            if existing:
                # Update existing settings
                db.session.execute(
                    text("""
                        UPDATE email_settings
                        SET from_email = :from_email,
                            from_name = :from_name,
                            reply_to = :reply_to,
                            is_enabled = :is_enabled,
                            updated_at = :updated_at
                        WHERE business_id = :business_id
                    """),
                    {
                        "business_id": business_id,
                        "from_email": from_email,
                        "from_name": from_name,
                        "reply_to": reply_to,
                        "is_enabled": is_enabled,
                        "updated_at": now
                    }
                )
            else:
                # Insert new settings
                db.session.execute(
                    text("""
                        INSERT INTO email_settings 
                        (business_id, provider, from_email, from_name, reply_to, is_enabled, created_at, updated_at)
                        VALUES (:business_id, 'sendgrid', :from_email, :from_name, :reply_to, :is_enabled, :created_at, :updated_at)
                    """),
                    {
                        "business_id": business_id,
                        "from_email": from_email,
                        "from_name": from_name,
                        "reply_to": reply_to,
                        "is_enabled": is_enabled,
                        "created_at": now,
                        "updated_at": now
                    }
                )
            
            db.session.commit()
            logger.info(f"[EMAIL] Email settings saved for business {business_id} (from_email={from_email}, from_name={from_name})")
            return True
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to upsert email settings for business {business_id}: {e}")
            from server.db import db
            db.session.rollback()
            return False
    
    def send_crm_email(
        self,
        business_id: int,
        to_email: str,
        subject: str,
        html: str,
        text: Optional[str] = None,
        lead_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send CRM email with per-business settings and complete logging
        
        Args:
            business_id: Business ID
            to_email: Recipient email
            subject: Email subject
            html: HTML body (will be sanitized)
            text: Plain text body (optional)
            lead_id: Lead ID if sending to a lead
            created_by_user_id: User who initiated the send
            meta: Additional metadata (JSON)
            
        Returns:
            dict: {
                'success': bool,
                'email_id': int or None,
                'error': str or None,
                'message': str
            }
        """
        from server.db import db
        from sqlalchemy import text
        import json
        
        logger.info(f"[EMAIL] send requested business_id={business_id} lead_id={lead_id} to={to_email}")
        
        # 1. Load email settings
        settings = self.get_email_settings(business_id)
        
        if not settings:
            error_msg = "Email settings not configured for this business"
            logger.warning(f"[EMAIL] {error_msg} business_id={business_id}")
            return {
                'success': False,
                'email_id': None,
                'error': 'not_configured',
                'message': error_msg
            }
        
        if not settings['is_enabled']:
            error_msg = "Email sending is disabled for this business"
            logger.warning(f"[EMAIL] {error_msg} business_id={business_id}")
            return {
                'success': False,
                'email_id': None,
                'error': 'disabled',
                'message': error_msg
            }
        
        # 2. Sanitize HTML
        html_sanitized = sanitize_html(html)
        
        # 3. Create email_messages record in 'queued' status
        try:
            result = db.session.execute(
                text("""
                    INSERT INTO email_messages
                    (business_id, lead_id, created_by_user_id, to_email, subject, 
                     body_html, body_text, provider, from_email, from_name, reply_to,
                     status, meta, created_at)
                    VALUES (:business_id, :lead_id, :created_by_user_id, :to_email, :subject,
                            :body_html, :body_text, :provider, :from_email, :from_name, :reply_to,
                            'queued', :meta, :created_at)
                    RETURNING id
                """),
                {
                    "business_id": business_id,
                    "lead_id": lead_id,
                    "created_by_user_id": created_by_user_id,
                    "to_email": to_email,
                    "subject": subject,
                    "body_html": html_sanitized,
                    "body_text": text or strip_html(html_sanitized),
                    "provider": "sendgrid",
                    "from_email": settings['from_email'],
                    "from_name": settings['from_name'],
                    "reply_to": settings['reply_to'],
                    "meta": json.dumps(meta) if meta else None,
                    "created_at": datetime.utcnow()
                }
            )
            email_id = result.scalar()
            db.session.commit()
        except Exception as e:
            logger.error(f"[EMAIL] Failed to create email_messages record: {e}")
            db.session.rollback()
            return {
                'success': False,
                'email_id': None,
                'error': 'database_error',
                'message': str(e)
            }
        
        # 4. Check if SendGrid is configured
        if not self.client:
            error_msg = "SendGrid API key not configured"
            logger.error(f"[EMAIL] {error_msg}")
            
            # Update status to failed
            try:
                db.session.execute(
                    text("""
                        UPDATE email_messages
                        SET status = 'failed', error = :error
                        WHERE id = :email_id
                    """),
                    {"email_id": email_id, "error": "missing_sendgrid_api_key"}
                )
                db.session.commit()
            except Exception as e:
                logger.error(f"[EMAIL] Failed to update email status: {e}")
                db.session.rollback()
            
            return {
                'success': False,
                'email_id': email_id,
                'error': 'missing_api_key',
                'message': error_msg
            }
        
        # 5. Send via SendGrid
        try:
            from_email_obj = Email(settings['from_email'], settings['from_name'])
            to_email_obj = To(to_email)
            
            message = Mail(
                from_email=from_email_obj,
                to_emails=to_email_obj,
                subject=subject,
                html_content=html_sanitized,
                plain_text_content=text or strip_html(html_sanitized)
            )
            
            # Set reply-to if configured
            if settings['reply_to']:
                message.reply_to = Email(settings['reply_to'])
            
            # Send email
            response = self.client.send(message)
            
            if response.status_code >= 200 and response.status_code < 300:
                # Success - update status
                provider_message_id = response.headers.get('X-Message-Id', None)
                
                db.session.execute(
                    text("""
                        UPDATE email_messages
                        SET status = 'sent',
                            provider_message_id = :provider_message_id,
                            sent_at = :sent_at
                        WHERE id = :email_id
                    """),
                    {
                        "email_id": email_id,
                        "provider_message_id": provider_message_id,
                        "sent_at": datetime.utcnow()
                    }
                )
                db.session.commit()
                
                logger.info(f"[EMAIL] sent business_id={business_id} email_id={email_id} provider_id={provider_message_id}")
                
                return {
                    'success': True,
                    'email_id': email_id,
                    'error': None,
                    'message': 'Email sent successfully'
                }
            else:
                # SendGrid returned error status
                error_msg = f"SendGrid error: {response.status_code}"
                logger.error(f"[EMAIL] failed business_id={business_id} email_id={email_id} error={error_msg}")
                
                db.session.execute(
                    text("""
                        UPDATE email_messages
                        SET status = 'failed', error = :error
                        WHERE id = :email_id
                    """),
                    {"email_id": email_id, "error": error_msg}
                )
                db.session.commit()
                
                return {
                    'success': False,
                    'email_id': email_id,
                    'error': 'sendgrid_error',
                    'message': error_msg
                }
                
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[EMAIL] failed business_id={business_id} email_id={email_id} error={error_msg}")
            
            # Update status to failed
            try:
                db.session.execute(
                    text("""
                        UPDATE email_messages
                        SET status = 'failed', error = :error
                        WHERE id = :email_id
                    """),
                    {"email_id": email_id, "error": error_msg}
                )
                db.session.commit()
            except Exception as update_error:
                logger.error(f"[EMAIL] Failed to update email status: {update_error}")
                db.session.rollback()
            
            return {
                'success': False,
                'email_id': email_id,
                'error': 'exception',
                'message': error_msg
            }
    
    def send_test_email(self, business_id: int, to_email: str) -> Dict[str, Any]:
        """
        Send a test email using business settings
        
        Args:
            business_id: Business ID
            to_email: Test recipient email
            
        Returns:
            dict with success status and message
        """
        subject = "בדיקת הגדרות מייל - PROSAAS"
        html = """
        <!DOCTYPE html>
        <html dir="rtl" lang="he">
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; direction: rtl; text-align: right; }
                .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                .success { color: #22c55e; font-size: 24px; font-weight: bold; }
            </style>
        </head>
        <body>
            <div class="container">
                <p class="success">✅ הגדרות המייל פועלות כראוי!</p>
                <p>זהו מייל בדיקה ממערכת PROSAAS.</p>
                <p>אם קיבלת מייל זה, הגדרות המייל שלך מוגדרות נכון.</p>
            </div>
        </body>
        </html>
        """
        
        return self.send_crm_email(
            business_id=business_id,
            to_email=to_email,
            subject=subject,
            html=html,
            meta={'type': 'test_email'}
        )

# Singleton instance
_email_service = None

def get_email_service() -> EmailService:
    """Get singleton instance of EmailService"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
