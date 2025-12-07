"""
Invoices and Payments Tools for AgentKit
Handles invoice creation, payment links, and billing operations
"""
# 🔥 CRITICAL FIX: Import OpenAI Agents SDK directly (server/agents/__init__.py is now empty)
from agents import function_tool

from pydantic import BaseModel, Field
from typing import Optional, List, Literal, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class InvoiceItem(BaseModel):
    """Single invoice line item"""
    description: str = Field(..., description="Item description in Hebrew")
    quantity: float = Field(1.0, description="Quantity", ge=0.01)
    unit_price: float = Field(..., description="Price per unit in currency", ge=0)

class InvoiceCreateInput(BaseModel):
    """Input for creating an invoice"""
    business_id: int = Field(..., description="Business ID", ge=1)
    lead_id: Optional[int] = Field(None, description="Related lead ID")
    appointment_id: Optional[int] = Field(None, description="Related appointment ID")
    customer_name: str = Field(..., description="Customer full name", min_length=2, max_length=200)
    customer_phone: Optional[str] = Field(None, description="Customer phone (optional)")
    currency: Literal["ILS", "USD"] = Field("ILS", description="Currency code")
    vat_rate: float = Field(0.17, description="VAT rate (0.17 for Israel)", ge=0, le=1)
    items: List[Dict[str, Any]] = Field(..., description="Invoice items as list of dicts with description, quantity, unit_price")
    issue_status: Literal["draft", "final"] = Field("final", description="Draft or final invoice")
    send_channel: Optional[Literal["whatsapp", "sms", "email"]] = Field(None, description="Send via this channel")

class InvoiceCreateOutput(BaseModel):
    """Invoice creation result"""
    ok: bool
    invoice_id: Optional[int] = None
    payment_link: Optional[str] = None
    total_amount: Optional[float] = None
    reason: Optional[str] = None

class PaymentLinkInput(BaseModel):
    """Input for generating payment link"""
    business_id: int = Field(..., description="Business ID", ge=1)
    invoice_id: int = Field(..., description="Invoice ID to generate payment link for", ge=1)

class PaymentLinkOutput(BaseModel):
    """Payment link result"""
    ok: bool
    payment_link: Optional[str] = None
    invoice_id: Optional[int] = None
    reason: Optional[str] = None

# ================================================================================
# TOOL FUNCTIONS
# ================================================================================

@function_tool
def invoices_create(
    business_id: int,
    customer_name: str,
    description: str,
    quantity: float,
    unit_price: float,
    currency: str = "ILS",
    vat_rate: float = 0.17,
    issue_status: str = "final",
    lead_id: Optional[int] = None,
    appointment_id: Optional[int] = None,
    customer_phone: Optional[str] = None,
    send_channel: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a single-line invoice and optionally generate payment link
    
    Args:
        business_id: Business ID
        customer_name: Customer full name
        description: Item description (e.g., "עיסוי מרגיע", "שירותי תיווך")
        quantity: Quantity (default 1.0)
        unit_price: Price per unit in currency
        currency: Currency code (ILS/USD)
        vat_rate: VAT rate (default 0.17 for Israel)
        issue_status: "draft" or "final"
        lead_id: Related lead ID (optional)
        appointment_id: Related appointment ID (optional)
        customer_phone: Customer phone for sending (optional)
        send_channel: Send via whatsapp/sms/email (optional)
        
    Returns:
        Dict with ok, invoice_id, payment_link, total_amount, reason
    """
    try:
        logger.info(f"🧾 Creating invoice for {customer_name}, business_id={business_id}")
        logger.info(f"   Item: {description} x {quantity} @ {unit_price} {currency}")
        
        # Validate inputs
        if quantity <= 0 or unit_price < 0:
            return {
                "ok": False,
                "reason": "כמות וסכום חייבים להיות מספרים חיוביים"
            }
        
        # Calculate totals
        subtotal = float(quantity) * float(unit_price)
        vat_amount = subtotal * float(vat_rate)
        total_amount = subtotal + vat_amount
        
        logger.info(f"   Subtotal: {subtotal}, VAT: {vat_amount}, Total: {total_amount}")
        
        # Import models
        from server.models_sql import db, Invoice, InvoiceItem as DBInvoiceItem, Customer, Lead
        
        # 🔥 FIX: Create or find Customer (not Lead!)
        # Invoice.customer_id points to Customer table, not Lead table!
        customer = None
        phone_to_use = customer_phone
        
        # If no phone provided, try to get from Flask context (for AI Agent calls)
        if not phone_to_use:
            from flask import g
            if hasattr(g, 'agent_context'):
                phone_to_use = g.agent_context.get('customer_phone') or g.agent_context.get('whatsapp_from')
                if phone_to_use:
                    logger.info(f"✅ Got customer phone from context: {phone_to_use}")
        
        # If we have a phone, find or create customer
        if phone_to_use:
            # Try to find existing customer by phone
            customer = Customer.query.filter_by(
                business_id=int(business_id),
                phone_e164=phone_to_use
            ).first()
            
            if not customer:
                # Create new customer
                customer = Customer()
                customer.business_id = int(business_id)
                customer.name = customer_name
                customer.phone_e164 = phone_to_use
                customer.status = "new"
                db.session.add(customer)
                db.session.flush()  # Get customer ID
                logger.info(f"✅ Created new Customer: ID={customer.id}, name={customer_name}, phone={phone_to_use}")
            else:
                logger.info(f"✅ Found existing Customer: ID={customer.id}")
        
        # Create invoice
        invoice = Invoice()
        invoice.business_id = int(business_id)
        invoice.customer_id = customer.id if customer else None  # Now uses real customer_id!
        invoice.appointment_id = int(appointment_id) if appointment_id else None
        invoice.customer_name = customer_name
        invoice.customer_phone = phone_to_use  # Use the resolved phone
        invoice.currency = currency
        invoice.subtotal = subtotal
        invoice.vat_rate = float(vat_rate)
        invoice.vat_amount = vat_amount
        invoice.total = total_amount
        invoice.status = issue_status  # draft or final
        invoice.issued_at = datetime.utcnow() if issue_status == "final" else None
        
        db.session.add(invoice)
        db.session.flush()  # Get invoice ID
        
        # Add single line item
        item = DBInvoiceItem()
        item.invoice_id = invoice.id
        item.description = description
        item.quantity = float(quantity)
        item.unit_price = float(unit_price)
        item.total = item.quantity * item.unit_price
        db.session.add(item)
        
        db.session.commit()
        
        logger.info(f"✅ Invoice created: ID={invoice.id}, Total={total_amount} {currency}")
        
        # Generate payment link (placeholder - integrate with actual payment provider)
        payment_link = f"https://pay.example.com/invoice/{invoice.id}"
        
        # TODO: Integrate with actual payment provider (Stripe, PayPal, etc.)
        # payment_link = stripe_service.create_payment_link(invoice.id, total_amount, currency)
        
        # Send via channel if requested
        if send_channel and customer_phone:
            # TODO: Integrate with notification service
            logger.info(f"📱 Sending invoice via {send_channel} to {customer_phone}")
            # notify_service.send_invoice(send_channel, customer_phone, invoice.id, payment_link)
        
        return {
            "ok": True,
            "invoice_id": invoice.id,
            "payment_link": payment_link,
            "total_amount": total_amount
        }
        
    except Exception as e:
        logger.error(f"❌ Error creating invoice: {e}")
        from server.models_sql import db
        db.session.rollback()
        return {
            "ok": False,
            "reason": str(e)[:160]
        }

@function_tool
def payments_link(
    business_id: int,
    invoice_id: int
) -> Dict[str, Any]:
    """
    Generate or retrieve payment link for an existing invoice
    
    Args:
        business_id: Business ID
        invoice_id: Invoice ID to generate payment link for
        
    Returns:
        Dict with ok, payment_link, invoice_id, reason
    """
    try:
        logger.info(f"💳 Generating payment link for invoice_id={invoice_id}, business_id={business_id}")
        
        from server.models_sql import Invoice
        
        # Find invoice
        invoice = Invoice.query.filter_by(id=invoice_id, business_id=business_id).first()
        if not invoice:
            return {
                "ok": False,
                "reason": "חשבונית לא נמצאה"
            }
        
        # Generate payment link (placeholder - integrate with actual payment provider)
        payment_link = f"https://pay.example.com/invoice/{invoice.id}"
        
        # TODO: Integrate with actual payment provider
        # payment_link = stripe_service.create_payment_link(invoice.id, invoice.total, invoice.currency)
        
        logger.info(f"✅ Payment link generated: {payment_link}")
        
        return {
            "ok": True,
            "payment_link": payment_link,
            "invoice_id": invoice.id
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating payment link: {e}")
        return {
            "ok": False,
            "reason": str(e)[:160]
        }
