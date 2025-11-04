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
    business_type = db.Column(db.String(255), nullable=False, default="real_estate")
    phone_e164 = db.Column('phone_number', db.String(255))  # ✅ Map to DB column phone_number
    whatsapp_number = db.Column(db.String(255))
    greeting_message = db.Column(db.Text)
    whatsapp_greeting = db.Column(db.Text)
    system_prompt = db.Column(db.Text)
    whatsapp_enabled = db.Column(db.Boolean, default=False)
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
    call_sid = db.Column(db.String(64), unique=True, index=True)  # ✅ Unique constraint to prevent duplicates
    from_number = db.Column(db.String(64), index=True)
    to_number = db.Column(db.String(64))  # ✅ BUILD 88: Added to_number field
    direction = db.Column(db.String(16), default="inbound")  # ✅ BUILD 106: inbound/outbound
    duration = db.Column(db.Integer, default=0)  # ✅ BUILD 106: Call duration in seconds
    call_status = db.Column(db.String(32), default="in-progress")  # ✅ BUILD 90: Legacy field for production DB compatibility
    recording_url = db.Column(db.String(512))
    transcription = db.Column(db.Text)
    summary = db.Column(db.Text)  # ✨ סיכום חכם קצר של השיחה (80-150 מילים) - BUILD 106
    status = db.Column(db.String(32), default="received")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    ai_prompt = db.Column(db.Text)
    model = db.Column(db.String(50), default="gpt-4o-mini")  # AI model for prompts
    max_tokens = db.Column(db.Integer, default=120)  # ⚡ BUILD 105: Optimized for faster responses (was 150)
    temperature = db.Column(db.Float, default=0.7)   # AI temperature setting (0-2)
    # Business settings
    phone_number = db.Column(db.String(255))  # Business phone number
    email = db.Column(db.String(255))  # Business email
    address = db.Column(db.String(500))  # Business address
    working_hours = db.Column(db.String(100))  # Business working hours
    timezone = db.Column(db.String(50), default="Asia/Jerusalem")  # Business timezone
    updated_by = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PromptRevisions(db.Model):
    __tablename__ = "prompt_revisions"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)  # auto-increment per tenant
    prompt = db.Column(db.Text)
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
    email = db.Column(db.String(255), index=True)
    
    # Lead tracking
    source = db.Column(db.String(32), default="form", index=True)  # call|whatsapp|form|manual
    external_id = db.Column(db.String(128), index=True)  # call_sid|wa_msg_id
    status = db.Column(db.String(32), default="new", index=True)  # Canonical lowercase: new|attempting|contacted|qualified|won|lost|unqualified
    order_index = db.Column(db.Integer, default=0, index=True)  # For Kanban board ordering within status
    
    # Assignment
    owner_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    
    # Metadata
    tags = db.Column(db.JSON)  # JSON array for flexible tagging
    notes = db.Column(db.Text)
    summary = db.Column(db.Text)  # ✨ סיכום חכם קצר (10-30 מילים) מכל השיחות
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_contact_at = db.Column(db.DateTime, index=True)
    
    # Computed properties
    @property
    def full_name(self):
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
    channel = db.Column(db.String(16), default="ui")  # ui|email|push|whatsapp
    
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

class LeadActivity(db.Model):
    """Activity timeline for leads"""
    __tablename__ = "lead_activities"
    
    id = db.Column(db.Integer, primary_key=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("leads.id"), nullable=False, index=True)
    
    type = db.Column(db.String(32), nullable=False, index=True)  # call|whatsapp|note|status_change|document|reminder
    payload = db.Column(db.JSON)  # Flexible data storage for different activity types
    
    at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))

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
    __tablename__ = "contract"
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True, index=True)  # nullable for direct contracts
    template_name = db.Column(db.String(80))
    template_id = db.Column(db.String(80))  # AgentKit: template identifier
    version = db.Column(db.String(20), default='v1')
    html_path = db.Column(db.String(260))
    pdf_path = db.Column(db.String(260))
    signed_name = db.Column(db.String(160))
    signed_at = db.Column(db.DateTime)
    signed_ip = db.Column(db.String(64))
    signature_data = db.Column(db.Text)  # Base64 encoded signature image
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # AgentKit additions
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey("appointments.id"), nullable=True, index=True)
    customer_name = db.Column(db.String(255))
    content = db.Column(db.Text)  # Contract content (filled template)
    status = db.Column(db.String(32), default="pending_signature")  # pending_signature/signed/cancelled
    variables = db.Column(db.JSON)  # Template variables as JSON

# === CALENDAR & APPOINTMENTS ===

class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=True, index=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=True, index=True)
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
    appointment_type = db.Column(db.String(64), default="viewing")  # viewing/meeting/signing/call_followup
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
    
    # Metadata
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # AI-generated flag (if appointment was auto-created from call/WhatsApp)
    auto_generated = db.Column(db.Boolean, default=False)
    source = db.Column(db.String(32), default="manual")  # manual/phone_call/whatsapp/ai_suggested

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
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)  # Hashed - matches existing schema
    role = db.Column(db.String(64), default="business")  # admin/business
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

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