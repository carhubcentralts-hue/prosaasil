"""
Additional CRM Routes
נתיבי CRM נוספים למערכת
"""

from flask import render_template, request, jsonify, flash, redirect
# Flask-Login removed for direct access
from datetime import datetime, timedelta
from models import Customer, Business, CallLog, AppointmentRequest
from app import app
from whatsapp_service import WhatsAppService
import logging

logger = logging.getLogger(__name__)
whatsapp_service = WhatsAppService()

# ========== NEW CRM API ROUTES ==========
@app.route('/api/dashboard-data')
def api_dashboard_data():
    """API endpoint for dashboard data"""
    try:
        from sqlalchemy import func
        
        # Calculate dashboard statistics
        total_calls = CallLog.query.count()
        new_leads = Customer.query.filter(
            Customer.first_contact_date >= datetime.now() - timedelta(days=7)
        ).count() if hasattr(Customer, 'first_contact_date') else 0
        
        # Real data for charts
        calls_chart = {
            'labels': [f"{(datetime.now() - timedelta(days=i)).strftime('%d/%m')}" for i in range(6, -1, -1)],
            'data': [CallLog.query.filter(
                CallLog.created_at >= datetime.now() - timedelta(days=i+1),
                CallLog.created_at < datetime.now() - timedelta(days=i)
            ).count() for i in range(6, -1, -1)]
        }
        
        # Monthly revenue (mock data for now)
        revenue_chart = {
            'labels': ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני'],
            'data': [15000, 22000, 18000, 25000, 32000, 28000]
        }
        
        # Recent activity from call logs
        recent_calls = CallLog.query.order_by(CallLog.created_at.desc()).limit(5).all()
        recent_activity = []
        
        for call in recent_calls:
            minutes_ago = int((datetime.now() - call.created_at).total_seconds() / 60)
            recent_activity.append({
                'type': 'call',
                'title': f'שיחה - {call.from_number}',
                'description': f'משך: {call.call_duration or 0} שניות',
                'timestamp': f'{minutes_ago} דקות'
            })
        
        return jsonify({
            'success': True,
            'total_calls': total_calls,
            'new_leads': new_leads, 
            'pending_tasks': 5,
            'monthly_revenue': 45000,
            'calls_chart': calls_chart,
            'revenue_chart': revenue_chart,
            'recent_activity': recent_activity,
            'upcoming_tasks': []
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        return jsonify({'success': False, 'error': str(e)})

# Task management route removed - handled in routes.py to avoid duplicate endpoint

@app.route('/quotes')
@app.route('/quotes/generate')
def quotes_generator():
    """Quote generator page"""
    try:
        customers = Customer.query.all() if Customer else []
        
        return render_template('quotes/generator.html', customers=customers)
    except Exception as e:
        logger.error(f"Error loading quotes generator: {e}")
        flash('שגיאה בטעינת מחולל הצעות המחיר', 'error')
        return redirect('/')

@app.route('/api/quotes/generate', methods=['POST'])
def api_generate_quote():
    """Generate quote and send via WhatsApp"""
    try:
        data = request.json
        
        # Generate unique quote number
        quote_number = f"Q{datetime.now().strftime('%Y%m%d')}{len(data.get('items', [])):02d}"
        
        # Calculate totals
        subtotal = sum(item['total'] for item in data.get('items', []))
        tax_amount = subtotal * (data.get('tax_rate', 17) / 100)
        total_amount = subtotal + tax_amount
        
        # Create WhatsApp message
        message = f"""
📋 *הצעת מחיר #{quote_number}*

👋 שלום {data['customer_name']}!

📝 *{data['title']}*
{data.get('description', '')}

💰 *פירוט עלויות:*
"""
        
        for item in data.get('items', []):
            message += f"• {item['description']}: {item['quantity']} × ₪{item['price']} = ₪{item['total']}\n"
        
        message += f"""
💵 *סיכום:*
• סכום ביניים: ₪{subtotal:.2f}
• מע״מ ({data.get('tax_rate', 17)}%): ₪{tax_amount:.2f}
• *סה״כ לתשלום: ₪{total_amount:.2f}*

⏰ תוקף ההצעה: {data.get('expiry_date', 'לא הוגדר')}

לאישור ההצעה או לשאלות נוספות, אתם מוזמנים לפנות אלינו.

תודה! 🙏
        """.strip()
        
        # Send via WhatsApp
        result = whatsapp_service.send_whatsapp_message(data['customer_phone'], message)
        
        if result.get('success'):
            return jsonify({
                'success': True,
                'quote_number': quote_number,
                'total_amount': total_amount,
                'pdf_filename': f'quote_{quote_number}.pdf',
                'message': 'הצעת המחיר נשלחה בהצלחה!'
            })
        else:
            return jsonify({
                'success': False,
                'error': 'שגיאה בשליחת הצעת המחיר דרך WhatsApp'
            })
            
    except Exception as e:
        logger.error(f"Error generating quote: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crm-action', methods=['POST'])
def api_crm_action():
    """CRM actions API (quote, contract, payment)"""
    try:
        data = request.json
        action = data.get('action')
        customer_phone = data.get('customer_phone')
        
        if action == 'quote':
            # Quick quote generation
            message = f"""
📋 *הצעת מחיר מהירה*

שלום! 👋

תודה על פנייתך. אנו נשמח להכין עבורך הצעת מחיר מפורטת.

🔗 *לפרטים נוספים ולקבלת הצעה מותאמת אישית:*
{request.url_root}quotes/generate?phone={customer_phone}

או התקשר אלינו ונכין עבורך הצעה מיידית!

תודה! 🙏
            """.strip()
            
        elif action == 'contract':
            message = f"""
📄 *חוזה דיגיטלי*

שלום! 👋

אנו מוכנים להכין עבורך חוזה דיגיטלי מקצועי.

📋 *החוזה יכלול:*
• תנאים ברורים ומפורטים
• חתימה דיגיטלית מאובטחת
• עמידה בתקנים המשפטיים

📞 *ליצירת קשר לחתימת חוזה:*
התקשר אלינו או שלח הודעה והכול יוסדר במהירות!

תודה! 🙏
            """.strip()
            
        elif action == 'payment':
            amount = data.get('amount', '0')
            description = data.get('description', 'תשלום')
            
            from payment_link_service import send_payment_link_whatsapp
            
            result = send_payment_link_whatsapp(
                customer_phone=customer_phone,
                customer_name=data.get('customer_name', 'לקוח'),
                amount=float(amount) if amount.replace('.', '').isdigit() else 100,
                description=description
            )
            
            return jsonify(result)
        
        else:
            return jsonify({'success': False, 'error': 'פעולה לא מוכרת'})
        
        # Send message for quote/contract actions
        result = whatsapp_service.send_whatsapp_message(customer_phone, message)
        
        return jsonify({
            'success': result.get('success', True),
            'message': f'הודעת {action} נשלחה בהצלחה!'
        })
        
    except Exception as e:
        logger.error(f"Error in CRM action: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/payments/create')
def payments_create():
    """Payment link creation page"""
    try:
        # Auto-fill from URL parameters
        customer_phone = request.args.get('phone', '')
        customer_name = request.args.get('name', '')
        amount = request.args.get('amount', '')
        reason = request.args.get('reason', '')
        
        return render_template('payments/create.html',
                             customer_phone=customer_phone,
                             customer_name=customer_name,
                             amount=amount,
                             reason=reason)
    except Exception as e:
        logger.error(f"Error loading payment creation page: {e}")
        # Return a simple form instead of template
        return """
        <div style="padding: 20px; font-family: Arial, sans-serif;">
            <h2>יצירת קישור תשלום</h2>
            <p>הדף בבניה. נא לפנות למנהל המערכת.</p>
            <a href="/" style="color: blue;">חזרה לדף הבית</a>
        </div>
        """

@app.route('/api/payments/create', methods=['POST'])
def api_create_payment():
    """Create payment link API"""
    try:
        data = request.json
        
        from payment_link_service import send_payment_link_whatsapp
        
        result = send_payment_link_whatsapp(
            customer_phone=data['customer_phone'],
            customer_name=data['customer_name'],
            amount=float(data['amount']),
            description=data['description'],
            provider=data.get('provider', 'tranzila')
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating payment link: {e}")
        return jsonify({'success': False, 'error': str(e)})

logger.info("✅ Additional CRM routes loaded successfully")