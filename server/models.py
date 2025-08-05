# Import db from app to avoid circular imports
import sys
import os
sys.path.append(os.path.dirname(__file__))

# Import after adding path to avoid circular imports  
from app import db
from datetime import datetime
from sqlalchemy import Text, DateTime, Integer, String, Boolean, Float, JSON
from flask_login import UserMixin

class Customer(db.Model):
    """מודל לקוחות"""
    __tablename__ = 'customers'
    
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    phone = db.Column(String(20), nullable=False)
    email = db.Column(String(120))
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=False)
    
    # Additional customer info
    status = db.Column(String(20), default='active')  # active, inactive, blocked
    source = db.Column(String(50))  # call, whatsapp, website, referral
    
    # Tracking fields
    first_contact_date = db.Column(DateTime, default=datetime.utcnow)
    last_contact_date = db.Column(DateTime)
    total_calls = db.Column(Integer, default=0)
    total_messages = db.Column(Integer, default=0)
    
    # JSON field for interaction log
    interaction_log = db.Column(Text)  # JSON string for interaction history
    
    # Metadata
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    business = db.relationship('Business', backref='customers')
    
    def __repr__(self):
        return f'<Customer {self.name} - {self.phone}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'status': self.status,
            'source': self.source,
            'first_contact_date': self.first_contact_date.isoformat() if self.first_contact_date else None,
            'last_contact_date': self.last_contact_date.isoformat() if self.last_contact_date else None,
            'total_calls': self.total_calls,
            'total_messages': self.total_messages,
            'created_at': self.created_at.isoformat()
        }

class Business(db.Model):
    __tablename__ = 'businesses'  # CRITICAL FIX: Specify correct table name
    
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    business_type = db.Column(String(50))  # restaurant, clinic, store, etc.
    phone_israel = db.Column(String(50))  # FIXED: Match actual database field name
    phone_whatsapp = db.Column(String(50))  # FIXED: Match actual database field name  
    ai_prompt = db.Column(Text)  # FIXED: Match actual database field name
    greeting_message = db.Column(Text)
    calls_enabled = db.Column(Boolean, default=False)      # הרשאות שיחות AI
    whatsapp_enabled = db.Column(Boolean, default=False)   # הרשאות WhatsApp
    crm_enabled = db.Column(Boolean, default=False)        # הרשאות CRM
    is_active = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Business {self.id}: {self.name} ({self.business_type})>'

class CallLog(db.Model):
    id = db.Column(Integer, primary_key=True)
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=False)
    call_sid = db.Column(String(50), unique=True, nullable=False)
    from_number = db.Column(String(20), nullable=False)
    to_number = db.Column(String(20), nullable=False)
    call_status = db.Column(String(20), nullable=False)
    call_duration = db.Column(Integer)  # in seconds
    conversation_summary = db.Column(Text)
    recording_url = db.Column(String(500))  # CRITICAL FIX: URL to Twilio recording
    transcription = db.Column(Text)  # Hebrew transcription from Whisper
    ai_response = db.Column(Text)  # GPT-4o response in Hebrew
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    ended_at = db.Column(DateTime)
    
    def __init__(self, business_id=None, call_sid=None, from_number=None, to_number=None, call_status=None):
        self.business_id = business_id
        self.call_sid = call_sid
        self.from_number = from_number
        self.to_number = to_number
        self.call_status = call_status
    
    def __repr__(self):
        return f'<CallLog {self.id}: {self.call_sid} ({self.call_status})>'
    
    business = db.relationship('Business', backref=db.backref('calls', lazy=True))

class ConversationTurn(db.Model):
    __tablename__ = 'conversation_turns'
    
    id = db.Column(Integer, primary_key=True)
    call_log_id = db.Column(Integer, db.ForeignKey('call_log.id'), nullable=True)
    call_sid = db.Column(String(50), nullable=False)  # Add call_sid field
    speaker = db.Column(String(10), nullable=False)  # 'user' or 'ai'
    message = db.Column(Text, nullable=False)
    confidence_score = db.Column(Float)  # for speech recognition confidence
    timestamp = db.Column(DateTime, default=datetime.utcnow)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, call_log_id=None, call_sid=None, speaker=None, message=None, confidence_score=None):
        if call_log_id is not None:
            self.call_log_id = call_log_id
        if call_sid is not None:
            self.call_sid = call_sid
        if speaker is not None:
            self.speaker = speaker
        if message is not None:
            self.message = message
        if confidence_score is not None:
            self.confidence_score = confidence_score
    
    def __repr__(self):
        return f'<ConversationTurn {self.id}: {self.speaker} - {self.message[:50]}...>'
    
    call_log = db.relationship('CallLog', backref=db.backref('conversation_turns', lazy=True, order_by='ConversationTurn.timestamp'))

# WhatsApp Models
class WhatsAppConversation(db.Model):
    __tablename__ = 'whatsapp_conversation'
    
    id = db.Column(Integer, primary_key=True)
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=False)
    customer_number = db.Column(String(255), nullable=False)
    customer_name = db.Column(String(255))
    status = db.Column(String(50), default='active')
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, customer_number=None, business_id=None, status='active'):
        self.customer_number = customer_number
        self.business_id = business_id 
        self.status = status
        
    def __repr__(self):
        return f'<WhatsAppConversation {self.id}: {self.customer_number} ({self.status})>'
    
    business = db.relationship('Business', backref=db.backref('whatsapp_conversations', lazy=True))

class WhatsAppMessage(db.Model):
    __tablename__ = 'whatsapp_message'
    
    id = db.Column(Integer, primary_key=True)
    conversation_id = db.Column(Integer, db.ForeignKey('whatsapp_conversation.id'), nullable=False)
    message_sid = db.Column(String(255), unique=True)
    from_number = db.Column(String(255), nullable=False)
    to_number = db.Column(String(255), nullable=False)
    message_body = db.Column(Text)
    direction = db.Column(String(20), nullable=False)  # 'inbound' or 'outbound'
    status = db.Column(String(50), default='sent')
    error_code = db.Column(String(50))
    error_message = db.Column(Text)
    media_url = db.Column(Text)
    media_type = db.Column(String(100))
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=False)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    
    def __init__(self, conversation_id=None, message_sid=None, from_number=None, to_number=None, 
                 message_body=None, direction=None, status='sent', business_id=None):
        self.conversation_id = conversation_id
        self.message_sid = message_sid
        self.from_number = from_number
        self.to_number = to_number
        self.message_body = message_body
        self.direction = direction
        self.status = status
        self.business_id = business_id
    
    conversation = db.relationship('WhatsAppConversation', backref=db.backref('messages', lazy=True, order_by='WhatsAppMessage.created_at'))
    business = db.relationship('Business', backref=db.backref('whatsapp_messages', lazy=True))

class AppointmentRequest(db.Model):
    id = db.Column(Integer, primary_key=True)
    call_log_id = db.Column(Integer, db.ForeignKey('call_log.id'), nullable=True)
    whatsapp_conversation_id = db.Column(Integer, db.ForeignKey('whatsapp_conversation.id'), nullable=True)
    customer_name = db.Column(String(100))
    customer_phone = db.Column(String(20))
    requested_date = db.Column(DateTime)
    requested_service = db.Column(String(200))
    status = db.Column(String(20), default='pending')  # pending, confirmed, cancelled
    source = db.Column(String(20), default='phone')  # phone, whatsapp
    created_at = db.Column(DateTime, default=datetime.utcnow)
    
    def __init__(self, call_log_id=None, whatsapp_conversation_id=None, customer_name=None, 
                 customer_phone=None, requested_date=None, requested_service=None, 
                 status='pending', source='phone'):
        self.call_log_id = call_log_id
        self.whatsapp_conversation_id = whatsapp_conversation_id
        self.customer_name = customer_name
        self.customer_phone = customer_phone
        self.requested_date = requested_date
        self.requested_service = requested_service
        self.status = status
        self.source = source
    
    call_log = db.relationship('CallLog', backref=db.backref('appointment_requests', lazy=True))

# User Authentication Model
class User(UserMixin, db.Model):
    """מודל משתמש עם הפרדת תפקידים והרשאות"""
    id = db.Column(Integer, primary_key=True)
    username = db.Column(String(80), unique=True, nullable=False)
    email = db.Column(String(120), unique=True, nullable=False)
    password_hash = db.Column(String(256), nullable=False)
    role = db.Column(String(20), nullable=False, default='business')  # admin, business
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=True)
    is_active = db.Column(Boolean, default=True)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    last_login = db.Column(DateTime)
    
    # הרשאות ספציפיות לכל ערוץ תקשורת
    can_access_phone = db.Column(Boolean, default=True)  # גישה למערכת הטלפון
    can_access_whatsapp = db.Column(Boolean, default=True)  # גישה למערכת WhatsApp
    can_access_crm = db.Column(Boolean, default=True)  # גישה למערכת CRM
    can_manage_business = db.Column(Boolean, default=False)  # ניהול עסק (רק למנהל)
    
    # Relationship with business
    business = db.relationship('Business', backref=db.backref('users', lazy=True))
    
    def __init__(self, username=None, email=None, password_hash=None, role='business', 
                 business_id=None, is_active=True, can_access_phone=True, 
                 can_access_whatsapp=True, can_access_crm=True, can_manage_business=False):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.business_id = business_id
        self.is_active = is_active
        self.can_access_phone = can_access_phone
        self.can_access_whatsapp = can_access_whatsapp
        self.can_access_crm = can_access_crm
        self.can_manage_business = can_manage_business
    
    def has_phone_access(self):
        """בדיקה אם למשתמש יש גישה למערכת הטלפון"""
        return self.role == 'admin' or (self.can_access_phone and self.is_active)
    
    def has_whatsapp_access(self):
        """בדיקה אם למשתמש יש גישה למערכת WhatsApp"""
        return self.role == 'admin' or (self.can_access_whatsapp and self.is_active)
    
    def has_crm_access(self):
        """בדיקה אם למשתמש יש גישה למערכת CRM"""
        return self.role == 'admin' or (self.can_access_crm and self.is_active)
    
    def can_manage_businesses(self):
        """בדיקה אם המשתמש יכול לנהל עסקים"""
        return self.role == 'admin' and self.username == 'שי'

# CRM Models for Customer and Task Management  
class CRMCustomer(db.Model):
    """מודל לקוח למערכת CRM"""
    __tablename__ = 'crm_customer'
    
    id = db.Column(Integer, primary_key=True)
    name = db.Column(String(100), nullable=False)
    phone = db.Column(String(20), nullable=False)
    email = db.Column(String(120))
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=False)
    status = db.Column(String(20), default='active')  # active, inactive, prospect
    source = db.Column(String(50), default='phone')  # phone, whatsapp, manual
    notes = db.Column(Text)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    business = db.relationship('Business', backref=db.backref('crm_customers', lazy=True))
    
    def __repr__(self):
        return f'<CRMCustomer {self.name}: {self.phone}>'

class CRMTask(db.Model):
    """מודל משימות למערכת CRM"""
    __tablename__ = 'crm_task'
    id = db.Column(Integer, primary_key=True)
    title = db.Column(String(200), nullable=False)
    description = db.Column(Text)
    status = db.Column(String(20), default='pending')  # pending, in_progress, completed, cancelled
    priority = db.Column(String(20), default='medium')  # low, medium, high, urgent
    assigned_to = db.Column(String(100))  # Username of assigned user
    business_id = db.Column(Integer, db.ForeignKey('businesses.id'), nullable=False)
    customer_id = db.Column(Integer, db.ForeignKey('crm_customer.id'), nullable=True)
    due_date = db.Column(DateTime)
    created_at = db.Column(DateTime, default=datetime.utcnow)
    updated_at = db.Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = db.Column(DateTime)
    
    business = db.relationship('Business', backref=db.backref('tasks', lazy=True))
    customer = db.relationship('CRMCustomer', backref=db.backref('tasks', lazy=True))
    
    def __repr__(self):
        return f'<Task {self.title}: {self.status}>'


# מודל פגישות למערכת לוח השנה
class Appointment(db.Model):
    """מודל פגישות ותורים"""
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('crm_customer.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('businesses.id'), nullable=False)
    appointment_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    note = db.Column(db.Text)
    status = db.Column(db.String(50), default='scheduled')  # scheduled, confirmed, completed, cancelled
    reminder_sent = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # יחסים
    customer = db.relationship('CRMCustomer', backref='appointments')
    business = db.relationship('Business', backref='appointments')