"""
Task 9: Data Validation and Testing Service
שירות וולידציה ובדיקות מידע מתקדם
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import re
from app import db
from models import Business, CRMCustomer, CallLog, ConversationTurn

logger = logging.getLogger(__name__)

class DataValidationService:
    """Task 9: Comprehensive data validation service"""
    
    @staticmethod
    def validate_customer_data(customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Task 9: Validate customer data integrity"""
        errors = []
        warnings = []
        
        try:
            # Phone number validation
            phone = customer_data.get('phone', '')
            if not phone:
                errors.append('מספר טלפון חסר')
            elif not re.match(r'^\+972[1-9]\d{8}$', phone):
                errors.append('פורמט מספר טלפון לא תקין - נדרש +972XXXXXXXXX')
            
            # Name validation
            name = customer_data.get('name', '')
            if not name or len(name.strip()) < 2:
                errors.append('שם חייב להכיל לפחות 2 תווים')
            
            # Hebrew text validation
            if name:
                hebrew_chars = len(re.findall(r'[\u0590-\u05FF]', name))
                total_chars = len([c for c in name if c.isalpha()])
                if total_chars > 0 and hebrew_chars / total_chars < 0.3:
                    warnings.append('השם מכיל מעט תווים עבריים')
            
            # Business ID validation
            business_id = customer_data.get('business_id')
            if not business_id:
                errors.append('מזהה עסק חסר')
            else:
                business = Business.query.get(business_id)
                if not business:
                    errors.append(f'עסק עם מזהה {business_id} לא נמצא')
            
            # Source validation
            source = customer_data.get('source', '')
            valid_sources = ['call', 'whatsapp', 'manual', 'website', 'payment_link']
            if source not in valid_sources:
                warnings.append(f'מקור לא מוכר: {source}')
            
            validation_result = {
                'is_valid': len(errors) == 0,
                'errors': errors,
                'warnings': warnings,
                'validated_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"📊 Customer data validation: {len(errors)} errors, {len(warnings)} warnings")
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating customer data: {e}")
            return {
                'is_valid': False,
                'errors': [f'שגיאה בוולידציה: {str(e)}'],
                'warnings': [],
                'validated_at': datetime.utcnow().isoformat()
            }
    
    @staticmethod 
    def validate_call_log_integrity() -> Dict[str, Any]:
        """Task 9: Validate call log data integrity"""
        try:
            # Check for orphaned conversation turns
            orphaned_turns = db.session.query(ConversationTurn).filter(
                ~ConversationTurn.call_log_id.in_(
                    db.session.query(CallLog.id)
                )
            ).count()
            
            # Check for calls without turns
            calls_without_turns = db.session.query(CallLog).filter(
                ~CallLog.id.in_(
                    db.session.query(ConversationTurn.call_log_id).distinct()
                )
            ).count()
            
            # Check for invalid phone numbers in call logs
            invalid_phone_calls = db.session.query(CallLog).filter(
                ~CallLog.from_number.op('~')(r'^\+972[1-9]\d{8}$')
            ).count()
            
            # Check for missing business associations
            calls_without_business = db.session.query(CallLog).filter(
                CallLog.business_id.is_(None)
            ).count()
            
            # Recent call activity validation
            recent_calls = db.session.query(CallLog).filter(
                CallLog.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            
            integrity_report = {
                'orphaned_conversation_turns': orphaned_turns,
                'calls_without_turns': calls_without_turns,
                'invalid_phone_numbers': invalid_phone_calls,
                'calls_without_business': calls_without_business,
                'recent_24h_calls': recent_calls,
                'overall_health': 'good' if (orphaned_turns + calls_without_business + invalid_phone_calls) == 0 else 'needs_attention',
                'validated_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"📊 Call log integrity check: {integrity_report['overall_health']}")
            return {
                'success': True,
                'integrity_report': integrity_report
            }
            
        except Exception as e:
            logger.error(f"Error validating call log integrity: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def run_system_health_check() -> Dict[str, Any]:
        """Task 9: Comprehensive system health check"""
        try:
            health_checks = {}
            
            # Database connectivity
            try:
                db.session.execute('SELECT 1')
                health_checks['database'] = {'status': 'healthy', 'message': 'חיבור תקין'}
            except Exception as e:
                health_checks['database'] = {'status': 'error', 'message': f'שגיאת חיבור: {str(e)}'}
            
            # Business configuration check
            try:
                businesses = Business.query.count()
                active_businesses = Business.query.filter_by(is_active=True).count()
                health_checks['businesses'] = {
                    'status': 'healthy' if businesses > 0 else 'warning',
                    'total': businesses,
                    'active': active_businesses,
                    'message': f'{active_businesses} עסקים פעילים מתוך {businesses}'
                }
            except Exception as e:
                health_checks['businesses'] = {'status': 'error', 'message': str(e)}
            
            # Customer data health
            try:
                total_customers = CRMCustomer.query.count()
                active_customers = CRMCustomer.query.filter_by(status='active').count()
                health_checks['customers'] = {
                    'status': 'healthy',
                    'total': total_customers,
                    'active': active_customers,
                    'message': f'{active_customers} לקוחות פעילים מתוך {total_customers}'
                }
            except Exception as e:
                health_checks['customers'] = {'status': 'error', 'message': str(e)}
            
            # Call system health
            try:
                total_calls = CallLog.query.count()
                recent_calls = CallLog.query.filter(
                    CallLog.created_at >= datetime.utcnow() - timedelta(hours=24)
                ).count()
                health_checks['calls'] = {
                    'status': 'healthy',
                    'total': total_calls,
                    'recent_24h': recent_calls,
                    'message': f'{recent_calls} שיחות ב-24 השעות האחרונות'
                }
            except Exception as e:
                health_checks['calls'] = {'status': 'error', 'message': str(e)}
            
            # Overall system status
            error_count = sum(1 for check in health_checks.values() if check['status'] == 'error')
            warning_count = sum(1 for check in health_checks.values() if check['status'] == 'warning')
            
            overall_status = 'healthy'
            if error_count > 0:
                overall_status = 'critical'
            elif warning_count > 0:
                overall_status = 'warning'
            
            system_health = {
                'overall_status': overall_status,
                'checks': health_checks,
                'summary': {
                    'healthy': sum(1 for check in health_checks.values() if check['status'] == 'healthy'),
                    'warnings': warning_count,
                    'errors': error_count
                },
                'checked_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"🏥 System health check: {overall_status} ({len(health_checks)} checks)")
            return {
                'success': True,
                'health_status': system_health
            }
            
        except Exception as e:
            logger.error(f"Error running system health check: {e}")
            return {
                'success': False,
                'error': str(e)
            }

# Global validation service instance
validation_service = DataValidationService()

# Task 9: Wrapper functions for easy import
def validate_customer(customer_data: Dict[str, Any]) -> Dict[str, Any]:
    """Task 9: Validate customer data wrapper"""
    return validation_service.validate_customer_data(customer_data)

def check_call_log_integrity() -> Dict[str, Any]:
    """Task 9: Check call log integrity wrapper"""
    return validation_service.validate_call_log_integrity()

def run_health_check() -> Dict[str, Any]:
    """Task 9: Run system health check wrapper"""
    return validation_service.run_system_health_check()