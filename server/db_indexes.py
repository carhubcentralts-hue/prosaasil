"""
Database Indexes Registry - Single Source of Truth
===================================================

This file is the ONLY place where performance-only indexes should be defined.

❌ DO NOT add CREATE INDEX statements to migration files
✅ All performance indexes MUST be added here

Index Structure:
    - name: Unique identifier for the index
    - sql: The CREATE INDEX statement (uses CONCURRENTLY IF NOT EXISTS)
    - critical: Whether this index is critical for basic functionality
    - table: Table name (for reference)
    - description: What the index is for (for documentation)

Guidelines:
    1. Always use "CREATE INDEX CONCURRENTLY IF NOT EXISTS"
    2. Set critical=True only for indexes required for basic app functionality
    3. Set critical=False for performance-only indexes (most indexes)
    4. Add clear descriptions for future maintainability
    5. Use partial indexes (WHERE clauses) when appropriate to reduce size
"""

# ============================================================================
# LEADS / CRM DOMAIN
# ============================================================================

# ============================================================================
# LEADS / CRM DOMAIN
# Core lead management and customer relationship indexes
# ============================================================================
INDEX_DEFS_LEADS_CRM = [
    {
        "name": "idx_leads_tenant",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_tenant ON leads(tenant_id)",
        "critical": False,
        "description": "Index on leads for leads tenant"
    },
    {
        "name": "idx_leads_status",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_status ON leads(status)",
        "critical": False,
        "description": "Index on leads for leads status"
    },
    {
        "name": "idx_leads_source",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_source ON leads(source)",
        "critical": False,
        "description": "Index on leads for leads source"
    },
    {
        "name": "idx_leads_phone",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_phone ON leads(phone_e164)",
        "critical": False,
        "description": "Index on leads for leads phone"
    },
    {
        "name": "idx_leads_email",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_email ON leads(email)",
        "critical": False,
        "description": "Index on leads for leads email"
    },
    {
        "name": "idx_leads_external_id",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_external_id ON leads(external_id)",
        "critical": False,
        "description": "Index on leads for leads external id"
    },
    {
        "name": "idx_leads_owner",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_owner ON leads(owner_user_id)",
        "critical": False,
        "description": "Index on leads for leads owner"
    },
    {
        "name": "idx_leads_created",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_created ON leads(created_at)",
        "critical": False,
        "description": "Index on leads for leads created"
    },
    {
        "name": "idx_leads_contact",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_contact ON leads(last_contact_at)",
        "critical": False,
        "description": "Index on leads for leads contact"
    },
    {
        "name": "idx_lead_reminders_lead",
        "table": "lead_reminders",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_reminders_lead ON lead_reminders(lead_id)",
        "critical": False,
        "description": "Index on lead_reminders for lead reminders lead"
    },
    {
        "name": "idx_lead_reminders_due",
        "table": "lead_reminders",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_reminders_due ON lead_reminders(due_at)",
        "critical": False,
        "description": "Index on lead_reminders for lead reminders due"
    },
    {
        "name": "idx_lead_activities_lead",
        "table": "lead_activities",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_activities_lead ON lead_activities(lead_id)",
        "critical": False,
        "description": "Index on lead_activities for lead activities lead"
    },
    {
        "name": "idx_lead_activities_type",
        "table": "lead_activities",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_activities_type ON lead_activities(type)",
        "critical": False,
        "description": "Index on lead_activities for lead activities type"
    },
    {
        "name": "idx_lead_activities_time",
        "table": "lead_activities",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_activities_time ON lead_activities(at)",
        "critical": False,
        "description": "Index on lead_activities for lead activities time"
    },
    {
        "name": "idx_merge_candidates_lead",
        "table": "lead_merge_candidates",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_merge_candidates_lead ON lead_merge_candidates(lead_id)",
        "critical": False,
        "description": "Index on lead_merge_candidates for merge candidates lead"
    },
    {
        "name": "idx_merge_candidates_dup",
        "table": "lead_merge_candidates",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_merge_candidates_dup ON lead_merge_candidates(duplicate_lead_id)",
        "critical": False,
        "description": "Index on lead_merge_candidates for merge candidates dup"
    },
    {
        "name": "idx_leads_order_index",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_order_index ON leads(order_index)",
        "critical": False,
        "description": "Index on leads for leads order index"
    },
    {
        "name": "ix_outbound_lead_lists_tenant_id",
        "table": "outbound_lead_lists",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbound_lead_lists_tenant_id ON outbound_lead_lists(tenant_id)",
        "critical": False,
        "description": "Index on outbound_lead_lists for outbound lead lists tenant id"
    },
    {
        "name": "ix_leads_outbound_list_id",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_leads_outbound_list_id ON leads(outbound_list_id)",
        "critical": False,
        "description": "Index on leads for leads outbound list id"
    },
    {
        "name": "idx_lead_attachments_tenant_lead",
        "table": "lead_attachments",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_attachments_tenant_lead ON lead_attachments(tenant_id, lead_id)",
        "critical": False,
        "description": "Index on lead_attachments for lead attachments tenant lead"
    },
    {
        "name": "idx_lead_attachments_lead_id",
        "table": "lead_attachments",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_attachments_lead_id ON lead_attachments(lead_id)",
        "critical": False,
        "description": "Index on lead_attachments for lead attachments lead id"
    },
    {
        "name": "idx_lead_attachments_note_id",
        "table": "lead_attachments",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_attachments_note_id ON lead_attachments(note_id)",
        "critical": False,
        "description": "Index on lead_attachments for lead attachments note id"
    },
    {
        "name": "idx_lead_attachments_created_at",
        "table": "lead_attachments",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_lead_attachments_created_at ON lead_attachments(created_at)",
        "critical": False,
        "description": "Index on lead_attachments for lead attachments created at"
    },
    {
        "name": "idx_leads_detected_topic",
        "table": "leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_leads_detected_topic ON leads(detected_topic_id)",
        "critical": False,
        "description": "Index on leads for leads detected topic"
    },
    {
        "name": "ix_project_leads_project_id",
        "table": "project_leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_leads_project_id ON project_leads(project_id)",
        "critical": False,
        "description": "Index on project_leads for project leads project id"
    },
    {
        "name": "ix_project_leads_lead_id",
        "table": "project_leads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_project_leads_lead_id ON project_leads(lead_id)",
        "critical": False,
        "description": "Index on project_leads for project leads lead id"
    },
]


# ============================================================================
# CALLS DOMAIN
# Call log, sessions, and telephony indexes
# ============================================================================
INDEX_DEFS_CALLS = [
    {
        "name": "idx_call_turn_sid",
        "table": "call_turn",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_turn_sid ON call_turn(call_sid)",
        "critical": False,
        "description": "Index on call_turn for call turn sid"
    },
    {
        "name": "idx_call_turn_business_time",
        "table": "call_turn",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_turn_business_time ON call_turn(business_id, started_at)",
        "critical": False,
        "description": "Index on call_turn for call turn business time"
    },
    {
        "name": "idx_call_session_sid",
        "table": "call_session",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_session_sid ON call_session(call_sid)",
        "critical": False,
        "description": "Index on call_session for call session sid"
    },
    {
        "name": "idx_call_session_business",
        "table": "call_session",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_session_business ON call_session(business_id)",
        "critical": False,
        "description": "Index on call_session for call session business"
    },
    {
        "name": "idx_call_session_lead",
        "table": "call_session",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_session_lead ON call_session(lead_id)",
        "critical": False,
        "description": "Index on call_session for call session lead"
    },
    {
        "name": "idx_outbound_call_runs_business_id",
        "table": "outbound_call_runs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_runs_business_id ON outbound_call_runs(business_id)",
        "critical": False,
        "description": "Index on outbound_call_runs for outbound call runs business id"
    },
    {
        "name": "idx_outbound_call_runs_status",
        "table": "outbound_call_runs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_runs_status ON outbound_call_runs(status)",
        "critical": False,
        "description": "Index on outbound_call_runs for outbound call runs status"
    },
    {
        "name": "idx_outbound_call_runs_created_at",
        "table": "outbound_call_runs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_runs_created_at ON outbound_call_runs(created_at)",
        "critical": False,
        "description": "Index on outbound_call_runs for outbound call runs created at"
    },
    {
        "name": "idx_outbound_call_jobs_run_id",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_jobs_run_id ON outbound_call_jobs(run_id)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs run id"
    },
    {
        "name": "idx_outbound_call_jobs_lead_id",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_jobs_lead_id ON outbound_call_jobs(lead_id)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs lead id"
    },
    {
        "name": "idx_outbound_call_jobs_status",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_jobs_status ON outbound_call_jobs(status)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs status"
    },
    {
        "name": "idx_outbound_call_jobs_call_sid",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_jobs_call_sid ON outbound_call_jobs(call_sid)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs call sid"
    },
    {
        "name": "idx_call_log_parent_call_sid",
        "table": "call_log",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_log_parent_call_sid ON call_log(parent_call_sid)",
        "critical": False,
        "description": "Index on call_log for call log parent call sid"
    },
    {
        "name": "idx_call_log_twilio_direction",
        "table": "call_log",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_log_twilio_direction ON call_log(twilio_direction)",
        "critical": False,
        "description": "Index on call_log for call log twilio direction"
    },
    {
        "name": "idx_call_log_detected_topic",
        "table": "call_log",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_call_log_detected_topic ON call_log(detected_topic_id)",
        "critical": False,
        "description": "Index on call_log for call log detected topic"
    },
    {
        "name": "idx_outbound_call_jobs_twilio_sid",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_jobs_twilio_sid ON outbound_call_jobs(twilio_call_sid)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs twilio sid"
    },
    {
        "name": "idx_outbound_call_jobs_lock_token",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_outbound_call_jobs_lock_token ON outbound_call_jobs(dial_lock_token)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs lock token"
    },
    {
        "name": "ix_call_log_project_id",
        "table": "call_log",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_call_log_project_id ON call_log(project_id)",
        "critical": False,
        "description": "Index on call_log for call log project id"
    },
    {
        "name": "ix_outbound_call_jobs_project_id",
        "table": "outbound_call_jobs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbound_call_jobs_project_id ON outbound_call_jobs(project_id)",
        "critical": False,
        "description": "Index on outbound_call_jobs for outbound call jobs project id"
    },
]


# ============================================================================
# WHATSAPP DOMAIN
# WhatsApp conversations and broadcasts
# ============================================================================
INDEX_DEFS_WHATSAPP = [
    {
        "name": "idx_wa_conv_state_business",
        "table": "whatsapp_conversation_state",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_state_business ON whatsapp_conversation_state(business_id)",
        "critical": False,
        "description": "Index on whatsapp_conversation_state for wa conv state business"
    },
    {
        "name": "idx_wa_conv_state_phone",
        "table": "whatsapp_conversation_state",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_state_phone ON whatsapp_conversation_state(phone)",
        "critical": False,
        "description": "Index on whatsapp_conversation_state for wa conv state phone"
    },
    {
        "name": "idx_wa_conv_business_open",
        "table": "whatsapp_conversation",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_business_open ON whatsapp_conversation(business_id, is_open)",
        "critical": False,
        "description": "Index on whatsapp_conversation for wa conv business open"
    },
    {
        "name": "idx_wa_conv_customer",
        "table": "whatsapp_conversation",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_customer ON whatsapp_conversation(business_id, customer_wa_id)",
        "critical": False,
        "description": "Index on whatsapp_conversation for wa conv customer"
    },
    {
        "name": "idx_wa_conv_last_msg",
        "table": "whatsapp_conversation",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_last_msg ON whatsapp_conversation(last_message_at)",
        "critical": False,
        "description": "Index on whatsapp_conversation for wa conv last msg"
    },
    {
        "name": "idx_wa_conv_last_cust_msg",
        "table": "whatsapp_conversation",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_last_cust_msg ON whatsapp_conversation(last_customer_message_at)",
        "critical": False,
        "description": "Index on whatsapp_conversation for wa conv last cust msg"
    },
    {
        "name": "idx_wa_conv_detected_topic",
        "table": "whatsapp_conversation",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_wa_conv_detected_topic ON whatsapp_conversation(detected_topic_id)",
        "critical": False,
        "description": "Index on whatsapp_conversation for wa conv detected topic"
    },
    {
        "name": "idx_whatsapp_broadcasts_business",
        "table": "whatsapp_broadcasts",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_whatsapp_broadcasts_business ON whatsapp_broadcasts(business_id)",
        "critical": False,
        "description": "Index on whatsapp_broadcasts for whatsapp broadcasts business"
    },
    {
        "name": "idx_whatsapp_broadcasts_status",
        "table": "whatsapp_broadcasts",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_whatsapp_broadcasts_status ON whatsapp_broadcasts(status)",
        "critical": False,
        "description": "Index on whatsapp_broadcasts for whatsapp broadcasts status"
    },
    {
        "name": "idx_whatsapp_broadcast_recipients_broadcast",
        "table": "whatsapp_broadcast_recipients",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_whatsapp_broadcast_recipients_broadcast ON whatsapp_broadcast_recipients(broadcast_id)",
        "critical": False,
        "description": "Index on whatsapp_broadcast_recipients for whatsapp broadcast recipients broadcast"
    },
    {
        "name": "idx_whatsapp_broadcast_recipients_status",
        "table": "whatsapp_broadcast_recipients",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_whatsapp_broadcast_recipients_status ON whatsapp_broadcast_recipients(status)",
        "critical": False,
        "description": "Index on whatsapp_broadcast_recipients for whatsapp broadcast recipients status"
    },
]


# ============================================================================
# CONTRACTS DOMAIN
# Contract management and digital signatures
# ============================================================================
INDEX_DEFS_CONTRACTS = [
    {
        "name": "idx_contract_lead",
        "table": "contract",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_lead ON contract(lead_id)",
        "critical": False,
        "description": "Index on contract for contract lead"
    },
    {
        "name": "idx_contract_business_created",
        "table": "contract",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_business_created ON contract(business_id, created_at DESC)",
        "critical": False,
        "description": "Index on contract for contract business created"
    },
    {
        "name": "idx_contract_business_status",
        "table": "contract",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_business_status ON contract(business_id, status)",
        "critical": False,
        "description": "Index on contract for contract business status"
    },
    {
        "name": "idx_contract_files_contract",
        "table": "contract_files",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_files_contract ON contract_files(contract_id, created_at DESC)",
        "critical": False,
        "description": "Index on contract_files for contract files contract"
    },
    {
        "name": "idx_contract_files_business",
        "table": "contract_files",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_files_business ON contract_files(business_id)",
        "critical": False,
        "description": "Index on contract_files for contract files business"
    },
    {
        "name": "idx_contract_files_attachment",
        "table": "contract_files",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_files_attachment ON contract_files(attachment_id)",
        "critical": False,
        "description": "Index on contract_files for contract files attachment"
    },
    {
        "name": "idx_contract_tokens_hash",
        "table": "contract_sign_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_tokens_hash ON contract_sign_tokens(token_hash)",
        "critical": False,
        "description": "Index on contract_sign_tokens for contract tokens hash"
    },
    {
        "name": "idx_contract_tokens_contract",
        "table": "contract_sign_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_tokens_contract ON contract_sign_tokens(contract_id)",
        "critical": False,
        "description": "Index on contract_sign_tokens for contract tokens contract"
    },
    {
        "name": "idx_contract_tokens_expires",
        "table": "contract_sign_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_tokens_expires ON contract_sign_tokens(expires_at)",
        "critical": False,
        "description": "Index on contract_sign_tokens for contract tokens expires"
    },
    {
        "name": "idx_contract_events_contract",
        "table": "contract_sign_events",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_events_contract ON contract_sign_events(contract_id, created_at)",
        "critical": False,
        "description": "Index on contract_sign_events for contract events contract"
    },
    {
        "name": "idx_contract_events_business",
        "table": "contract_sign_events",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_contract_events_business ON contract_sign_events(business_id)",
        "critical": False,
        "description": "Index on contract_sign_events for contract events business"
    },
]


# ============================================================================
# AUTH / SECURITY DOMAIN
# Authentication, tokens, and security events
# ============================================================================
INDEX_DEFS_AUTH_SECURITY = [
    {
        "name": "idx_refresh_tokens_user_id",
        "table": "refresh_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_user_id ON refresh_tokens(user_id)",
        "critical": False,
        "description": "Index on refresh_tokens for refresh tokens user id"
    },
    {
        "name": "idx_refresh_tokens_tenant_id",
        "table": "refresh_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_tenant_id ON refresh_tokens(tenant_id)",
        "critical": False,
        "description": "Index on refresh_tokens for refresh tokens tenant id"
    },
    {
        "name": "idx_refresh_tokens_token_hash",
        "table": "refresh_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_token_hash ON refresh_tokens(token_hash)",
        "critical": False,
        "description": "Index on refresh_tokens for refresh tokens token hash"
    },
    {
        "name": "idx_refresh_tokens_expires_at",
        "table": "refresh_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_expires_at ON refresh_tokens(expires_at)",
        "critical": False,
        "description": "Index on refresh_tokens for refresh tokens expires at"
    },
    {
        "name": "idx_refresh_tokens_is_valid",
        "table": "refresh_tokens",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_refresh_tokens_is_valid ON refresh_tokens(is_valid)",
        "critical": False,
        "description": "Index on refresh_tokens for refresh tokens is valid"
    },
]


# ============================================================================
# OUTBOUND DOMAIN
# Outbound campaigns and projects
# ============================================================================
INDEX_DEFS_OUTBOUND = [
    {
        "name": "ix_outbound_projects_tenant_id",
        "table": "outbound_projects",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbound_projects_tenant_id ON outbound_projects(tenant_id)",
        "critical": False,
        "description": "Index on outbound_projects for outbound projects tenant id"
    },
    {
        "name": "ix_outbound_projects_status",
        "table": "outbound_projects",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_outbound_projects_status ON outbound_projects(status)",
        "critical": False,
        "description": "Index on outbound_projects for outbound projects status"
    },
]


# ============================================================================
# MISCELLANEOUS
# Other indexes not fitting above categories
# ============================================================================
INDEX_DEFS_MISC = [
    {
        "name": "idx_threads_biz_last",
        "table": "threads",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_threads_biz_last ON threads(business_id, last_message_at DESC)",
        "critical": False,
        "description": "Index on threads for threads biz last"
    },
    {
        "name": "idx_msgs_thread_time",
        "table": "messages",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_msgs_thread_time ON messages(thread_id, created_at)",
        "critical": False,
        "description": "Index on messages for msgs thread time"
    },
    {
        "name": "idx_tenant_version",
        "table": "prompt_revisions",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_tenant_version ON prompt_revisions(tenant_id, version)",
        "critical": False,
        "description": "Index on prompt_revisions for tenant version"
    },
    {
        "name": "idx_bcc_business",
        "table": "business_contact_channels",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bcc_business ON business_contact_channels(business_id)",
        "critical": False,
        "description": "Index on business_contact_channels for bcc business"
    },
    {
        "name": "idx_bcc_channel",
        "table": "business_contact_channels",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bcc_channel ON business_contact_channels(channel_type)",
        "critical": False,
        "description": "Index on business_contact_channels for bcc channel"
    },
    {
        "name": "idx_bcc_identifier",
        "table": "business_contact_channels",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_bcc_identifier ON business_contact_channels(identifier)",
        "critical": False,
        "description": "Index on business_contact_channels for bcc identifier"
    },
    {
        "name": "idx_business_active",
        "table": "faqs",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_business_active ON faqs(business_id, is_active)",
        "critical": False,
        "description": "Index on faqs for business active"
    },
    {
        "name": "idx_business_topic_active",
        "table": "business_topics",
        "sql": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_business_topic_active ON business_topics(business_id, is_active)",
        "critical": False,
        "description": "Index on business_topics for business topic active"
    },
]


# ============================================================================
# COMBINED INDEX DEFINITIONS
# All indexes from all domains combined into single list
# ============================================================================
INDEX_DEFS = (
    INDEX_DEFS_LEADS_CRM +
    INDEX_DEFS_CALLS +
    INDEX_DEFS_WHATSAPP +
    INDEX_DEFS_CONTRACTS +
    INDEX_DEFS_AUTH_SECURITY +
    INDEX_DEFS_OUTBOUND +
    INDEX_DEFS_MISC
)


# Export for convenience
__all__ = ['INDEX_DEFS']
