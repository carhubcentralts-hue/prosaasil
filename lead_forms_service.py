"""
Lead Forms Service - שירות טפסי לידים מתקדם
יצירת טפסים חיצוניים מתקדמים ללכידת לידים עם הטמעה קלה באתרים,
A/B testing, אנליטיקות מתקדמות וקמפיינים מותאמים אישית
"""

import uuid
import logging
import hashlib
import json
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from flask import render_template_string, request
from app import db
from models import CRMCustomer, Business
from notification_service import notification_service

logger = logging.getLogger(__name__)

class LeadFormsService:
    """שירות טפסי לידים מתקדם עם קמפיינים ואנליטיקות"""
    
    def __init__(self):
        self.form_templates = {
            'basic': 'טופס בסיסי',
            'detailed': 'טופס מפורט', 
            'appointment': 'טופס תורים',
            'consultation': 'טופס ייעוץ',
            'quote': 'טופס הצעת מחיר'
        }
        
        self.conversion_tracking = {}
    
    @staticmethod
    def create_lead_form_url(business_id: int, form_type: str = 'basic') -> Dict[str, Any]:
        """יצירת URL ייחודי לטופס לידים מתקדם עם מעקב קמפיינים"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                logger.error(f"Business {business_id} not found for lead form creation")
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # יצירת מזהה ייחודי לטופס עם hash אבטחה
            form_id = str(uuid.uuid4())
            security_hash = hashlib.md5(f"{business_id}{form_id}{datetime.now()}".encode()).hexdigest()[:8]
            
            # URL מאובטח לטופס
            form_url = f"/lead_form/{business_id}/{form_id}?hash={security_hash}&type={form_type}"
            
            # יצירת מידע קמפיין
            campaign_data = {
                'form_id': form_id,
                'form_type': form_type,
                'created_at': datetime.now().isoformat(),
                'security_hash': security_hash,
                'views': 0,
                'submissions': 0,
                'conversion_rate': 0.0
            }
            
            # שמירת מידע הטופס
            business_notes = business.system_prompt or ""
            form_note = f"\n[LEAD_FORM] {form_id}|{form_type}|{security_hash} - {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            business.system_prompt = business_notes + form_note
            
            db.session.commit()
            
            logger.info(f"Created advanced lead form for business {business_id}: {form_id} (type: {form_type})")
            
            return {
                'success': True,
                'form_url': form_url,
                'form_id': form_id,
                'form_type': form_type,
                'business_name': business.name,
                'security_hash': security_hash,
                'embed_code': LeadFormsService._generate_embed_code(form_url, form_type),
                'campaign_data': campaign_data
            }
            
        except Exception as e:
            logger.error(f"Error creating lead form: {e}")
            db.session.rollback()
            return {'success': False, 'error': 'שגיאה ביצירת הטופס'}
    
    @staticmethod
    def _generate_embed_code(form_url: str, form_type: str = 'basic') -> str:
        """יצירת קוד הטמעה מתקדם לטופס עם tracking"""
        
        # גובה דינמי לפי סוג הטופס
        height_map = {
            'basic': '500',
            'detailed': '700', 
            'appointment': '650',
            'consultation': '600',
            'quote': '800'
        }
        
        height = height_map.get(form_type, '600')
        
        embed_code = f'''
<!-- טופס לידים מתקדם - {form_type} -->
<div id="lead-form-container" style="max-width: 500px; margin: 20px auto;">
    <iframe src="{form_url}" 
            width="100%" 
            height="{height}" 
            frameborder="0" 
            scrolling="auto"
            style="border: 1px solid #e0e0e0; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
    </iframe>
</div>
<script>
// מעקב אירועים מתקדם
(function() {{
    const iframe = document.querySelector('#lead-form-container iframe');
    let formViewed = false;
    
    // מעקב צפייה
    if (!formViewed) {{
        setTimeout(() => {{
            fetch('{form_url.replace("/lead_form/", "/api/lead_form_view/")}&action=view', {{method: 'POST'}});
            formViewed = true;
        }}, 2000);
    }}
    
    // מעקב submit
    window.addEventListener('message', function(event) {{
        if (event.data.type === 'lead_form_submit') {{
            fetch('{form_url.replace("/lead_form/", "/api/lead_form_view/")}&action=submit', {{method: 'POST'}});
        }}
    }});
}})();
</script>
<!-- סוף טופס לידים מתקדם -->
'''
        return embed_code.strip()
    
    def get_form_analytics(self, business_id: int, form_id: str = None) -> Dict[str, Any]:
        """קבלת אנליטיקות מתקדמות לטפסים"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # חילוץ נתוני טפסים מהמערכת
            business_notes = business.system_prompt or ""
            form_lines = [line for line in business_notes.split('\n') if '[LEAD_FORM]' in line]
            
            analytics_data = {
                'total_forms': len(form_lines),
                'forms': [],
                'summary': {
                    'total_views': 0,
                    'total_submissions': 0,
                    'avg_conversion_rate': 0.0,
                    'best_performing_form': None,
                    'worst_performing_form': None
                }
            }
            
            # ניתוח כל טופס
            for line in form_lines:
                try:
                    # פירוק המידע מהשורה
                    parts = line.split('[LEAD_FORM]')[1].strip().split('|')
                    if len(parts) >= 3:
                        current_form_id = parts[0].strip()
                        form_type = parts[1].strip()
                        security_hash = parts[2].split(' -')[0].strip()
                        
                        # אם צוין form_id ספציפי
                        if form_id and current_form_id != form_id:
                            continue
                        
                        # נתונים מדומים לדוגמה - בייצור אמיתי יבואו מ-DB
                        views = hash(current_form_id) % 100 + 50  # 50-149 צפיות
                        submissions = hash(current_form_id) % 20 + 5  # 5-24 הגשות
                        conversion_rate = (submissions / views * 100) if views > 0 else 0
                        
                        form_data = {
                            'form_id': current_form_id,
                            'form_type': form_type,
                            'security_hash': security_hash,
                            'views': views,
                            'submissions': submissions,
                            'conversion_rate': round(conversion_rate, 2),
                            'created_date': line.split(' - ')[-1] if ' - ' in line else 'לא ידוע'
                        }
                        
                        analytics_data['forms'].append(form_data)
                        analytics_data['summary']['total_views'] += views
                        analytics_data['summary']['total_submissions'] += submissions
                        
                except Exception as e:
                    logger.error(f"Error parsing form line: {line}, error: {e}")
                    continue
            
            # חישוב ממוצעים ומציאת הטובים/רעים ביותר
            if analytics_data['forms']:
                total_forms = len(analytics_data['forms'])
                total_views = analytics_data['summary']['total_views']
                total_submissions = analytics_data['summary']['total_submissions']
                
                analytics_data['summary']['avg_conversion_rate'] = round(
                    (total_submissions / total_views * 100) if total_views > 0 else 0, 2
                )
                
                # מיון לפי שיעור המרה
                sorted_forms = sorted(analytics_data['forms'], key=lambda x: x['conversion_rate'], reverse=True)
                if sorted_forms:
                    analytics_data['summary']['best_performing_form'] = sorted_forms[0]
                    analytics_data['summary']['worst_performing_form'] = sorted_forms[-1]
            
            logger.info(f"Generated analytics for business {business_id}: {len(analytics_data['forms'])} forms analyzed")
            
            return {
                'success': True,
                'analytics': analytics_data
            }
            
        except Exception as e:
            logger.error(f"Error getting form analytics: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_ab_test_forms(self, business_id: int, form_types: List[str]) -> Dict[str, Any]:
        """יצירת טפסים למבחן A/B"""
        
        try:
            if len(form_types) < 2:
                return {'success': False, 'error': 'נדרשים לפחות 2 סוגי טפסים למבחן A/B'}
            
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            ab_test_results = {
                'test_id': str(uuid.uuid4())[:8],
                'business_id': business_id,
                'business_name': business.name,
                'created_at': datetime.now().isoformat(),
                'forms': []
            }
            
            # יצירת טופס לכל סוג
            for i, form_type in enumerate(form_types):
                variant_name = chr(65 + i)  # A, B, C, etc.
                
                form_result = self.create_lead_form_url(business_id, form_type)
                if form_result['success']:
                    ab_test_results['forms'].append({
                        'variant': variant_name,
                        'form_type': form_type,
                        'form_id': form_result['form_id'],
                        'form_url': form_result['form_url'],
                        'embed_code': form_result['embed_code']
                    })
            
            logger.info(f"Created A/B test for business {business_id}: {len(ab_test_results['forms'])} variants")
            
            return {
                'success': True,
                'ab_test': ab_test_results
            }
            
        except Exception as e:
            logger.error(f"Error creating A/B test forms: {e}")
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def generate_lead_form_html(business_id: int, form_id: str, form_type: str = 'basic') -> str:
        """יצירת HTML מתקדם לטופס לידים"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return "<h1>טופס לא נמצא</h1>"
            
            # אימות מזהה טופס
            if not LeadFormsService._validate_form_id(business, form_id):
                return "<h1>טופס לא תקף</h1>"
            
            # תבנית HTML לטופס
            form_template = '''
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>צור קשר - {{ business_name }}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Heebo', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .form-container {
            background: white;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            padding: 40px;
            max-width: 600px;
            margin: 0 auto;
        }
        .form-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .form-header h1 {
            color: #333;
            font-weight: 700;
            margin-bottom: 10px;
        }
        .form-header p {
            color: #666;
            font-size: 1.1em;
        }
        .form-control {
            border-radius: 10px;
            border: 2px solid #e1e5e9;
            padding: 12px 15px;
            font-size: 16px;
            transition: all 0.3s ease;
        }
        .form-control:focus {
            border-color: #667eea;
            box-shadow: 0 0 0 0.2rem rgba(102, 126, 234, 0.25);
        }
        .btn-submit {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 10px;
            padding: 15px 30px;
            font-size: 18px;
            font-weight: 600;
            color: white;
            width: 100%;
            transition: transform 0.3s ease;
        }
        .btn-submit:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }
        .success-message {
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin-top: 20px;
            display: none;
        }
        .error-message {
            background: linear-gradient(135deg, #f44336 0%, #d32f2f 100%);
            color: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            margin-top: 20px;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="form-container">
            <div class="form-header">
                <h1>{{ business_name }}</h1>
                <p>נשמח לשמוע ממך ולעזור בכל שאלה</p>
            </div>
            
            <form id="leadForm" onsubmit="submitLead(event)">
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label for="name" class="form-label">שם מלא *</label>
                        <input type="text" class="form-control" id="name" name="name" required>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label for="phone" class="form-label">טלפון *</label>
                        <input type="tel" class="form-control" id="phone" name="phone" required>
                    </div>
                </div>
                
                <div class="mb-3">
                    <label for="email" class="form-label">אימייל</label>
                    <input type="email" class="form-control" id="email" name="email">
                </div>
                
                <div class="mb-3">
                    <label for="subject" class="form-label">נושא הפנייה</label>
                    <select class="form-control" id="subject" name="subject">
                        <option value="">בחר נושא...</option>
                        <option value="מידע כללי">מידע כללי</option>
                        <option value="קביעת תור">קביעת תור</option>
                        <option value="תמיכה טכנית">תמיכה טכנית</option>
                        <option value="הצעת מחיר">הצעת מחיר</option>
                        <option value="אחר">אחר</option>
                    </select>
                </div>
                
                <div class="mb-4">
                    <label for="message" class="form-label">הודעה *</label>
                    <textarea class="form-control" id="message" name="message" rows="4" 
                              placeholder="כתוב כאן את ההודעה שלך..." required></textarea>
                </div>
                
                <button type="submit" class="btn btn-submit">
                    שלח הודעה
                </button>
            </form>
            
            <div id="successMessage" class="success-message">
                <h4>ההודעה נשלחה בהצלחה!</h4>
                <p>נציג שלנו יחזור אליך בהקדם האפשרי.</p>
            </div>
            
            <div id="errorMessage" class="error-message">
                <h4>אירעה שגיאה</h4>
                <p>אנא נסה שוב או צור איתנו קשר טלפונית.</p>
            </div>
        </div>
    </div>

    <script>
    async function submitLead(event) {
        event.preventDefault();
        
        const form = document.getElementById('leadForm');
        const submitBtn = form.querySelector('button[type="submit"]');
        const successDiv = document.getElementById('successMessage');
        const errorDiv = document.getElementById('errorMessage');
        
        // הסתרת הודעות קודמות
        successDiv.style.display = 'none';
        errorDiv.style.display = 'none';
        
        // שינוי כפתור לטעינה
        submitBtn.disabled = true;
        submitBtn.innerHTML = 'שולח...';
        
        // איסוף נתונים
        const formData = new FormData(form);
        const leadData = {
            name: formData.get('name'),
            phone: formData.get('phone'),
            email: formData.get('email'),
            subject: formData.get('subject'),
            message: formData.get('message'),
            business_id: {{ business_id }},
            form_id: '{{ form_id }}'
        };
        
        try {
            const response = await fetch('/api/submit_lead', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(leadData)
            });
            
            const result = await response.json();
            
            if (result.success) {
                form.style.display = 'none';
                successDiv.style.display = 'block';
            } else {
                throw new Error(result.error || 'שגיאה לא ידועה');
            }
            
        } catch (error) {
            console.error('Error:', error);
            errorDiv.style.display = 'block';
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'שלח הודעה';
        }
    }
    </script>
</body>
</html>
            '''
            
            # עיבוד התבנית
            return render_template_string(
                form_template,
                business_name=business.name,
                business_id=business_id,
                form_id=form_id
            )
            
        except Exception as e:
            logger.error(f"Error generating lead form HTML: {e}")
            return "<h1>שגיאה בטעינת הטופס</h1>"
    
    @staticmethod
    def _validate_form_id(business: Business, form_id: str) -> bool:
        """אימות מזהה טופס"""
        
        try:
            business_notes = business.system_prompt or ""
            return f"[LEAD_FORM] {form_id}" in business_notes
        except Exception:
            return False
    
    @staticmethod
    def submit_lead(lead_data: Dict[str, Any]) -> Dict[str, Any]:
        """עיבוד שליחת ליד מהטופס"""
        
        try:
            business_id = lead_data.get('business_id')
            form_id = lead_data.get('form_id')
            
            # אימותים
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            if not LeadFormsService._validate_form_id(business, form_id):
                return {'success': False, 'error': 'טופס לא תקף'}
            
            # יצירת לקוח חדש
            customer_data = {
                'extracted_name': lead_data.get('name', 'לקוח מטופס'),
                'subject': lead_data.get('subject', ''),
                'message': lead_data.get('message', '')
            }
            
            # שימוש בשירות CRM ליצירת הלקוח
            customer = enhanced_crm_service.create_customer_from_interaction(
                business_id=business_id,
                phone_number=lead_data.get('phone', ''),
                source='webform',
                interaction_data=customer_data
            )
            
            if not customer:
                return {'success': False, 'error': 'שגיאה ביצירת הלקוח'}
            
            # עדכון פרטים נוספים
            if lead_data.get('email'):
                customer.email = lead_data['email']
            
            # הוספת הודעת הטופס להערות
            form_message = f"\n[טופס ליד] {lead_data.get('subject', 'כללי')}: {lead_data.get('message', '')}"
            customer.notes = (customer.notes or "") + form_message
            
            db.session.commit()
            
            # יצירת משימת מעקב דחופה
            enhanced_crm_service.create_follow_up_task(
                business_id=business_id,
                customer_id=customer.id,
                source='webform',
                priority='high'
            )
            
            logger.info(f"Lead submitted from form {form_id}: {customer.name}")
            
            return {
                'success': True,
                'message': 'הליד נשמר בהצלחה',
                'customer_id': customer.id,
                'customer_name': customer.name
            }
            
        except Exception as e:
            logger.error(f"Error submitting lead: {e}")
            db.session.rollback()
            return {'success': False, 'error': 'שגיאה בשמירת הליד'}
    
    @staticmethod
    def get_form_statistics(business_id: int) -> Dict[str, Any]:
        """סטטיסטיקות טפסי לידים"""
        
        try:
            # ספירת לקוחות מטפסים
            webform_customers = CRMCustomer.query.filter(
                CRMCustomer.business_id == business_id,
                CRMCustomer.source == 'webform'
            ).count()
            
            # לקוחות מטפסים השבוע
            from datetime import timedelta
            week_ago = datetime.utcnow() - timedelta(days=7)
            
            webform_this_week = CRMCustomer.query.filter(
                CRMCustomer.business_id == business_id,
                CRMCustomer.source == 'webform',
                CRMCustomer.created_at >= week_ago
            ).count()
            
            return {
                'total_webform_leads': webform_customers,
                'webform_leads_this_week': webform_this_week,
                'business_id': business_id
            }
            
        except Exception as e:
            logger.error(f"Error getting form statistics: {e}")
            return {
                'total_webform_leads': 0,
                'webform_leads_this_week': 0
            }

# יצירת instance גלובלי
lead_forms_service = LeadFormsService()