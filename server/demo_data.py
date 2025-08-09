from werkzeug.security import generate_password_hash
from models import db, User, Business

def create_demo_data():
    """Create demo data for testing the system"""
    
    # Check if demo data already exists
    if User.query.filter_by(username='admin').first():
        return
    
    try:
        # Create demo business
        business = Business(
            name="שי דירות ומשרדים בע״מ",
            phone_israel="+972-3-555-7777",
            business_type="נדלן ותיווך"
        )
        db.session.add(business)
        db.session.flush()  # Get the business ID
        
        # Create demo admin user
        admin_user = User(
            username='admin',
            password_hash=generate_password_hash('admin123'),
            role='admin'
        )
        db.session.add(admin_user)
        
        # Create demo business user
        business_user = User(
            username='business',
            password_hash=generate_password_hash('business123'),
            role='business',
            business_id=business.id
        )
        db.session.add(business_user)
        
        db.session.commit()
        print("✅ Demo data created successfully")
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error creating demo data: {e}")