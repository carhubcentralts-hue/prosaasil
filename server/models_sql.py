"""
SQLAlchemy models for Hebrew AI Call Center CRM
Production-ready database models with proper relationships and indexing
"""
from server.db import db
from datetime import datetime

class Business(db.Model):
    __tablename__ = "business"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(255), nullable=False, default="general")  # 🔥 BUILD 200: Generic default - works for any business type
    phone_e164 = db.Column('phone_number', db.String(255))  # ✅ Map to DB column phone_number
    whatsapp_number = db.Column(db.String(255))
    greeting_message = db.Column(db.Text)
    whatsapp_greeting = db.Column(db.Text)
    system_prompt = db.Column(db.Text)
    # WhatsApp AI prompt configuration (prompt-only mode)
    whatsapp_system_prompt = db.Column(db.Text)  # Dedicated WhatsApp prompt from DB
    whatsapp_temperature = db.Column(db.Float, default=0.0)  # Temperature for WhatsApp AI
    whatsapp_model = db.Column(db.String(50), default="gpt-4o-mini")  # Model for WhatsApp
    whatsapp_max_tokens = db.Column(db.Integer, default=350)  # Max tokens for WhatsApp
    whatsapp_enabled = db.Column(db.Boolean, default=False)
    whatsapp_provider = db.Column(db.String(32), default="baileys")  # "baileys" | "meta" - WhatsApp provider choice
    phone_permissions = db.Column(db.Boolean, default=True)
    whatsapp_permissions = db.Column(db.Boolean, default=True)
    is_active = db.Column(db.Boolean, default=True)
    calls_enabled = db.Column(db.Boolean, default=True)
    crm_enabled = db.Column(db.Boolean, default=True)
    payments_enabled = db.Column(db.Boolean, default=False)      # Payment enablement per business
    default_provider = db.Column(db.String(20), default="paypal")  # 'paypal'|'tranzila'
    # Support settings for admin tenant management
    working_hours = db.Column(db.String(50), default="08:00-18:00")  # Support working hours
    voice_message = db.Column(db.Text)  # Custom voice message for support calls
    # WhatsApp webhook secret for n8n integration (unique per business)
    webhook_secret = db.Column(db.String(128), unique=True, nullable=True)  # Format: wh_n8n_<random_hex>
    # Voice Library - per-business voice selection for Realtime phone calls
    voice_id = db.Column(db.String(32), nullable=False, default="ash")  # LEGACY: OpenAI Realtime voice (kept for compatibility)
    # TTS Provider and Voice Selection (Voice only - Brain is always OpenAI)
    # 🔥 CRITICAL: This controls VOICE (TTS) only, NOT the LLM brain
    # Brain (LLM) is always OpenAI. Voice can be OpenAI TTS or Google Gemini TTS.
    tts_provider = db.Column(db.String(32), default="openai")  # LEGACY: "openai" | "gemini" - kept for compatibility
    tts_voice_id = db.Column(db.String(64), default="alloy")  # LEGACY: TTS voice ID - kept for compatibility
    tts_language = db.Column(db.String(16), default="he-IL")  # TTS language code
    tts_speed = db.Column(db.Float, default=1.0)  # TTS speaking speed (0.5 - 2.0)
    # 🔥 NEW: AI Provider Selection - Single source of truth
    # The ai_provider determines BOTH the LLM brain AND the TTS voice AND STT
    # When ai_provider="openai": Uses OpenAI for everything (Realtime API or pipeline)
    # When ai_provider="gemini": Uses Gemini for LLM+TTS, can use OpenAI Whisper for STT
    ai_provider = db.Column(db.String(32), default="openai")  # "openai" | "gemini" - Main provider selection
    voice_name = db.Column(db.String(64), default="alloy")  # Voice name within the selected provider
    # Company registration info
    company_id = db.Column(db.String(50), nullable=True)  # Israeli company registration number (ח.פ)
    # Page-level permissions - which pages/modules are enabled for this business
    # 🔥 HOTFIX: Made nullable=True temporarily to handle migration transition period
    # During deployment, column may not exist yet, so queries would fail with nullable=False
    # After migration 71 completes, this can be changed back to nullable=False
    enabled_pages = db.Column(db.JSON, nullable=True, default=list)  # List of page_keys from page_registry
    # ✅ BUILD 113: Flexible tab configuration for lead detail page
    # JSONB object with primary and secondary tab arrays
    # Default: {} (empty object - tabs will be generated dynamically)
    # Max 3 primary + 3 secondary (6 total)
    # Available tabs: activity, reminders, documents, overview, whatsapp, calls, email, contracts, appointments, ai_notes, notes
    lead_tabs_config = db.Column(db.JSON, nullable=False, default=dict, server_default='{}')  # ✅ NOT NULL with default
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Property aliases for compatibility - לפי ההנחיות המדויקות
    @property
    def phone(self):
        return self.phone_e164
    
    @phone.setter
    def phone(self, value):
        self.phone_e164 = value
    
    @property
    def phone_number(self):
        return self.phone_e164
    
    @phone_number.setter
    def phone_number(self, value):
        self.phone_e164 = value

class BusinessContactChannel(db.Model):
    """Multi-tenant channel routing - maps contact identifiers to businesses"""
    __tablename__ = "business_contact_channels"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    channel_type = db.Column(db.String(32), nullable=False, index=True)  # 'twilio_voice', 'twilio_sms', 'whatsapp'
    identifier = db.Column(db.String(255), nullable=False, index=True)  # E.164 phone or tenant slug (business_1)
    is_primary = db.Column(db.Boolean, default=False)
    config_json = db.Column(db.Text)  # JSON for extra config
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: one identifier per channel type
    __table_args__ = (
        db.UniqueConstraint('channel_type', 'identifier', name='uq_channel_identifier'),
    )

class ContactIdentity(db.Model):
    """
    🎯 BUILD 200: Unified Contact Identity Mapping Layer
    
    Prevents duplicate leads across WhatsApp and Phone channels by creating
    a consistent mapping between external identifiers and lead_id.
    
    Key Concepts:
    - WhatsApp: external_id = normalized remoteJid (e.g., "972525951893@s.whatsapp.net")
    - Phone: external_id = normalized E.164 (e.g., "+972525951893")
    - Same person contacting via both channels = ONE lead with TWO contact_identities
    
    This enables:
    - No duplicate leads when same person contacts via multiple channels
    - Proper message routing (always reply to correct JID/phone)
    - Cross-channel lead linking based on phone number
    """
    __tablename__ = "contact_identities"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Channel type: 'whatsapp' or 'phone'
    channel = db.Column(db.String(32), nullable=False, index=True)
    
    # External identifier:
    # - For WhatsApp: normalized remoteJid (e.g., "972525951893@s.whatsapp.net")
    # - For Phone: normalized E.164 (e.g., "+972525951893")
    external_id = db.Column(db.String(255), nullable=False)
    
    # Lead this contact identity maps to
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    lead = db.relationship("Lead", backref=db.backref("contact_identities", lazy="dynamic"))
    business = db.relationship("Business", backref=db.backref("contact_identities", lazy="dynamic"))
    
    # Indexes (defined via migration 120, listed here for documentation)
    # UNIQUE INDEX: idx_contact_identities_unique_mapping ON (business_id, channel, external_id)
    # INDEX: idx_contact_identities_lead ON (business_id, lead_id)
    # INDEX: idx_contact_identities_channel ON (channel)
    
    def __repr__(self):
        return f"<ContactIdentity {self.channel}:{self.external_id[:20]}... → lead_id={self.lead_id}>"

class Customer(db.Model):
    __tablename__ = "customer"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    phone_e164 = db.Column('phone_number', db.String(64), index=True)  # ✅ Map to DB column phone_number
    email = db.Column(db.String(255))
    status = db.Column(db.String(64), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CallLog(db.Model):
    __tablename__ = "call_log"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)  # BUILD 174: Link to lead for outbound calls
    outbound_template_id = db.Column(db.Integer, db.ForeignKey("outbound_call_templates.id"), nullable=True)  # BUILD 174: Template used for outbound call
    project_id = db.Column(db.Integer, nullable=True, index=True)  # Project ID for calls initiated from projects (FK to outbound_projects)
    call_sid = db.Column(db.String(64), unique=True, index=True)  # ✅ Unique constraint to prevent duplicates
    parent_call_sid = db.Column(db.String(64), nullable=True, index=True)  # 🔥 Parent call SID for child legs
    from_number = db.Column(db.String(64), index=True)
    to_number = db.Column(db.String(64))  # ✅ BUILD 88: Added to_number field
    direction = db.Column(db.String(16), default="inbound")  # ✅ BUILD 106: inbound/outbound (normalized)
    twilio_direction = db.Column(db.String(32), nullable=True)  # 🔥 Original Twilio direction (outbound-api, outbound-dial, etc.)
    duration = db.Column(db.Integer, default=0)  # ✅ BUILD 106: Call duration in seconds
    
    # ⚠️ DEPRECATED: Use 'status' field instead
    # 🔥 SSOT: This field is kept ONLY for backward compatibility with old DB records
    # ❌ DO NOT UPDATE THIS FIELD - use 'status' field for all new code
    # 📋 Migration plan: Will be removed in future version after data migration
    call_status = db.Column(db.String(32), default="in-progress")  # ✅ BUILD 90: Legacy field - DO NOT USE
    
    recording_url = db.Column(db.String(512))
    recording_sid = db.Column(db.String(64), nullable=True)  # 🔥 BUILD 342: Twilio Recording SID
    transcription = db.Column(db.Text)
    summary = db.Column(db.Text)  # ✨ סיכום חכם קצר של השיחה (80-150 מילים) - BUILD 106
    status = db.Column(db.String(32), default="received")
    
    # 🆕 POST-CALL EXTRACTION: Full offline transcript + extracted lead fields
    final_transcript = db.Column(db.Text, nullable=True)  # Full high-quality Hebrew transcript from recording
    extracted_service = db.Column(db.String(255), nullable=True)  # Service type extracted from transcript
    extracted_city = db.Column(db.String(255), nullable=True)  # City extracted from transcript
    extraction_confidence = db.Column(db.Float, nullable=True)  # Confidence score (0.0-1.0)
    
    # 🔥 BUILD 342: Recording Quality Metadata - Verify actual recording transcription
    audio_bytes_len = db.Column(db.Integer, nullable=True)  # Recording file size in bytes (>0 = valid download)
    audio_duration_sec = db.Column(db.Float, nullable=True)  # Recording duration in seconds from metadata
    transcript_source = db.Column(db.String(32), nullable=True)  # "recording"/"realtime"/"failed" - source of final_transcript
    
    # 🎙️ SSOT: Recording Mode Tracking (prevents double recording costs)
    # Values: "TWILIO_CALL_RECORD" | "RECORDING_API" | "OFF" | None
    recording_mode = db.Column(db.String(32), nullable=True)  # How recording was initiated
    
    # 💰 TWILIO COST METRICS (Cost Killer - tracks billing factors)
    # 🔥 DURATION TRACKING: Use these columns for call timing (Migration 51)
    # Stream metrics - PRIMARY source for call timing
    stream_started_at = db.Column(db.DateTime, nullable=True)  # When WebSocket stream started
    stream_ended_at = db.Column(db.DateTime, nullable=True)  # When WebSocket stream ended
    stream_duration_sec = db.Column(db.Float, nullable=True)  # Stream duration in seconds
    stream_connect_count = db.Column(db.Integer, default=0)  # How many times WS reconnected (>1 = cost issue)
    
    # Webhook/retry metrics
    webhook_11205_count = db.Column(db.Integer, default=0)  # Count of Twilio 11205 errors
    webhook_retry_count = db.Column(db.Integer, default=0)  # Count of webhook retries
    
    # Recording metrics
    recording_count = db.Column(db.Integer, default=0)  # How many recordings created (should be 0 or 1)
    
    # Cost classification
    estimated_cost_bucket = db.Column(db.String(16), nullable=True)  # "LOW"/"MED"/"HIGH" based on metrics
    
    # 🆕 AI TOPIC CLASSIFICATION: Detected topic from transcript
    detected_topic_id = db.Column(db.Integer, db.ForeignKey("business_topics.id"), nullable=True, index=True)
    detected_topic_confidence = db.Column(db.Float, nullable=True)  # Confidence score (0.0-1.0)
    detected_topic_source = db.Column(db.String(32), default="embedding")  # "embedding" - classification method
    
    # 🔥 NAME SSOT: Customer name for NAME_ANCHOR system (especially outbound calls)
    customer_name = db.Column(db.String(255), nullable=True)  # Customer/lead name for outbound calls
    
    # 🔥 SUMMARY STATUS: Track summary generation for long calls
    summary_status = db.Column(db.String(32), nullable=True)  # "pending" | "processing" | "completed" | "failed" | None
    
    # 🔥 ERROR TRACKING: Store error information for failed calls
    error_message = db.Column(db.Text, nullable=True)  # Error message for failed calls
    error_code = db.Column(db.String(64), nullable=True)  # Error code for failed calls
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # BUILD 174: Relationships for outbound calls
    lead = db.relationship("Lead", backref=db.backref("call_logs", lazy="dynamic"), foreign_keys="[CallLog.lead_id]")
    outbound_template = db.relationship("OutboundCallTemplate", backref=db.backref("calls", lazy="dynamic"), foreign_keys="[CallLog.outbound_template_id]")
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_call_log_recent_outbound', 'business_id', 'direction', 'created_at'),
    )

class ConversationTurn(db.Model):
    """תורות שיחה - כל הודעה בשיחה טלפונית או WhatsApp"""
    __tablename__ = "conversation_turn"
    id = db.Column(db.Integer, primary_key=True)
    call_log_id = db.Column(db.Integer, db.ForeignKey("call_log.id"), index=True)
    call_sid = db.Column(db.String(64), index=True)
    speaker = db.Column(db.String(32))  # 'user' or 'assistant'
    message = db.Column(db.Text)
    confidence_score = db.Column(db.Float)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# AI Prompt Management - לפי ההנחיות המדויקות
class BusinessSettings(db.Model):
    __tablename__ = "business_settings"
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), primary_key=True)
    ai_prompt = db.Column(db.Text)  # AI prompt for inbound calls
    outbound_ai_prompt = db.Column(db.Text)  # 🔥 BUILD 174: AI prompt for outbound calls (separate from inbound)
    model = db.Column(db.String(50), default="gpt-4o-mini")  # AI model for prompts
    max_tokens = db.Column(db.Integer, default=120)  # ⚡ BUILD 105: Optimized for faster responses (was 150)
    temperature = db.Column(db.Float, default=0.7)   # AI temperature setting (0-2)
    # Business settings
    phone_number = db.Column(db.String(255))  # Business phone number
    email = db.Column(db.String(255))  # Business email
    address = db.Column(db.String(500))  # Business address
    working_hours = db.Column(db.String(100))  # Business working hours
    timezone = db.Column(db.String(50), default="Asia/Jerusalem")  # Business timezone
    
    # 🔥 POLICY ENGINE - Dynamic business policy (no hardcoded hours!)
    slot_size_min = db.Column(db.Integer, default=60)  # Appointment slot size in minutes (15/30/60)
    allow_24_7 = db.Column(db.Boolean, default=False)  # Allow 24/7 booking
    opening_hours_json = db.Column(db.JSON, nullable=True)  # {"sun":[["10:00","20:00"]], "mon":[...], ...}
    booking_window_days = db.Column(db.Integer, default=30)  # How many days ahead can customers book
    min_notice_min = db.Column(db.Integer, default=0)  # Minimum notice time in minutes before appointment
    require_phone_before_booking = db.Column(db.Boolean, default=False)  # 🔥 BUILD 182/183: Use Caller ID by default, ask verbally if enabled (NO DTMF)
    
    # 🔥 BUILD 177: Generic Webhook for external integrations (n8n, Zapier, etc.)
    generic_webhook_url = db.Column(db.String(512), nullable=True)  # Generic webhook URL for call transcripts (fallback for both inbound and outbound)
    # 🔥 BUILD 183: Separate webhooks for inbound/outbound calls with generic fallback
    inbound_webhook_url = db.Column(db.String(512), nullable=True)  # Webhook for inbound calls (fallback to generic_webhook_url if not set)
    outbound_webhook_url = db.Column(db.String(512), nullable=True)  # Webhook for outbound calls (fallback to generic_webhook_url if not set)
    # 🔥 UI SPRINT: Status change webhook - sends lead status changes to external integrations
    status_webhook_url = db.Column(db.String(512), nullable=True)  # Webhook URL for lead status changes
    
    # 🔥 BUILD 163: Auto hang-up settings
    auto_end_after_lead_capture = db.Column(db.Boolean, default=False)  # Hang up after all lead details collected
    auto_end_on_goodbye = db.Column(db.Boolean, default=True)  # Hang up when customer says goodbye - NOW ENABLED BY DEFAULT
    
    # 🔥 BUILD 163: Bot speaks first setting (🔥 DEPRECATED: Always True in runtime, kept for DB compatibility)
    bot_speaks_first = db.Column(db.Boolean, default=False)  # Bot plays greeting before listening (DEPRECATED: Ignored in runtime)
    
    # 🔥 BUILD 186: Calendar scheduling toggle - when enabled, AI will try to schedule appointments
    enable_calendar_scheduling = db.Column(db.Boolean, default=True)  # AI schedules appointments during inbound calls
    
    # 🔥 BUILD 164: Smart Call Control Settings (Step 2 Spec)
    silence_timeout_sec = db.Column(db.Integer, default=15)  # Seconds of silence before asking "are you there?"
    silence_max_warnings = db.Column(db.Integer, default=2)  # Max warnings before polite hangup
    smart_hangup_enabled = db.Column(db.Boolean, default=True)  # AI decides hangup based on context, not keywords
    required_lead_fields = db.Column(db.JSON, nullable=True)  # ["name", "phone", "service_type", "preferred_time"]
    
    # 🔥 BUILD 309: SIMPLE_MODE Call Profile - Dynamic call goal and confirmation settings
    call_goal = db.Column(db.String(50), default="lead_only")  # "lead_only" or "appointment" - determines flow
    confirm_before_hangup = db.Column(db.Boolean, default=True)  # Always confirm with user before hanging up
    
    # 🔥 BUILD 204: Dynamic STT Vocabulary - per-business terminology for better transcription
    # Format: {"services": ["תספורת", "צביעה"], "staff": ["דנה", "יוסי"], "products": ["מוס", "לק"], "locations": ["תל אביב"]}
    stt_vocabulary_json = db.Column(db.JSON, nullable=True)  # Business-specific vocabulary for STT hints
    business_context = db.Column(db.String(500), nullable=True)  # Short context: "מספרת יוקרה לגברים ונשים"
    
    # 🔥 CRM Context-Aware Support: Customer service mode
    # When enabled, AI will use CRM context (lead notes, appointments) to provide personalized support
    enable_customer_service = db.Column(db.Boolean, default=False)  # Toggle for customer service mode
    
    # 📦 Assets Library AI Integration: Control whether AI can access assets tools
    # When enabled, AI can search and retrieve asset information during conversations
    assets_use_ai = db.Column(db.Boolean, default=True)  # Toggle for AI access to assets library
    
    # 🔥 Configurable Appointment Types & Statuses: Per-business customization
    # Format: [{"key": "viewing", "label": "צפייה", "color": "blue"}, {"key": "meeting", "label": "פגישה", "color": "green"}]
    appointment_types_json = db.Column(db.JSON, nullable=True)  # Custom appointment types per business
    appointment_statuses_json = db.Column(db.JSON, nullable=True)  # Custom appointment statuses per business
    
    # 🔥 Default Calendar Selection: Main calendar for appointments tab
    default_calendar_id = db.Column(db.Integer, db.ForeignKey("business_calendars.id"), nullable=True)  # Default/main calendar
    
    updated_by = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class OutboundCallTemplate(db.Model):
    """
    BUILD 174: Outbound call templates for AI-initiated calls
    תבניות לשיחות יוצאות - מאפשר להגדיר מטרות שונות לשיחות יוצאות
    """
    __tablename__ = "outbound_call_templates"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)  # e.g., "תיאום פגישה", "בירור חוב", "חידוש שירות"
    description = db.Column(db.String(500))  # Short description for UI
    prompt_text = db.Column(db.Text, nullable=False)  # Hebrew AI behavior instructions
    greeting_template = db.Column(db.Text)  # Optional custom greeting: "שלום {{lead_name}}, כאן..."
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    business = db.relationship("Business", backref="outbound_templates")
    
    __table_args__ = (
        db.Index('idx_business_template_active', 'business_id', 'is_active'),
    )


class OutboundLeadList(db.Model):
    """
    BUILD 182: Bulk-imported lead lists for outbound calls
    רשימת לידים מיובאת לשיחות יוצאות - עד 5000 לידים לעסק
    """
    __tablename__ = "outbound_lead_lists"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)  # e.g. "ייבוא 03/12/2025"
    file_name = db.Column(db.String(255), nullable=True)  # Original uploaded file name
    total_leads = db.Column(db.Integer, default=0)  # Number of leads imported
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship to business
    business = db.relationship("Business", backref="outbound_lead_lists")
    
    # Relationship to leads - defined via backref in Lead model


class FAQ(db.Model):
    """Business-specific FAQs for fast-path responses"""
    __tablename__ = "faqs"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Core FAQ fields
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    
    # Fast-Path fields (Migration 22)
    intent_key = db.Column(db.String(50), nullable=True)  # e.g., "price", "hours", "address"
    patterns_json = db.Column(db.JSON, nullable=True)  # Array of regex patterns for matching
    channels = db.Column(db.String(20), default="voice")  # "voice", "whatsapp", or "both"
    priority = db.Column(db.Integer, default=0)  # Higher priority FAQs match first
    lang = db.Column(db.String(10), default="he-IL")  # Language code
    
    # Status & ordering
    is_active = db.Column(db.Boolean, default=True)
    order_index = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    business = db.relationship("Business", backref="faqs")
    
    __table_args__ = (
        db.Index('idx_business_active', 'business_id', 'is_active'),
    )

class PromptRevisions(db.Model):
    __tablename__ = "prompt_revisions"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)  # auto-increment per tenant
    prompt = db.Column(db.Text)
    status_change_prompt = db.Column(db.Text)  # 🔥 NEW: Instructions for AI on how to change lead statuses
    whatsapp_system_prompt = db.Column(db.Text)  # 🔥 NEW: WhatsApp-specific system prompt
    changed_by = db.Column(db.String(255))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # אינדקס (tenant_id, version)
    __table_args__ = (
        db.Index('idx_tenant_version', 'tenant_id', 'version'),
    )

class WhatsAppMessage(db.Model):
    __tablename__ = "whatsapp_message"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    to_number = db.Column(db.String(64), index=True)      # למי נשלח/ממי התקבל
    direction = db.Column(db.String(8))                   # 'out' / 'in'
    body = db.Column(db.Text)
    message_type = db.Column(db.String(16), default="text") # text | media | template
    media_url = db.Column(db.String(512))                 # למדיה נכנסת/יוצאת
    status = db.Column(db.String(32), default="queued")   # queued/sent/delivered/read/failed/received
    provider = db.Column(db.String(16), default="baileys")# baileys/twilio
    provider_message_id = db.Column(db.String(128))
    delivered_at = db.Column(db.DateTime)
    read_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class WhatsAppConversationState(db.Model):
    """BUILD 150: Track AI active/inactive state per WhatsApp conversation
    AgentKit Only: Track conversation context for better agent behavior
    """
    __tablename__ = "whatsapp_conversation_state"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    phone = db.Column(db.String(64), nullable=False, index=True)  # Customer phone number
    ai_active = db.Column(db.Boolean, default=True)  # True = AI responds, False = human only
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    
    # AgentKit Only: Track conversation flow to prevent loops
    last_user_message = db.Column(db.Text, nullable=True)  # Last message from user
    last_agent_message = db.Column(db.Text, nullable=True)  # Last message from agent
    conversation_stage = db.Column(db.String(64), nullable=True)  # Current conversation stage
    
    __table_args__ = (
        db.UniqueConstraint('business_id', 'phone', name='uq_business_phone_state'),
    )


class WhatsAppConversation(db.Model):
    """BUILD 162: WhatsApp conversation sessions for tracking and auto-summary"""
    __tablename__ = "whatsapp_conversation"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    customer_number = db.Column(db.String(64), nullable=False, index=True)  # ✅ BUILD 170.1: Required by DB schema
    customer_name = db.Column(db.String(255), nullable=True)  # ✅ BUILD 170.1: Optional customer name
    status = db.Column(db.String(32), nullable=True)  # ✅ BUILD 170.1: Optional status field
    provider = db.Column(db.String(32), default="baileys")  # baileys / meta
    customer_wa_id = db.Column(db.String(64), nullable=True, index=True)  # Customer WhatsApp number (legacy)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)  # Link to Lead if exists
    
    # Session timestamps
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_customer_message_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Session state
    is_open = db.Column(db.Boolean, default=True, index=True)
    summary_created = db.Column(db.Boolean, default=False)
    summary = db.Column(db.Text)  # AI-generated session summary
    
    # 🆕 AI TOPIC CLASSIFICATION: Detected topic from conversation
    detected_topic_id = db.Column(db.Integer, db.ForeignKey("business_topics.id"), nullable=True, index=True)
    detected_topic_confidence = db.Column(db.Float, nullable=True)  # Confidence score (0.0-1.0)
    detected_topic_source = db.Column(db.String(32), default="embedding")  # "embedding" - classification method
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_wa_conv_business_open', 'business_id', 'is_open'),
        db.Index('idx_wa_conv_customer', 'business_id', 'customer_wa_id'),
    )


# === LEADS CRM SYSTEM - Monday/HubSpot/Salesforce style ===

class Lead(db.Model):
    """Lead model for advanced CRM system with Kanban board support"""
    __tablename__ = "leads"
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Relationships
    tenant = db.relationship("Business", backref="leads")
    
    # Core lead info
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    phone_e164 = db.Column(db.String(64), index=True)
    phone_raw = db.Column(db.String(64))  # 🔥 FIX #6: Original phone input for debugging
    email = db.Column(db.String(255), index=True)
    gender = db.Column(db.String(16), nullable=True)  # 'male', 'female', or NULL - auto-detected or manually set
    
    # Name tracking (unified name field with source tracking)
    name = db.Column(db.String(255))  # Full name from any source
    name_source = db.Column(db.String(32))  # Source: 'whatsapp', 'call', 'manual'
    name_updated_at = db.Column(db.DateTime)  # When name was last updated
    
    # 🔥 FIX #3 & #6: WhatsApp identity mapping
    whatsapp_jid = db.Column(db.String(128), index=True)  # Primary WhatsApp identifier (remoteJid)
    whatsapp_jid_alt = db.Column(db.String(128))  # Alternative identifier (sender_pn/participant)
    reply_jid = db.Column(db.String(128), index=True)  # 🔥 CRITICAL: EXACT JID to reply to (last seen)
    reply_jid_type = db.Column(db.String(32))  # Type: 's.whatsapp.net' or 'lid' or 'g.us'
    
    # Lead tracking
    source = db.Column(db.String(32), default="form", index=True)  # call|whatsapp|form|manual|imported_outbound
    external_id = db.Column(db.String(128), index=True)  # call_sid|wa_msg_id
    status = db.Column(db.String(32), default="new", index=True)  # Canonical lowercase: new|attempting|contacted|qualified|won|lost|unqualified
    order_index = db.Column(db.Integer, default=0, index=True)  # For Kanban board ordering within status
    
    # 🆕 STATUS TRACKING FOR SCHEDULED MESSAGES: Deduplication and timing
    status_sequence_token = db.Column(db.Integer, nullable=False, default=0)  # Incremented each time lead enters a status
    status_entered_at = db.Column(db.DateTime, default=datetime.utcnow)  # When lead entered current status
    
    # BUILD 182: Outbound import list tracking
    outbound_list_id = db.Column(db.Integer, db.ForeignKey("outbound_lead_lists.id"), nullable=True, index=True)
    outbound_list = db.relationship("OutboundLeadList", backref=db.backref("leads", lazy="dynamic"))
    
    # Assignment
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    
    # Metadata
    tags = db.Column(db.JSON)  # JSON array for flexible tagging
    notes = db.Column(db.Text)
    summary = db.Column(db.Text)  # ✨ סיכום חכם קצר (10-30 מילים) מכל השיחות
    
    # 🆕 POST-CALL EXTRACTION: Service type and city extracted from call transcripts
    service_type = db.Column(db.String(255), nullable=True)  # Service type extracted from calls (e.g., "פורץ מנעולים")
    city = db.Column(db.String(255), nullable=True)  # City extracted from calls (e.g., "תל אביב")
    
    # BUILD 162: WhatsApp session summary
    whatsapp_last_summary = db.Column(db.Text)  # Latest WhatsApp conversation summary
    whatsapp_last_summary_at = db.Column(db.DateTime)  # When summary was created
    
    # 🆕 UNIFIED CUSTOMER MEMORY: Shared memory for calls + WhatsApp
    # Single source of truth for customer context across all channels
    customer_profile_json = db.Column(db.JSON, nullable=True)  # Customer profile (name, city, services, preferences)
    last_summary = db.Column(db.Text, nullable=True)  # Short summary of last interaction (5-10 lines)
    summary_updated_at = db.Column(db.DateTime, nullable=True)  # When last_summary was updated
    last_interaction_at = db.Column(db.DateTime, nullable=True, index=True)  # Last message timestamp (any channel)
    last_channel = db.Column(db.String(16), nullable=True)  # 'whatsapp' | 'call' - last interaction channel
    
    # Call direction tracking for filtering (inbound/outbound)
    # 🔒 IMPORTANT: Set ONCE on first interaction, never overridden by subsequent calls
    last_call_direction = db.Column(db.String(16), nullable=True, index=True)  # inbound|outbound - set on first call only
    
    # 🆕 AI TOPIC CLASSIFICATION: Detected topic from transcript
    detected_topic_id = db.Column(db.Integer, db.ForeignKey("business_topics.id"), nullable=True, index=True)
    detected_topic_confidence = db.Column(db.Float, nullable=True)  # Confidence score (0.0-1.0)
    detected_topic_source = db.Column(db.String(32), default="embedding")  # "embedding" - classification method
    
    # 🆕 WEBHOOK INGESTION: Raw payload from webhook sources
    raw_payload = db.Column(db.JSON, nullable=True)  # Store original webhook payload for debugging and data recovery
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contact_at = db.Column(db.DateTime, index=True)
    
    # Computed properties
    @property
    def full_name(self):
        # Prefer unified name field if available
        if self.name:
            return self.name
        # Fallback to first_name + last_name
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or "ללא שם"
    
    @property
    def display_phone(self):
        if self.phone_e164:
            # Convert +972501234567 to 050-123-4567
            phone = self.phone_e164.replace('+972', '0')
            if len(phone) == 10:
                return f"{phone[:3]}-{phone[3:6]}-{phone[6:]}"
        return self.phone_e164

class LeadReminder(db.Model):
    """Reminders for leads - 'חזור אליי' functionality - now supports general business reminders"""
    __tablename__ = "lead_reminders"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenant support - direct business ownership
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Optional lead association - nullable for general reminders
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)
    
    due_at = db.Column(db.DateTime, nullable=False, index=True)
    note = db.Column(db.Text)
    description = db.Column(db.Text)  # BUILD 143: Additional details
    channel = db.Column(db.String(16), default="ui")  # ui|email|push|whatsapp
    priority = db.Column(db.String(16), default="medium")  # BUILD 143: low|medium|high
    reminder_type = db.Column(db.String(32), default="general")  # BUILD 143: general|lead_related
    
    # Status tracking
    delivered_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_tenant_due_at', 'tenant_id', 'due_at'),
    )

class LeadStatus(db.Model):
    """Custom lead statuses per business"""
    __tablename__ = "lead_statuses"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Status configuration
    name = db.Column(db.String(64), nullable=False)  # Internal name (e.g., "new", "contacted")
    label = db.Column(db.String(128), nullable=False)  # Display name (e.g., "חדש", "נוצר קשר")
    color = db.Column(db.String(64), default="bg-gray-100 text-gray-800")  # Tailwind classes
    description = db.Column(db.Text)  # Optional description
    
    # Ordering and system
    order_index = db.Column(db.Integer, default=0, index=True)  # Pipeline order
    is_active = db.Column(db.Boolean, default=True)  # Can be disabled without deleting
    is_default = db.Column(db.Boolean, default=False)  # Default status for new leads
    is_system = db.Column(db.Boolean, default=False)  # System statuses (like "Won", "Lost")
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="lead_statuses")
    
    # Unique constraint: name per business
    __table_args__ = (
        db.UniqueConstraint('business_id', 'name', name='_business_status_name'),
        db.Index('idx_business_order', 'business_id', 'order_index'),
    )

class LeadStatusHistory(db.Model):
    """Audit log for lead status changes"""
    __tablename__ = "lead_status_history"
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Status change details
    old_status = db.Column(db.String(64))  # Previous status value
    new_status = db.Column(db.String(64), nullable=False)  # New status value
    changed_by = db.Column(db.Integer, db.ForeignKey("users.id"))  # User who made the change (None for AI/automated)
    change_reason = db.Column(db.Text)  # Reason for the change
    confidence_score = db.Column(db.Float)  # AI confidence score (0.0-1.0) for AI-generated changes
    
    # Context
    channel = db.Column(db.String(32))  # Channel where change originated (whatsapp, call, manual, system)
    metadata_json = db.Column(db.JSON)  # Additional metadata
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    lead = db.relationship("Lead", backref="status_history")
    business = db.relationship("Business")
    
    # Indexes for common queries
    __table_args__ = (
        db.Index('idx_lead_status_history_lead', 'lead_id', 'created_at'),
        db.Index('idx_lead_status_history_tenant', 'tenant_id', 'created_at'),
    )

class WebhookLeadIngest(db.Model):
    """Webhook configuration for lead ingestion from external sources (Make, Zapier, etc.)
    
    Maximum of 3 webhooks per business - each webhook receives POST requests with lead data
    and creates leads in a pre-configured status. Supports secret-based authentication.
    """
    __tablename__ = "webhook_lead_ingest"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Webhook configuration
    name = db.Column(db.String(255), nullable=False)  # Descriptive name (e.g., "Make Source 1", "Facebook Leads")
    secret = db.Column(db.String(128), nullable=False)  # Authentication token for X-Webhook-Secret header
    status_id = db.Column(db.Integer, db.ForeignKey("lead_statuses.id", ondelete="SET NULL"), nullable=True, index=True)  # Target status for new leads (nullable - defaults to 'new')
    is_active = db.Column(db.Boolean, default=True, nullable=False)  # Enable/disable webhook
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="webhook_lead_ingests")
    status = db.relationship("LeadStatus")
    
    # Indexes
    __table_args__ = (
        db.Index('idx_webhook_lead_ingest_business', 'business_id', 'is_active'),
    )

class LeadActivity(db.Model):
    """Activity timeline for leads"""
    __tablename__ = "lead_activities"
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    
    type = db.Column(db.String(32), nullable=False, index=True)  # call|whatsapp|note|status_change|document|reminder
    payload = db.Column(db.JSON)  # Flexible data storage for different activity types
    
    at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

class LeadNote(db.Model):
    """Individual notes for leads - separate from WhatsApp/call logs
    BUILD 172: Permanent notes with edit/delete and file attachments
    CRM Context-Aware Support: Added note_type for call summaries and system notes
    """
    __tablename__ = "lead_notes"
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # CRM Context-Aware Support: note_type for categorizing notes
    # Values: 'manual' (user-created), 'call_summary' (AI-generated after call), 'system' (auto-generated)
    note_type = db.Column(db.String(32), default='manual', index=True)
    
    content = db.Column(db.Text, nullable=False)
    attachments = db.Column(db.JSON, default=list)  # [{id, name, url, type, size}]
    
    # CRM Context-Aware Support: Optional call_id to link note to a specific call
    call_id = db.Column(db.Integer, db.ForeignKey("call_log.id"), nullable=True, index=True)
    
    # CRM Context-Aware Support: Structured fields for call summaries
    # Format: {"sentiment": "positive", "outcome": "appointment_set", "next_step_date": "2024-01-20"}
    structured_data = db.Column(db.JSON, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    
    __table_args__ = (
        db.Index('idx_lead_notes_lead', 'lead_id', 'created_at'),
        db.Index('idx_lead_notes_type', 'lead_id', 'note_type'),
    )

class LeadAttachment(db.Model):
    """File attachments for leads - secure file storage with tenant isolation"""
    __tablename__ = "lead_attachments"
    
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    note_id = db.Column(db.Integer, db.ForeignKey("lead_notes.id", ondelete="SET NULL"), nullable=True, index=True)
    
    filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(128), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)
    storage_key = db.Column(db.String(512), nullable=False)  # Path in storage (local or S3)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    
    __table_args__ = (
        db.Index('idx_lead_attachments_tenant_lead', 'tenant_id', 'lead_id'),
    )

class LeadMergeCandidate(db.Model):
    """Potential duplicate leads for merging"""
    __tablename__ = "lead_merge_candidates"
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    duplicate_lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    
    confidence_score = db.Column(db.Float, default=0.0)  # 0.0-1.0
    reason = db.Column(db.String(64))  # phone|email|name|combined
    
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    merged_at = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# === CRM MODELS לפי הנחיות 100% GO ===

class Deal(db.Model):
    __tablename__ = "deal"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id", ondelete="CASCADE"), nullable=False, index=True)  # ✅ CRITICAL FIX: Points to customer table (not leads!) with CASCADE delete to prevent orphaned records
    title = db.Column(db.String(160))
    stage = db.Column(db.String(40), default='new')  # new / qualified / won / lost
    amount = db.Column(db.Integer)  # אגורות/שקלים — תואם CURRENCY
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    __tablename__ = "payment"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)  # Business reference
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True, index=True)  # Made nullable for standalone payments
    provider = db.Column(db.String(20), nullable=False)      # 'paypal' | 'tranzila' | 'noop'
    provider_ref = db.Column(db.String(100), index=True)     # orderID (PayPal), transaction id (Tranzila)
    amount = db.Column(db.Integer, nullable=False)           # באגורות
    currency = db.Column(db.String(8), default='ils')
    status = db.Column(db.String(20), default='created')     # created|approved|captured|failed|simulated
    customer_name = db.Column(db.String(160))                # Customer name for frontend compatibility
    description = db.Column(db.String(255))                  # Payment description
    paid_at = db.Column(db.DateTime)                         # When payment was completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Legacy Stripe fields (keep for compatibility, not used)
    stripe_payment_intent = db.Column(db.String(80), unique=True, nullable=True)

class PaymentGateway(db.Model):
    __tablename__ = "payment_gateway"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False)
    provider = db.Column(db.String(20), nullable=False)          # 'paypal'|'tranzila'
    mode = db.Column(db.String(10), default="sandbox")           # sandbox|live
    # PayPal
    paypal_client_id = db.Column(db.String(200))
    paypal_secret = db.Column(db.String(200))
    paypal_webhook_id = db.Column(db.String(120))
    # Tranzila
    tranzila_terminal = db.Column(db.String(120))
    tranzila_secret = db.Column(db.String(200))                  # For HMAC if needed
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Invoice(db.Model):
    __tablename__ = "invoice"
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True, index=True)  # nullable for direct invoices
    payment_id = db.Column(db.Integer, db.ForeignKey("payment.id"), nullable=True, index=True)  # Direct link to payment
    invoice_number = db.Column(db.String(40), unique=True, index=True)
    subtotal = db.Column(db.Numeric(10, 2))  # Changed to Numeric for proper decimals
    tax = db.Column(db.Numeric(10, 2))  # VAT amount
    vat_amount = db.Column(db.Numeric(10, 2))  # Alias for tax
    vat_rate = db.Column(db.Numeric(5, 4), default=0.17)  # VAT rate
    total = db.Column(db.Numeric(10, 2))
    pdf_path = db.Column(db.String(260))  # נתיב יחסי ל-static
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)
    issue_date = db.Column(db.DateTime)  # Alias for issued_at
    
    # AgentKit additions
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True, index=True)
    customer_name = db.Column(db.String(255))
    customer_phone = db.Column(db.String(64))
    currency = db.Column(db.String(8), default="ILS")  # ILS/USD
    status = db.Column(db.String(32), default="draft")  # draft/final/paid/cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class InvoiceItem(db.Model):
    """Invoice line items"""
    __tablename__ = "invoice_item"
    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoice.id"), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Numeric(10, 2), default=1.0)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    total = db.Column(db.Numeric(10, 2), nullable=False)

class Contract(db.Model):
    """
    Contracts - Digital contract management with signatures
    
    Status flow: draft -> sent -> signed (or cancelled)
    Files stored via attachments table (R2)
    """
    __tablename__ = "contract"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)
    
    # Legacy fields (kept for backwards compatibility)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True, index=True)
    
    # Core fields
    title = db.Column(db.String(255))
    status = db.Column(db.String(32), default="draft")  # draft|sent|signed|cancelled (CHECK constraint in migration)
    
    # Signer information
    signer_name = db.Column(db.String(255))
    signer_phone = db.Column(db.String(255))
    signer_email = db.Column(db.String(255))
    
    # Template and content (legacy)
    template_name = db.Column(db.String(80))
    template_id = db.Column(db.String(80))
    version = db.Column(db.String(20), default='v1')
    content = db.Column(db.Text)  # Contract content (filled template)
    variables = db.Column(db.JSON)  # Template variables as JSON
    customer_name = db.Column(db.String(255))
    
    # Legacy file paths (deprecated - use contract_files → attachments)
    html_path = db.Column(db.String(260))
    pdf_path = db.Column(db.String(260))
    
    # Signature data (legacy)
    signed_name = db.Column(db.String(160))
    signed_at = db.Column(db.DateTime)
    signed_ip = db.Column(db.String(64))
    signature_data = db.Column(db.Text)  # Base64 encoded signature image
    
    # Audit fields
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ContractFile(db.Model):
    """
    Contract Files - Links contracts to attachments (R2 storage)
    
    Reuses attachments table for actual file storage
    purpose: original|signed|extra_doc|template
    """
    __tablename__ = "contract_files"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"), nullable=False, index=True)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachments.id"), nullable=False, index=True)
    
    # File purpose/role
    purpose = db.Column(db.String(32), nullable=False)  # original|signed|extra_doc|template (CHECK constraint)
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)  # Soft delete


class ContractSignToken(db.Model):
    """
    Contract Sign Tokens - DB-based secure tokens for signing (NOT JWT)
    
    Stores hashed random tokens with expiration
    Can be revoked/checked in DB
    """
    __tablename__ = "contract_sign_tokens"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"), nullable=False, index=True)
    
    # Token data (hashed for security)
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    scope = db.Column(db.String(32), nullable=False, default='sign')
    
    # Expiration and usage tracking
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    used_at = db.Column(db.DateTime, nullable=True)
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class ContractSignEvent(db.Model):
    """
    Contract Sign Events - Audit trail for contract operations
    
    event_type: created|file_uploaded|sent_for_signature|viewed|signed_completed|cancelled
    event_metadata: JSON with event-specific data (renamed from metadata to avoid SQLAlchemy reserved word)
    """
    __tablename__ = "contract_sign_events"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    contract_id = db.Column(db.Integer, db.ForeignKey("contract.id"), nullable=False, index=True)
    
    # Event data
    event_type = db.Column(db.String(32), nullable=False)  # created|file_uploaded|... (CHECK constraint)
    event_metadata = db.Column(db.JSON)  # Event-specific data (IP, user agent, etc.) - renamed from 'metadata' to avoid SQLAlchemy reserved word
    
    # Audit fields
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

# === CALENDAR & APPOINTMENTS ===

class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)  # Link to lead if exists
    call_log_id = db.Column(db.Integer, db.ForeignKey("call_log.id"), nullable=True, index=True)  # Link to call that scheduled this
    whatsapp_message_id = db.Column(db.Integer, db.ForeignKey("whatsapp_message.id"), nullable=True, index=True)  # Link to WhatsApp message
    
    # Appointment details
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    start_time = db.Column(db.DateTime, nullable=False, index=True)
    end_time = db.Column(db.DateTime, nullable=False, index=True)
    location = db.Column(db.String(500))  # Address or "זום", "טלפון" etc
    
    # Status and type
    status = db.Column(db.String(32), default="scheduled")  # scheduled/confirmed/completed/cancelled/no_show
    appointment_type = db.Column(db.String(64), default="appointment")  # Generic: appointment/meeting/consultation/service
    priority = db.Column(db.String(16), default="medium")  # low/medium/high/urgent
    
    # Contact info (for cases without customer record)
    contact_name = db.Column(db.String(255))
    contact_phone = db.Column(db.String(64))
    contact_email = db.Column(db.String(255))
    
    # Reminders and notifications
    reminder_sent = db.Column(db.Boolean, default=False)
    reminder_sent_at = db.Column(db.DateTime)
    whatsapp_reminder_sent = db.Column(db.Boolean, default=False)
    email_reminder_sent = db.Column(db.Boolean, default=False)
    
    # Meeting notes and follow-up
    notes = db.Column(db.Text)
    outcome = db.Column(db.String(64))  # successful/no_show/rescheduled/cancelled
    follow_up_needed = db.Column(db.Boolean, default=False)
    follow_up_date = db.Column(db.DateTime)
    
    # ✅ BUILD 144: Call summary - סיכום השיחה שממנה נוצרה הפגישה
    call_summary = db.Column(db.Text)  # AI-generated summary from the call that created this appointment
    call_transcript = db.Column(db.Text)  # Full transcript from the call that created this appointment
    dynamic_summary = db.Column(db.Text)  # Dynamic conversation summary with intent, action, sentiment analysis
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # AI-generated flag (if appointment was auto-created from call/WhatsApp)
    auto_generated = db.Column(db.Boolean, default=False)
    source = db.Column(db.String(32), default="manual")  # manual/phone_call/whatsapp/ai_suggested
    
    # 🔥 NEW: Calendar association - which calendar was this appointment created in
    calendar_id = db.Column(db.Integer, db.ForeignKey("business_calendars.id"), nullable=True, index=True)

class BusinessCalendar(db.Model):
    """
    Dynamic calendar configuration for businesses
    Allows businesses to manage multiple calendars with different purposes
    Example: "פגישות", "הובלות", "ד״ר אלונה – מרפאה תל אביב"
    """
    __tablename__ = "business_calendars"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Calendar identification
    name = db.Column(db.String(255), nullable=False)  # Display name: "פגישות", "הובלות", etc.
    type_key = db.Column(db.String(64), nullable=True)  # Optional identifier: meetings, moves, doctor_alona_tlv
    
    # Provider configuration
    provider = db.Column(db.String(32), default="internal")  # internal/google/outlook
    calendar_external_id = db.Column(db.String(255), nullable=True)  # External calendar ID for Google/Outlook
    
    # Status and priority
    is_active = db.Column(db.Boolean, default=True, index=True)
    priority = db.Column(db.Integer, default=0)  # Higher priority = preferred when multiple match
    
    # Default scheduling settings
    default_duration_minutes = db.Column(db.Integer, default=60)
    buffer_before_minutes = db.Column(db.Integer, default=0)  # Time buffer before appointments
    buffer_after_minutes = db.Column(db.Integer, default=0)   # Time buffer after appointments
    
    # Usage labels for AI routing (JSON array)
    allowed_tags = db.Column(db.JSON, nullable=False, default=list)  # ["פגישה", "ייעוץ", "הובלה", "טיפול"]
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("calendars", lazy="dynamic"))
    appointments = db.relationship("Appointment", backref="calendar", lazy="dynamic")
    
    # Indexes
    __table_args__ = (
        db.Index('idx_business_calendars_business_active', 'business_id', 'is_active'),
        db.Index('idx_business_calendars_priority', 'business_id', 'priority'),
    )

class CalendarRoutingRule(db.Model):
    """
    Smart routing rules for calendar selection
    Allows businesses to define when to use which calendar
    Example: "אם לקוח מדבר על הובלה → השתמש בלוח הובלות"
    """
    __tablename__ = "calendar_routing_rules"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    calendar_id = db.Column(db.Integer, db.ForeignKey("business_calendars.id"), nullable=False, index=True)
    
    # Matching criteria (JSON arrays)
    match_labels = db.Column(db.JSON, nullable=False, default=list)  # ["הובלה", "העברת דירה"]
    match_keywords = db.Column(db.JSON, nullable=False, default=list)  # ["הובלה", "מוביל", "דירה"]
    
    # Channel scope
    channel_scope = db.Column(db.String(32), default="all")  # all/calls/whatsapp
    
    # Ambiguity handling
    when_ambiguous_ask = db.Column(db.Boolean, default=False)
    question_text = db.Column(db.String(500), nullable=True)  # "זה פגישה או הובלה?"
    
    # Priority and status
    priority = db.Column(db.Integer, default=0)  # Higher priority = checked first
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("calendar_routing_rules", lazy="dynamic"))
    calendar = db.relationship("BusinessCalendar", backref=db.backref("routing_rules", lazy="dynamic"))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_calendar_routing_business_active', 'business_id', 'is_active'),
        db.Index('idx_calendar_routing_calendar', 'calendar_id'),
    )

class AppointmentAutomation(db.Model):
    """
    Appointment confirmation automation rules
    Allows businesses to send automated WhatsApp messages based on appointment status changes
    """
    __tablename__ = "appointment_automations"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Automation identification
    name = db.Column(db.String(255), nullable=False)  # "אישור הגעה – סטטוס 'נקבע'"
    enabled = db.Column(db.Boolean, default=True, index=True)
    
    # Trigger configuration
    trigger_status_ids = db.Column(db.JSON, nullable=False, default=list)  # Array of status strings: ["scheduled", "confirmed"]
    calendar_ids = db.Column(db.JSON, nullable=True, default=None)  # Optional: Array of calendar IDs to filter by (null = all calendars)
    appointment_type_keys = db.Column(db.JSON, nullable=True, default=None)  # Optional: Array of appointment type keys to filter by (null = all types)
    
    # Schedule offsets (when to send messages relative to appointment time)
    # Format: [{"type":"before","minutes":1440},{"type":"after","minutes":1440},{"type":"immediate"}]
    schedule_offsets = db.Column(db.JSON, nullable=False, default=list)
    
    # Message configuration
    channel = db.Column(db.String(32), default="whatsapp", nullable=False)  # Currently only "whatsapp"
    message_template = db.Column(db.Text, nullable=False)  # Template with placeholders: {first_name}, {business_name}, etc.
    
    # Behavior settings
    send_once_per_offset = db.Column(db.Boolean, default=True)  # Prevent duplicate sends for same offset
    dedupe_key_mode = db.Column(db.String(64), default="business+appointment+offset")  # Deduplication strategy
    
    # Cancel if status changes
    cancel_on_status_exit = db.Column(db.Boolean, default=True)  # Cancel scheduled jobs if appointment status changes out
    
    # Active weekdays: Array of integers 0-6 (0=Sunday, 6=Saturday) or null for always active  
    # Example: [0,1,2,3,4] = Sunday-Thursday only
    active_weekdays = db.Column(db.JSON, nullable=True, default=None)  # null = all days, [0,1,2,3,4] = specific days
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("appointment_automations", lazy="dynamic"))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_appointment_automations_business_enabled', 'business_id', 'enabled'),
    )

class AppointmentAutomationRun(db.Model):
    """
    Tracks individual automation execution runs
    Records when automations were scheduled, sent, or failed
    """
    __tablename__ = "appointment_automation_runs"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    automation_id = db.Column(db.Integer, db.ForeignKey("appointment_automations.id"), nullable=False, index=True)
    
    # Offset signature for deduplication (e.g., "before_1440", "after_1440", "immediate")
    offset_signature = db.Column(db.String(64), nullable=False, index=True)
    
    # Scheduling information
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)  # When to send the message
    
    # Execution status
    status = db.Column(db.String(32), default="pending", nullable=False, index=True)  # pending/sent/failed/canceled
    attempts = db.Column(db.Integer, default=0)
    last_error = db.Column(db.Text)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    sent_at = db.Column(db.DateTime)
    canceled_at = db.Column(db.DateTime)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("appointment_automation_runs", lazy="dynamic"))
    appointment = db.relationship("Appointment", backref=db.backref("automation_runs", lazy="dynamic", cascade="all, delete-orphan"))
    automation = db.relationship("AppointmentAutomation", backref=db.backref("runs", lazy="dynamic", cascade="all, delete-orphan"))
    
    # Indexes and constraints
    __table_args__ = (
        db.Index('idx_appointment_automation_runs_scheduled', 'business_id', 'status', 'scheduled_for'),
        db.Index('idx_appointment_automation_runs_appointment', 'appointment_id', 'status'),
        # Unique constraint for deduplication
        db.UniqueConstraint('business_id', 'appointment_id', 'automation_id', 'offset_signature', 
                          name='uq_appointment_automation_run_dedupe'),
    )

class CRMTask(db.Model):
    """משימות CRM - ניהול משימות לעסקים"""
    __tablename__ = "crm_task"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    status = db.Column(db.String(32), default="todo")  # todo/doing/done
    priority = db.Column(db.String(32), default="medium")  # low/medium/high
    assigned_to = db.Column(db.String(255))  # User name or email
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)  # ✨ קישור ללידים
    due_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

class User(db.Model):
    """✅ BUILD 124: Fixed to match production DB schema (only 'name' column, not first_name/last_name)"""
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # ✅ Production DB has only 'name' column (not first_name/last_name)
    name = db.Column(db.String(255))
    
    role = db.Column(db.String(50), default="owner")
    # roles: system_admin (global access), owner (full business control), admin (limited business access), agent (calls/CRM only)
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    last_activity_at = db.Column(db.DateTime)  # For idle timeout tracking
    
    # Password reset fields
    reset_token_hash = db.Column(db.String(255), nullable=True)  # Hashed reset token
    reset_token_expiry = db.Column(db.DateTime, nullable=True)  # Token expiration time
    reset_token_used = db.Column(db.Boolean, default=False)  # One-time use flag
    
    # Push notification preference (user's choice to receive notifications)
    push_enabled = db.Column(db.Boolean, default=True)  # User preference for push notifications
    
    business = db.relationship("Business", backref="users")
    
    # ✅ Optional properties for first_name/last_name split (if needed by downstream code)
    @property
    def first_name(self):
        """Parse first name from full name"""
        if not self.name:
            return None
        parts = self.name.split(' ', 1)
        return parts[0] if parts else None
    
    @property
    def last_name(self):
        """Parse last name from full name"""
        if not self.name:
            return None
        parts = self.name.split(' ', 1)
        return parts[1] if len(parts) > 1 else None

class RefreshToken(db.Model):
    """
    Refresh tokens for session management
    Implements secure token storage with hashing and expiry
    Each token tracks its own activity for per-session idle timeout
    """
    __tablename__ = "refresh_tokens"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True, index=True)
    
    # Token storage (hashed for security)
    token_hash = db.Column(db.String(255), nullable=False, unique=True, index=True)
    
    # Security binding
    user_agent_hash = db.Column(db.String(255), nullable=True)  # Hash of user agent string
    
    # Expiry and validity
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    is_valid = db.Column(db.Boolean, default=True, index=True)
    
    # Remember me flag
    remember_me = db.Column(db.Boolean, default=False)
    
    # Per-session activity tracking for idle timeout
    last_activity_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_used_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship("User", backref="refresh_tokens")
    tenant = db.relationship("Business")
    
    def is_expired(self):
        """Check if token is expired"""
        return datetime.utcnow() > self.expires_at
    
    def is_idle(self, idle_minutes: int = 75) -> bool:
        """Check if token has been idle too long"""
        if not self.last_activity_at:
            return False
        idle_duration = datetime.utcnow() - self.last_activity_at
        return (idle_duration.total_seconds() / 60) > idle_minutes
    
    def __repr__(self):
        return f"<RefreshToken {self.id} user_id={self.user_id} expires={self.expires_at}>"

class CallSession(db.Model):
    """✨ Call session state - for appointment deduplication and tracking"""
    __tablename__ = "call_session"
    id = db.Column(db.Integer, primary_key=True)
    call_sid = db.Column(db.String(64), unique=True, nullable=True, index=True)  # Nullable for outbound calls
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True, index=True)
    
    # Appointment deduplication - prevent creating same appointment twice
    last_requested_slot = db.Column(db.String(100))  # ISO datetime: "2025-11-19T18:00:00+02:00"
    last_confirmed_slot = db.Column(db.String(100))  # ISO datetime: "2025-11-19T18:00:00+02:00"
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AgentTrace(db.Model):
    """✨ BUILD 119: Agent action traces - מעקב אחר פעולות Agent"""
    __tablename__ = "agent_trace"
    id = db.Column(db.Integer, primary_key=True)
    
    # Context
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    agent_type = db.Column(db.String(64), nullable=False)  # booking/sales
    channel = db.Column(db.String(32), nullable=False)  # calls/whatsapp/api
    
    # Customer info
    customer_phone = db.Column(db.String(64), index=True)
    customer_name = db.Column(db.String(255))
    
    # User input
    user_message = db.Column(db.Text, nullable=False)
    
    # Agent response
    agent_response = db.Column(db.Text)
    
    # Tool calls (JSON array)
    tool_calls = db.Column(db.JSON)  # [{"tool": "calendar.create_appointment", "status": "success", "result": {...}}]
    tool_count = db.Column(db.Integer, default=0)
    
    # Status
    status = db.Column(db.String(32), default="success")  # success/error/fallback
    error_message = db.Column(db.Text)
    
    # Performance
    duration_ms = db.Column(db.Integer)  # Response time in milliseconds
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<AgentTrace {self.id} - {self.agent_type} - {self.tool_count} tools>"


class RecordingRun(db.Model):
    """
    Recording Run - tracks background recording download/transcription jobs
    RQ Worker-based execution with progress tracking and cancellation support
    """
    __tablename__ = "recording_runs"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    call_sid = db.Column(db.String(64), nullable=False, index=True)  # Twilio Call SID
    recording_sid = db.Column(db.String(64), nullable=True)  # Twilio Recording SID (if available)
    recording_url = db.Column(db.String(512), nullable=True)
    
    # Status tracking
    status = db.Column(db.String(32), nullable=False, default='queued')  # queued|running|completed|failed|cancelled
    cancel_requested = db.Column(db.Boolean, default=False, nullable=False)
    
    # Job metadata
    job_type = db.Column(db.String(32), default='download')  # 'download' or 'full' (download+transcribe)
    
    # Error tracking
    error_message = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("recording_runs", lazy="dynamic"))
    
    __table_args__ = (
        db.Index('idx_recording_runs_business_status', 'business_id', 'status'),
        db.Index('idx_recording_runs_call_sid', 'call_sid'),
        db.CheckConstraint("status IN ('queued', 'running', 'completed', 'failed', 'cancelled')", name='chk_recording_run_status'),
    )


class OutboundCallRun(db.Model):
    """Bulk outbound calling campaign/run tracking"""
    __tablename__ = "outbound_call_runs"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    outbound_list_id = db.Column(db.Integer, db.ForeignKey("outbound_lead_lists.id"), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # User who created the run
    
    # Configuration
    concurrency = db.Column(db.Integer, default=3)
    total_leads = db.Column(db.Integer, default=0)
    
    # Progress tracking
    queued_count = db.Column(db.Integer, default=0)
    in_progress_count = db.Column(db.Integer, default=0)
    completed_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    cursor_position = db.Column(db.Integer, default=0)  # Current position in queue for resume
    
    # Status
    status = db.Column(db.String(32), default="pending")  # pending|running|completed|failed|cancelled|paused
    cancel_requested = db.Column(db.Boolean, default=False, nullable=False)  # User requested cancellation
    last_error = db.Column(db.Text)
    
    # Worker coordination
    locked_by_worker = db.Column(db.String(128), nullable=True)  # Worker ID holding the lock
    lock_ts = db.Column(db.DateTime, nullable=True)  # Lock timestamp for timeout detection
    last_heartbeat_at = db.Column(db.DateTime, nullable=True)  # Last worker heartbeat (for stale detection)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)  # When run actually started processing
    ended_at = db.Column(db.DateTime, nullable=True)  # When run finished (completed/cancelled/failed)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(db.DateTime)  # Legacy field, use ended_at instead


class OutboundCallJob(db.Model):
    """Individual call job within a bulk run"""
    __tablename__ = "outbound_call_jobs"
    __table_args__ = (
        db.UniqueConstraint('run_id', 'lead_id', name='unique_run_lead'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(db.Integer, db.ForeignKey("outbound_call_runs.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)  # Business isolation
    call_log_id = db.Column(db.Integer, db.ForeignKey("call_log.id"), nullable=True)
    project_id = db.Column(db.Integer, nullable=True, index=True)  # Project ID for calls initiated from projects (FK to outbound_projects)
    
    # Status
    status = db.Column(db.String(32), default="queued", index=True)  # queued|dialing|calling|completed|failed
    error_message = db.Column(db.Text)
    
    # Call details
    call_sid = db.Column(db.String(64))
    
    # 🔒 BUILD: Deduplication fields for preventing duplicate calls
    twilio_call_sid = db.Column(db.String(64), nullable=True, index=True)  # Twilio call SID for idempotency
    dial_started_at = db.Column(db.DateTime, nullable=True)  # When dial attempt started
    dial_lock_token = db.Column(db.String(64), nullable=True, index=True)  # UUID for atomic locking
    
    # 🔥 NAME SSOT: Lead name cached for NAME_ANCHOR system
    lead_name = db.Column(db.String(255), nullable=True)  # Lead name cached from Lead table
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Relationships
    run = db.relationship("OutboundCallRun", backref="jobs")
    lead = db.relationship("Lead")


class WhatsAppBroadcast(db.Model):
    """WhatsApp Broadcast Campaign"""
    __tablename__ = "whatsapp_broadcasts"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Campaign details
    name = db.Column(db.String(255))
    provider = db.Column(db.String(32))  # meta|baileys
    message_type = db.Column(db.String(32))  # template|freetext
    template_id = db.Column(db.String(255))
    template_name = db.Column(db.String(255))
    message_text = db.Column(db.Text)
    
    # Audience
    audience_filter = db.Column(db.JSON)  # Statuses, tags, etc.
    
    # Status and progress
    # ✅ ENHANCEMENT 1: Clear status progression: accepted → queued → running → completed/failed/partial/cancelled
    status = db.Column(db.String(32), default="accepted", index=True)  # accepted|queued|running|completed|failed|paused|partial|cancelled
    total_recipients = db.Column(db.Integer, default=0)
    processed_count = db.Column(db.Integer, default=0)  # Total processed (sent+failed+cancelled)
    sent_count = db.Column(db.Integer, default=0)
    failed_count = db.Column(db.Integer, default=0)
    cancelled_count = db.Column(db.Integer, default=0)  # Recipients cancelled before sending
    
    # ✅ Cancel support: Real cancel that worker respects
    cancel_requested = db.Column(db.Boolean, default=False, nullable=False)  # User requested cancellation
    
    # ✅ ENHANCEMENT 3: Idempotency key to prevent duplicates
    idempotency_key = db.Column(db.String(64), index=True)
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # 🔥 FIX: Added missing field
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    stopped_by = db.Column(db.Integer, db.ForeignKey("users.id"))  # User who stopped the broadcast
    stopped_at = db.Column(db.DateTime)  # When the broadcast was stopped
    
    # Relationships
    business = db.relationship("Business")
    creator = db.relationship("User", foreign_keys=[created_by])
    stopper = db.relationship("User", foreign_keys=[stopped_by])


class WhatsAppBroadcastRecipient(db.Model):
    """Individual recipient in a broadcast campaign"""
    __tablename__ = "whatsapp_broadcast_recipients"
    
    id = db.Column(db.Integer, primary_key=True)
    broadcast_id = db.Column(db.Integer, db.ForeignKey("whatsapp_broadcasts.id"), nullable=False, index=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Recipient details
    phone = db.Column(db.String(64), nullable=False)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=True)
    
    # Status
    # ✅ ENHANCEMENT 1: Clear status progression: queued → processing → sent → delivered/failed/cancelled
    status = db.Column(db.String(32), default="queued", index=True)  # queued|processing|sent|delivered|failed|cancelled
    error_message = db.Column(db.Text)
    
    # Message details
    message_id = db.Column(db.String(255))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)  # ✅ ENHANCEMENT 1: Track delivery if available
    
    # Relationships
    broadcast = db.relationship("WhatsAppBroadcast", backref="recipients")
    lead = db.relationship("Lead")


# === AI TOPIC CLASSIFICATION SYSTEM ===

class BusinessTopic(db.Model):
    """Business topics for AI-based classification of calls/conversations"""
    __tablename__ = "business_topics"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    
    # Topic details
    name = db.Column(db.String(255), nullable=False)  # e.g., "פורץ מנעולים"
    synonyms = db.Column(db.JSON, nullable=True)  # JSONB array of synonyms for better matching
    
    # Service type mapping - maps topic to canonical service_type for lead
    # e.g., topic "locksmith" → service_type "מנעולן"
    canonical_service_type = db.Column(db.String(255), nullable=True)  # Canonical service type this topic maps to
    
    # Embedding for semantic search - stored as JSONB array of floats
    embedding = db.Column(db.JSON, nullable=True)  # JSONB array [float, float, ...] - 1536 dimensions for text-embedding-3-small
    
    # Status
    is_active = db.Column(db.Boolean, default=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="topics")
    
    __table_args__ = (
        db.Index('idx_business_topic_active', 'business_id', 'is_active'),
    )


class BusinessAISettings(db.Model):
    """AI settings for topic classification and embedding"""
    __tablename__ = "business_ai_settings"
    
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), primary_key=True)
    
    # Embedding settings - NO API KEY stored here (use ENV vars)
    embedding_enabled = db.Column(db.Boolean, default=False)  # Enable topic classification
    embedding_threshold = db.Column(db.Float, default=0.78)  # Minimum confidence score (0.0-1.0)
    embedding_top_k = db.Column(db.Integer, default=3)  # Number of top matches to consider
    
    # Auto-tagging settings
    auto_tag_leads = db.Column(db.Boolean, default=True)  # Automatically tag leads with detected topic
    auto_tag_calls = db.Column(db.Boolean, default=True)  # Automatically tag calls with detected topic
    auto_tag_whatsapp = db.Column(db.Boolean, default=False)  # Automatically tag WhatsApp conversations
    
    # Service type mapping from topics
    # When enabled and topic has canonical_service_type, update lead.service_type
    map_topic_to_service_type = db.Column(db.Boolean, default=False)  # Map detected topic to lead.service_type
    service_type_min_confidence = db.Column(db.Float, default=0.75)  # Minimum confidence to map topic to service_type
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="ai_settings", uselist=False)


# === PUSH NOTIFICATIONS SYSTEM ===

class PushSubscription(db.Model):
    """
    Push notification subscriptions for users
    Supports: webpush (Web Push API), fcm (Firebase Cloud Messaging), apns (Apple Push)
    """
    __tablename__ = "push_subscriptions"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Channel type: webpush | fcm | apns
    channel = db.Column(db.String(16), nullable=False, default="webpush")
    
    # WebPush subscription data
    endpoint = db.Column(db.Text, nullable=False)  # Push service endpoint URL
    p256dh = db.Column(db.Text)  # Public key for encryption
    auth = db.Column(db.Text)  # Auth secret for encryption
    
    # Device info (user agent, platform)
    device_info = db.Column(db.String(512))
    
    # Active status
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="push_subscriptions")
    user = db.relationship("User", backref="push_subscriptions")
    
    # Unique constraint: one endpoint per user
    __table_args__ = (
        db.UniqueConstraint('user_id', 'endpoint', name='uq_push_subscription_user_endpoint'),
    )


class ReminderPushLog(db.Model):
    """
    Track sent reminder push notifications to prevent duplicates.
    Uses DB-backed deduplication to work correctly with multiple workers/replicas.
    """
    __tablename__ = "reminder_push_log"
    
    id = db.Column(db.Integer, primary_key=True)
    reminder_id = db.Column(db.Integer, db.ForeignKey("lead_reminders.id", ondelete="CASCADE"), nullable=False, index=True)
    offset_minutes = db.Column(db.Integer, nullable=False)  # 30 or 15
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Unique constraint: one notification per reminder per offset
    __table_args__ = (
        db.UniqueConstraint('reminder_id', 'offset_minutes', name='uq_reminder_push_log'),
        db.Index('idx_reminder_push_log_sent_at', 'sent_at'),  # For cleanup queries
    )


# =============================================================================
# ISO 27001 SECURITY EVENT LOGGING
# =============================================================================

class SecurityEvent(db.Model):
    """
    Security Events Table - ISO 27001 Compliance
    
    Tracks all security-related events for audit, compliance, and incident response.
    Required for:
    - A.12.4 Logging and monitoring
    - A.16 Information security incident management
    - Audit readiness and evidence collection
    """
    __tablename__ = "security_events"
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Multi-tenant: Some events are system-wide (NULL), some are tenant-specific
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True, index=True)
    
    # Event classification
    event_type = db.Column(db.String(64), nullable=False, index=True)  # auth_failure, access_denied, data_access, config_change, etc.
    severity = db.Column(db.String(16), nullable=False, default="low", index=True)  # critical, high, medium, low
    
    # Event details
    description = db.Column(db.Text, nullable=False)
    
    # Impact assessment (for incidents)
    impact = db.Column(db.Text, nullable=True)  # Business impact assessment
    
    # Response and resolution
    response = db.Column(db.Text, nullable=True)  # Actions taken
    lessons_learned = db.Column(db.Text, nullable=True)  # Post-incident findings
    
    # Status tracking
    status = db.Column(db.String(32), default="open", index=True)  # open, investigating, mitigated, resolved, closed
    
    # User context
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    user_email = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(64), nullable=True)
    user_agent = db.Column(db.String(512), nullable=True)
    
    # Resource context
    resource_type = db.Column(db.String(64), nullable=True)  # user, lead, call, etc.
    resource_id = db.Column(db.String(64), nullable=True)
    
    # Request context
    endpoint = db.Column(db.String(255), nullable=True)
    method = db.Column(db.String(16), nullable=True)  # GET, POST, PUT, DELETE
    
    # Additional metadata as JSON
    event_metadata = db.Column(db.JSON, nullable=True)  # Flexible additional data
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Assignment for incident response
    assigned_to_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("security_events", lazy="dynamic"), foreign_keys=[business_id])
    reporter = db.relationship("User", backref=db.backref("reported_security_events", lazy="dynamic"), foreign_keys=[user_id])
    assigned_to = db.relationship("User", backref=db.backref("assigned_security_events", lazy="dynamic"), foreign_keys=[assigned_to_user_id])
    
    # Valid values for constrained fields
    SEVERITY_LEVELS = ('critical', 'high', 'medium', 'low')
    STATUS_VALUES = ('open', 'investigating', 'mitigated', 'resolved', 'closed')
    
    # Indexes and constraints for efficient querying and data integrity
    __table_args__ = (
        db.Index('idx_security_events_business_severity', 'business_id', 'severity'),
        db.Index('idx_security_events_status_created', 'status', 'created_at'),
        db.Index('idx_security_events_type_created', 'event_type', 'created_at'),
        db.CheckConstraint("severity IN ('critical', 'high', 'medium', 'low')", name='chk_security_events_severity'),
        db.CheckConstraint("status IN ('open', 'investigating', 'mitigated', 'resolved', 'closed')", name='chk_security_events_status'),
    )

class Attachment(db.Model):
    """
    Unified Attachments System - Single source for all file attachments
    Used by: Email, WhatsApp messages, Broadcasts, Receipts, Contracts
    
    Features:
    - Multi-tenant isolation (business_id)
    - Secure file storage with tenant-isolated paths
    - Channel compatibility tracking (email/whatsapp/broadcast)
    - Purpose-based file separation (receipts/contracts/emails/whatsapp/general)
    - Origin module tracking for security and audit
    - Soft delete support
    - Audit trail (uploaded_by, created_at)
    
    Security Model:
    - Purpose + origin_module provide double-verification
    - API must filter by purpose/context - no "show all" default
    - Multi-tenant isolation enforced at all queries
    """
    __tablename__ = "attachments"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # File metadata
    filename_original = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=False)
    file_size = db.Column(db.Integer, nullable=False)  # bytes
    
    # Storage
    storage_path = db.Column(db.String(512), nullable=False)  # Relative path: {business_id}/{purpose}/{yyyy}/{mm}/{attachment_id}.ext
    public_url = db.Column(db.String(512), nullable=True)  # Temporary signed URL (if applicable)
    
    # Purpose - file categorization for separation (SECURITY CRITICAL)
    # Values: general_upload, email_attachment, whatsapp_media, broadcast_media,
    #         contract_original, contract_signed, receipt_source, receipt_preview
    purpose = db.Column(db.String(50), nullable=False, default='general_upload', index=True)
    
    # Origin module - tracks which system created this file (AUDIT/SECURITY)
    # Values: uploads, email, whatsapp, broadcast, contracts, receipts
    origin_module = db.Column(db.String(50), nullable=True, index=True)
    
    # Channel compatibility - which channels support this file type/size
    channel_compatibility = db.Column(db.JSON, default={"email": True, "whatsapp": True, "broadcast": True})
    
    # Additional metadata (dimensions for images, duration for videos, etc.)
    # ⚠️ IMPORTANT: Named 'meta_json' to avoid SQLAlchemy reserved word 'metadata'
    # DB column is still named 'metadata' for backward compatibility
    meta_json = db.Column('metadata', db.JSON, nullable=True)
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("attachments", lazy="dynamic"), foreign_keys=[business_id])
    uploader = db.relationship("User", backref=db.backref("uploaded_attachments", lazy="dynamic"), foreign_keys=[uploaded_by])
    deleter = db.relationship("User", backref=db.backref("deleted_attachments", lazy="dynamic"), foreign_keys=[deleted_by])
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_attachments_business', 'business_id', 'created_at'),
        db.Index('idx_attachments_uploader', 'uploaded_by', 'created_at'),
        db.Index('idx_attachments_purpose', 'business_id', 'purpose', 'created_at'),
        db.Index('idx_attachments_origin', 'business_id', 'origin_module'),
    )


# === ASSETS LIBRARY (מאגר) ===

class AssetItem(db.Model):
    """
    Asset items for the Assets Library (מאגר)
    Stores properties, inventory, catalog items, or any business-specific items
    """
    __tablename__ = "asset_items"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Core fields
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    tags = db.Column(db.JSON, default=list)  # Array of tags for filtering
    category = db.Column(db.String(64), nullable=True)  # e.g., "דירה", "מוצר", "שירות"
    
    # Status
    status = db.Column(db.String(16), nullable=False, default="active")  # active|archived
    
    # Custom fields for business-specific data
    custom_fields = db.Column(db.JSON, nullable=True)  # Dynamic key-value fields
    
    # Audit fields
    created_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("asset_items", lazy="dynamic"))
    creator = db.relationship("User", foreign_keys=[created_by], backref=db.backref("created_assets", lazy="dynamic"))
    updater = db.relationship("User", foreign_keys=[updated_by], backref=db.backref("updated_assets", lazy="dynamic"))
    media = db.relationship("AssetItemMedia", backref="asset_item", lazy="dynamic", cascade="all, delete-orphan")
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_asset_items_business_updated', 'business_id', 'updated_at'),
        db.Index('idx_asset_items_business_status_category', 'business_id', 'status', 'category'),
        db.CheckConstraint("status IN ('active', 'archived')", name='chk_asset_item_status'),
    )


class AssetItemMedia(db.Model):
    """
    Media attachments for asset items
    Links AssetItem to Attachment (R2 storage)
    """
    __tablename__ = "asset_item_media"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_item_id = db.Column(db.Integer, db.ForeignKey("asset_items.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Media role
    role = db.Column(db.String(32), nullable=False, default="gallery")  # cover|gallery|floorplan|other
    sort_order = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("asset_media", lazy="dynamic"))
    attachment = db.relationship("Attachment", backref=db.backref("asset_item_media", lazy="dynamic"))
    
    # Indexes for efficient querying
    __table_args__ = (
        db.Index('idx_asset_item_media_sort', 'asset_item_id', 'sort_order'),
        db.CheckConstraint("role IN ('cover', 'gallery', 'floorplan', 'other')", name='chk_asset_media_role'),
    )


# === GMAIL RECEIPTS SYSTEM ===

class GmailConnection(db.Model):
    """
    Gmail OAuth connections for businesses
    Stores encrypted refresh tokens for accessing Gmail API
    Multi-tenant: Each business can have one Gmail connection
    """
    __tablename__ = "gmail_connections"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Google OAuth fields
    email_address = db.Column(db.String(255), nullable=False)  # Connected Gmail address
    google_sub = db.Column(db.String(255), nullable=True)  # Google user ID
    refresh_token_encrypted = db.Column(db.Text, nullable=False)  # Encrypted refresh token
    
    # Connection status
    status = db.Column(db.String(32), nullable=False, default="connected")  # connected|disconnected|error
    error_message = db.Column(db.Text, nullable=True)  # Last error if status is 'error'
    
    # Sync tracking
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_history_id = db.Column(db.String(64), nullable=True)  # Gmail history ID for incremental sync
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("gmail_connection", uselist=False, lazy="joined"))
    
    # Status constraints
    __table_args__ = (
        db.CheckConstraint("status IN ('connected', 'disconnected', 'error')", name='chk_gmail_connection_status'),
    )


class Receipt(db.Model):
    """
    Receipts extracted from Gmail
    Stores metadata about receipts and links to attachment storage
    Multi-tenant with unique constraint on gmail_message_id per business
    
    New Features:
    - Email content storage for HTML→PNG rendering
    - Preview attachment ID for thumbnails
    """
    __tablename__ = "receipts"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Source identification
    source = db.Column(db.String(32), nullable=False, default="gmail")  # gmail|manual|upload
    gmail_message_id = db.Column(db.String(255), nullable=True, index=True)  # Unique Gmail message ID
    gmail_thread_id = db.Column(db.String(255), nullable=True)
    
    # Email metadata (legacy fields - kept for backward compatibility)
    from_email = db.Column(db.String(255), nullable=True)
    subject = db.Column(db.String(500), nullable=True)
    received_at = db.Column(db.DateTime, nullable=True, index=True)
    
    # Email content for preview generation
    email_subject = db.Column(db.String(500), nullable=True)
    email_from = db.Column(db.String(255), nullable=True)
    email_date = db.Column(db.DateTime, nullable=True)
    email_html_snippet = db.Column(db.Text, nullable=True)  # HTML content for HTML→PNG rendering
    
    # Extracted receipt data
    vendor_name = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(12, 2), nullable=True)  # Extracted amount
    currency = db.Column(db.String(3), nullable=False, default="ILS")
    invoice_number = db.Column(db.String(100), nullable=True)
    invoice_date = db.Column(db.Date, nullable=True)
    
    # AI extraction confidence
    confidence = db.Column(db.Integer, nullable=True)  # 0-100 confidence score
    raw_extraction_json = db.Column(db.JSON, nullable=True)  # Full extraction results
    
    # Status management
    status = db.Column(db.String(32), nullable=False, default="pending_review")  # pending_review|approved|rejected|not_receipt
    needs_review = db.Column(db.Boolean, default=False)  # True if confidence too low or missing critical data
    receipt_type = db.Column(db.String(32), nullable=True)  # confirmation|receipt|invoice|statement (for filtering)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    
    # Attachment references (via unified attachments system)
    attachment_id = db.Column(db.Integer, db.ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True, index=True)  # Original attachment
    preview_attachment_id = db.Column(db.Integer, db.ForeignKey("attachments.id", ondelete="SET NULL"), nullable=True, index=True)  # Preview/thumbnail
    
    # Preview tracking (Migration 91)
    preview_status = db.Column(db.String(20), nullable=False, default='pending')  # pending|generated|failed|not_available|skipped
    preview_failure_reason = db.Column(db.Text, nullable=True)  # Error message if preview generation failed
    
    # Enhanced preview tracking (Migration 101)
    preview_image_key = db.Column(db.String(512), nullable=True)  # Direct R2 storage key for preview image (mandatory after processing)
    preview_source = db.Column(db.String(32), nullable=True)  # email_html|attachment_pdf|attachment_image|receipt_url|html_fallback
    
    # Extraction tracking (Migration 101)
    extraction_status = db.Column(db.String(32), nullable=False, default='pending')  # pending|processing|success|needs_review|failed
    extraction_error = db.Column(db.Text, nullable=True)  # Detailed error message for failed extractions
    
    # Soft delete
    is_deleted = db.Column(db.Boolean, default=False, index=True)
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("receipts", lazy="dynamic"))
    reviewer = db.relationship("User", backref=db.backref("reviewed_receipts", lazy="dynamic"))
    attachment = db.relationship("Attachment", backref=db.backref("receipts", lazy="dynamic"), foreign_keys=[attachment_id])
    preview_attachment = db.relationship("Attachment", foreign_keys=[preview_attachment_id])
    
    # Indexes for efficient querying
    # Note: PostgreSQL allows multiple NULLs in unique constraint by default,
    # but we use a partial unique index in migration for explicit control
    __table_args__ = (
        db.Index('idx_receipts_business_received', 'business_id', 'received_at'),
        db.Index('idx_receipts_business_status', 'business_id', 'status'),
        db.Index('idx_receipts_preview_attachment', 'preview_attachment_id'),
        db.CheckConstraint("status IN ('pending_review', 'approved', 'rejected', 'not_receipt', 'incomplete')", name='chk_receipt_status'),
        db.CheckConstraint("source IN ('gmail', 'manual', 'upload')", name='chk_receipt_source'),
    )


class ReceiptSyncRun(db.Model):
    """
    Receipt Sync Run tracking for long-running Gmail sync jobs
    Allows monitoring progress and resuming interrupted syncs
    """
    __tablename__ = "receipt_sync_runs"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Sync configuration
    mode = db.Column(db.String(20), nullable=False, default='incremental')  # full|incremental
    from_date = db.Column(db.Date, nullable=True)  # Start date for date range syncs
    to_date = db.Column(db.Date, nullable=True)  # End date for date range syncs
    months_back = db.Column(db.Integer, nullable=True)  # Months to go back for backfill
    run_to_completion = db.Column(db.Boolean, nullable=True)  # If True, ignore time limits (nullable to distinguish unset)
    max_seconds_per_run = db.Column(db.Integer, nullable=True)  # Per-run time limit
    
    # Progress tracking
    status = db.Column(db.String(20), nullable=False, default='running')  # running|paused|completed|failed|cancelled
    cancel_requested = db.Column(db.Boolean, default=False, nullable=False)  # User requested cancellation
    started_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)  # When cancellation was requested
    last_heartbeat_at = db.Column(db.DateTime, nullable=True, index=True)  # Last activity timestamp for stale run detection
    
    # Counters
    pages_scanned = db.Column(db.Integer, default=0)
    messages_scanned = db.Column(db.Integer, default=0)
    candidate_receipts = db.Column(db.Integer, default=0)
    saved_receipts = db.Column(db.Integer, default=0)
    skipped_count = db.Column(db.Integer, default=0)  # Messages skipped (already processed)
    preview_generated_count = db.Column(db.Integer, default=0)
    errors_count = db.Column(db.Integer, default=0)
    
    # State for resumable syncs
    last_page_token = db.Column(db.String(255), nullable=True)
    last_internal_date = db.Column(db.String(50), nullable=True)
    current_month = db.Column(db.String(10), nullable=True)  # For monthly backfill tracking (YYYY-MM format)
    
    # Error tracking
    error_message = db.Column(db.Text, nullable=True)
    
    # Audit
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("receipt_sync_runs", lazy="dynamic"))
    
    # Indexes
    __table_args__ = (
        db.Index('idx_receipt_sync_runs_business', 'business_id', 'started_at'),
        db.Index('idx_receipt_sync_runs_status', 'status', 'started_at'),
        db.CheckConstraint("mode IN ('full', 'full_backfill', 'incremental')", name='chk_receipt_sync_mode'),
        db.CheckConstraint("status IN ('running', 'paused', 'completed', 'failed', 'cancelled')", name='chk_receipt_sync_status'),
    )


class BackgroundJob(db.Model):
    """
    Background Jobs tracking for heavy batch operations
    Supports stable, resumable batch processing with progress tracking
    
    Features:
    - Multi-tenant isolation (business_id)
    - Job status tracking (queued/running/paused/completed/failed/cancelled)
    - Progress tracking (total/processed/succeeded/failed_count)
    - Cursor-based resumability for interrupted jobs
    - Prevents concurrent jobs per business (unique partial index)
    
    Use cases:
    - delete_receipts_all: Batch delete all receipts with progress
    """
    __tablename__ = "background_jobs"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    requested_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Job identification
    job_type = db.Column(db.String(64), nullable=False)  # e.g., 'delete_receipts_all'
    
    # Progress tracking
    status = db.Column(db.String(32), nullable=False, default='queued')  # queued|running|paused|completed|failed|cancelled
    total = db.Column(db.Integer, default=0)  # Total items to process
    processed = db.Column(db.Integer, default=0)  # Items processed so far
    succeeded = db.Column(db.Integer, default=0)  # Items successfully processed
    failed_count = db.Column(db.Integer, default=0)  # Items that failed
    
    # Error tracking
    last_error = db.Column(db.Text, nullable=True)  # Last error message
    
    # Resumability - stores state for continuing interrupted jobs
    cursor = db.Column(db.Text, nullable=True)  # JSON string storing position (e.g., {"last_id": 12345})
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    heartbeat_at = db.Column(db.DateTime, nullable=True)  # For stale job detection
    
    # Relationships
    business = db.relationship("Business", backref=db.backref("background_jobs", lazy="dynamic"))
    requested_by = db.relationship("User", backref=db.backref("requested_jobs", lazy="dynamic"))
    
    # Computed property for progress percentage
    @property
    def percent(self):
        """Calculate completion percentage"""
        if self.total == 0:
            return 0.0
        return round((self.processed / self.total) * 100, 1)
    
    # Indexes and constraints
    # Note: Unique partial index is created in migration (idx_background_jobs_unique_active)
    # to prevent concurrent jobs of same type per business
    __table_args__ = (
        db.Index('idx_background_jobs_business_type_status', 'business_id', 'job_type', 'status'),
        db.Index('idx_background_jobs_created_at', 'created_at'),
        db.CheckConstraint("status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled')", name='chk_job_status'),
        db.CheckConstraint("""job_type IN (
            'delete_receipts_all',
            'delete_leads', 
            'update_leads',
            'delete_imported_leads',
            'enqueue_outbound_calls',
            'broadcast'
        )""", name='chk_job_type'),
    )


# === SCHEDULED WHATSAPP MESSAGES SYSTEM ===

class ScheduledMessageRule(db.Model):
    """
    Scheduling rule defining "who, what, when" for WhatsApp messages
    Creates pending messages when leads enter specified statuses
    
    🎯 Multi-step support: Can have multiple steps (via ScheduledMessageRuleStep)
    Each step has its own delay and message template
    """
    __tablename__ = "scheduled_message_rules"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Rule configuration
    name = db.Column(db.String(255), nullable=False)  # User-friendly name
    is_active = db.Column(db.Boolean, default=True, index=True)  # Enable/disable rule
    
    # WhatsApp template to send (for future use - currently will send plain text)
    template_name = db.Column(db.String(255))  # Template identifier
    message_text = db.Column(db.Text, nullable=False)  # Message content (LEGACY - for backward compatibility)
    
    # Timing configuration
    delay_minutes = db.Column(db.Integer, nullable=False, default=0)  # Delay after status change (LEGACY - use delay_seconds)
    delay_seconds = db.Column(db.Integer, nullable=False, default=0)  # Delay after status change in seconds (LEGACY)
    send_window_start = db.Column(db.String(5))  # Optional: e.g., "09:00"
    send_window_end = db.Column(db.String(5))  # Optional: e.g., "20:00"
    
    # Provider selection for WhatsApp sending
    provider = db.Column(db.String(32), default="baileys")  # "baileys" | "meta" | "auto" - WhatsApp provider choice
    
    # Multi-step configuration (NEW)
    send_immediately_on_enter = db.Column(db.Boolean, default=False, nullable=False)  # Send message immediately on status change
    immediate_message = db.Column(db.Text, nullable=True)  # Message to send immediately (if different from message_text)
    apply_mode = db.Column(db.String(32), default="ON_ENTER_ONLY", nullable=False)  # "ON_ENTER_ONLY" | "WHILE_IN_STATUS"
    
    # Active weekdays: Array of integers 0-6 (0=Sunday, 6=Saturday) or null for always active
    # Example: [0,1,2,3,4] = Sunday-Thursday only
    active_weekdays = db.Column(db.JSON, nullable=True, default=None)  # null = all days, [0,1,2,3,4] = specific days
    
    # Excluded weekdays: Array of integers 0-6 (0=Sunday, 6=Saturday) to exclude from automation
    # Example: [5,6] = exclude Friday and Saturday
    excluded_weekdays = db.Column(db.JSON, nullable=True, default=None)  # null = no exclusions, [5,6] = exclude specific days
    
    # Recurring schedule configuration (NEW)
    schedule_type = db.Column(db.String(32), default="STATUS_CHANGE", nullable=False)  # "STATUS_CHANGE" | "RECURRING_TIME"
    recurring_times = db.Column(db.JSON, nullable=True, default=None)  # Array of times in "HH:MM" format, e.g. ["09:00", "15:00"]
    
    # Metadata
    created_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="scheduled_message_rules")
    created_by = db.relationship("User", backref="created_scheduled_rules")
    statuses = db.relationship(
        "LeadStatus",
        secondary="scheduled_rule_statuses",
        backref="scheduled_rules"
    )
    steps = db.relationship("ScheduledMessageRuleStep", backref="rule", cascade="all, delete-orphan", order_by="ScheduledMessageRuleStep.step_index")
    scheduled_messages = db.relationship("ScheduledMessagesQueue", backref="rule", cascade="all, delete-orphan")
    
    __table_args__ = (
        db.Index('idx_business_active', 'business_id', 'is_active'),
    )


class ScheduledRuleStatus(db.Model):
    """
    Junction table: many-to-many relationship between rules and lead statuses
    A rule can trigger on multiple statuses, and a status can have multiple rules
    """
    __tablename__ = "scheduled_rule_statuses"
    
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("scheduled_message_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    status_id = db.Column(db.Integer, db.ForeignKey("lead_statuses.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Unique constraint: one rule-status pair only
    __table_args__ = (
        db.UniqueConstraint('rule_id', 'status_id', name='_rule_status_uc'),
    )


class ScheduledMessageRuleStep(db.Model):
    """
    Individual step in a multi-step scheduled message sequence
    Each rule can have multiple steps with different delays and messages
    """
    __tablename__ = "scheduled_message_rule_steps"
    
    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("scheduled_message_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    step_index = db.Column(db.Integer, nullable=False)  # 1, 2, 3, etc. (1-indexed for display)
    message_template = db.Column(db.Text, nullable=False)  # Message content with optional variables
    delay_seconds = db.Column(db.Integer, nullable=False, default=0)  # Delay after status change
    enabled = db.Column(db.Boolean, nullable=False, default=True)  # Can disable individual steps
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: one step index per rule
    __table_args__ = (
        db.UniqueConstraint('rule_id', 'step_index', name='_rule_step_uc'),
        db.Index('idx_rule_steps_rule_step', 'rule_id', 'step_index'),
    )


class ScheduledMessagesQueue(db.Model):
    """
    Queue of scheduled WhatsApp messages to be sent
    Each row represents one future send for a specific lead
    Can be linked to a specific step in a multi-step sequence
    """
    __tablename__ = "scheduled_messages_queue"
    
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id", ondelete="CASCADE"), nullable=False, index=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("scheduled_message_rules.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = db.Column(db.Integer, db.ForeignKey("scheduled_message_rule_steps.id", ondelete="SET NULL"), nullable=True, index=True)  # NEW: Link to specific step
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)  # 🔥 FIX: Allow NULL when lead is deleted
    
    # Message details
    channel = db.Column(db.String(32), nullable=False, default='whatsapp')  # "whatsapp" - channel type
    provider = db.Column(db.String(32), nullable=False, default='baileys')  # "baileys" | "meta" - provider to use for sending
    message_text = db.Column(db.Text, nullable=False)  # Rendered message text
    remote_jid = db.Column(db.String(255), nullable=False)  # WhatsApp JID (phone@s.whatsapp.net)
    
    # Scheduling
    scheduled_for = db.Column(db.DateTime, nullable=False, index=True)  # When to send
    
    # Status tracking
    status = db.Column(
        db.String(20), 
        nullable=False, 
        default='pending',
        index=True
    )  # pending|sent|failed|canceled
    
    locked_at = db.Column(db.DateTime)  # Claim timestamp (prevents double-send)
    sent_at = db.Column(db.DateTime)  # Actual send timestamp
    error_message = db.Column(db.Text)  # Error details if failed
    attempts = db.Column(db.Integer, nullable=False, default=0)  # Number of send attempts
    
    # Deduplication key (CRITICAL for idempotency)
    dedupe_key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship("Business", backref="scheduled_messages")
    # rule relationship is now defined in ScheduledMessageRule with cascade
    step = db.relationship("ScheduledMessageRuleStep", backref="scheduled_messages")  # NEW: Link to step
    lead = db.relationship("Lead", backref="scheduled_messages")
    
    __table_args__ = (
        db.Index('idx_business_status_scheduled', 'business_id', 'status', 'scheduled_for'),
        db.Index('idx_rule_status', 'rule_id', 'status'),
    )
