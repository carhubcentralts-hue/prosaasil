"""
Advanced Customer Service - שירות לקוחות מתקדם
מערכת ניהול פרופילי לקוחות מתקדמת עם הערכת סיכונים וסיגמנטציה אוטומטית
"""

import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_
from app import db
from models import CRMCustomer, Business, CallLog, ConversationTurn, AppointmentRequest

logger = logging.getLogger(__name__)

class AdvancedCustomerService:
    """שירות לקוחות מתקדם עם ניתוח התנהגות ופרופילינג"""
    
    def __init__(self):
        self.risk_scoring_weights = {
            'call_frequency': 0.25,
            'payment_history': 0.30,
            'complaint_count': 0.20,
            'engagement_level': 0.15,
            'response_time': 0.10
        }
    
    def create_customer_profile(self, customer_id: int) -> Dict[str, Any]:
        """יצירת פרופיל מקיף של לקוח"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return {'success': False, 'error': 'לקוח לא נמצא'}
            
            # נתוני שיחות
            call_stats = self._analyze_call_patterns(customer_id)
            
            # ניתוח התנהגות
            behavior_analysis = self._analyze_customer_behavior(customer_id)
            
            # הערכת סיכון
            risk_score = self._calculate_risk_score(customer_id)
            
            # סיגמנטציה
            segment = self._determine_customer_segment(customer, call_stats, behavior_analysis)
            
            # המלצות פעולה
            recommendations = self._generate_action_recommendations(customer, risk_score, segment)
            
            profile = {
                'customer_id': customer_id,
                'basic_info': {
                    'name': customer.full_name,
                    'phone': customer.phone,
                    'email': getattr(customer, 'email', ''),
                    'status': customer.status,
                    'created_at': customer.created_at.strftime('%d/%m/%Y'),
                    'last_contact': self._get_last_contact_date(customer_id)
                },
                'call_statistics': call_stats,
                'behavior_analysis': behavior_analysis,
                'risk_assessment': {
                    'score': risk_score,
                    'level': self._get_risk_level(risk_score),
                    'factors': self._identify_risk_factors(customer_id)
                },
                'segmentation': segment,
                'recommendations': recommendations,
                'updated_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Customer profile created for {customer_id}: segment={segment['category']}, risk={risk_score}")
            
            return {
                'success': True,
                'profile': profile
            }
            
        except Exception as e:
            logger.error(f"Error creating customer profile: {e}")
            return {'success': False, 'error': str(e)}
    
    def _analyze_call_patterns(self, customer_id: int) -> Dict[str, Any]:
        """ניתוח דפוסי שיחות של לקוח"""
        
        try:
            # שיחות ב-30 הימים האחרונים
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            calls = CallLog.query.filter(
                and_(
                    CallLog.customer_id == customer_id,
                    CallLog.call_time >= thirty_days_ago
                )
            ).all()
            
            if not calls:
                return {
                    'total_calls': 0,
                    'avg_duration': 0,
                    'call_frequency': 0,
                    'peak_hours': [],
                    'call_success_rate': 0
                }
            
            # חישובי בסיס
            total_calls = len(calls)
            durations = [call.duration for call in calls if call.duration]
            avg_duration = sum(durations) / len(durations) if durations else 0
            
            # תדירות שיחות (שיחות לשבוע)
            call_frequency = total_calls / 4.3  # חישוב ממוצע לשבוע
            
            # שעות שיא
            hour_counts = {}
            for call in calls:
                hour = call.call_time.hour
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
            
            peak_hours = sorted(hour_counts.items(), key=lambda x: x[1], reverse=True)[:3]
            peak_hours = [f"{hour:02d}:00" for hour, _ in peak_hours]
            
            # שיחות מוצלחות (שהסתיימו תקין)
            successful_calls = [call for call in calls if call.status == 'completed']
            success_rate = (len(successful_calls) / total_calls * 100) if total_calls > 0 else 0
            
            return {
                'total_calls': total_calls,
                'avg_duration': round(avg_duration, 2),
                'call_frequency': round(call_frequency, 2),
                'peak_hours': peak_hours,
                'call_success_rate': round(success_rate, 2)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing call patterns: {e}")
            return {'total_calls': 0, 'avg_duration': 0, 'call_frequency': 0}
    
    def _analyze_customer_behavior(self, customer_id: int) -> Dict[str, Any]:
        """ניתוח התנהגות לקוח"""
        
        try:
            conversations = ConversationTurn.query.join(CallLog).filter(
                CallLog.customer_id == customer_id
            ).all()
            
            if not conversations:
                return {
                    'engagement_score': 0,
                    'sentiment_trend': 'neutral',
                    'communication_style': 'unknown',
                    'response_time': 0
                }
            
            # ניתוח טקסט שיחות
            positive_keywords = ['תודה', 'מעולה', 'נהדר', 'שמח', 'מרוצה']
            negative_keywords = ['בעיה', 'כועס', 'לא מרוצה', 'תלונה', 'רע']
            
            positive_count = 0
            negative_count = 0
            total_words = 0
            
            for conv in conversations:
                if conv.message:
                    words = conv.message.lower().split()
                    total_words += len(words)
                    
                    for word in words:
                        if any(pos in word for pos in positive_keywords):
                            positive_count += 1
                        if any(neg in word for neg in negative_keywords):
                            negative_count += 1
            
            # חישוב מדד מעורבות
            engagement_score = min(100, (total_words / len(conversations)) * 10) if conversations else 0
            
            # מגמת סנטימנט
            if positive_count > negative_count * 1.5:
                sentiment = 'positive'
            elif negative_count > positive_count * 1.5:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'
            
            # סגנון תקשורת
            avg_message_length = total_words / len(conversations) if conversations else 0
            if avg_message_length > 20:
                communication_style = 'detailed'
            elif avg_message_length > 10:
                communication_style = 'moderate'
            else:
                communication_style = 'brief'
            
            return {
                'engagement_score': round(engagement_score, 2),
                'sentiment_trend': sentiment,
                'communication_style': communication_style,
                'total_interactions': len(conversations),
                'avg_message_length': round(avg_message_length, 2)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing customer behavior: {e}")
            return {'engagement_score': 0, 'sentiment_trend': 'neutral'}
    
    def _calculate_risk_score(self, customer_id: int) -> float:
        """חישוב ציון סיכון לקוח (0-100)"""
        
        try:
            customer = CRMCustomer.query.get(customer_id)
            if not customer:
                return 50.0  # ציון ברירת מחדל
            
            risk_factors = {
                'call_frequency': 0,
                'payment_history': 0,
                'complaint_count': 0,
                'engagement_level': 0,
                'response_time': 0
            }
            
            # תדירות שיחות גבוהה = סיכון גבוה יותר
            call_stats = self._analyze_call_patterns(customer_id)
            if call_stats['call_frequency'] > 3:  # יותר מ-3 שיחות בשבוע
                risk_factors['call_frequency'] = 70
            elif call_stats['call_frequency'] > 1:
                risk_factors['call_frequency'] = 40
            else:
                risk_factors['call_frequency'] = 20
            
            # היסטוריית תשלומים (אם קיימת)
            # כאן ניתן להוסיף לוגיקה לבדיקת תשלומים
            risk_factors['payment_history'] = 30  # ברירת מחדל
            
            # ספירת תלונות
            complaint_keywords = ['תלונה', 'בעיה', 'כועס', 'לא מרוצה']
            complaint_count = 0
            
            conversations = ConversationTurn.query.join(CallLog).filter(
                CallLog.customer_id == customer_id
            ).all()
            
            for conv in conversations:
                if conv.message:
                    message_lower = conv.message.lower()
                    if any(keyword in message_lower for keyword in complaint_keywords):
                        complaint_count += 1
            
            if complaint_count > 5:
                risk_factors['complaint_count'] = 80
            elif complaint_count > 2:
                risk_factors['complaint_count'] = 50
            else:
                risk_factors['complaint_count'] = 20
            
            # רמת מעורבות
            behavior = self._analyze_customer_behavior(customer_id)
            engagement = behavior.get('engagement_score', 0)
            
            if engagement < 20:
                risk_factors['engagement_level'] = 60  # מעורבות נמוכה = סיכון
            elif engagement > 80:
                risk_factors['engagement_level'] = 20  # מעורבות גבוהה = סיכון נמוך
            else:
                risk_factors['engagement_level'] = 40
            
            # זמן תגובה
            risk_factors['response_time'] = 30  # ברירת מחדל
            
            # חישוב ציון מורכב
            total_score = sum(
                risk_factors[factor] * self.risk_scoring_weights[factor]
                for factor in risk_factors
            )
            
            return round(total_score, 2)
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}")
            return 50.0
    
    def _get_risk_level(self, risk_score: float) -> str:
        """קביעת רמת סיכון לפי ציון"""
        
        if risk_score >= 70:
            return 'high'
        elif risk_score >= 40:
            return 'medium'
        else:
            return 'low'
    
    def _determine_customer_segment(self, customer: CRMCustomer, call_stats: Dict, behavior: Dict) -> Dict[str, Any]:
        """קביעת סגמנט לקוח"""
        
        try:
            # לוגיקת סיגמנטציה
            call_frequency = call_stats.get('call_frequency', 0)
            engagement = behavior.get('engagement_score', 0)
            sentiment = behavior.get('sentiment_trend', 'neutral')
            
            # קטגוריות סגמנטים
            if call_frequency > 2 and engagement > 60 and sentiment == 'positive':
                category = 'VIP_Active'
                description = 'לקוח VIP פעיל ומרוצה'
                priority = 'high'
            elif call_frequency > 1 and sentiment == 'negative':
                category = 'At_Risk'
                description = 'לקוח בסיכון - דורש טיפול מיוחד'
                priority = 'urgent'
            elif engagement > 70:
                category = 'Engaged'
                description = 'לקוח מעורב ואקטיבי'
                priority = 'medium'
            elif call_frequency < 0.5:
                category = 'Inactive'
                description = 'לקוח לא פעיל - זקוק לחידוש'
                priority = 'low'
            else:
                category = 'Regular'
                description = 'לקוח רגיל'
                priority = 'medium'
            
            return {
                'category': category,
                'description': description,
                'priority': priority,
                'updated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error determining customer segment: {e}")
            return {'category': 'Regular', 'description': 'לקוח רגיל', 'priority': 'medium'}
    
    def _generate_action_recommendations(self, customer: CRMCustomer, risk_score: float, segment: Dict) -> List[Dict[str, Any]]:
        """יצירת המלצות פעולה"""
        
        recommendations = []
        
        try:
            # המלצות לפי רמת סיכון
            if risk_score >= 70:
                recommendations.extend([
                    {
                        'type': 'urgent_contact',
                        'title': 'יצירת קשר דחופה',
                        'description': f'ליד בסיכון גבוה - יש ליצור קשר תוך 2 שעות',
                        'priority': 'urgent',
                        'estimated_time': '30 דקות'
                    },
                    {
                        'type': 'manager_review',
                        'title': 'סקירת מנהל',
                        'description': 'העבר למנהל לטיפול מיוחד',
                        'priority': 'high',
                        'estimated_time': '15 דקות'
                    }
                ])
            
            # המלצות לפי סגמנט
            segment_category = segment.get('category', 'Regular')
            
            if segment_category == 'VIP_Active':
                recommendations.append({
                    'type': 'vip_treatment',
                    'title': 'יחס VIP',
                    'description': 'לקוח VIP - תן עדיפות בכל פניה',
                    'priority': 'high',
                    'estimated_time': '10 דקות'
                })
            elif segment_category == 'At_Risk':
                recommendations.append({
                    'type': 'retention_campaign',
                    'title': 'מסע שימור',
                    'description': 'לקוח בסיכון - הפעל מסע שימור',
                    'priority': 'urgent',
                    'estimated_time': '45 דקות'
                })
            elif segment_category == 'Inactive':
                recommendations.append({
                    'type': 'reactivation',
                    'title': 'הפעלה מחדש',
                    'description': 'לקוח לא פעיל - שלח הצעה מיוחדת',
                    'priority': 'medium',
                    'estimated_time': '20 דקות'
                })
            
            # המלצות כלליות
            last_contact = self._get_last_contact_date(customer.id)
            if last_contact and (datetime.utcnow() - last_contact).days > 30:
                recommendations.append({
                    'type': 'follow_up',
                    'title': 'מעקב תקופתי',
                    'description': 'לא היה קשר מעל 30 יום - יש ליצור קשר',
                    'priority': 'medium',
                    'estimated_time': '15 דקות'
                })
            
            return recommendations
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            return []
    
    def _get_last_contact_date(self, customer_id: int) -> Optional[datetime]:
        """קבלת תאריך הקשר האחרון"""
        
        try:
            last_call = CallLog.query.filter_by(customer_id=customer_id).order_by(
                CallLog.call_time.desc()
            ).first()
            
            return last_call.call_time if last_call else None
            
        except Exception as e:
            logger.error(f"Error getting last contact date: {e}")
            return None
    
    def _identify_risk_factors(self, customer_id: int) -> List[str]:
        """זיהוי גורמי סיכון ספציפיים"""
        
        risk_factors = []
        
        try:
            # בדיקת תדירות שיחות גבוהה
            call_stats = self._analyze_call_patterns(customer_id)
            if call_stats.get('call_frequency', 0) > 3:
                risk_factors.append('תדירות שיחות גבוהה')
            
            # בדיקת סנטימנט שלילי
            behavior = self._analyze_customer_behavior(customer_id)
            if behavior.get('sentiment_trend') == 'negative':
                risk_factors.append('סנטימנט שלילי')
            
            # בדיקת מעורבות נמוכה
            if behavior.get('engagement_score', 0) < 20:
                risk_factors.append('מעורבות נמוכה')
            
            # בדיקת שיחות לא מוצלחות
            if call_stats.get('call_success_rate', 100) < 70:
                risk_factors.append('שיעור שיחות לא מוצלחות גבוה')
            
            return risk_factors
            
        except Exception as e:
            logger.error(f"Error identifying risk factors: {e}")
            return []


# יצירת אינסטנס global
advanced_customer_service = AdvancedCustomerService()