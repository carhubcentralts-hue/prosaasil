"""
Consolidated Model Definitions - Single Source of Truth
All SQLAlchemy models imported from models_sql.py for consistency
"""

# Import all models from the authoritative source
from server.models_sql import (
    db,
    User,
    Business,
    Customer, 
    CallLog,
    WhatsAppMessage,
    Lead,
    LeadReminder,
    LeadStatus,
    LeadActivity,
    LeadMergeCandidate,
    Deal,
    Payment,
    PaymentGateway,
    Invoice,
    Contract,
    Appointment,
    BusinessSettings,
    PromptRevisions
)

# Re-export everything for backward compatibility
__all__ = [
    'db',
    'User', 'Business', 'Customer', 'CallLog', 'WhatsAppMessage',
    'Lead', 'LeadReminder', 'LeadStatus', 'LeadActivity', 'LeadMergeCandidate',
    'Deal', 'Payment', 'PaymentGateway', 'Invoice', 'Contract', 'Appointment',
    'BusinessSettings', 'PromptRevisions'
]