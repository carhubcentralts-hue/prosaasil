"""
SQLAlchemy models for Hebrew AI Call Center CRM
Production-ready database models with proper relationships and indexing
"""
from server.db import db
from datetime import datetime

class Business(db.Model):
    __tablename__ = "businesses"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    business_type = db.Column(db.String(255), nullable=False, default="real_estate")
    phone_e164 = db.Column(db.String(255))  # ✅ Unified field name
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

class Customer(db.Model):
    __tablename__ = "customer"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    phone_e164 = db.Column(db.String(64), index=True)  # ✅ Unified field name
    email = db.Column(db.String(255))
    status = db.Column(db.String(64), default="new")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CallLog(db.Model):
    __tablename__ = "call_log"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("business.id"), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"))
    call_sid = db.Column(db.String(64), index=True)
    from_number = db.Column(db.String(64), index=True)
    recording_url = db.Column(db.String(512))
    transcription = db.Column(db.Text)
    status = db.Column(db.String(32), default="received")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# AI Prompt Management - לפי ההנחיות המדויקות
class BusinessSettings(db.Model):
    __tablename__ = "business_settings"
    tenant_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), primary_key=True)
    ai_prompt = db.Column(db.Text)
    updated_by = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PromptRevisions(db.Model):
    __tablename__ = "prompt_revisions"
    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False)
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
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
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

# === CRM MODELS לפי הנחיות 100% GO ===

class Deal(db.Model):
    __tablename__ = "deal"
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customer.id"), nullable=False, index=True)
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
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=False, index=True)
    invoice_number = db.Column(db.String(40), unique=True, index=True)
    subtotal = db.Column(db.Integer)
    tax = db.Column(db.Integer)
    total = db.Column(db.Integer)
    pdf_path = db.Column(db.String(260))  # נתיב יחסי ל-static
    issued_at = db.Column(db.DateTime, default=datetime.utcnow)

class Contract(db.Model):
    __tablename__ = "contract"
    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey("deal.id"), nullable=False, index=True)
    template_name = db.Column(db.String(80))
    version = db.Column(db.String(20), default='v1')
    html_path = db.Column(db.String(260))
    pdf_path = db.Column(db.String(260))
    signed_name = db.Column(db.String(160))
    signed_at = db.Column(db.DateTime)
    signed_ip = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# === CALENDAR & APPOINTMENTS ===

class Appointment(db.Model):
    __tablename__ = "appointments"
    id = db.Column(db.Integer, primary_key=True)
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=False, index=True)
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

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)  # Hashed - matches existing schema
    role = db.Column(db.String(64), default="business")  # admin/business
    business_id = db.Column(db.Integer, db.ForeignKey("businesses.id"), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)