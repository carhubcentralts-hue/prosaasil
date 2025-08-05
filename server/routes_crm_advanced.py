"""
Advanced CRM Routes - Hebrew AI CRM System
מסלולי CRM מתקדמים למערכת CRM עברית AI
Advanced customer pages, digital contracts, invoicing system
"""

from flask import request, jsonify, render_template, send_file, redirect, url_for
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
import logging

# אמצוא ויבא את האובייקטים הנדרשים מ-main app
app = None
db = None

def init_advanced_crm(main_app, main_db):
    global app, db
    app = main_app
    db = main_db
    
from models import Business, Customer, Task, WhatsAppMessage, CallLog
from datetime import datetime, timedelta
import json
import logging
import os
from werkzeug.utils import secure_filename
import uuid

logger = logging.getLogger(__name__)

@app.route('/api/customers/<int:customer_id>/advanced', methods=['GET'])
def get_advanced_customer_profile(customer_id):
    """דף לקוח מתקדם עם כל הפרטים"""
    try:
        business_id = request.headers.get('Business-ID') or request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
            
        customer = Customer.query.filter_by(id=customer_id, business_id=int(business_id)).first()
        if not customer:
            return jsonify({'error': 'Customer not found'}), 404
            
        # Get all interactions
        whatsapp_messages = WhatsAppMessage.query.filter_by(
            business_id=int(business_id)
        ).filter(
            (WhatsAppMessage.from_number == customer.phone) | 
            (WhatsAppMessage.to_number == customer.phone)
        ).order_by(WhatsAppMessage.created_at.desc()).limit(50).all()
        
        call_logs = CallLog.query.filter_by(
            business_id=int(business_id),
            from_number=customer.phone
        ).order_by(CallLog.created_at.desc()).limit(20).all()
        
        tasks = Task.query.filter_by(
            business_id=int(business_id),
            customer_id=customer_id
        ).order_by(Task.created_at.desc()).all()
        
        # Calculate customer stats
        total_messages = len(whatsapp_messages)
        total_calls = len(call_logs)
        
        # Recent activity (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_messages = [msg for msg in whatsapp_messages if msg.created_at >= thirty_days_ago]
        recent_calls = [call for call in call_logs if call.created_at >= thirty_days_ago]
        
        customer_data = {
            'id': customer.id,
            'name': customer.name,
            'phone': customer.phone,
            'email': customer.email,
            'status': customer.status,
            'source': customer.source,
            'created_at': customer.created_at.isoformat() if customer.created_at else None,
            'last_contact_date': customer.last_contact_date.isoformat() if customer.last_contact_date else None,
            'notes': customer.notes,
            'tags': customer.tags,
            'stats': {
                'total_messages': total_messages,
                'total_calls': total_calls,
                'recent_messages_30d': len(recent_messages),
                'recent_calls_30d': len(recent_calls),
                'open_tasks': len([t for t in tasks if t.status != 'completed'])
            },
            'recent_whatsapp': [{
                'id': msg.id,
                'message_body': msg.message_body,
                'direction': msg.direction,
                'created_at': msg.created_at.isoformat(),
                'status': msg.status
            } for msg in whatsapp_messages[:10]],
            'recent_calls': [{
                'id': call.id,
                'call_sid': call.call_sid,
                'call_status': call.call_status,
                'call_duration': call.call_duration,
                'created_at': call.created_at.isoformat() if call.created_at else None,
                'transcription': call.transcription,
                'ai_response': call.ai_response
            } for call in call_logs[:10]],
            'tasks': [{
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status,
                'priority': task.priority,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'created_at': task.created_at.isoformat() if task.created_at else None
            } for task in tasks]
        }
        
        return jsonify({'success': True, 'customer': customer_data})
        
    except Exception as e:
        logger.error(f"Error getting advanced customer profile: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/customers/<int:customer_id>/contracts', methods=['GET', 'POST'])
def customer_contracts(customer_id):
    """חוזים דיגיטליים ללקוח"""
    try:
        business_id = request.headers.get('Business-ID') or request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
            
        if request.method == 'GET':
            # Get all contracts for customer
            contracts = db.session.execute("""
                SELECT c.*, ds.signature_data, ds.signed_at 
                FROM contracts c
                LEFT JOIN digital_signatures ds ON c.id = ds.contract_id
                WHERE c.customer_id = %s AND c.business_id = %s
                ORDER BY c.created_at DESC
            """, (customer_id, int(business_id))).fetchall()
            
            contract_list = []
            for contract in contracts:
                contract_list.append({
                    'id': contract[0],
                    'title': contract[2],
                    'content': contract[3],
                    'status': contract[4],
                    'created_at': contract[5].isoformat() if contract[5] else None,
                    'signed_at': contract[7].isoformat() if contract[7] else None,
                    'has_signature': bool(contract[6])
                })
                
            return jsonify({'success': True, 'contracts': contract_list})
            
        elif request.method == 'POST':
            # Create new contract
            data = request.get_json()
            
            # Insert contract
            contract_id = str(uuid.uuid4())
            db.session.execute("""
                INSERT INTO contracts (id, customer_id, business_id, title, content, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                contract_id,
                customer_id,
                int(business_id),
                data.get('title', 'חוזה חדש'),
                data.get('content', ''),
                'draft',
                datetime.utcnow()
            ))
            db.session.commit()
            
            return jsonify({'success': True, 'contract_id': contract_id, 'message': 'החוזה נוצר בהצלחה'})
            
    except Exception as e:
        logger.error(f"Error handling customer contracts: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/contracts/<contract_id>/sign', methods=['POST'])
def sign_contract(contract_id):
    """חתימה דיגיטלית על חוזה"""
    try:
        data = request.get_json()
        signature_data = data.get('signature')
        signer_name = data.get('signer_name')
        signer_email = data.get('signer_email')
        
        if not signature_data:
            return jsonify({'error': 'חתימה נדרשת'}), 400
            
        # Save digital signature
        signature_id = str(uuid.uuid4())
        db.session.execute("""
            INSERT INTO digital_signatures (id, contract_id, signature_data, signer_name, signer_email, signed_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            signature_id,
            contract_id,
            signature_data,
            signer_name,
            signer_email,
            datetime.utcnow()
        ))
        
        # Update contract status
        db.session.execute("""
            UPDATE contracts SET status = 'signed', updated_at = %s WHERE id = %s
        """, (datetime.utcnow(), contract_id))
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'החוזה נחתם בהצלחה'})
        
    except Exception as e:
        logger.error(f"Error signing contract: {e}")
        return jsonify({'error': 'שגיאה בחתימת החוזה'}), 500

@app.route('/api/customers/<int:customer_id>/invoices', methods=['GET', 'POST'])
def customer_invoices(customer_id):
    """חשבוניות ללקוח"""
    try:
        business_id = request.headers.get('Business-ID') or request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
            
        if request.method == 'GET':
            # Get all invoices for customer
            invoices = db.session.execute("""
                SELECT * FROM invoices 
                WHERE customer_id = %s AND business_id = %s
                ORDER BY created_at DESC
            """, (customer_id, int(business_id))).fetchall()
            
            invoice_list = []
            for invoice in invoices:
                invoice_list.append({
                    'id': invoice[0],
                    'invoice_number': invoice[3],
                    'amount': float(invoice[4]) if invoice[4] else 0,
                    'currency': invoice[5] or 'ILS',
                    'status': invoice[6],
                    'due_date': invoice[7].isoformat() if invoice[7] else None,
                    'created_at': invoice[8].isoformat() if invoice[8] else None,
                    'description': invoice[9],
                    'items': json.loads(invoice[10]) if invoice[10] else []
                })
                
            return jsonify({'success': True, 'invoices': invoice_list})
            
        elif request.method == 'POST':
            # Create new invoice
            data = request.get_json()
            
            # Generate invoice number
            invoice_number = f"INV-{datetime.now().strftime('%Y%m%d')}-{customer_id:04d}"
            
            invoice_id = str(uuid.uuid4())
            db.session.execute("""
                INSERT INTO invoices 
                (id, customer_id, business_id, invoice_number, amount, currency, status, due_date, created_at, description, items)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                invoice_id,
                customer_id,
                int(business_id),
                invoice_number,
                data.get('amount', 0),
                data.get('currency', 'ILS'),
                'draft',
                datetime.strptime(data.get('due_date'), '%Y-%m-%d') if data.get('due_date') else None,
                datetime.utcnow(),
                data.get('description', ''),
                json.dumps(data.get('items', []))
            ))
            db.session.commit()
            
            return jsonify({
                'success': True, 
                'invoice_id': invoice_id,
                'invoice_number': invoice_number,
                'message': 'החשבונית נוצרה בהצלחה'
            })
            
    except Exception as e:
        logger.error(f"Error handling customer invoices: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/invoices/<invoice_id>/send', methods=['POST'])
def send_invoice(invoice_id):
    """שליחת חשבונית ללקוח"""
    try:
        # Update invoice status
        db.session.execute("""
            UPDATE invoices SET status = 'sent', sent_at = %s WHERE id = %s
        """, (datetime.utcnow(), invoice_id))
        db.session.commit()
        
        # Here you would integrate with email service or WhatsApp to send
        
        return jsonify({'success': True, 'message': 'החשבונית נשלחה בהצלחה'})
        
    except Exception as e:
        logger.error(f"Error sending invoice: {e}")
        return jsonify({'error': 'שגיאה בשליחת החשבונית'}), 500

@app.route('/api/crm/integration/whatsapp-calls', methods=['GET'])
def get_integrated_communications():
    """התממשקות מלאה בין WhatsApp ושיחות דרך CRM"""
    try:
        business_id = request.headers.get('Business-ID') or request.args.get('business_id')
        if not business_id:
            return jsonify({'error': 'Business ID required'}), 400
            
        customer_id = request.args.get('customer_id')
        
        query_filter = f" AND c.business_id = {int(business_id)}"
        if customer_id:
            query_filter += f" AND c.id = {int(customer_id)}"
            
        # Integrated view of all customer communications
        integrated_data = db.session.execute(f"""
            SELECT 
                c.id as customer_id,
                c.name as customer_name,
                c.phone,
                c.email,
                COUNT(DISTINCT wm.id) as whatsapp_messages,
                COUNT(DISTINCT cl.id) as call_logs,
                MAX(wm.created_at) as last_whatsapp,
                MAX(cl.created_at) as last_call,
                c.last_contact_date,
                c.status as customer_status
            FROM customers c
            LEFT JOIN whatsapp_message wm ON (
                (wm.from_number = c.phone OR wm.to_number = c.phone) 
                AND wm.business_id = c.business_id
            )
            LEFT JOIN call_log cl ON (
                cl.from_number = c.phone 
                AND cl.business_id = c.business_id
            )
            WHERE 1=1 {query_filter}
            GROUP BY c.id, c.name, c.phone, c.email, c.last_contact_date, c.status
            ORDER BY GREATEST(
                COALESCE(MAX(wm.created_at), '1900-01-01'), 
                COALESCE(MAX(cl.created_at), '1900-01-01')
            ) DESC
        """).fetchall()
        
        result = []
        for row in integrated_data:
            result.append({
                'customer_id': row[0],
                'customer_name': row[1],
                'phone': row[2],
                'email': row[3],
                'stats': {
                    'whatsapp_messages': row[4],
                    'call_logs': row[5],
                    'last_whatsapp': row[6].isoformat() if row[6] else None,
                    'last_call': row[7].isoformat() if row[7] else None,
                    'last_contact_date': row[8].isoformat() if row[8] else None
                },
                'customer_status': row[9]
            })
            
        return jsonify({'success': True, 'integrated_communications': result})
        
    except Exception as e:
        logger.error(f"Error getting integrated communications: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Database table creation for advanced features
def create_advanced_crm_tables():
    """יוצר טבלאות מתקדמות ל-CRM"""
    try:
        db.session.execute("""
            CREATE TABLE IF NOT EXISTS contracts (
                id VARCHAR(255) PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                business_id INTEGER NOT NULL,
                title VARCHAR(500) NOT NULL,
                content TEXT,
                status VARCHAR(50) DEFAULT 'draft',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        db.session.execute("""
            CREATE TABLE IF NOT EXISTS digital_signatures (
                id VARCHAR(255) PRIMARY KEY,
                contract_id VARCHAR(255) NOT NULL,
                signature_data TEXT NOT NULL,
                signer_name VARCHAR(255),
                signer_email VARCHAR(255),
                signed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        db.session.execute("""
            CREATE TABLE IF NOT EXISTS invoices (
                id VARCHAR(255) PRIMARY KEY,
                customer_id INTEGER NOT NULL,
                business_id INTEGER NOT NULL,
                invoice_number VARCHAR(100) NOT NULL,
                amount DECIMAL(10,2),
                currency VARCHAR(10) DEFAULT 'ILS',
                status VARCHAR(50) DEFAULT 'draft',
                due_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                items JSON,
                sent_at TIMESTAMP
            )
        """)
        
        db.session.commit()
        logger.info("✅ Advanced CRM tables created successfully")
        
    except Exception as e:
        logger.error(f"Error creating advanced CRM tables: {e}")

# Initialize tables on import
create_advanced_crm_tables()