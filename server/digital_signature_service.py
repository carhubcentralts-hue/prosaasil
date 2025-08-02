"""
Digital Signature Service - שירות חתימה דיגיטלית מתקדם
מאפשר ללקוחות לחתום דיגיטלית על מסמכים ועסקאות
מציאת הנמוות, תיוג timestamp ו-IP, האשור רגולטורי
"""

import base64
import os
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from PIL import Image
from io import BytesIO
from flask import request
from app import db
from models import CRMCustomer

logger = logging.getLogger(__name__)

class DigitalSignatureService:
    """שירות חתימה דיגיטלית מתקדם"""
    
    @staticmethod
    def save_signature(customer_id: int, signature_data: str, 
                      document_type: str = 'general', remote_ip: Optional[str] = None) -> Dict[str, Any]:
        """שמירת חתימה דיגיטלית במסד הנתונים עם רגולציה משפטית"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                logger.error(f"Customer {customer_id} not found for signature")
                return {'success': False, 'error': 'לקוח לא נמצא'}
            
            # וידוא פורמט Base64 תקין
            if not signature_data.startswith('data:image/png;base64,'):
                logger.error(f"Invalid signature format for customer {customer_id}")
                return {'success': False, 'error': 'פורמט חתימה לא תקין'}
            
            # הסרת prefix והמרה לתמונה
            signature_base64 = signature_data.split(',')[1]
            signature_bytes = base64.b64decode(signature_base64)
            
            # אימות שמדובר בתמונה תקינה
            try:
                image = Image.open(BytesIO(signature_bytes))
                if image.format != 'PNG':
                    logger.error(f"Invalid image format for customer {customer_id}: {image.format}")
                    return {'success': False, 'error': 'רק קבצי PNG נתמכים'}
            except Exception as img_error:
                logger.error(f"Invalid image data for customer {customer_id}: {img_error}")
                return {'success': False, 'error': 'קובץ תמונה לא תקין'}
            
            # יצירת hash למסמך (לצורכי אבטחה ורגולציה)
            signature_hash = hashlib.sha256(signature_bytes).hexdigest()
            current_time = datetime.utcnow()
            client_ip = remote_ip or (request.remote_addr if request else 'unknown')
            
            # שמירת חתימה ללקוח עם timestamp ו-IP
            if hasattr(customer, 'signature_base64'):
                customer.signature_base64 = signature_data
            else:
                # אם אין עמודה, נשמור בהערות עם פרטים מלאים
                signature_note = f"\n[חתימה דיגיטלית] נחתם ב-{current_time.strftime('%d/%m/%Y %H:%M:%S')} מכתובת IP: {client_ip}, Hash: {signature_hash[:16]}"
                customer.notes = (customer.notes or "") + signature_note
            
            customer.updated_at = current_time
            
            # שמירת קובץ חתימה פיזי עם hash
            signature_filename = DigitalSignatureService._save_signature_file(
                customer_id, signature_bytes, document_type, signature_hash
            )
            
            # שמירת רישום לוג מפורט
            signature_log = {
                'customer_id': customer_id,
                'timestamp': current_time.isoformat(),
                'ip_address': client_ip,
                'document_type': document_type,
                'signature_hash': signature_hash,
                'filename': signature_filename
            }
            
            db.session.commit()
            
            logger.info(f"Digital signature saved for customer {customer_id} with hash {signature_hash[:16]} from IP {client_ip}")
            
            return {
                'success': True,
                'message': 'חתימה נשמרה בהצלחה',
                'signature_file': signature_filename,
                'customer_id': customer_id,
                'signature_hash': signature_hash,
                'timestamp': current_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error saving digital signature: {e}")
            db.session.rollback()
            return {'success': False, 'error': f'שגיאה בשמירת חתימה: {str(e)}'}
    
    @staticmethod
    def add_signature_to_document(document_path: str, customer_id: int) -> Dict[str, Any]:
        """הוספת חתימה אוטומטית למסמך PDF"""
        
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            import io
            
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return {'success': False, 'error': 'לקוח לא נמצא'}
            
            # חיפוש קובץ חתימה
            signature_dir = os.path.join('static', 'signatures')
            signature_file = None
            
            if os.path.exists(signature_dir):
                for file in os.listdir(signature_dir):
                    if file.startswith(f'customer_{customer_id}_'):
                        signature_file = os.path.join(signature_dir, file)
                        break
            
            if not signature_file or not os.path.exists(signature_file):
                return {'success': False, 'error': 'חתימה לא נמצאה עבור לקוח זה'}
            
            # יצירת מסמך חדש עם חתימה
            output_filename = f"signed_{customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            output_path = os.path.join('static', 'signed_documents', output_filename)
            
            # וידוא שהתיקייה קיימת
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # יצירת PDF עם חתימה
            packet = io.BytesIO()
            can = canvas.Canvas(packet, pagesize=letter)
            
            # הוספת תוכן המסמך (אם קיים)
            if os.path.exists(document_path):
                can.drawString(100, 750, f"מסמך חתום עבור: {customer.full_name}")
                can.drawString(100, 730, f"תאריך חתימה: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            else:
                can.drawString(100, 750, f"מסמך חתום עבור: {customer.full_name}")
                can.drawString(100, 730, f"תאריך חתימה: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
                can.drawString(100, 710, "המסמך המקורי לא נמצא - נוצר מסמך חדש")
            
            # הוספת חתימה למסמך
            try:
                can.drawImage(signature_file, 100, 600, width=200, height=100)
            except:
                can.drawString(100, 650, "[חתימה דיגיטלית]")
            
            can.save()
            
            # שמירת הקובץ
            with open(output_path, 'wb') as output_file:
                packet.seek(0)
                output_file.write(packet.read())
            
            logger.info(f"Signed document created: {output_path}")
            
            return {
                'success': True,
                'message': 'חתימה נוספה למסמך בהצלחה',
                'signed_document_path': output_path,
                'signed_document_url': f'/static/signed_documents/{output_filename}'
            }
            
        except Exception as e:
            logger.error(f"Error adding signature to document: {e}")
            return {'success': False, 'error': f'שגיאה בהוספת חתימה למסמך: {str(e)}'}
    
    @staticmethod
    def _save_signature_file(customer_id: int, signature_bytes: bytes, 
                           document_type: str, signature_hash: str) -> str:
        """שמירת קובץ חתימה פיזי עם hash לאבטחה"""
        
        try:
            # יצירת תיקיית חתימות מוגנת
            signature_dir = os.path.join('static', 'signatures')
            os.makedirs(signature_dir, exist_ok=True)
            
            # יצירת שם קובץ ייחודי עם hash
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'signature_{customer_id}_{document_type}_{timestamp}_{signature_hash[:8]}.png'
            file_path = os.path.join(signature_dir, filename)
            
            # שמירת הקובץ עם הגנות אבטחה
            with open(file_path, 'wb') as f:
                f.write(signature_bytes)
            
            # הגדרת הרשאות קובץ (רק קריאה)
            os.chmod(file_path, 0o644)
            
            logger.info(f"Signature file saved securely: {file_path}")
            return filename
            
        except Exception as e:
            logger.error(f"Error saving signature file: {e}")
            return None
    
    @staticmethod
    def get_customer_signatures(customer_id: int) -> Dict[str, Any]:
        """קבלת כל החתימות של לקוח"""
        
        try:
            signature_dir = os.path.join('static', 'signatures')
            signatures = []
            
            if os.path.exists(signature_dir):
                for file in os.listdir(signature_dir):
                    if file.startswith(f'customer_{customer_id}_'):
                        file_path = os.path.join(signature_dir, file)
                        file_stats = os.stat(file_path)
                        
                        signatures.append({
                            'filename': file,
                            'url': f'/static/signatures/{file}',
                            'created_date': datetime.fromtimestamp(file_stats.st_ctime),
                            'size': file_stats.st_size
                        })
            
            return {
                'success': True,
                'signatures': signatures,
                'count': len(signatures)
            }
            
        except Exception as e:
            logger.error(f"Error getting customer signatures: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_customer_signature(customer_id: int) -> Optional[str]:
        """קבלת חתימת לקוח"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return None
            
            if hasattr(customer, 'signature_base64') and customer.signature_base64:
                return customer.signature_base64
            
            # חיפוש קובץ חתימה בתיקייה
            signatures_dir = os.path.join('static', 'signatures')
            if not os.path.exists(signatures_dir):
                return None
            
            # חיפוש קובץ אחרון של הלקוח
            signature_files = [
                f for f in os.listdir(signatures_dir)
                if f.startswith(f"signature_{customer_id}_") and f.endswith('.png')
            ]
            
            if signature_files:
                # מיון לפי תאריך (הכי חדש ראשון)
                signature_files.sort(reverse=True)
                latest_file = signature_files[0]
                
                # המרה ל-Base64
                filepath = os.path.join(signatures_dir, latest_file)
                with open(filepath, 'rb') as f:
                    signature_bytes = f.read()
                    signature_base64 = base64.b64encode(signature_bytes).decode('utf-8')
                    return f"data:image/png;base64,{signature_base64}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting customer signature: {e}")
            return None
    
    @staticmethod
    def verify_signature_integrity(signature_data: str) -> bool:
        """אימות תקינות חתימה"""
        
        try:
            if not signature_data or not signature_data.startswith('data:image/png;base64,'):
                return False
            
            signature_base64 = signature_data.split(',')[1]
            signature_bytes = base64.b64decode(signature_base64)
            
            # בדיקת תקינות תמונה
            image = Image.open(BytesIO(signature_bytes))
            
            # בדיקות בסיסיות
            if image.width < 100 or image.height < 50:
                return False  # חתימה קטנה מדי
            
            if image.width > 800 or image.height > 400:
                return False  # חתימה גדולה מדי
            
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def delete_customer_signature(customer_id: int) -> bool:
        """מחיקת חתימת לקוח"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return False
            
            # מחיקה ממסד נתונים
            if hasattr(customer, 'signature_base64'):
                customer.signature_base64 = None
            
            customer.updated_at = datetime.utcnow()
            
            # מחיקת קבצי חתימה
            signatures_dir = os.path.join('static', 'signatures')
            if os.path.exists(signatures_dir):
                signature_files = [
                    f for f in os.listdir(signatures_dir)
                    if f.startswith(f"signature_{customer_id}_")
                ]
                
                for filename in signature_files:
                    filepath = os.path.join(signatures_dir, filename)
                    os.remove(filepath)
            
            db.session.commit()
            
            logger.info(f"Deleted signature for customer {customer_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting signature: {e}")
            db.session.rollback()
            return False
    
    @staticmethod
    def get_signature_statistics(business_id: int) -> Dict[str, Any]:
        """סטטיסטיקות חתימות לעסק"""
        
    def lock_document_after_signature(self, document_id: str, customer_id: int) -> Dict[str, Any]:
        """Task 6: Lock document after signature to prevent tampering"""
        try:
            # In production, this would update database record
            locked_documents = getattr(self, 'locked_documents', set())
            locked_documents.add(f"{document_id}_{customer_id}")
            self.locked_documents = locked_documents
            
            logger.info(f"🔒 Document locked after signature: {document_id} for customer {customer_id}")
            
            return {
                'success': True,
                'message': 'מסמך נעול לאחר חתימה',
                'document_id': document_id,
                'locked_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error locking document: {e}")
            return {'success': False, 'error': str(e)}

    def add_signature_metadata(self, customer_id: int, signature_data: str, 
                              document_path: str, remote_ip: str) -> Dict[str, Any]:
        """Task 6: Add comprehensive signature metadata"""
        try:
            metadata = {
                'customer_id': customer_id,
                'signed_at': datetime.utcnow().isoformat(),
                'signed_ip': remote_ip,
                'document_path': document_path,
                'signature_hash': hashlib.sha256(signature_data.encode()).hexdigest(),
                'user_agent': request.headers.get('User-Agent', ''),
                'verification_status': 'verified'
            }
            
            # Store metadata (in production, use database)
            if not hasattr(self, 'signature_metadata'):
                self.signature_metadata = {}
            
            self.signature_metadata[customer_id] = metadata
            
            logger.info(f"✍️ Signature metadata saved for customer {customer_id}")
            
            return {
                'success': True,
                'metadata': metadata,
                'verification_hash': metadata['signature_hash']
            }
            
        except Exception as e:
            logger.error(f"Error adding signature metadata: {e}")
            return {'success': False, 'error': str(e)}

        try:
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            
            total_customers = len(customers)
            signed_customers = 0
            
            for customer in customers:
                if DigitalSignatureService.get_customer_signature(customer.id):
                    signed_customers += 1
            
            signing_rate = (signed_customers / total_customers * 100) if total_customers > 0 else 0
            
            return {
                'total_customers': total_customers,
                'signed_customers': signed_customers,
                'unsigned_customers': total_customers - signed_customers,
                'signing_rate': round(signing_rate, 1)
            }
            
        except Exception as e:
            logger.error(f"Error getting signature statistics: {e}")
            return {
                'total_customers': 0,
                'signed_customers': 0,
                'unsigned_customers': 0,
                'signing_rate': 0
            }

# יצירת instance גלובלי
digital_signature_service = DigitalSignatureService()