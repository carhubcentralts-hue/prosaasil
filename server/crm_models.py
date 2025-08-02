"""
CRM Models Extension
מודלים נוספים למערכת CRM מתקדמת
"""

from app import db
from datetime import datetime
import json

class CustomerTask(db.Model):
    """מודל למשימות לקוחות"""
    __tablename__ = 'customer_tasks'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Task Details
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(20), default='medium')  # low, medium, high, urgent
    status = db.Column(db.String(20), default='pending')   # pending, in_progress, completed, cancelled
    
    # Relationships
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'))
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    assigned_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Dates
    due_date = db.Column(db.DateTime)
    completed_date = db.Column(db.DateTime)
    reminder_date = db.Column(db.DateTime)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Task Type & Category
    task_type = db.Column(db.String(50))  # call, email, meeting, follow_up, quote, payment
    category = db.Column(db.String(50))   # sales, support, technical, billing
    
    # Automatic Reminders
    auto_reminder = db.Column(db.Boolean, default=False)
    reminder_sent = db.Column(db.Boolean, default=False)
    
    # JSON Fields
    task_data = db.Column(db.Text)  # JSON string for additional task data
    
    # Relationships
    customer = db.relationship('Customer', backref='tasks')
    business = db.relationship('Business', backref='customer_tasks')
    assigned_user = db.relationship('User', backref='assigned_tasks')
    
    def __repr__(self):
        return f'<CustomerTask {self.title}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed_date': self.completed_date.isoformat() if self.completed_date else None,
            'customer_name': self.customer.name if self.customer else None,
            'customer_phone': self.customer.phone if self.customer else None,
            'assigned_user': self.assigned_user.username if self.assigned_user else None,
            'task_type': self.task_type,
            'category': self.category,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @property
    def is_overdue(self):
        if self.due_date and self.status != 'completed':
            return datetime.now() > self.due_date
        return False
    
    @property 
    def priority_color(self):
        colors = {
            'low': 'info',
            'medium': 'warning', 
            'high': 'danger',
            'urgent': 'dark'
        }
        return colors.get(self.priority, 'secondary')
    
    @property
    def status_color(self):
        colors = {
            'pending': 'warning',
            'in_progress': 'info',
            'completed': 'success',
            'cancelled': 'secondary'
        }
        return colors.get(self.status, 'secondary')


class CustomerInteraction(db.Model):
    """מודל לתיעוד אינטראקציות עם לקוחות"""
    __tablename__ = 'customer_interactions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic Info
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Interaction Details
    interaction_type = db.Column(db.String(50), nullable=False)  # call, whatsapp, email, meeting, quote, payment, contract
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    outcome = db.Column(db.String(100))  # interested, not_interested, follow_up, closed, paid
    
    # Metadata
    interaction_date = db.Column(db.DateTime, default=datetime.now)
    duration_minutes = db.Column(db.Integer)  # For calls and meetings
    
    # References
    reference_id = db.Column(db.String(100))  # CallLog ID, WhatsApp message ID, etc.
    reference_type = db.Column(db.String(50))  # call_log, whatsapp_conversation, etc.
    
    # JSON Data
    interaction_data = db.Column(db.Text)  # JSON string for detailed interaction data
    
    # Relationships  
    customer = db.relationship('Customer', backref='interactions')
    business = db.relationship('Business', backref='customer_interactions')
    user = db.relationship('User', backref='customer_interactions')
    
    def __repr__(self):
        return f'<CustomerInteraction {self.interaction_type} - {self.customer.name if self.customer else "Unknown"}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_name': self.customer.name if self.customer else None,
            'customer_phone': self.customer.phone if self.customer else None,
            'interaction_type': self.interaction_type,
            'title': self.title,
            'description': self.description,
            'outcome': self.outcome,
            'interaction_date': self.interaction_date.isoformat(),
            'duration_minutes': self.duration_minutes,
            'user_name': self.user.username if self.user else 'מערכת',
            'data': json.loads(self.interaction_data) if self.interaction_data else {}
        }
    
    @property
    def interaction_icon(self):
        icons = {
            'call': 'fas fa-phone',
            'whatsapp': 'fab fa-whatsapp', 
            'email': 'fas fa-envelope',
            'meeting': 'fas fa-handshake',
            'quote': 'fas fa-file-invoice-dollar',
            'payment': 'fas fa-credit-card',
            'contract': 'fas fa-file-signature',
            'task': 'fas fa-tasks'
        }
        return icons.get(self.interaction_type, 'fas fa-comment')
    
    @property
    def outcome_color(self):
        colors = {
            'interested': 'success',
            'not_interested': 'danger',
            'follow_up': 'warning',
            'closed': 'success',
            'paid': 'primary',
            'pending': 'info'
        }
        return colors.get(self.outcome, 'secondary')


class Quote(db.Model):
    """מודל להצעות מחיר"""
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    
    # Customer & Business
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    business_id = db.Column(db.Integer, db.ForeignKey('business.id'), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    
    # Quote Details
    title = db.Column(db.String(200))
    description = db.Column(db.Text)
    
    # Financial
    subtotal = db.Column(db.Numeric(10, 2), default=0)
    tax_rate = db.Column(db.Numeric(5, 2), default=17)  # Israeli VAT
    tax_amount = db.Column(db.Numeric(10, 2), default=0)
    total_amount = db.Column(db.Numeric(10, 2), default=0)
    currency = db.Column(db.String(3), default='ILS')
    
    # Status
    status = db.Column(db.String(20), default='draft')  # draft, sent, accepted, rejected, expired
    
    # Dates
    created_date = db.Column(db.DateTime, default=datetime.now)
    sent_date = db.Column(db.DateTime)
    expiry_date = db.Column(db.DateTime)
    accepted_date = db.Column(db.DateTime)
    
    # Files
    pdf_filename = db.Column(db.String(255))
    signature_filename = db.Column(db.String(255))
    
    # Quote Items (JSON)
    items_json = db.Column(db.Text)  # JSON array of quote items
    
    # Customer Response
    customer_notes = db.Column(db.Text)
    internal_notes = db.Column(db.Text)
    
    # Relationships
    customer = db.relationship('Customer', backref='quotes')
    business = db.relationship('Business', backref='quotes')
    created_by = db.relationship('User', backref='created_quotes')
    
    def __repr__(self):
        return f'<Quote {self.quote_number}>'
    
    @property
    def items(self):
        if self.items_json:
            return json.loads(self.items_json)
        return []
    
    @items.setter
    def items(self, value):
        self.items_json = json.dumps(value, ensure_ascii=False)
    
    def calculate_totals(self):
        """חישוב סכומים"""
        items = self.items
        self.subtotal = sum(float(item.get('price', 0)) * int(item.get('quantity', 1)) for item in items)
        self.tax_amount = self.subtotal * (self.tax_rate / 100)
        self.total_amount = self.subtotal + self.tax_amount
    
    def to_dict(self):
        return {
            'id': self.id,
            'quote_number': self.quote_number,
            'title': self.title,
            'description': self.description,
            'customer_name': self.customer.name if self.customer else None,
            'customer_phone': self.customer.phone if self.customer else None,
            'subtotal': float(self.subtotal) if self.subtotal else 0,
            'tax_rate': float(self.tax_rate) if self.tax_rate else 0,
            'tax_amount': float(self.tax_amount) if self.tax_amount else 0,
            'total_amount': float(self.total_amount) if self.total_amount else 0,
            'currency': self.currency,
            'status': self.status,
            'items': self.items,
            'created_date': self.created_date.isoformat(),
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'pdf_filename': self.pdf_filename
        }


# Extend existing Customer model with interaction log
def add_interaction_log_to_customer():
    """הוספת שדה interaction_log לטבלת הלקוחות"""
    try:
        from models import Customer
        if not hasattr(Customer, 'interaction_log'):
            # This would be added via migration in production
            pass
    except:
        pass