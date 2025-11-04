"""
Invoices and Payments Tools for AgentKit
Handles invoice creation, payment links, and billing operations
"""
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
    items: List[Dict[str, Any]],
    currency: str = "ILS",
    vat_rate: float = 0.17,
    issue_status: str = "final",
    lead_id: Optional[int] = None,
    appointment_id: Optional[int] = None,
    customer_phone: Optional[str] = None,
    send_channel: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create an invoice with line items and optionally generate payment link
    
    Args:
        business_id: Business ID
        customer_name: Customer full name
        items: List of items, each with description, quantity, unit_price
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
        logger.info(f"   Items: {items}")
        
        # Validate items
        if not items or len(items) == 0:
            return {
                "ok": False,
                "reason": "חסרים פריטים בחשבונית"
            }
        
        # Validate each item using Pydantic (strict mode safety)
        validated_items = []
        for raw_item in items:
            try:
                # Coerce to InvoiceItem model (handles string→float conversion)
                item_obj = InvoiceItem(**raw_item)
                validated_items.append(item_obj)
            except Exception as e:
                logger.error(f"Invalid item: {raw_item}, error: {e}")
                return {
                    "ok": False,
                    "reason": f"פריט לא תקין בחשבונית: {str(e)[:80]}"
                }
        
        # Calculate totals with validated numeric types
        subtotal = sum(float(item.quantity) * float(item.unit_price) for item in validated_items)
        vat_amount = subtotal * float(vat_rate)
        total_amount = subtotal + vat_amount
        
        logger.info(f"   Subtotal: {subtotal}, VAT: {vat_amount}, Total: {total_amount}")
        
        # Import models
        from server.models_sql import db, Invoice, InvoiceItem as DBInvoiceItem
        
        # Create invoice
        invoice = Invoice()
        invoice.business_id = business_id
        invoice.customer_id = lead_id  # Using lead_id as customer_id
        invoice.appointment_id = appointment_id
        invoice.customer_name = customer_name
        invoice.customer_phone = customer_phone
        invoice.currency = currency
        invoice.subtotal = subtotal
        invoice.vat_rate = vat_rate
        invoice.vat_amount = vat_amount
        invoice.total = total_amount
        invoice.status = issue_status  # draft or final
        invoice.issue_date = datetime.utcnow() if issue_status == "final" else None
        
        db.session.add(invoice)
        db.session.flush()  # Get invoice ID
        
        # Add line items (using validated items)
        for item_obj in validated_items:
            item = DBInvoiceItem()
            item.invoice_id = invoice.id
            item.description = item_obj.description
            item.quantity = float(item_obj.quantity)
            item.unit_price = float(item_obj.unit_price)
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
