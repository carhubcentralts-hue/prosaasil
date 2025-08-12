#!/usr/bin/env python3
"""
Clean Models - מודל נקי ללא קונפליקטים
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class CleanBusiness(db.Model):
    __tablename__ = 'clean_businesses'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    business_type = db.Column(db.String(100), default='real_estate')
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    address = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'business_type': self.business_type,
            'phone': self.phone,
            'email': self.email,
            'address': self.address,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CleanCallLog(db.Model):
    __tablename__ = 'clean_call_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    call_sid = db.Column(db.String(100), unique=True)
    business_id = db.Column(db.Integer, default=1)
    from_number = db.Column(db.String(50))
    to_number = db.Column(db.String(50))
    call_status = db.Column(db.String(50), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'call_sid': self.call_sid,
            'business_id': self.business_id,
            'from_number': self.from_number,
            'to_number': self.to_number,
            'call_status': self.call_status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class CleanConversationTurn(db.Model):
    __tablename__ = 'clean_conversation_turns'
    
    id = db.Column(db.Integer, primary_key=True)
    call_log_id = db.Column(db.Integer, db.ForeignKey('clean_call_logs.id'))
    turn_number = db.Column(db.Integer, default=1)
    user_input = db.Column(db.Text)
    ai_response = db.Column(db.Text)
    recording_url = db.Column(db.String(500))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'call_log_id': self.call_log_id,
            'turn_number': self.turn_number,
            'user_input': self.user_input,
            'ai_response': self.ai_response,
            'recording_url': self.recording_url,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }