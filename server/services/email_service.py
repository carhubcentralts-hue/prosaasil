"""
Email service using SendGrid for sending transactional emails
Production-grade implementation with proper error handling and logging
"""
import os
import logging
from typing import Optional
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

logger = logging.getLogger(__name__)

# SendGrid configuration from environment
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
MAIL_FROM_EMAIL = os.getenv('MAIL_FROM_EMAIL', 'noreply@prosaas.pro')
MAIL_FROM_NAME = os.getenv('MAIL_FROM_NAME', 'PROSAAS')
MAIL_REPLY_TO = os.getenv('MAIL_REPLY_TO', 'support@prosaas.pro')

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
                import re
                plain_content = re.sub('<[^<]+?>', '', html_content)
            
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
            bool: True if email was sent successfully
        """
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
            <p style="word-break: break-all; color: #007bff;">{reset_url}</p>
            
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

# Singleton instance
_email_service = None

def get_email_service() -> EmailService:
    """Get singleton instance of EmailService"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
