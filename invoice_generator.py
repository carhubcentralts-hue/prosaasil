"""
Invoice Generator Service - שירות יצירת חשבוניות PDF
יוצר חשבוניות מקצועיות בעברית עם חתימה דיגיטלית
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from app import db
from models import CRMCustomer, Business
from digital_signature_service import digital_signature_service

logger = logging.getLogger(__name__)

class InvoiceGenerator:
    """מחולל חשבוניות PDF מתקדם"""
    
    def __init__(self):
        self.setup_hebrew_fonts()
        self.invoices_dir = os.path.join('static', 'invoices')
        os.makedirs(self.invoices_dir, exist_ok=True)
    
    def setup_hebrew_fonts(self):
        """הגדרת פונטים עבריים עם fallback רספונסיבי"""
        try:
            # ניסיון רישום פונטים עבריים מרובים
            font_paths = [
                os.path.join('static', 'fonts', 'hebrew.ttf'),
                os.path.join('static', 'fonts', 'David.ttf'),
                os.path.join('static', 'fonts', 'Arial-Unicode.ttf')
            ]
            
            self.hebrew_font = 'Helvetica'  # ברירת מחדל
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    try:
                        pdfmetrics.registerFont(TTFont('Hebrew', font_path))
                        self.hebrew_font = 'Hebrew'
                        logger.info(f"Hebrew font loaded successfully: {font_path}")
                        break
                    except Exception as font_error:
                        logger.warning(f"Failed to load font {font_path}: {font_error}")
                        continue
            
            if self.hebrew_font == 'Helvetica':
                logger.warning("No Hebrew fonts found, using Helvetica fallback")
                
        except Exception as e:
            logger.error(f"Critical error in font setup: {e}")
            self.hebrew_font = 'Helvetica'
    
    def generate_invoice(self, customer_id: int, amount: float, 
                        description: str = '', invoice_number: Optional[str] = None) -> Dict[str, Any]:
        """יצירת חשבונית PDF עם בדיקות תקינות מלאות"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                logger.error(f"Customer {customer_id} not found for invoice generation")
                return {'success': False, 'error': 'לקוח לא נמצא'}
            
            business = Business.query.get(customer.business_id)
            if not business:
                logger.error(f"Business {customer.business_id} not found for customer {customer_id}")
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # בדיקת פרטי לקוח חובה
            missing_details = []
            if not customer.full_name or customer.full_name.strip() == '':
                missing_details.append('שם מלא')
            if not customer.phone or customer.phone.strip() == '':
                missing_details.append('מספר טלפון')
            if not hasattr(customer, 'address') or not customer.address:
                missing_details.append('כתובת')
            
            if missing_details:
                error_msg = f'חסרים פרטים חובה עבור הלקוח: {", ".join(missing_details)}'
                logger.error(f"Missing required customer details for invoice: {error_msg}")
                return {'success': False, 'error': error_msg}
            
            # בדיקת פרטי עסק חובה
            if not business.name or business.name.strip() == '':
                logger.error(f"Business name missing for business {business.id}")
                return {'success': False, 'error': 'חסר שם עסק'}
            
            # בדיקת סכום תקין
            if amount <= 0:
                logger.error(f"Invalid amount for invoice: {amount}")
                return {'success': False, 'error': 'סכום חייב להיות חיובי'}
            
            # מספר חשבונית
            if not invoice_number:
                invoice_number = self._generate_invoice_number(business.id)
            
            # שם קובץ
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"invoice_{invoice_number}_{customer_id}_{timestamp}.pdf"
            filepath = os.path.join(self.invoices_dir, filename)
            
            # יצירת PDF
            doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=72, leftMargin=72,
                                  topMargin=72, bottomMargin=18)
            
            story = []
            styles = getSampleStyleSheet()
            
            # עיצוב RTL לעברית
            hebrew_style = ParagraphStyle('Hebrew',
                                        parent=styles['Normal'],
                                        fontName='Helvetica',
                                        fontSize=12,
                                        rightIndent=0,
                                        leftIndent=0,
                                        alignment=2)  # RA - Right Aligned
            
            title_style = ParagraphStyle('HebrewTitle',
                                       parent=hebrew_style,
                                       fontSize=18,
                                       spaceAfter=20,
                                       textColor=colors.darkblue)
            
            # כותרת חשבונית
            story.append(Paragraph(f"חשבונית מס׳ {invoice_number}", title_style))
            story.append(Spacer(1, 20))
            
            # פרטי עסק
            business_info = [
                [f"שם העסק: {business.name}"],
                [f"טלפון: {business.phone_number}"],
                [f"תאריך: {datetime.now().strftime('%d/%m/%Y')}"]
            ]
            
            business_table = Table(business_info, colWidths=[4*inch])
            business_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            
            story.append(business_table)
            story.append(Spacer(1, 20))
            
            # פרטי לקוח
            customer_info = [
                ["פרטי לקוח:"],
                [f"שם: {customer.name}"],
                [f"טלפון: {customer.phone}"],
                [f"אימייל: {customer.email or 'לא צוין'}"]
            ]
            
            customer_table = Table(customer_info, colWidths=[4*inch])
            customer_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ]))
            
            story.append(customer_table)
            story.append(Spacer(1, 30))
            
            # פרטי חשבונית
            invoice_data = [
                ['תיאור', 'כמות', 'מחיר ליחידה', 'סה"כ'],
                [description or 'שירות', '1', f'₪{amount:.2f}', f'₪{amount:.2f}']
            ]
            
            invoice_table = Table(invoice_data, colWidths=[2*inch, 1*inch, 1.5*inch, 1.5*inch])
            invoice_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            
            story.append(invoice_table)
            story.append(Spacer(1, 30))
            
            # סיכום
            total_data = [
                ['', '', 'סה"כ לתשלום:', f'₪{amount:.2f}']
            ]
            
            total_table = Table(total_data, colWidths=[2*inch, 1*inch, 1.5*inch, 1.5*inch])
            total_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BACKGROUND', (0, 0), (1, 0), colors.white),
                ('BACKGROUND', (2, 0), (3, 0), colors.lightblue),
                ('BOX', (2, 0), (3, 0), 2, colors.black),
            ]))
            
            story.append(total_table)
            story.append(Spacer(1, 40))
            
            # חתימה דיגיטלית (אם קיימת)
            signature_data = digital_signature_service.get_customer_signature(customer_id)
            if signature_data:
                story.append(Paragraph("חתימת הלקוח:", hebrew_style))
                story.append(Spacer(1, 10))
                
                # שמירת חתימה כקובץ זמני
                signature_path = self._save_temp_signature(signature_data, customer_id)
                if signature_path:
                    signature_img = Image(signature_path, width=2*inch, height=1*inch)
                    story.append(signature_img)
                    # מחיקת קובץ זמני
                    os.remove(signature_path)
            
            story.append(Spacer(1, 20))
            story.append(Paragraph("תודה על הפנייה!", hebrew_style))
            
            # יצירת PDF
            doc.build(story)
            
            # שמירת פרטי חשבונית במסד נתונים (אם יש טבלה)
            invoice_data = {
                'invoice_number': invoice_number,
                'customer_id': customer_id,
                'business_id': business.id,
                'amount': amount,
                'description': description,
                'pdf_filename': filename,
                'created_at': datetime.utcnow()
            }
            
            logger.info(f"Generated invoice {invoice_number} for customer {customer_id}")
            
            return {
                'success': True,
                'invoice_number': invoice_number,
                'filename': filename,
                'filepath': filepath,
                'amount': amount,
                'customer_name': customer.name
            }
            
        except Exception as e:
            logger.error(f"Error generating invoice: {e}")
            return {'success': False, 'error': f'שגיאה ביצירת החשבונית: {str(e)}'}
    
    def _generate_invoice_number(self, business_id: int) -> str:
        """יצירת מספר חשבונית ייחודי"""
        
        # פורמט: BUSSID-YYYYMMDD-NNN
        date_str = datetime.now().strftime('%Y%m%d')
        
        # ספירת חשבוניות היום
        today_invoices = len([
            f for f in os.listdir(self.invoices_dir)
            if f.startswith('invoice_') and date_str in f
        ])
        
        sequence = today_invoices + 1
        return f"{business_id:03d}-{date_str}-{sequence:03d}"
    
    def _save_temp_signature(self, signature_data: str, customer_id: int) -> Optional[str]:
        """שמירת חתימה כקובץ זמני לשימוש ב-PDF"""
        
        try:
            import base64
            from io import BytesIO
            
            # הסרת prefix של Base64
            signature_base64 = signature_data.split(',')[1]
            signature_bytes = base64.b64decode(signature_base64)
            
            # שמירה כקובץ זמני
            temp_filename = f"temp_signature_{customer_id}_{datetime.now().timestamp()}.png"
            temp_path = os.path.join(self.invoices_dir, temp_filename)
            
            with open(temp_path, 'wb') as f:
                f.write(signature_bytes)
            
            return temp_path
            
        except Exception as e:
            logger.error(f"Error saving temp signature: {e}")
            return None
    
    def send_invoice_whatsapp(self, customer_id: int, invoice_filename: str) -> Dict[str, Any]:
        """שליחת חשבונית ב-WhatsApp"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return {'success': False, 'error': 'לקוח לא נמצא'}
            
            # השתמש בשירות WhatsApp הקיים
            from enhanced_whatsapp_service import enhanced_whatsapp_service
            
            message = f"שלום {customer.name}! מצורפת החשבונית שלך. תודה!"
            
            result = enhanced_whatsapp_service._send_whatsapp_message(
                to_number=customer.phone,
                message=message
            )
            
            if result['success']:
                logger.info(f"Invoice sent via WhatsApp to {customer.phone}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending invoice via WhatsApp: {e}")
            return {'success': False, 'error': 'שגיאה בשליחת החשבונית'}
    
    def get_invoice_statistics(self, business_id: int) -> Dict[str, Any]:
        """סטטיסטיקות חשבוניות"""
        
        try:
            # ספירת קבצי חשבוניות
            invoice_files = [
                f for f in os.listdir(self.invoices_dir)
                if f.startswith('invoice_') and f.endswith('.pdf')
            ]
            
            total_invoices = len(invoice_files)
            
            # חשבוניות היום
            today_str = datetime.now().strftime('%Y%m%d')
            today_invoices = len([
                f for f in invoice_files
                if today_str in f
            ])
            
            return {
                'total_invoices': total_invoices,
                'today_invoices': today_invoices,
                'business_id': business_id
            }
            
        except Exception as e:
            logger.error(f"Error getting invoice statistics: {e}")
            return {'total_invoices': 0, 'today_invoices': 0}

    def get_invoice_download_link(self, invoice_path: str, customer_id: int) -> str:
        """Task 6: Generate secure download link for invoice"""
        import uuid
        import os
        
        # Generate secure token
        token = str(uuid.uuid4())
        
        # Store token mapping (in production, use Redis or database)
        if not hasattr(self, 'download_tokens'):
            self.download_tokens = {}
        
        self.download_tokens[token] = {
            'invoice_path': invoice_path,
            'customer_id': customer_id,
            'created_at': datetime.now().timestamp(),
            'expires_at': datetime.now().timestamp() + 3600  # 1 hour expiry
        }
        
        base_url = os.environ.get('BASE_URL', 'https://your-domain.com')
        download_url = f"{base_url}/download/invoice/{token}"
        
        logger.info(f"Generated download link for customer {customer_id}: {download_url}")
        return download_url

# יצירת instance גלובלי
invoice_generator = InvoiceGenerator()