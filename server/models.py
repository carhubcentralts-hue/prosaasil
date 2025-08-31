# Basic models for CRM functionality
from datetime import datetime

class Customer:
    def __init__(self, id, name, phone, email="", company="", status="new", source="phone"):
        self.id = id
        self.name = name
        self.phone = phone
        self.email = email
        self.company = company
        self.status = status
        self.source = source
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "company": self.company,
            "status": self.status,
            "source": self.source,
            "created_at": self.created_at.isoformat()
        }

class Business:
    def __init__(self, id, name, domain=None, active=True):
        self.id = id
        self.name = name
        self.domain = domain
        self.active = active
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            "id": self.id, 
            "name": self.name, 
            "domain": self.domain, 
            "active": self.active,
            "created_at": self.created_at.isoformat()
        }

class CallLog:
    def __init__(self, id, customer_id, phone_number, status="completed"):
        self.id = id
        self.customer_id = customer_id
        self.phone_number = phone_number
        self.status = status
        self.created_at = datetime.now()
        
    def to_dict(self):
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "phone_number": self.phone_number,
            "status": self.status,
            "created_at": self.created_at.isoformat()
        }
        
# Sample data for development
SAMPLE_CUSTOMERS = [
    Customer(1, "דוד כהן", "+972-50-123-4567", "david@email.com", "כהן נדל״ן", "active", "phone"),
    Customer(2, "שרה לוי", "+972-52-987-6543", "sara@email.com", "לוי השקעות", "lead", "whatsapp"),
    Customer(3, "מיכל אברהם", "+972-54-456-7890", "michal@email.com", "", "new", "website"),
]

# Import SQLAlchemy models for authentication
from server.models_sql import User, Business, CallLog as SQLCallLog, db

# Re-export for compatibility
__all__ = ['User', 'Business', 'SQLCallLog', 'Customer', 'CallLog', 'db']

# Fake database placeholder for old code compatibility
# db = None  # Now using real SQLAlchemy db