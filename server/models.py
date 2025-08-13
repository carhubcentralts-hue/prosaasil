# Basic models for CRM functionality

class Customer:
    def __init__(self, id, name, phone, email="", company="", status="new", source="phone"):
        self.id = id
        self.name = name
        self.phone = phone
        self.email = email
        self.company = company
        self.status = status
        self.source = source
        
# Sample data for development
SAMPLE_CUSTOMERS = [
    Customer(1, "דוד כהן", "+972-50-123-4567", "david@email.com", "כהן נדל״ן", "active", "phone"),
    Customer(2, "שרה לוי", "+972-52-987-6543", "sara@email.com", "לוי השקעות", "lead", "whatsapp"),
    Customer(3, "מיכל אברהם", "+972-54-456-7890", "michal@email.com", "", "new", "website"),
]