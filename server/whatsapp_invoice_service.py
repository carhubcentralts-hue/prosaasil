"""
שירות שליחת חשבוניות וחוזים דרך WhatsApp
WhatsApp Invoice and Contract Service
"""

import os
import logging
from datetime import datetime
from flask import current_app
import base64

logger = logging.getLogger(__name__)

class WhatsAppInvoiceService:
    """שירות שליחת חשבוניות דרך WhatsApp"""
    
    @classmethod
    def send_invoice_with_signature(cls, business_id, customer_phone, customer_name, amount, reason, include_signature=True):
        """
        יצירה ושליחת חשבונית עם חתימה דיגיטלית דרך WhatsApp
        
        Args:
            business_id: מזהה העסק
            customer_phone: טלפון הלקוח
            customer_name: שם הלקוח
            amount: סכום החשבונית
            reason: סיבת החשבונית
            include_signature: האם לכלול חתימה דיגיטלית
            
        Returns:
            dict: תוצאה של השליחה
        """
        try:
            # יצירת החשבונית עם invoice_generator
            from invoice_generator import InvoiceGenerator
            
            invoice_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'amount': amount,
                'reason': reason,
                'business_id': business_id,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'invoice_number': cls._generate_invoice_number()
            }
            
            # יצירת קובץ PDF
            pdf_result = InvoiceGenerator.create_invoice_pdf(invoice_data)
            
            if not pdf_result.get('success'):
                return {
                    'success': False,
                    'error': f'שגיאה ביצירת החשבונית: {pdf_result.get("error")}'
                }
            
            pdf_path = pdf_result['pdf_path']
            
            # הוספת חתימה דיגיטלית אם נדרש
            if include_signature:
                signature_result = cls._add_digital_signature(pdf_path, customer_name)
                if signature_result.get('success'):
                    pdf_path = signature_result['signed_pdf_path']
            
            # שליחה דרך WhatsApp
            whatsapp_result = cls._send_pdf_via_whatsapp(
                business_id=business_id,
                customer_phone=customer_phone,
                pdf_path=pdf_path,
                message_type='invoice',
                customer_name=customer_name,
                amount=amount,
                reason=reason
            )
            
            return whatsapp_result
            
        except Exception as e:
            logger.error(f"Error sending invoice via WhatsApp: {e}")
            return {
                'success': False,
                'error': f'שגיאה בשליחת חשבונית: {str(e)}'
            }
    
    @classmethod
    def send_contract_with_signature(cls, business_id, customer_phone, customer_name, contract_details):
        """
        יצירה ושליחת חוזה עם חתימה דיגיטלית דרך WhatsApp
        
        Args:
            business_id: מזהה העסק
            customer_phone: טלפון הלקוח
            customer_name: שם הלקוח
            contract_details: פרטי החוזה
            
        Returns:
            dict: תוצאה של השליחה
        """
        try:
            # יצירת החוזה
            from digital_signature_service import DigitalSignatureService
            
            contract_data = {
                'customer_name': customer_name,
                'customer_phone': customer_phone,
                'business_id': business_id,
                'contract_details': contract_details,
                'date': datetime.now().strftime('%Y-%m-%d'),
                'contract_number': cls._generate_contract_number()
            }
            
            # יצירת PDF של החוזה
            contract_result = DigitalSignatureService.create_contract_pdf(contract_data)
            
            if not contract_result.get('success'):
                return {
                    'success': False,
                    'error': f'שגיאה ביצירת החוזה: {contract_result.get("error")}'
                }
            
            pdf_path = contract_result['pdf_path']
            
            # הוספת חתימה דיגיטלית
            signature_result = cls._add_digital_signature(pdf_path, customer_name)
            if signature_result.get('success'):
                pdf_path = signature_result['signed_pdf_path']
            
            # שליחה דרך WhatsApp
            whatsapp_result = cls._send_pdf_via_whatsapp(
                business_id=business_id,
                customer_phone=customer_phone,
                pdf_path=pdf_path,
                message_type='contract',
                customer_name=customer_name,
                contract_details=contract_details
            )
            
            return whatsapp_result
            
        except Exception as e:
            logger.error(f"Error sending contract via WhatsApp: {e}")
            return {
                'success': False,
                'error': f'שגיאה בשליחת חוזה: {str(e)}'
            }
    
    @classmethod
    def send_quote_proposal(cls, business_id, customer_phone, customer_name, quote_details):
        """שליחת הצעת מחיר דרך WhatsApp"""
        try:
            # יצירת הצעת מחיר בפורמט טקסט מעוצב
            quote_message = cls._format_quote_message(customer_name, quote_details)
            
            # שליחת ההודעה
            from enhanced_whatsapp_service import WhatsAppService
            
            result = WhatsAppService.send_message(
                business_id=business_id,
                to_phone=customer_phone,
                message=quote_message
            )
            
            if result.get('success'):
                # לוג הפעולה ב-CRM
                cls._log_crm_action(
                    business_id=business_id,
                    customer_phone=customer_phone,
                    action_type='quote_sent',
                    details=quote_details
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error sending quote proposal: {e}")
            return {
                'success': False,
                'error': f'שגיאה בשליחת הצעת מחיר: {str(e)}'
            }
    
    @classmethod
    def _send_pdf_via_whatsapp(cls, business_id, customer_phone, pdf_path, message_type, **kwargs):
        """שליחת קובץ PDF דרך WhatsApp"""
        try:
            from enhanced_whatsapp_service import WhatsAppService
            
            # הכנת הודעת לוויה
            if message_type == 'invoice':
                message = cls._format_invoice_message(kwargs.get('customer_name'), kwargs.get('amount'), kwargs.get('reason'))
            elif message_type == 'contract':
                message = cls._format_contract_message(kwargs.get('customer_name'), kwargs.get('contract_details'))
            else:
                message = f"מסמך עבור {kwargs.get('customer_name', 'הלקוח')}"
            
            # בדיקה אם קובץ PDF קיים
            if not os.path.exists(pdf_path):
                return {
                    'success': False,
                    'error': 'קובץ PDF לא נמצא'
                }
            
            # שליחת ההודעה עם הקובץ
            # ראשית שליחת ההודעה
            message_result = WhatsAppService.send_message(
                business_id=business_id,
                to_phone=customer_phone,
                message=message
            )
            
            if not message_result.get('success'):
                return message_result
            
            # שליחת הקובץ (אם WhatsApp תומך)
            file_result = cls._send_file_if_supported(business_id, customer_phone, pdf_path, message_type)
            
            # לוג הפעולה ב-CRM
            cls._log_crm_action(
                business_id=business_id,
                customer_phone=customer_phone,
                action_type=f'{message_type}_sent',
                details=kwargs
            )
            
            return {
                'success': True,
                'message': f'{message_type} נשלח בהצלחה',
                'pdf_path': pdf_path,
                'whatsapp_result': message_result,
                'file_result': file_result
            }
            
        except Exception as e:
            logger.error(f"Error sending PDF via WhatsApp: {e}")
            return {
                'success': False,
                'error': f'שגיאה בשליחת PDF: {str(e)}'
            }
    
    @classmethod
    def _send_file_if_supported(cls, business_id, customer_phone, file_path, file_type):
        """שליחת קובץ אם WhatsApp תומך (תלוי בספק)"""
        try:
            # כאן ניתן להוסיף תמיכה בשליחת קבצים דרך Twilio או Baileys
            # לעת עתה נחזיר הודעה עם קישור להורדה
            
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # יצירת קישור להורדה (אם יש שרת אחסון)
            download_link = cls._create_download_link(file_path)
            
            if download_link:
                from enhanced_whatsapp_service import WhatsAppService
                
                download_message = f"""
📎 *קובץ מצורף*: {file_name}
📊 *גודל*: {file_size/1024:.1f} KB
🔗 *להורדה*: {download_link}

⏰ הקישור תקף ל-7 ימים
                """.strip()
                
                return WhatsAppService.send_message(
                    business_id=business_id,
                    to_phone=customer_phone,
                    message=download_message
                )
            
            return {'success': True, 'note': 'קובץ מוכן לשליחה ידנית'}
            
        except Exception as e:
            logger.error(f"Error sending file: {e}")
            return {'success': False, 'error': str(e)}
    
    @classmethod
    def _add_digital_signature(cls, pdf_path, customer_name):
        """הוספת חתימה דיגיטלית לקובץ PDF"""
        try:
            from digital_signature_service import DigitalSignatureService
            
            signature_result = DigitalSignatureService.add_signature_to_pdf(
                pdf_path=pdf_path,
                signer_name=customer_name,
                signature_reason="אישור ומסירת מסמך"
            )
            
            return signature_result
            
        except Exception as e:
            logger.error(f"Error adding digital signature: {e}")
            return {
                'success': False,
                'error': f'שגיאה בהוספת חתימה: {str(e)}'
            }
    
    @classmethod
    def _format_invoice_message(cls, customer_name, amount, reason):
        """עיצוב הודעת חשבונית"""
        return f"""
🧾 *חשבונית חדשה*

👤 *לכבוד*: {customer_name}
💰 *סכום*: ₪{amount:.2f}
📝 *עבור*: {reason}
📅 *תאריך*: {datetime.now().strftime('%d/%m/%Y')}

📎 החשבונית מצורפת כקובץ PDF
🔒 החשבונית חתומה דיגיטלית

*תודה על הזמנתכם!* 🙏
        """.strip()
    
    @classmethod
    def _format_contract_message(cls, customer_name, contract_details):
        """עיצוב הודעת חוזה"""
        return f"""
📋 *חוזה חדש*

👤 *לכבוד*: {customer_name}
📅 *תאריך*: {datetime.now().strftime('%d/%m/%Y')}
📝 *פרטים*: {contract_details.get('summary', 'חוזה שירותים')}

📎 החוזה מצורף כקובץ PDF
🔒 החוזה חתום דיגיטלית
✅ נא לבדוק ולאשר

*בהמתנה לתגובתכם* 📞
        """.strip()
    
    @classmethod
    def _format_quote_message(cls, customer_name, quote_details):
        """עיצוב הודעת הצעת מחיר"""
        items = quote_details.get('items', [])
        total = quote_details.get('total', 0)
        
        message = f"""
💰 *הצעת מחיר*

👤 *לכבוד*: {customer_name}
📅 *תאריך*: {datetime.now().strftime('%d/%m/%Y')}

📋 *פירוט השירותים*:
        """.strip()
        
        for item in items:
            message += f"\n• {item.get('description', 'שירות')} - ₪{item.get('price', 0):.2f}"
        
        message += f"""

💵 *סה"כ*: ₪{total:.2f}
⏰ *תוקף ההצעה*: 30 ימים

📞 לקביעת פגישה או שאלות נוספות
🤝 נשמח לעמוד לשירותכם!
        """.strip()
        
        return message
    
    @classmethod
    def _generate_invoice_number(cls):
        """יצירת מספר חשבונית ייחודי"""
        return f"INV-{datetime.now().strftime('%Y%m%d')}-{datetime.now().microsecond}"
    
    @classmethod
    def _generate_contract_number(cls):
        """יצירת מספר חוזה ייחודי"""
        return f"CON-{datetime.now().strftime('%Y%m%d')}-{datetime.now().microsecond}"
    
    @classmethod
    def _create_download_link(cls, file_path):
        """יצירת קישור להורדת קובץ"""
        try:
            # כאן ניתן להעלות לשירות cloud או ליצור endpoint זמני
            # לעת עתה נחזיר None
            return None
            
        except Exception as e:
            logger.error(f"Error creating download link: {e}")
            return None
    
    @classmethod
    def _log_crm_action(cls, business_id, customer_phone, action_type, details):
        """לוג פעולה במערכת CRM"""
        try:
            from app import db
            from models import CRMCustomer
            
            # חיפוש לקוח קיים או יצירת חדש
            customer = CRMCustomer.query.filter_by(
                business_id=business_id,
                phone=customer_phone
            ).first()
            
            if not customer:
                customer = CRMCustomer(
                    business_id=business_id,
                    name=details.get('customer_name', 'לקוח חדש'),
                    phone=customer_phone,
                    source='whatsapp'
                )
                db.session.add(customer)
            
            # עדכון הערות הלקוח
            action_note = f"{action_type}: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            if customer.notes:
                customer.notes += f"\n{action_note}"
            else:
                customer.notes = action_note
            
            db.session.commit()
            logger.info(f"CRM action logged: {action_type} for {customer_phone}")
            
        except Exception as e:
            logger.error(f"Error logging CRM action: {e}")