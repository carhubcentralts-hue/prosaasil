"""
Hebrew Label Service - Converts codes/IDs to Hebrew display labels
Ensures all labels sent to LLM are in Hebrew as required by the system

This service:
1. Maps status codes to Hebrew labels from LeadStatus table
2. Maps appointment status codes to Hebrew labels from BusinessSettings
3. Provides fallback for missing labels with warnings
4. Formats custom fields with Hebrew labels
"""
import logging
from typing import Dict, Any, Optional, List
from server.db import db
from server.models_sql import LeadStatus, BusinessSettings

logger = logging.getLogger(__name__)


class HebrewLabelService:
    """Service for converting codes/IDs to Hebrew display labels"""
    
    def __init__(self, business_id: int):
        """
        Initialize service for a specific business
        
        Args:
            business_id: Business/tenant ID for multi-tenant scoping
        """
        self.business_id = business_id
        self._lead_status_cache = None
        self._appointment_status_cache = None
    
    def get_lead_status_label(self, status_code: str) -> Dict[str, Any]:
        """
        Get Hebrew label for lead status code
        
        Priority order:
        1. Query LeadStatus table for this business (primary source)
        2. If not found, use default English → Hebrew mapping
        3. If still not found, return fallback with WARNING
        
        Args:
            status_code: Status code/name (e.g., "new", "contacted", "active")
            
        Returns:
            Dict with status_id, status_code, and status_label_he
        """
        if not status_code:
            logger.warning(f"⚠️ [HebrewLabel] get_lead_status_label called with empty status_code")
            return {
                "status_id": None,
                "status_code": None,
                "status_label_he": "לא ידוע"
            }
        
        try:
            # Priority 1: Query LeadStatus table for this business
            lead_status = LeadStatus.query.filter_by(
                business_id=self.business_id,
                name=status_code
            ).first()
            
            if lead_status:
                return {
                    "status_id": lead_status.id,
                    "status_code": status_code,
                    "status_label_he": lead_status.label or status_code
                }
            
            # Priority 2: Use default English → Hebrew mapping
            default_mappings = {
                "new": "חדש",
                "attempting": "בניסיון קשר",
                "no_answer": "לא ענה",
                "contacted": "נוצר קשר",
                "interested": "מעוניין",
                "follow_up": "חזרה",
                "not_relevant": "לא רלוונטי",
                "qualified": "מוכשר",
                "won": "זכיה",
                "lost": "אובדן",
                "unqualified": "לא מוכשר",
                "active": "פעיל",
                "lead": "ליד",
                "customer": "לקוח"
            }
            
            if status_code in default_mappings:
                logger.info(f"ℹ️ [HebrewLabel] Using default mapping for status '{status_code}' → '{default_mappings[status_code]}'")
                return {
                    "status_id": None,
                    "status_code": status_code,
                    "status_label_he": default_mappings[status_code]
                }
            
            # Priority 3: Fallback with WARNING
            logger.warning(f"⚠️ [HebrewLabel] Lead status '{status_code}' not found in LeadStatus table or defaults for business {self.business_id}")
            return {
                "status_id": None,
                "status_code": status_code,
                "status_label_he": f"לא ידוע (status={status_code})"
            }
        
        except Exception as e:
            logger.error(f"❌ [HebrewLabel] Error getting lead status label: {e}")
            return {
                "status_id": None,
                "status_code": status_code,
                "status_label_he": f"שגיאה (status={status_code})"
            }
    
    def get_appointment_status_label(self, status_code: str) -> Dict[str, Any]:
        """
        Get Hebrew label for appointment/calendar status code
        
        Priority order:
        1. Query BusinessSettings.appointment_statuses_json (primary source)
        2. If not found, use default English → Hebrew mapping
        3. If still not found, return fallback with WARNING
        
        Args:
            status_code: Status code (e.g., "scheduled", "confirmed", "completed")
            
        Returns:
            Dict with calendar_status_id, calendar_status_code, and calendar_status_label_he
        """
        if not status_code:
            logger.warning(f"⚠️ [HebrewLabel] get_appointment_status_label called with empty status_code")
            return {
                "calendar_status_id": None,
                "calendar_status_code": None,
                "calendar_status_label_he": "לא ידוע"
            }
        
        try:
            # Priority 1: Query BusinessSettings for appointment_statuses_json
            settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
            
            if settings and settings.appointment_statuses_json:
                # appointment_statuses_json format: [{"key": "scheduled", "label": "נקבע", "color": "blue"}, ...]
                statuses = settings.appointment_statuses_json
                
                if isinstance(statuses, list):
                    for status_def in statuses:
                        if isinstance(status_def, dict) and status_def.get('key') == status_code:
                            return {
                                "calendar_status_id": status_def.get('id'),
                                "calendar_status_code": status_code,
                                "calendar_status_label_he": status_def.get('label') or status_code
                            }
            
            # Priority 2: Use default English → Hebrew mappings
            default_mappings = {
                "scheduled": "נקבע",
                "confirmed": "מאושר/ת",
                "completed": "הושלם",
                "cancelled": "בוטל",
                "canceled": "בוטל",  # Alternative spelling
                "pending": "ממתין",
                "rescheduled": "נדחה",
                "no_show": "לא הגיע",
                "in_progress": "בתהליך"
            }
            
            if status_code in default_mappings:
                logger.info(f"ℹ️ [HebrewLabel] Using default mapping for appointment status '{status_code}' → '{default_mappings[status_code]}'")
                return {
                    "calendar_status_id": None,
                    "calendar_status_code": status_code,
                    "calendar_status_label_he": default_mappings[status_code]
                }
            
            # Priority 3: Fallback with WARNING
            logger.warning(f"⚠️ [HebrewLabel] Appointment status '{status_code}' not found in BusinessSettings or defaults for business {self.business_id}")
            
            return {
                "calendar_status_id": None,
                "calendar_status_code": status_code,
                "calendar_status_label_he": f"לא ידוע (status={status_code})"
            }
        
        except Exception as e:
            logger.error(f"❌ [HebrewLabel] Error getting appointment status label: {e}")
            return {
                "calendar_status_id": None,
                "calendar_status_code": status_code,
                "calendar_status_label_he": f"שגיאה (status={status_code})"
            }
    
    def format_custom_fields(self, custom_fields: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Format custom fields with labels (⚠️ TEMPORARY ENGLISH FALLBACK)
        
        IMPORTANT: This function currently returns English labels, NOT Hebrew.
        Hebrew labels require a CustomFieldDefinition table or custom_fields_schema.
        
        Args:
            custom_fields: Dict of custom field key-value pairs
            
        Returns:
            List of dicts with field_key, field_label (English fallback), and value
        
        TODO: Implement proper Hebrew labels from DB sources:
            1. BusinessSettings.custom_fields_schema
            2. CustomFieldDefinition table  
            3. Hard-coded mapping for common fields
        """
        if not custom_fields:
            return []
        
        try:
            formatted_fields = []
            
            for field_key, field_value in custom_fields.items():
                # TODO: Implement proper Hebrew labels from DB
                # Potential sources:
                # 1. BusinessSettings.custom_fields_schema: {"treatment_duration": {"label_he": "משך טיפול"}}
                # 2. CustomFieldDefinition table with business_id, field_key, label_he
                # 3. Hard-coded mapping for common fields
                
                # Temporary: Use English title-case as fallback
                field_label = field_key.replace('_', ' ').title()
                logger.warning(f"⚠️ [HebrewLabel] Using English fallback label for custom field '{field_key}' - implement CustomFieldDefinition for Hebrew")
                
                formatted_fields.append({
                    "field_key": field_key,
                    "field_label": field_label,  # Currently English fallback - NOT Hebrew
                    "value": field_value
                })
            
            return formatted_fields
        
        except Exception as e:
            logger.error(f"❌ [HebrewLabel] Error formatting custom fields: {e}")
            return []
    
    def get_all_lead_statuses(self) -> List[Dict[str, Any]]:
        """
        Get all lead statuses for this business with Hebrew labels
        
        Returns:
            List of dicts with status_id, status_code, status_label_he
        """
        try:
            statuses = LeadStatus.query.filter_by(
                business_id=self.business_id
            ).order_by(LeadStatus.order_index).all()
            
            return [
                {
                    "status_id": status.id,
                    "status_code": status.name,
                    "status_label_he": status.label
                }
                for status in statuses
            ]
        
        except Exception as e:
            logger.error(f"❌ [HebrewLabel] Error getting all lead statuses: {e}")
            return []
    
    def get_all_appointment_statuses(self) -> List[Dict[str, Any]]:
        """
        Get all appointment statuses for this business with Hebrew labels
        
        Returns:
            List of dicts with calendar_status_id, calendar_status_code, calendar_status_label_he
        """
        try:
            settings = BusinessSettings.query.filter_by(tenant_id=self.business_id).first()
            
            if settings and settings.appointment_statuses_json:
                statuses = settings.appointment_statuses_json
                
                if isinstance(statuses, list):
                    return [
                        {
                            "calendar_status_id": status.get('id'),
                            "calendar_status_code": status.get('key'),
                            "calendar_status_label_he": status.get('label')
                        }
                        for status in statuses
                        if isinstance(status, dict) and status.get('key')
                    ]
            
            # Return empty if no custom statuses defined
            return []
        
        except Exception as e:
            logger.error(f"❌ [HebrewLabel] Error getting all appointment statuses: {e}")
            return []


def get_hebrew_label_service(business_id: int) -> HebrewLabelService:
    """
    Factory function to get HebrewLabelService instance
    
    Args:
        business_id: Business/tenant ID
        
    Returns:
        HebrewLabelService instance
    """
    return HebrewLabelService(business_id)
