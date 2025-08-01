"""
Database Initialization and Seed Data
אתחול מסד נתונים וטעינת נתונים ראשוניים
"""
import os
import sys
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db
from models import (
    Business, User, CRMCustomer, CRMTask, 
    WhatsAppConversation, WhatsAppMessage,
    CallLog, ConversationTurn, AppointmentRequest,
    Appointment
)
import logging

logger = logging.getLogger(__name__)

def init_database():
    """אתחול מסד הנתונים"""
    try:
        with app.app_context():
            # יצירת כל הטבלאות
            db.create_all()
            logger.info("✅ Database tables created successfully")
            return True
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}")
        return False

def create_admin_user():
    """יצירת משתמש מנהל ראשי"""
    try:
        with app.app_context():
            # בדיקה אם המנהל כבר קיים
            admin = User.query.filter_by(username='שי', role='admin').first()
            if admin:
                logger.info("👤 Admin user 'שי' already exists")
                return True
            
            # יצירת משתמש מנהל
            admin_user = User(
                username='שי',
                email='admin@hebrewcrm.com',
                password_hash=generate_password_hash('HebrewCRM2024!'),
                role='admin',
                is_active=True,
                can_access_phone=True,
                can_access_whatsapp=True,
                can_access_crm=True,
                can_manage_business=True
            )
            
            db.session.add(admin_user)
            db.session.commit()
            
            logger.info("✅ Admin user 'שי' created successfully")
            logger.info("📧 Admin email: admin@hebrewcrm.com")
            logger.info("🔑 Admin password: HebrewCRM2024!")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating admin user: {e}")
        db.session.rollback()
        return False

def create_sample_business():
    """יצירת עסק לדוגמה"""
    try:
        with app.app_context():
            # בדיקה אם עסק הדוגמה כבר קיים
            sample_business = Business.query.filter_by(name='עסק לדוגמה').first()
            if sample_business:
                logger.info("🏢 Sample business already exists")
                return True
            
            # יצירת עסק לדוגמה
            business = Business(
                name='עסק לדוגמה',
                business_type='consulting',
                phone_number='+972501234567',
                whatsapp_number='whatsapp:+972501234567',
                greeting_message='שלום! ברוכים הבאים לעסק שלנו. איך נוכל לעזור לכם היום?',
                whatsapp_greeting='שלום מ-WhatsApp! אנחנו כאן לעזור לכם 😊',
                system_prompt='''אתה עוזר וירטואלי חכם ומקצועי של עסק ייעוץ בישראל. 
אתה מדבר עברית בצורה טבעית ונעימה.
תפקידך לעזור ללקוחות, לענות על שאלות ולתאם תורים.
היה אדיב, מקצועי ועוזר.''',
                whatsapp_enabled=True,
                phone_permissions=True,
                whatsapp_permissions=True,
                is_active=True
            )
            
            db.session.add(business)
            db.session.commit()
            
            # יצירת משתמש עסק
            business_user = User(
                username='עסק_לדוגמה',
                email='business@example.com',
                password_hash=generate_password_hash('Business123!'),
                role='business',
                business_id=business.id,
                is_active=True,
                can_access_phone=True,
                can_access_whatsapp=True,
                can_access_crm=True
            )
            
            db.session.add(business_user)
            db.session.commit()
            
            logger.info("✅ Sample business created successfully")
            logger.info(f"🏢 Business ID: {business.id}")
            logger.info("👤 Business user: עסק_לדוגמה / Business123!")
            return business.id
            
    except Exception as e:
        logger.error(f"❌ Error creating sample business: {e}")
        db.session.rollback()
        return None

def create_sample_customers(business_id):
    """יצירת לקוחות לדוגמה"""
    try:
        with app.app_context():
            # בדיקה אם כבר יש לקוחות
            existing_customers = CRMCustomer.query.filter_by(business_id=business_id).count()
            if existing_customers > 0:
                logger.info("👥 Sample customers already exist")
                return True
            
            sample_customers = [
                {
                    'name': 'דוד כהן',
                    'phone': '+972501111111',
                    'email': 'david.cohen@example.com',
                    'status': 'active',
                    'source': 'phone',
                    'notes': 'לקוח VIP, מעוניין בשירותי ייעוץ עסקי'
                },
                {
                    'name': 'שרה לוי',
                    'phone': '+972502222222',
                    'email': 'sarah.levi@example.com',
                    'status': 'prospect',
                    'source': 'whatsapp',
                    'notes': 'פנייה ראשונה, מעוניינת בפיתוח אתר'
                },
                {
                    'name': 'משה ישראלי',
                    'phone': '+972503333333',
                    'email': 'moshe@example.com',
                    'status': 'active',
                    'source': 'referral',
                    'notes': 'הגיע דרך המלצה, לקוח פוטנציאלי גדול'
                },
                {
                    'name': 'רותי גולדברג',
                    'phone': '+972504444444',
                    'email': 'ruth.gold@example.com',
                    'status': 'prospect',
                    'source': 'website',
                    'notes': 'מילאה טופס באתר, מעוניינת בשיווק דיגיטלי'
                },
                {
                    'name': 'אבי רוזן',
                    'phone': '+972505555555',
                    'email': 'avi.rosen@example.com',
                    'status': 'active',
                    'source': 'phone',
                    'notes': 'לקוח ותיק, שירותי תחזוקה חודשיים'
                }
            ]
            
            for customer_data in sample_customers:
                customer = CRMCustomer(
                    business_id=business_id,
                    **customer_data
                )
                db.session.add(customer)
            
            db.session.commit()
            
            logger.info(f"✅ Created {len(sample_customers)} sample customers")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating sample customers: {e}")
        db.session.rollback()
        return False

def create_sample_tasks(business_id):
    """יצירת משימות לדוגמה"""
    try:
        with app.app_context():
            # בדיקה אם כבר יש משימות
            existing_tasks = CRMTask.query.filter_by(business_id=business_id).count()
            if existing_tasks > 0:
                logger.info("📋 Sample tasks already exist")
                return True
            
            # קבלת לקוחות לקישור למשימות
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            
            sample_tasks = [
                {
                    'title': 'התקשרות ללקוח דוד כהן',
                    'description': 'להתקשר ולתאם פגישת ייעוץ עסקי',
                    'status': 'pending',
                    'priority': 'high',
                    'customer_id': customers[0].id if customers else None,
                    'assigned_to': 'עסק_לדוגמה',
                    'due_date': datetime.utcnow() + timedelta(days=1)
                },
                {
                    'title': 'הכנת הצעת מחיר לשרה לוי',
                    'description': 'הכנת הצעת מחיר מפורטת לפיתוח אתר',
                    'status': 'in_progress',
                    'priority': 'medium',
                    'customer_id': customers[1].id if len(customers) > 1 else None,
                    'assigned_to': 'עסק_לדוגמה',
                    'due_date': datetime.utcnow() + timedelta(days=3)
                },
                {
                    'title': 'מעקב אחר פרויקט משה ישראלי',
                    'description': 'בדיקת התקדמות הפרויקט ועדכון הלקוח',
                    'status': 'pending',
                    'priority': 'medium',
                    'customer_id': customers[2].id if len(customers) > 2 else None,
                    'assigned_to': 'עסק_לדוגמה',
                    'due_date': datetime.utcnow() + timedelta(days=7)
                },
                {
                    'title': 'שליחת חומרים לרותי גולדברג',
                    'description': 'שליחת חומרי הסבר על שירותי השיווק הדיגיטלי',
                    'status': 'completed',
                    'priority': 'low',
                    'customer_id': customers[3].id if len(customers) > 3 else None,
                    'assigned_to': 'עסק_לדוגמה',
                    'due_date': datetime.utcnow() - timedelta(days=1),
                    'completed_at': datetime.utcnow() - timedelta(hours=5)
                },
                {
                    'title': 'תחזוקה חודשית - אבי רוזן',
                    'description': 'ביצוע תחזוקה חודשית לאתר הלקוח',
                    'status': 'pending',
                    'priority': 'medium',
                    'customer_id': customers[4].id if len(customers) > 4 else None,
                    'assigned_to': 'עסק_לדוגמה',
                    'due_date': datetime.utcnow() + timedelta(days=15)
                }
            ]
            
            for task_data in sample_tasks:
                task = CRMTask(
                    business_id=business_id,
                    **task_data
                )
                db.session.add(task)
            
            db.session.commit()
            
            logger.info(f"✅ Created {len(sample_tasks)} sample tasks")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating sample tasks: {e}")
        db.session.rollback()
        return False

def create_sample_appointments(business_id):
    """יצירת תורים לדוגמה"""
    try:
        with app.app_context():
            # בדיקה אם כבר יש תורים
            existing_appointments = Appointment.query.filter_by(business_id=business_id).count()
            if existing_appointments > 0:
                logger.info("📅 Sample appointments already exist")
                return True
            
            # קבלת לקוחות לקישור לתורים
            customers = CRMCustomer.query.filter_by(business_id=business_id).all()
            
            if not customers:
                logger.warning("⚠️ No customers found for appointments")
                return True
            
            sample_appointments = [
                {
                    'customer_id': customers[0].id,
                    'appointment_date': datetime.utcnow() + timedelta(days=1, hours=10),
                    'duration_minutes': 60,
                    'note': 'פגישת ייעוץ עסקי ראשונית',
                    'status': 'scheduled'
                },
                {
                    'customer_id': customers[1].id,
                    'appointment_date': datetime.utcnow() + timedelta(days=3, hours=14),
                    'duration_minutes': 90,
                    'note': 'הצגת הצעת מחיר לפיתוח אתר',
                    'status': 'confirmed'
                },
                {
                    'customer_id': customers[2].id,
                    'appointment_date': datetime.utcnow() + timedelta(days=7, hours=9),
                    'duration_minutes': 45,
                    'note': 'סקירת התקדמות פרויקט',
                    'status': 'scheduled'
                }
            ]
            
            for appointment_data in sample_appointments:
                appointment = Appointment(
                    business_id=business_id,
                    **appointment_data
                )
                db.session.add(appointment)
            
            db.session.commit()
            
            logger.info(f"✅ Created {len(sample_appointments)} sample appointments")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error creating sample appointments: {e}")
        db.session.rollback()
        return False

def run_full_initialization():
    """הרצת אתחול מלא של המערכת"""
    logger.info("🚀 Starting full system initialization...")
    
    # 1. אתחול מסד נתונים
    if not init_database():
        logger.error("❌ Database initialization failed")
        return False
    
    # 2. יצירת משתמש מנהל
    if not create_admin_user():
        logger.error("❌ Admin user creation failed")
        return False
    
    # 3. יצירת עסק לדוגמה
    business_id = create_sample_business()
    if not business_id:
        logger.error("❌ Sample business creation failed")
        return False
    
    # 4. יצירת נתוני דוגמה
    if not create_sample_customers(business_id):
        logger.error("❌ Sample customers creation failed")
        return False
    
    if not create_sample_tasks(business_id):
        logger.error("❌ Sample tasks creation failed")
        return False
    
    if not create_sample_appointments(business_id):
        logger.error("❌ Sample appointments creation failed")
        return False
    
    logger.info("✅ Full system initialization completed successfully!")
    logger.info("🎉 The Hebrew CRM system is ready to use!")
    logger.info("")
    logger.info("📊 Summary:")
    logger.info("- Admin user: שי / HebrewCRM2024!")
    logger.info("- Sample business: עסק לדוגמה")
    logger.info("- Business user: עסק_לדוגמה / Business123!")
    logger.info("- 5 sample customers")
    logger.info("- 5 sample tasks")
    logger.info("- 3 sample appointments")
    logger.info("")
    logger.info("🌐 Access the system at: http://localhost:5000")
    
    return True

if __name__ == '__main__':
    # הגדרת logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # הרצת האתחול
    success = run_full_initialization()
    
    if success:
        print("✅ Initialization completed successfully!")
        sys.exit(0)
    else:
        print("❌ Initialization failed!")
        sys.exit(1)