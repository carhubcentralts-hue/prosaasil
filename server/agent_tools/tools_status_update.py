"""
Unified Status Update Tool for AI Agents
Single tool for updating lead status across all channels (WhatsApp, Calls)

This tool uses the UnifiedStatusService as the single source of truth
"""
from agents import function_tool
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


# ================================================================================
# TOOL INPUT/OUTPUT SCHEMAS
# ================================================================================

class UpdateLeadStatusInput(BaseModel):
    """Input for updating lead status"""
    business_id: int = Field(..., description="Business ID (tenant_id) - REQUIRED for multi-tenant security", ge=1)
    lead_id: int = Field(..., description="Lead ID to update status for", ge=1)
    status: str = Field(..., description="New status value (e.g., 'appointment_scheduled', 'not_relevant', 'callback_requested')")
    reason: str = Field(..., description="Clear reason for status change - what happened in the conversation that triggered this update")
    confidence: Optional[float] = Field(
        None, 
        description="Confidence level for this status change (0.0 to 1.0). Use 1.0 for explicit statements, 0.7-0.9 for implied actions",
        ge=0.0,
        le=1.0
    )


class UpdateLeadStatusOutput(BaseModel):
    """Output for update_lead_status"""
    success: bool
    message: str
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    skipped: bool = False


# ================================================================================
# TOOL IMPLEMENTATION
# ================================================================================

@function_tool
def update_lead_status(input: UpdateLeadStatusInput) -> UpdateLeadStatusOutput:
    """
    Update lead status with audit logging and validation.
    
    ⚠️ IMPORTANT RULES:
    1. Only update status when there's a CLEAR signal from the conversation
    2. Do NOT guess or assume - must have explicit confirmation
    3. Always provide a specific reason explaining what triggered the update
    
    Common status values:
    - appointment_scheduled: Lead scheduled an appointment (confirmed date/time)
    - callback_requested: Lead asked to be called back later
    - not_relevant: Lead explicitly said not interested / wrong number / not relevant
    - interested: Lead expressed clear interest in the service
    - qualified: Lead meets criteria and ready to move forward
    - closed_won: Deal was confirmed as closed/won
    
    Examples of VALID updates:
    ✅ "נקבעה פגישה ליום ראשון" → status=appointment_scheduled, reason="לקוח נקבע פגישה ליום ראשון בשעה 10:00"
    ✅ "תתקשרו אליי מחר" → status=callback_requested, reason="לקוח ביקש שנחזור אליו מחר"
    ✅ "טעיתם במספר, אני לא מעוניין" → status=not_relevant, reason="לקוח אמר שטעינו במספר ולא מעוניין"
    
    Examples of INVALID updates (don't do these):
    ❌ Updating to "interested" just because lead answered the phone
    ❌ Updating to "qualified" without explicit confirmation from lead
    ❌ Guessing status based on tone or incomplete information
    
    This tool:
    - Uses single source of truth (UnifiedStatusService)
    - Creates audit log with who/when/why/channel
    - Validates status progression (no downgrades)
    - Checks status family equivalence (avoids duplicate updates)
    - Works for both WhatsApp and Calls
    
    Security: Query is scoped to business_id (multi-tenant safe).
    """
    try:
        from server.services.unified_status_service import update_lead_status_unified
        from flask import g
        
        # Detect channel from context
        channel = "unknown"
        if hasattr(g, 'agent_channel'):
            channel = g.agent_channel
        elif hasattr(g, 'whatsapp_conversation'):
            channel = "whatsapp"
        elif hasattr(g, 'call_sid'):
            channel = "call"
        
        # Call unified service
        result = update_lead_status_unified(
            business_id=input.business_id,
            lead_id=input.lead_id,
            new_status=input.status,
            reason=input.reason,
            confidence=input.confidence,
            channel=channel,
            metadata={
                'tool': 'update_lead_status',
                'ai_generated': True
            }
        )
        
        return UpdateLeadStatusOutput(
            success=result.success,
            message=result.message,
            old_status=result.old_status,
            new_status=result.new_status,
            skipped=result.skipped
        )
        
    except Exception as e:
        logger.error(f"Error in update_lead_status tool: {e}", exc_info=True)
        return UpdateLeadStatusOutput(
            success=False,
            message=f"Error updating status: {str(e)}"
        )
