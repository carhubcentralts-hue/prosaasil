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

# Try to import CSS sanitizer - requires tinycss2
try:
    from bleach.css_sanitizer import CSSSanitizer
    _HAS_CSS_SANITIZER = True
except ImportError:
    CSSSanitizer = None
    _HAS_CSS_SANITIZER = False

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

# CSS Sanitizer for safe inline styles
# Allow common safe CSS properties for email styling
if _HAS_CSS_SANITIZER:
    css_sanitizer = CSSSanitizer(allowed_css_properties=[
        'color', 'background-color', 'font-size', 'font-weight', 'font-family',
        'text-align', 'text-decoration', 'padding', 'margin', 'border',
        'border-radius', 'width', 'height', 'max-width', 'max-height',
        'display', 'line-height', 'letter-spacing'
    ])
else:
    css_sanitizer = None
    logger.warning("[EMAIL] CSS sanitizer not available - tinycss2 not installed. Inline styles will be stripped.")

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
    'th': ['style'],
    'h1': ['style'],
    'h2': ['style'],
    'h3': ['style'],
    'h4': ['style'],
    'h5': ['style'],
    'h6': ['style']
}

def strip_html(html: str) -> str:
    """Strip HTML tags from string for plain text version"""
    return HTML_TAG_REGEX.sub('', html)

def sanitize_html(html: str) -> str:
    """
    Sanitize HTML to prevent XSS attacks
    
    Uses CSS sanitizer to allow safe inline styles while blocking dangerous CSS.
    This prevents XSS via CSS (e.g., expression(), url() with javascript:, etc.)
    If CSS sanitizer is not available (tinycss2 not installed), strips all style attributes.
    """
    if _HAS_CSS_SANITIZER:
        return bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=ALLOWED_ATTRIBUTES,
            css_sanitizer=css_sanitizer,
            strip=True
        )
    else:
        # Fallback: strip all style attributes if CSS sanitizer not available
        allowed_attrs_no_style = {
            tag: [attr for attr in attrs if attr != 'style']
            for tag, attrs in ALLOWED_ATTRIBUTES.items()
        }
        return bleach.clean(
            html,
            tags=ALLOWED_TAGS,
            attributes=allowed_attrs_no_style,
            strip=True
        )

def render_variables(template: str, variables: Dict[str, Any]) -> str:
    """
    Safely render template variables using simple string replacement
    
    Whitelist of allowed variables:
    - {{business.name}}, {{business.phone}}
    - {{lead.first_name}}, {{lead.last_name}}, {{lead.email}}, {{lead.phone}}
    - {{agent.name}}, {{agent.email}}
    - {{cta.url}}, {{cta.text}}
    
    Args:
        template: Template string with {{variable}} placeholders
        variables: Dict of variables to substitute
        
    Returns:
        Rendered template with variables replaced
    """
    result = template
    
    # Flatten nested dicts for easy replacement
    flat_vars = {}
    for key, value in variables.items():
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                flat_vars[f"{key}.{subkey}"] = str(subvalue) if subvalue is not None else ''
        else:
            flat_vars[key] = str(value) if value is not None else ''
    
    # Replace all {{variable}} patterns
    for var_name, var_value in flat_vars.items():
        pattern = f"{{{{{var_name}}}}}"
        result = result.replace(pattern, var_value)
    
    # Remove any remaining unreplaced variables
    result = re.sub(r'\{\{[^}]+\}\}', '', result)
    
    return result

def load_base_layout() -> str:
    """Load the base email layout template"""
    template_path = os.path.join(
        os.path.dirname(__file__),
        'email_templates',
        'base_layout.html'
    )
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"[EMAIL] Failed to load base layout template: {e}")
        # Return a simple fallback template
        return """
        <html dir="rtl">
        <body>
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: white; padding: 30px;">
                    <div>{{greeting}}</div>
                    <div>{{body_content}}</div>
                </div>
                <div style="padding: 20px; color: #666; font-size: 12px;">
                    {{footer_content}}
                </div>
            </div>
        </body>
        </html>
        """

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
            from sqlalchemy import text as sa_text
            
            result = db.session.execute(
                sa_text("""
                    SELECT id, business_id, provider, from_email, from_name, 
                           reply_to, reply_to_enabled, brand_logo_url, brand_primary_color,
                           default_greeting, footer_html, footer_text, is_enabled, 
                           created_at, updated_at
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
                'reply_to_enabled': result[6],
                'brand_logo_url': result[7],
                'brand_primary_color': result[8],
                'default_greeting': result[9],
                'footer_html': result[10],
                'footer_text': result[11],
                'is_enabled': result[12],
                'created_at': result[13],
                'updated_at': result[14]
            }
        except Exception as e:
            logger.error(f"[EMAIL] Failed to get email settings for business {business_id}: {e}")
            return None
    
    def upsert_email_settings(
        self,
        business_id: int,
        from_name: str,
        reply_to: Optional[str] = None,
        reply_to_enabled: bool = True,
        brand_logo_url: Optional[str] = None,
        brand_primary_color: Optional[str] = None,
        default_greeting: Optional[str] = None,
        footer_html: Optional[str] = None,
        footer_text: Optional[str] = None,
        is_enabled: bool = True
    ) -> bool:
        """
        Create or update email settings for a business
        
        🔒 CRITICAL: from_email is ENFORCED to noreply@prosaas.pro
        Business can customize branding, greeting, footer, and reply_to
        
        Args:
            business_id: Business ID
            from_name: Display name (what customer sees)
            reply_to: Reply-to address (where replies go - can be any email)
            reply_to_enabled: Enable/disable reply-to functionality
            brand_logo_url: Logo URL for email header
            brand_primary_color: Primary brand color (hex)
            default_greeting: Default greeting template with variables
            footer_html: Footer HTML content
            footer_text: Footer plain text fallback
            is_enabled: Enable/disable email sending
            
        Returns:
            bool: True if successful
        """
        try:
            from server.db import db
            from sqlalchemy import text as sa_text
            
            # 🔒 ENFORCED: Always use verified SendGrid address
            from_email = ALLOWED_FROM_EMAILS[0]  # noreply@prosaas.pro
            
            # Check if settings exist
            existing = self.get_email_settings(business_id)
            
            now = datetime.utcnow()
            
            if existing:
                # Update existing settings
                db.session.execute(
                    sa_text("""
                        UPDATE email_settings
                        SET from_email = :from_email,
                            from_name = :from_name,
                            reply_to = :reply_to,
                            reply_to_enabled = :reply_to_enabled,
                            brand_logo_url = :brand_logo_url,
                            brand_primary_color = :brand_primary_color,
                            default_greeting = :default_greeting,
                            footer_html = :footer_html,
                            footer_text = :footer_text,
                            is_enabled = :is_enabled,
                            updated_at = :updated_at
                        WHERE business_id = :business_id
                    """),
                    {
                        "business_id": business_id,
                        "from_email": from_email,
                        "from_name": from_name,
                        "reply_to": reply_to,
                        "reply_to_enabled": reply_to_enabled,
                        "brand_logo_url": brand_logo_url,
                        "brand_primary_color": brand_primary_color or '#2563EB',
                        "default_greeting": default_greeting or 'שלום {{lead.first_name}},',
                        "footer_html": footer_html,
                        "footer_text": footer_text,
                        "is_enabled": is_enabled,
                        "updated_at": now
                    }
                )
            else:
                # Insert new settings
                db.session.execute(
                    sa_text("""
                        INSERT INTO email_settings 
                        (business_id, provider, from_email, from_name, reply_to, reply_to_enabled,
                         brand_logo_url, brand_primary_color, default_greeting, footer_html, footer_text,
                         is_enabled, created_at, updated_at)
                        VALUES (:business_id, 'sendgrid', :from_email, :from_name, :reply_to, :reply_to_enabled,
                                :brand_logo_url, :brand_primary_color, :default_greeting, :footer_html, :footer_text,
                                :is_enabled, :created_at, :updated_at)
                    """),
                    {
                        "business_id": business_id,
                        "from_email": from_email,
                        "from_name": from_name,
                        "reply_to": reply_to,
                        "reply_to_enabled": reply_to_enabled,
                        "brand_logo_url": brand_logo_url,
                        "brand_primary_color": brand_primary_color or '#2563EB',
                        "default_greeting": default_greeting or 'שלום {{lead.first_name}},',
                        "footer_html": footer_html,
                        "footer_text": footer_text,
                        "is_enabled": is_enabled,
                        "created_at": now,
                        "updated_at": now
                    }
                )
            
            db.session.commit()
            logger.info(f"[EMAIL] Email settings saved for business {business_id} with full branding")
            return True
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to upsert email settings for business {business_id}: {e}")
            from server.db import db
            db.session.rollback()
            return False
    
    # ========================================================================
    # TEMPLATE MANAGEMENT FUNCTIONS
    # ========================================================================
    
    def list_templates(self, business_id: int, active_only: bool = True) -> list:
        """
        List email templates for a business
        
        Args:
            business_id: Business ID
            active_only: Only return active templates
            
        Returns:
            list of template dicts
        """
        try:
            from server.db import db
            from sqlalchemy import text as sa_text
            
            query = """
                SELECT id, business_id, name, type, subject_template, 
                       html_template, text_template, is_active,
                       created_by_user_id, created_at, updated_at
                FROM email_templates
                WHERE business_id = :business_id
            """
            
            if active_only:
                query += " AND is_active = TRUE"
            
            query += " ORDER BY created_at DESC"
            
            result = db.session.execute(
                sa_text(query),
                {"business_id": business_id}
            ).fetchall()
            
            templates = []
            for row in result:
                templates.append({
                    'id': row[0],
                    'business_id': row[1],
                    'name': row[2],
                    'type': row[3],
                    'subject_template': row[4],
                    'html_template': row[5],
                    'text_template': row[6],
                    'is_active': row[7],
                    'created_by_user_id': row[8],
                    'created_at': row[9],
                    'updated_at': row[10]
                })
            
            return templates
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to list templates for business {business_id}: {e}")
            return []
    
    def create_template(
        self,
        business_id: int,
        name: str,
        subject_template: str,
        html_template: str,
        text_template: Optional[str] = None,
        template_type: str = 'generic',
        created_by_user_id: Optional[int] = None
    ) -> Optional[int]:
        """
        Create a new email template
        
        Args:
            business_id: Business ID
            name: Template name
            subject_template: Subject with {{variables}}
            html_template: HTML body with {{variables}}
            text_template: Plain text version (optional)
            template_type: Type (generic, lead_outreach, followup, etc.)
            created_by_user_id: User who created the template
            
        Returns:
            Template ID or None if failed
        """
        try:
            from server.db import db
            from sqlalchemy import text as sa_text
            
            result = db.session.execute(
                sa_text("""
                    INSERT INTO email_templates
                    (business_id, name, type, subject_template, html_template, 
                     text_template, created_by_user_id, is_active, created_at, updated_at)
                    VALUES (:business_id, :name, :type, :subject_template, :html_template,
                            :text_template, :created_by_user_id, TRUE, :created_at, :updated_at)
                    RETURNING id
                """),
                {
                    "business_id": business_id,
                    "name": name,
                    "type": template_type,
                    "subject_template": subject_template,
                    "html_template": html_template,
                    "text_template": text_template,
                    "created_by_user_id": created_by_user_id,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
            
            template_id = result.scalar()
            db.session.commit()
            
            logger.info(f"[EMAIL] Template created: id={template_id}, business_id={business_id}, name={name}")
            return template_id
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to create template for business {business_id}: {e}")
            from server.db import db
            db.session.rollback()
            return None
    
    def update_template(
        self,
        business_id: int,
        template_id: int,
        name: Optional[str] = None,
        subject_template: Optional[str] = None,
        html_template: Optional[str] = None,
        text_template: Optional[str] = None,
        template_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> bool:
        """
        Update an existing email template
        
        Args:
            business_id: Business ID (for security check)
            template_id: Template ID to update
            name: New name (optional)
            subject_template: New subject (optional)
            html_template: New HTML body (optional)
            text_template: New text body (optional)
            template_type: New type (optional)
            is_active: Active status (optional)
            
        Returns:
            True if successful
        """
        try:
            from server.db import db
            from sqlalchemy import text as sa_text
            
            # Build update query dynamically based on provided fields
            update_fields = []
            params = {
                "template_id": template_id,
                "business_id": business_id,
                "updated_at": datetime.utcnow()
            }
            
            if name is not None:
                update_fields.append("name = :name")
                params["name"] = name
            
            if subject_template is not None:
                update_fields.append("subject_template = :subject_template")
                params["subject_template"] = subject_template
            
            if html_template is not None:
                update_fields.append("html_template = :html_template")
                params["html_template"] = html_template
            
            if text_template is not None:
                update_fields.append("text_template = :text_template")
                params["text_template"] = text_template
            
            if template_type is not None:
                update_fields.append("type = :type")
                params["type"] = template_type
            
            if is_active is not None:
                update_fields.append("is_active = :is_active")
                params["is_active"] = is_active
            
            if not update_fields:
                return True  # Nothing to update
            
            update_fields.append("updated_at = :updated_at")
            
            query = f"""
                UPDATE email_templates
                SET {', '.join(update_fields)}
                WHERE id = :template_id AND business_id = :business_id
            """
            
            result = db.session.execute(sa_text(query), params)
            db.session.commit()
            
            if result.rowcount > 0:
                logger.info(f"[EMAIL] Template updated: id={template_id}, business_id={business_id}")
                return True
            else:
                logger.warning(f"[EMAIL] Template not found or not owned by business: id={template_id}, business_id={business_id}")
                return False
                
        except Exception as e:
            logger.error(f"[EMAIL] Failed to update template {template_id}: {e}")
            from server.db import db
            db.session.rollback()
            return False
    
    def delete_template(self, business_id: int, template_id: int) -> bool:
        """
        Soft delete a template (set is_active=False)
        
        Args:
            business_id: Business ID (for security check)
            template_id: Template ID to delete
            
        Returns:
            True if successful
        """
        return self.update_template(
            business_id=business_id,
            template_id=template_id,
            is_active=False
        )
    
    def render_template(
        self,
        template: Dict[str, Any],
        lead: Optional[Dict[str, Any]] = None,
        business: Optional[Dict[str, Any]] = None,
        agent: Optional[Dict[str, Any]] = None,
        extra_vars: Optional[Dict[str, Any]] = None
    ) -> Dict[str, str]:
        """
        Render a template with provided variables
        
        Args:
            template: Template dict with subject_template, html_template, text_template
            lead: Lead information dict
            business: Business information dict
            agent: Agent information dict
            extra_vars: Additional variables
            
        Returns:
            dict with 'subject', 'html', 'text' keys
        """
        # Build variables dict
        variables = {}
        
        if lead:
            variables['lead'] = {
                'first_name': lead.get('first_name', ''),
                'last_name': lead.get('last_name', ''),
                'email': lead.get('email', ''),
                'phone': lead.get('phone_e164', lead.get('phone', ''))
            }
        
        if business:
            variables['business'] = {
                'name': business.get('name', ''),
                'phone': business.get('phone_e164', business.get('phone', ''))
            }
        
        if agent:
            variables['agent'] = {
                'name': agent.get('name', ''),
                'email': agent.get('email', '')
            }
        
        if extra_vars:
            variables.update(extra_vars)
        
        # Render subject, html, and text
        rendered_subject = render_variables(template.get('subject_template', ''), variables)
        rendered_html = render_variables(template.get('html_template', ''), variables)
        rendered_text = render_variables(template.get('text_template', ''), variables) if template.get('text_template') else strip_html(rendered_html)
        
        return {
            'subject': rendered_subject,
            'html': rendered_html,
            'text': rendered_text
        }
    
    def send_crm_email(
        self,
        business_id: int,
        to_email: str,
        subject: Optional[str] = None,
        html: Optional[str] = None,
        plain_text: Optional[str] = None,
        lead_id: Optional[int] = None,
        template_id: Optional[int] = None,
        created_by_user_id: Optional[int] = None,
        to_name: Optional[str] = None,
        meta: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send CRM email with per-business settings, template support, and complete logging
        
        🎨 Complete email composition flow:
        1. Load business settings (branding, greeting, footer)
        2. If template_id: render template with variables
        3. Build greeting from settings.default_greeting
        4. Wrap content in beautiful base layout
        5. Add footer from settings.footer_html
        6. Sanitize HTML
        7. Send via SendGrid with proper from_name and reply_to
        
        Args:
            business_id: Business ID
            to_email: Recipient email
            subject: Email subject (required if no template)
            html: HTML body (required if no template)
            plain_text: Plain text body (optional)
            lead_id: Lead ID if sending to a lead
            template_id: Template ID to use instead of custom content
            created_by_user_id: User who initiated the send
            to_name: Recipient name (optional)
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
        from sqlalchemy import text as sa_text
        import json
        
        logger.info(f"[EMAIL] send requested business_id={business_id} lead_id={lead_id} template_id={template_id} to={to_email}")
        
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
        
        # 2. Prepare content (from template or direct)
        rendered_subject = subject
        rendered_body_html = html
        rendered_body_text = plain_text
        
        # Get lead and business info for variable rendering
        lead_info = None
        business_info = None
        agent_info = None
        
        try:
            # Get lead info if lead_id provided
            if lead_id:
                lead_result = db.session.execute(
                    sa_text("SELECT first_name, last_name, email, phone_e164 FROM leads WHERE id = :lead_id"),
                    {"lead_id": lead_id}
                ).fetchone()
                if lead_result:
                    lead_info = {
                        'first_name': lead_result[0] or '',
                        'last_name': lead_result[1] or '',
                        'email': lead_result[2] or '',
                        'phone': lead_result[3] or ''
                    }
            
            # Get business info
            biz_result = db.session.execute(
                sa_text("SELECT name, phone_number FROM business WHERE id = :business_id"),
                {"business_id": business_id}
            ).fetchone()
            if biz_result:
                business_info = {
                    'name': biz_result[0] or '',
                    'phone': biz_result[1] or ''
                }
            
            # Get agent info if created_by_user_id provided
            if created_by_user_id:
                agent_result = db.session.execute(
                    sa_text("SELECT name, email FROM users WHERE id = :user_id"),
                    {"user_id": created_by_user_id}
                ).fetchone()
                if agent_result:
                    agent_info = {
                        'name': agent_result[0] or '',
                        'email': agent_result[1] or ''
                    }
        except Exception as e:
            logger.warning(f"[EMAIL] Failed to fetch context info: {e}")
        
        # If template_id provided, render template
        if template_id:
            try:
                # Get template
                template_result = db.session.execute(
                    sa_text("""
                        SELECT subject_template, html_template, text_template
                        FROM email_templates
                        WHERE id = :template_id AND business_id = :business_id AND is_active = TRUE
                    """),
                    {"template_id": template_id, "business_id": business_id}
                ).fetchone()
                
                if not template_result:
                    error_msg = f"Template {template_id} not found or inactive"
                    logger.error(f"[EMAIL] {error_msg}")
                    return {
                        'success': False,
                        'email_id': None,
                        'error': 'template_not_found',
                        'message': error_msg
                    }
                
                # Render template
                rendered = self.render_template(
                    {
                        'subject_template': template_result[0],
                        'html_template': template_result[1],
                        'text_template': template_result[2]
                    },
                    lead=lead_info,
                    business=business_info,
                    agent=agent_info,
                    extra_vars=meta or {}
                )
                
                rendered_subject = rendered['subject']
                rendered_body_html = rendered['html']
                rendered_body_text = rendered['text']
                
            except Exception as e:
                error_msg = f"Failed to render template: {str(e)}"
                logger.error(f"[EMAIL] {error_msg}")
                return {
                    'success': False,
                    'email_id': None,
                    'error': 'template_render_error',
                    'message': error_msg
                }
        
        # Validate we have content
        if not rendered_subject or not rendered_body_html:
            error_msg = "Subject and HTML body are required"
            return {
                'success': False,
                'email_id': None,
                'error': 'missing_content',
                'message': error_msg
            }
        
        # 3. Build greeting with variables
        greeting_template = settings.get('default_greeting') or 'שלום {{lead.first_name}},'
        variables = {}
        if lead_info:
            variables['lead'] = lead_info
        if business_info:
            variables['business'] = business_info
        greeting_html = render_variables(greeting_template, variables)
        
        # 4. Sanitize body content (user input only - not the base layout!)
        body_html_sanitized = sanitize_html(rendered_body_html)
        
        # 5. Wrap in base layout (trusted - no sanitization)
        try:
            base_layout = load_base_layout()
            
            # Prepare layout variables
            brand_color = settings.get('brand_primary_color') or '#2563EB'
            logo_url = settings.get('brand_logo_url') or ''
            business_name = business_info['name'] if business_info else ''
            footer_html = settings.get('footer_html') or ''
            
            # Simple template replacement (using Python's format-style)
            final_html = base_layout
            final_html = final_html.replace('{{brand_primary_color}}', brand_color)
            final_html = final_html.replace('{{business_name}}', business_name)
            final_html = final_html.replace('{{greeting}}', greeting_html)
            final_html = final_html.replace('{{body_content}}', body_html_sanitized)
            # Footer content is business-configured, sanitize it to prevent XSS
            final_html = final_html.replace('{{footer_content}}', sanitize_html(footer_html) if footer_html else '')
            
            # Handle conditional logo
            if logo_url:
                final_html = final_html.replace('{{#if brand_logo_url}}', '')
                final_html = final_html.replace('{{brand_logo_url}}', logo_url)
                final_html = final_html.replace('{{else}}', '<!--')
                final_html = final_html.replace('{{/if}}', '-->')
            else:
                final_html = final_html.replace('{{#if brand_logo_url}}', '<!--')
                final_html = final_html.replace('{{brand_logo_url}}', '')
                final_html = final_html.replace('{{else}}', '-->')
                final_html = final_html.replace('{{/if}}', '')
            
            # Remove any {{#if signature}} blocks (not used yet)
            final_html = re.sub(r'\{\{#if signature\}\}.*?\{\{/if\}\}', '', final_html, flags=re.DOTALL)
            
            # Final HTML is NOT sanitized again - base layout is trusted
            # Only user content (body_html_sanitized and footer_html) was sanitized above
            final_html_sanitized = final_html
            
        except Exception as e:
            logger.error(f"[EMAIL] Failed to wrap in base layout: {e}. Using simple HTML.")
            final_html_sanitized = body_html_sanitized
        
        # Plain text version
        final_text = rendered_body_text or strip_html(body_html_sanitized)
        
        # 6. Create email_messages record in 'queued' status
        try:
            result = db.session.execute(
                sa_text("""
                    INSERT INTO email_messages
                    (business_id, lead_id, created_by_user_id, template_id, to_email, to_name,
                     subject, body_html, body_text, 
                     rendered_subject, rendered_body_html, rendered_body_text,
                     provider, from_email, from_name, reply_to,
                     status, meta, created_at)
                    VALUES (:business_id, :lead_id, :created_by_user_id, :template_id, :to_email, :to_name,
                            :subject, :body_html, :body_text,
                            :rendered_subject, :rendered_body_html, :rendered_body_text,
                            :provider, :from_email, :from_name, :reply_to,
                            'queued', :meta, :created_at)
                    RETURNING id
                """),
                {
                    "business_id": business_id,
                    "lead_id": lead_id,
                    "created_by_user_id": created_by_user_id,
                    "template_id": template_id,
                    "to_email": to_email,
                    "to_name": to_name,
                    "subject": subject or rendered_subject,
                    "body_html": html or rendered_body_html,
                    "body_text": plain_text or rendered_body_text,
                    "rendered_subject": rendered_subject,
                    "rendered_body_html": final_html_sanitized,
                    "rendered_body_text": final_text,
                    "provider": "sendgrid",
                    "from_email": settings['from_email'],
                    "from_name": settings['from_name'],
                    "reply_to": settings.get('reply_to') if settings.get('reply_to_enabled') else None,
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
        
        # 7. Check if SendGrid is configured
        if not self.client:
            error_msg = "SendGrid API key not configured"
            logger.error(f"[EMAIL] {error_msg}")
            
            # Update status to failed
            try:
                db.session.execute(
                    sa_text("""
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
        
        # 8. Send via SendGrid with branding
        try:
            from_email_obj = Email(settings['from_email'], settings['from_name'])
            to_email_obj = To(to_email)
            
            message = Mail(
                from_email=from_email_obj,
                to_emails=to_email_obj,
                subject=rendered_subject,
                html_content=final_html_sanitized,
                plain_text_content=final_text
            )
            
            # Set reply-to if enabled and configured
            if settings.get('reply_to_enabled') and settings.get('reply_to'):
                message.reply_to = Email(settings['reply_to'])
            
            # Send email
            response = self.client.send(message)
            
            if response.status_code >= 200 and response.status_code < 300:
                # Success - update status
                provider_message_id = response.headers.get('X-Message-Id', None)
                
                db.session.execute(
                    sa_text("""
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
                
                logger.info(f"[EMAIL] sent business_id={business_id} email_id={email_id} template_id={template_id} provider_id={provider_message_id}")
                
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
                    sa_text("""
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
                    sa_text("""
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
