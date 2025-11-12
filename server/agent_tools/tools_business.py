"""
Business information tools for Agent SDK
Allows agents to fetch business contact details, hours, and location
"""

import logging
from typing import Optional
from pydantic import BaseModel, Field
from agents import function_tool

logger = logging.getLogger(__name__)


class BusinessInfoOutput(BaseModel):
    """Business information output"""
    ok: bool
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    hours: Optional[str] = None
    error: Optional[str] = None
    message: Optional[str] = None


def _business_get_info_impl(business_id: Optional[int] = None) -> BusinessInfoOutput:
    """
    Get business contact information and details
    
    Returns business address, phone number, email, and working hours.
    Use this when customer asks for location, address, contact details, or hours.
    
    Args:
        business_id: Business ID (optional - auto-detected from context if not provided)
        
    Returns:
        BusinessInfoOutput with business details
    """
    try:
        from server.models_sql import db, Business, BusinessSettings
        from flask import g
        
        # 🔥 AUTO-DETECT business_id from context if not provided
        actual_business_id = business_id
        if not actual_business_id and hasattr(g, 'agent_context'):
            actual_business_id = g.agent_context.get('business_id')
            logger.info(f"✅ business_get_info: Auto-detected business_id={actual_business_id} from context")
        
        if not actual_business_id:
            logger.error("❌ business_get_info: No business_id provided or in context")
            return BusinessInfoOutput(
                ok=False,
                error="no_business_id",
                message="לא ניתן לזהות את העסק"
            )
        
        # Fetch business info
        business = Business.query.get(actual_business_id)
        settings = BusinessSettings.query.get(actual_business_id)
        
        if not business:
            logger.error(f"❌ business_get_info: Business {actual_business_id} not found")
            return BusinessInfoOutput(
                ok=False,
                error="business_not_found",
                message="פרטי העסק לא נמצאו במערכת"
            )
        
        # Build response with all available info
        result = BusinessInfoOutput(
            ok=True,
            name=business.name or "העסק",
            address=settings.address if settings and settings.address else "לא צויין",
            phone=settings.phone_number if settings and settings.phone_number else "לא צויין",
            email=settings.email if settings and settings.email else "לא צויין",
            hours=settings.working_hours if settings and settings.working_hours else "09:00-22:00"
        )
        
        logger.info(f"✅ business_get_info: {result.model_dump()}")
        return result
        
    except Exception as e:
        error_msg = str(e)[:120]
        logger.error(f"❌ business_get_info error: {error_msg}")
        import traceback
        traceback.print_exc()
        
        return BusinessInfoOutput(
            ok=False,
            error="fetch_error",
            message=f"לא ניתן לטעון פרטי עסק: {error_msg}"
        )


# 🔥 Decorated version for agents without business_id injection
@function_tool
def business_get_info(business_id: Optional[int] = None) -> BusinessInfoOutput:
    """
    Get business contact information and details
    
    Returns business address, phone number, email, and working hours.
    Use this when customer asks for location, address, contact details, or hours.
    
    Args:
        business_id: Business ID (optional - auto-detected from context if not provided)
        
    Returns:
        BusinessInfoOutput with business details
    """
    return _business_get_info_impl(business_id)
