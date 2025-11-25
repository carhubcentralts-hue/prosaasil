"""
Invoice Service - מערכת חשבוניות לפי הנחיות 100% GO
יצירת חשבוניות PDF/HTML עם מספר רץ ושמירת metadata
"""
from jinja2 import Template
from datetime import datetime
import os
import tempfile
from server.models_sql import Invoice, Deal, Customer
from server.db import db

def next_invoice_number():
    """יצירת מספר חשבונית הבא"""
    prefix = os.getenv("INVOICE_PREFIX", "INV")
    last = Invoice.query.order_by(Invoice.id.desc()).first()
    seq = (last.id + 1) if last else 1
    return f"{prefix}-{datetime.utcnow().strftime('%Y%m')}-{seq:04d}"

def render_invoice_html(deal, payment):
    """רינדור HTML עבור חשבונית"""
    company = os.getenv("COMPANY_NAME", "AgentLocator")
    vat = os.getenv("COMPANY_VAT_ID", "")
    
    template = Template("""
    <!DOCTYPE html>
    <html lang="he" dir="rtl">
    <head>
        <meta charset="utf-8"/>
        <title>חשבונית {{inv_no}}</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; direction: rtl; }
            .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 20px; }
            .company-info { margin: 20px 0; }
            .customer-info { margin: 20px 0; background: #f5f5f5; padding: 15px; }
            table { width: 100%; border-collapse: collapse; margin: 20px 0; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: right; }
            th { background-color: #f2f2f2; }
            .total { font-weight: bold; font-size: 18px; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>חשבונית {{inv_no}}</h1>
            <h2>{{company}}</h2>
            {% if vat %}<p>ח.פ/עוסק: {{vat}}</p>{% endif %}
        </div>
        
        <div class="customer-info">
            <h3>פרטי לקוח:</h3>
            <p><strong>שם:</strong> {{customer.name}}</p>
            {% if customer.phone %}<p><strong>טלפון:</strong> {{customer.phone}}</p>{% endif %}
            {% if customer.email %}<p><strong>אימייל:</strong> {{customer.email}}</p>{% endif %}
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>תיאור</th>
                    <th>כמות</th>
                    <th>מחיר יחידה</th>
                    <th>סכום</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>שירות/מוצר עבור "{{deal.title}}"</td>
                    <td>1</td>
                    <td>{{(payment.amount/100)|round(2)}} {{payment.currency.upper()}}</td>
                    <td>{{(payment.amount/100)|round(2)}} {{payment.currency.upper()}}</td>
                </tr>
            </tbody>
        </table>
        
        <div class="total">
            <p>סה"כ לתשלום: {{(payment.amount/100)|round(2)}} {{payment.currency.upper()}}</p>
        </div>
        
        <div class="company-info">
            <p>תאריך הפקה: {{now.strftime('%d/%m/%Y %H:%M')}}</p>
            <p>תודה על הפנייה!</p>
        </div>
    </body>
    </html>
    """)
    
    return template.render(
        inv_no=deal.id,
        company=company,
        vat=vat,
        customer=deal.customer if hasattr(deal, 'customer') else {'name': 'לקוח', 'phone': '', 'email': ''},
        deal=deal,
        payment=payment,
        now=datetime.utcnow()
    )

def create_invoice_for_payment(payment):
    """יצירת חשבונית עבור תשלום"""
    from server.models_sql import Customer
    
    # שליפת נתוני הדיל והלקוח
    deal = Deal.query.get(payment.deal_id)
    if not deal:
        raise ValueError(f"Deal {payment.deal_id} not found")
    
    # שליפת לקוח
    customer = Customer.query.get(deal.customer_id)
    if customer:
        deal.customer = customer
    
    inv_no = next_invoice_number()
    html = render_invoice_html(deal, payment)
    
    # יצירת תיקייה לחשבוניות
    out_dir = os.path.join("server", "static", "invoices")
    os.makedirs(out_dir, exist_ok=True)
    
    # שמירת HTML (fallback אם אין PDF support)
    html_path = os.path.join(out_dir, f"{inv_no}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    pdf_path = html_path  # Default to HTML if no PDF converter
    
    # נסיון המרה ל-PDF (אופציונלי)
    try:
        import pdfkit
        pdf_path = os.path.join(out_dir, f"{inv_no}.pdf")
        pdfkit.from_string(html, pdf_path, options={'encoding': 'UTF-8'})
    except ImportError:
        print("⚠️ pdfkit not available, saving as HTML")
    except Exception as e:
        print(f"⚠️ PDF conversion failed: {e}, using HTML")
    
    # שמירת חשבונית במסד הנתונים
    inv = Invoice()
    inv.deal_id = deal.id
    inv.invoice_number = inv_no
    inv.subtotal = payment.amount
    inv.tax = 0
    inv.total = payment.amount
    inv.pdf_path = pdf_path.replace("\\", "/")
    
    db.session.add(inv)
    db.session.commit()
    
    return inv