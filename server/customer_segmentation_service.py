"""
Customer Segmentation Service - שירות סיגמנטציה מתקדמת של לקוחות
מערכת מתקדמת לחלוקת לקוחות לקבוצות על בסיס התנהגות, רכישות, 
אינטראקציות ופוטנציאל עסקי
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from app import db
from models import CRMCustomer, Business, CallLog, ConversationTurn, AppointmentRequest
from crm_models import CustomerInteraction, Quote

logger = logging.getLogger(__name__)

class CustomerSegmentationService:
    """שירות סיגמנטציה מתקדמת של לקוחות"""
    
    def __init__(self):
        self.segment_definitions = {
            'vip_customers': {
                'name': 'לקוחות VIP',
                'description': 'לקוחות עם ערך עסקי גבוה',
                'criteria': 'total_value > 10000 OR interaction_frequency > 20',
                'color': 'gold'
            },
            'regular_customers': {
                'name': 'לקוחות קבועים',
                'description': 'לקוחות עם פעילות סדירה',
                'criteria': 'last_interaction < 30 days AND total_interactions > 5',
                'color': 'green'
            },
            'new_customers': {
                'name': 'לקוחות חדשים',
                'description': 'לקוחות שהצטרפו לאחרונה',
                'criteria': 'created_at > 30 days ago',
                'color': 'blue'
            },
            'inactive_customers': {
                'name': 'לקוחות לא פעילים',
                'description': 'לקוחות ללא פעילות ממושכת',
                'criteria': 'last_interaction > 90 days',
                'color': 'gray'
            },
            'high_potential': {
                'name': 'פוטנציאל גבוה',
                'description': 'לקוחות עם פוטנציאל עסקי גבוה',
                'criteria': 'quote_acceptance_rate > 50% OR avg_deal_size > 5000',
                'color': 'purple'
            },
            'churned': {
                'name': 'לקוחות שעזבו',
                'description': 'לקוחות שלא חזרו לאחר תורים',
                'criteria': 'last_interaction > 180 days AND had_appointments = true',
                'color': 'red'
            }
        }
        
        self.scoring_weights = {
            'recency': 0.3,      # כמה זמן עבר מאז האינטראקציה האחרונה
            'frequency': 0.3,    # תדירות האינטראקציות
            'monetary': 0.25,    # ערך כספי
            'engagement': 0.15   # רמת המעורבות
        }
    
    def analyze_customer_segments(self, business_id: int) -> Dict[str, Any]:
        """ניתוח מקיף של סיגמנטים בעסק"""
        
        try:
            business = Business.query.get(business_id)
            if not business:
                return {'success': False, 'error': 'עסק לא נמצא'}
            
            # קבלת כל הלקוחות של העסק
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            
            if not customers:
                return {
                    'success': True,
                    'message': 'אין לקוחות בעסק זה',
                    'segments': {},
                    'total_customers': 0
                }
            
            # חישוב נתונים לכל לקוח
            customer_data = []
            for customer in customers:
                data = self._calculate_customer_metrics(customer)
                customer_data.append(data)
            
            # חלוקה לסיגמנטים
            segments = {}
            for segment_key, segment_def in self.segment_definitions.items():
                segment_customers = self._filter_customers_by_segment(
                    customer_data, segment_key
                )
                
                segments[segment_key] = {
                    'name': segment_def['name'],
                    'description': segment_def['description'],
                    'color': segment_def['color'],
                    'count': len(segment_customers),
                    'percentage': round((len(segment_customers) / len(customers)) * 100, 1),
                    'customers': segment_customers[:10],  # הצגת 10 הראשונים
                    'avg_value': self._calculate_segment_avg_value(segment_customers),
                    'total_value': self._calculate_segment_total_value(segment_customers)
                }
            
            # ניתוח כללי
            analysis = {
                'total_customers': len(customers),
                'active_customers': len([c for c in customer_data if c['days_since_last_interaction'] <= 30]),
                'high_value_customers': len([c for c in customer_data if c['total_value'] > 5000]),
                'new_customers_30d': len([c for c in customer_data if c['days_since_created'] <= 30]),
                'churn_risk': len([c for c in customer_data if c['days_since_last_interaction'] > 60]),
                'avg_customer_value': round(sum(c['total_value'] for c in customer_data) / len(customer_data), 2),
                'segments': segments
            }
            
            logger.info(f"Customer segmentation analysis completed for business {business_id}: {len(customers)} customers analyzed")
            
            return {
                'success': True,
                'business_name': business.name,
                'analysis_date': datetime.now().isoformat(),
                'analysis': analysis
            }
            
        except Exception as e:
            logger.error(f"Error analyzing customer segments: {e}")
            return {'success': False, 'error': str(e)}
    
    def create_custom_segment(self, business_id: int, segment_data: Dict[str, Any]) -> Dict[str, Any]:
        """יצירת סיגמנט מותאם אישית"""
        
        try:
            required_fields = ['name', 'description', 'criteria']
            for field in required_fields:
                if field not in segment_data:
                    return {'success': False, 'error': f'שדה חסר: {field}'}
            
            segment_id = f"custom_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # אימות הקריטריונים
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            customer_data = [self._calculate_customer_metrics(c) for c in customers]
            
            try:
                filtered_customers = self._filter_customers_by_custom_criteria(
                    customer_data, segment_data['criteria']
                )
            except Exception as e:
                return {
                    'success': False, 
                    'error': f'שגיאה בקריטריונים: {str(e)}'
                }
            
            # שמירת הסיגמנט החדש
            custom_segment = {
                'id': segment_id,
                'name': segment_data['name'],
                'description': segment_data['description'],
                'criteria': segment_data['criteria'],
                'color': segment_data.get('color', 'teal'),
                'created_date': datetime.now().isoformat(),
                'customer_count': len(filtered_customers),
                'customers': filtered_customers
            }
            
            # שמירה בהערות העסק (דוגמה - בייצור יהיה DB נפרד)
            business = Business.query.get(business_id)
            business_notes = business.system_prompt or ""
            segment_note = f"\n[CUSTOM_SEGMENT] {segment_id}|{segment_data['name']}|{segment_data['criteria']} - {datetime.now().strftime('%d/%m/%Y')}"
            business.system_prompt = business_notes + segment_note
            
            db.session.commit()
            
            logger.info(f"Created custom segment '{segment_data['name']}' for business {business_id}")
            
            return {
                'success': True,
                'segment': custom_segment
            }
            
        except Exception as e:
            logger.error(f"Error creating custom segment: {e}")
            db.session.rollback()
            return {'success': False, 'error': str(e)}
    
    def get_segment_recommendations(self, business_id: int, segment_key: str) -> Dict[str, Any]:
        """קבלת המלצות שיווק לסיגמנט ספציפי"""
        
        try:
            segment_def = self.segment_definitions.get(segment_key)
            if not segment_def:
                return {'success': False, 'error': 'סיגמנט לא נמצא'}
            
            # המלצות לפי סוג הסיגמנט
            recommendations = {
                'vip_customers': {
                    'marketing_strategy': 'שירות אישי ובלעדי',
                    'communication_frequency': 'שבועי',
                    'channels': ['טלפון אישי', 'WhatsApp Business', 'דוא"ל מותאם'],
                    'offers': ['הנחות VIP', 'שירותים בלעדיים', 'עדיפות בתורים'],
                    'retention_tactics': ['תוכנית נאמנות', 'יועץ אישי', 'אירועים בלעדיים']
                },
                'regular_customers': {
                    'marketing_strategy': 'תחזוקת קשר סדירה',
                    'communication_frequency': 'דו-שבועי',
                    'channels': ['WhatsApp', 'SMS', 'דוא"ל'],
                    'offers': ['הנחות לקוחות קבועים', 'תזכורות לתורים'],
                    'retention_tactics': ['תוכנית הפניות', 'משוב קבוע', 'שירות מהיר']
                },
                'new_customers': {
                    'marketing_strategy': 'חוויית כניסה מושלמת',
                    'communication_frequency': 'יומי בשבוע הראשון',
                    'channels': ['WhatsApp', 'SMS ברוכים הבאים'],
                    'offers': ['הנחת לקוח חדש', 'ייעוץ חינמי', 'מידע על השירותים'],
                    'retention_tactics': ['מדריך לקוח', 'מעקב צמוד', 'משוב מהיר']
                },
                'inactive_customers': {
                    'marketing_strategy': 'קמפיין החזרה',
                    'communication_frequency': 'חד-פעמי עם מעקב',
                    'channels': ['טלפון', 'WhatsApp', 'דוא"ל אישי'],
                    'offers': ['הנחה מיוחדת לחזרה', 'שירות חינמי', 'ייעוץ'],
                    'retention_tactics': ['זיהוי סיבת העזיבה', 'הצעה מותאמת', 'שירות משופר']
                },
                'high_potential': {
                    'marketing_strategy': 'מכירות מותאמות',
                    'communication_frequency': 'שבועי',
                    'channels': ['טלפון', 'פגישות אישיות', 'WhatsApp Business'],
                    'offers': ['הצעות מיוחדות', 'חבילות מורחבות', 'תנאי תשלום נוחים'],
                    'retention_tactics': ['יועץ מכירות ייעודי', 'מעקב צמוד', 'שירות מהיר']
                },
                'churned': {
                    'marketing_strategy': 'קמפיין זכייה חוזרת',
                    'communication_frequency': 'חד-פעמי אגרסיבי',
                    'channels': ['טלפון אישי', 'WhatsApp', 'הודעת דוא"ל אישית'],
                    'offers': ['הנחה משמעותית', 'שירות חינמי', 'פגישה אישית'],
                    'retention_tactics': ['זיהוי בעיות עבר', 'שיפור שירות', 'הבטחות מחודשות']
                }
            }
            
            segment_rec = recommendations.get(segment_key, {})
            
            # הוספת המלצות טקטיות ספציפיות
            tactical_recommendations = self._generate_tactical_recommendations(
                business_id, segment_key
            )
            
            result = {
                'success': True,
                'segment_name': segment_def['name'],
                'segment_description': segment_def['description'],
                'strategic_recommendations': segment_rec,
                'tactical_recommendations': tactical_recommendations,
                'implementation_timeline': self._create_implementation_timeline(segment_key),
                'success_metrics': self._define_success_metrics(segment_key)
            }
            
            logger.info(f"Generated recommendations for segment '{segment_key}' in business {business_id}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error getting segment recommendations: {e}")
            return {'success': False, 'error': str(e)}
    
    def track_segment_performance(self, business_id: int, days_back: int = 30) -> Dict[str, Any]:
        """מעקב ביצועים של סיגמנטים"""
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            # ניתוח נתונים היסטוריים
            segments_analysis = self.analyze_customer_segments(business_id)
            if not segments_analysis['success']:
                return segments_analysis
            
            segments = segments_analysis['analysis']['segments']
            
            # מעקב תזוזות בין סיגמנטים
            segment_movements = {}
            for segment_key in self.segment_definitions.keys():
                segment_movements[segment_key] = {
                    'gained_customers': 0,  # דוגמה - בייצור יהיה חישוב אמיתי
                    'lost_customers': 0,
                    'net_change': 0,
                    'conversion_rate': 0.0
                }
            
            # חישוב ROI לכל סיגמנט
            segment_roi = {}
            for segment_key, segment_data in segments.items():
                if segment_data['count'] > 0:
                    avg_value = segment_data['avg_value']
                    # הערכת עלות שיווק (דוגמה)
                    marketing_cost = segment_data['count'] * 50  # 50₪ לכל לקוח
                    roi = ((avg_value - marketing_cost) / marketing_cost * 100) if marketing_cost > 0 else 0
                    
                    segment_roi[segment_key] = {
                        'marketing_cost': marketing_cost,
                        'revenue': segment_data['total_value'],
                        'roi_percentage': round(roi, 2),
                        'cost_per_customer': round(marketing_cost / segment_data['count'], 2) if segment_data['count'] > 0 else 0
                    }
            
            performance_data = {
                'analysis_period': f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}",
                'segments_snapshot': segments,
                'segment_movements': segment_movements,
                'roi_analysis': segment_roi,
                'top_performing_segment': max(segment_roi.keys(), key=lambda k: segment_roi[k]['roi_percentage']) if segment_roi else None,
                'recommendations': self._generate_performance_recommendations(segments, segment_roi)
            }
            
            logger.info(f"Segment performance tracking completed for business {business_id}")
            
            return {
                'success': True,
                'performance_data': performance_data
            }
            
        except Exception as e:
            logger.error(f"Error tracking segment performance: {e}")
            return {'success': False, 'error': str(e)}
    
    def _calculate_customer_metrics(self, customer: CRMCustomer) -> Dict[str, Any]:
        """חישוב מטריקות לקוח"""
        
        now = datetime.now()
        
        # חישוב ימים מאז יצירה ואינטראקציה אחרונה
        days_since_created = (now - customer.created_at).days if customer.created_at else 999
        days_since_last_interaction = (now - customer.last_interaction_date).days if customer.last_interaction_date else 999
        
        # ספירת אינטראקציות
        total_calls = customer.total_calls or 0
        total_messages = customer.total_messages or 0
        total_interactions = total_calls + total_messages
        
        # ספירת תורים
        appointments_count = AppointmentRequest.query.filter_by(
            business_id=customer.business_id,
            customer_phone=customer.phone
        ).count()
        
        # הערכת ערך כספי (דוגמה)
        estimated_value = total_interactions * 100 + appointments_count * 300
        
        # חישוב ציון מעורבות
        engagement_score = min(100, (total_interactions * 5) + (appointments_count * 10))
        
        # ציון RFM (Recency, Frequency, Monetary)
        recency_score = max(0, 100 - (days_since_last_interaction * 2))
        frequency_score = min(100, total_interactions * 10)
        monetary_score = min(100, estimated_value / 100)
        
        rfm_score = (
            recency_score * self.scoring_weights['recency'] +
            frequency_score * self.scoring_weights['frequency'] +
            monetary_score * self.scoring_weights['monetary'] +
            engagement_score * self.scoring_weights['engagement']
        )
        
        return {
            'id': customer.id,
            'name': customer.full_name,
            'phone': customer.phone,
            'email': customer.email,
            'days_since_created': days_since_created,
            'days_since_last_interaction': days_since_last_interaction,
            'total_interactions': total_interactions,
            'total_calls': total_calls,
            'total_messages': total_messages,
            'appointments_count': appointments_count,
            'total_value': estimated_value,
            'engagement_score': round(engagement_score, 1),
            'rfm_score': round(rfm_score, 1),
            'recency_score': round(recency_score, 1),
            'frequency_score': round(frequency_score, 1),
            'monetary_score': round(monetary_score, 1)
        }
    
    def _filter_customers_by_segment(self, customer_data: List[Dict], segment_key: str) -> List[Dict]:
        """סינון לקוחות לפי סיגמנט"""
        
        filtered = []
        
        for customer in customer_data:
            if segment_key == 'vip_customers':
                if customer['total_value'] > 1000 or customer['total_interactions'] > 15:
                    filtered.append(customer)
            
            elif segment_key == 'regular_customers':
                if (customer['days_since_last_interaction'] <= 30 and 
                    customer['total_interactions'] >= 5 and
                    customer['total_value'] <= 1000):
                    filtered.append(customer)
            
            elif segment_key == 'new_customers':
                if customer['days_since_created'] <= 30:
                    filtered.append(customer)
            
            elif segment_key == 'inactive_customers':
                if customer['days_since_last_interaction'] > 90:
                    filtered.append(customer)
            
            elif segment_key == 'high_potential':
                if (customer['rfm_score'] > 70 and 
                    customer['appointments_count'] > 0 and
                    customer['days_since_last_interaction'] <= 60):
                    filtered.append(customer)
            
            elif segment_key == 'churned':
                if (customer['days_since_last_interaction'] > 180 and 
                    customer['appointments_count'] > 0):
                    filtered.append(customer)
        
        return filtered
    
    def _filter_customers_by_custom_criteria(self, customer_data: List[Dict], criteria: str) -> List[Dict]:
        """סינון לקוחות לפי קריטריונים מותאמים"""
        
        # פרסור פשוט של קריטריונים (בייצור יהיה מתקדם יותר)
        filtered = []
        
        for customer in customer_data:
            # דוגמה לביצוע קריטריונים פשוטים
            try:
                # החלפת משתנים בקריטריון
                evaluated_criteria = criteria
                for key, value in customer.items():
                    evaluated_criteria = evaluated_criteria.replace(key, str(value))
                
                # בדיקה פשוטה (בייצור יהיה parser מתקדם יותר)
                if 'total_value > 500' in criteria and customer['total_value'] > 500:
                    filtered.append(customer)
                elif 'days_since_last_interaction < 14' in criteria and customer['days_since_last_interaction'] < 14:
                    filtered.append(customer)
                elif 'total_interactions > 10' in criteria and customer['total_interactions'] > 10:
                    filtered.append(customer)
                    
            except Exception as e:
                logger.warning(f"Error evaluating criteria for customer {customer['id']}: {e}")
                continue
        
        return filtered
    
    def _calculate_segment_avg_value(self, customers: List[Dict]) -> float:
        """חישוב ערך ממוצע לסיגמנט"""
        
        if not customers:
            return 0.0
        
        total_value = sum(customer['total_value'] for customer in customers)
        return round(total_value / len(customers), 2)
    
    def _calculate_segment_total_value(self, customers: List[Dict]) -> float:
        """חישוב ערך כולל לסיגמנט"""
        
        return sum(customer['total_value'] for customer in customers)
    
    def _generate_tactical_recommendations(self, business_id: int, segment_key: str) -> List[Dict[str, Any]]:
        """יצירת המלצות טקטיות ספציפיות"""
        
        tactical_recs = {
            'vip_customers': [
                {
                    'action': 'צור קשר אישי שבועי',
                    'priority': 'גבוה',
                    'timeline': 'מיידי',
                    'expected_result': 'שמירה על נאמנות'
                },
                {
                    'action': 'הצע שירותים בלעדיים',
                    'priority': 'גבוה',
                    'timeline': 'תוך שבוע',
                    'expected_result': 'הגדלת ערך לקוח'
                }
            ],
            'inactive_customers': [
                {
                    'action': 'שלח הודעת "התגעגענו" עם הנחה',
                    'priority': 'בינוני',
                    'timeline': 'תוך 3 ימים',
                    'expected_result': '15% חזרה ללקוחות'
                },
                {
                    'action': 'התקשר לבירור סיבת אי פעילות',
                    'priority': 'בינוני',
                    'timeline': 'תוך שבוע',
                    'expected_result': 'זיהוי בעיות ושיפור שירות'
                }
            ]
        }
        
        return tactical_recs.get(segment_key, [])
    
    def _create_implementation_timeline(self, segment_key: str) -> Dict[str, List[str]]:
        """יצירת לוח זמנים ליישום"""
        
        timelines = {
            'vip_customers': {
                'week_1': ['יצירת רשימת VIP', 'הגדרת יועץ אישי'],
                'week_2': ['התחלת קשר שבועי', 'הצעת שירותים בלעדיים'],
                'month_1': ['מעקב שביעות רצון', 'הערכת תוצאות']
            },
            'inactive_customers': {
                'day_1': ['זיהוי לקוחות לא פעילים'],
                'week_1': ['שליחת הודעות "התגעגענו"', 'מעקב תגובות'],
                'week_2': ['שיחות טלפון אישיות', 'הצעות מיוחדות'],
                'month_1': ['הערכת שיעור חזרה', 'שיפון אסטרטגיה']
            }
        }
        
        return timelines.get(segment_key, {})
    
    def _define_success_metrics(self, segment_key: str) -> Dict[str, str]:
        """הגדרת מטריקות הצלחה"""
        
        metrics = {
            'vip_customers': {
                'retention_rate': 'שמירה על 95% מהלקוחות',
                'value_increase': 'הגדלת ערך ממוצע ב-20%',
                'satisfaction_score': 'שביעות רצון מעל 9/10'
            },
            'inactive_customers': {
                'reactivation_rate': 'החזרת 15% מהלקוחות',
                'engagement_increase': 'הגדלת אינטראקציות ב-30%',
                'conversion_rate': 'המרה ל-5% תורים חדשים'
            }
        }
        
        return metrics.get(segment_key, {})
    
    def _generate_performance_recommendations(self, segments: Dict, roi_data: Dict) -> List[str]:
        """יצירת המלצות על בסיס ביצועים"""
        
        recommendations = []
        
        # המלצות על בסיס ROI
        if roi_data:
            best_roi_segment = max(roi_data.keys(), key=lambda k: roi_data[k]['roi_percentage'])
            worst_roi_segment = min(roi_data.keys(), key=lambda k: roi_data[k]['roi_percentage'])
            
            recommendations.extend([
                f"הגדל השקעה בסיגמנט '{self.segment_definitions[best_roi_segment]['name']}' (ROI גבוה)",
                f"בחן מחדש אסטרטגיה לסיגמנט '{self.segment_definitions[worst_roi_segment]['name']}' (ROI נמוך)"
            ])
        
        # המלצות על בסיס גודל סיגמנטים
        for segment_key, segment_data in segments.items():
            if segment_data['percentage'] > 40:
                recommendations.append(f"סיגמנט '{segment_data['name']}' גדול מדי - שקול חלוקה נוספת")
            elif segment_data['percentage'] < 5 and segment_data['count'] > 0:
                recommendations.append(f"סיגמנט '{segment_data['name']}' קטן - שקול מיזוג עם סיגמנט אחר")
        
        return recommendations


# יצירת אינסטנס global
customer_segmentation_service = CustomerSegmentationService()