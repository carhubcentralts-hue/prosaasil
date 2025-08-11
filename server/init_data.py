#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Initialize database with demo data for Shai Real Estate
"""

import os
import sys
import hashlib
from datetime import datetime

# Add server path
sys.path.append(os.path.dirname(__file__))

def init_shai_business():
    """Initialize Shai Real Estate business with demo data"""
    try:
        from app_new import app, db
        from models import User, Business, Customer, CallLog
        
        with app.app_context():
            # Create all tables
            db.create_all()
            
            # Create Shai Real Estate business
            shai_business = Business.query.filter_by(name="שי דירות ומשרדים בע״מ").first()
            if not shai_business:
                shai_business = Business(
                    name="שי דירות ומשרדים בע״מ",
                    business_type="נדלן ותיווך",
                    phone_israel="+972-3-555-7777",
                    phone_whatsapp="+1-555-123-4567",
                    ai_prompt="אני עוזר וירטואלי של חברת שי דירות ומשרדים. אני מתמחה בייעוץ נדלן, השכרה, מכירה ותיווך נכסים. אני כאן לעזור עם כל השאלות שלכם לגבי נכסים, מחירים, הליך רכישה והשכרה. איך אוכל לעזור לכם היום?",
                    greeting_message="שלום וברוכים הבאים לשי דירות ומשרדים! איך אוכל לעזור לכם היום?",
                    calls_enabled=True,
                    whatsapp_enabled=True,
                    crm_enabled=True,
                    is_active=True
                )
                db.session.add(shai_business)
                db.session.commit()
                print(f"✅ Created business: {shai_business.name}")
            
            # Create business user
            business_user = User.query.filter_by(email="shai@example.com").first()
            if not business_user:
                password_hash = hashlib.sha256("shai123".encode()).hexdigest()
                business_user = User(
                    email="shai@example.com",
                    name="שי כהן - מנכ״ל",
                    password_hash=password_hash,
                    business_id=shai_business.id,
                    is_active=True
                )
                db.session.add(business_user)
                db.session.commit()
                print(f"✅ Created business user: {business_user.email}")
            
            # Create demo customers with real estate context
            if Customer.query.filter_by(business_id=shai_business.id).count() < 5:
                demo_customers = [
                    Customer(
                        name="יוסי לוי", 
                        phone="+972-50-123-4567", 
                        email="yossi.levy@gmail.com", 
                        business_id=shai_business.id, 
                        source="call",
                        status="active"
                    ),
                    Customer(
                        name="רחל כהן", 
                        phone="+972-52-987-6543", 
                        email="rachel.cohen@gmail.com", 
                        business_id=shai_business.id, 
                        source="whatsapp",
                        status="active"
                    ),
                    Customer(
                        name="דוד גולן", 
                        phone="+972-54-555-1234", 
                        email="david.golan@gmail.com", 
                        business_id=shai_business.id, 
                        source="website",
                        status="active"
                    ),
                    Customer(
                        name="מיכל אברהם", 
                        phone="+972-53-777-8888", 
                        email="michal.a@gmail.com", 
                        business_id=shai_business.id, 
                        source="referral",
                        status="active"
                    ),
                    Customer(
                        name="אלי מזרחי", 
                        phone="+972-55-999-0000", 
                        email="eli.mizrahi@gmail.com", 
                        business_id=shai_business.id, 
                        source="call",
                        status="active"
                    )
                ]
                
                for customer in demo_customers:
                    db.session.add(customer)
                
                db.session.commit()
                print(f"✅ Created {len(demo_customers)} demo customers")
            
            # Create some demo call logs
            if CallLog.query.filter_by(business_id=shai_business.id).count() < 3:
                demo_calls = [
                    CallLog(
                        business_id=shai_business.id,
                        call_sid="CA123456789demo1",
                        from_number="+972-50-123-4567",
                        to_number="+972-3-555-7777",
                        call_status="completed",
                        call_duration=120,
                        transcription="שלום, אני מחפש דירה בתל אביב",
                        ai_response="שלום! אשמח לעזור לך למצוא דירה בתל אביב. איזה אזור מעניין אותך?",
                        conversation_summary="לקוח מחפש דירה בתל אביב"
                    ),
                    CallLog(
                        business_id=shai_business.id,
                        call_sid="CA123456789demo2",
                        from_number="+972-52-987-6543",
                        to_number="+972-3-555-7777",
                        call_status="completed",
                        call_duration=89,
                        transcription="אני רוצה לשכור משרד קטן",
                        ai_response="בטח! יש לנו מספר אפשרויות למשרדים. באיזה אזור אתה מחפש?",
                        conversation_summary="לקוחה מחפשת משרד להשכרה"
                    ),
                    CallLog(
                        business_id=shai_business.id,
                        call_sid="CA123456789demo3",
                        from_number="+972-54-555-1234",
                        to_number="+972-3-555-7777",
                        call_status="completed",
                        call_duration=156,
                        transcription="כמה עולה דירת 3 חדרים ברמת גן?",
                        ai_response="מחירי הדירות ברמת גן משתנים לפי מיקום. דירת 3 חדרים יכולה לעלות בין 1.8 למיליון 2.5 שקל.",
                        conversation_summary="שאלה על מחירי דירות ברמת גן"
                    )
                ]
                
                for call in demo_calls:
                    db.session.add(call)
                
                db.session.commit()
                print(f"✅ Created {len(demo_calls)} demo calls")
            
            print(f"🎯 Total customers: {Customer.query.filter_by(business_id=shai_business.id).count()}")
            print(f"📞 Total calls: {CallLog.query.filter_by(business_id=shai_business.id).count()}")
            print(f"🏢 Business ID: {shai_business.id}")
            print("🚀 Database initialization completed!")
            
            return True
            
    except Exception as e:
        print(f"❌ Error initializing database: {e}")
        return False

if __name__ == "__main__":
    init_shai_business()