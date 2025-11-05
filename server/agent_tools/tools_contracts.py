"""
Contracts and Digital Signatures Tools for AgentKit
Handles contract generation and signature collection
"""
# 🔥 CRITICAL FIX: Import OpenAI Agents SDK directly (server/agents/__init__.py is now empty)
from agents import function_tool

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# ================================================================================
# INPUT/OUTPUT SCHEMAS
# ================================================================================

class ContractGenerateInput(BaseModel):
    """Input for generating a contract"""
    business_id: int = Field(..., description="Business ID", ge=1)
    template_id: str = Field(..., description="Contract template ID (e.g., 'treatment_series', 'rental')")
    lead_id: Optional[int] = Field(None, description="Related lead ID")
    appointment_id: Optional[int] = Field(None, description="Related appointment ID")
    variables: Dict[str, str] = Field(..., description="Template variables like customer_name, date, price, etc.")

class ContractGenerateOutput(BaseModel):
    """Contract generation result"""
    ok: bool
    contract_id: Optional[int] = None
    sign_url: Optional[str] = None
    reason: Optional[str] = None

# ================================================================================
# TOOL FUNCTIONS
# ================================================================================

@function_tool
def contracts_generate_and_send(
    business_id: int,
    template_id: str,
    customer_name: str,
    service_description: str = "טיפולים",
    price: str = "0",
    treatment_count: str = "1",
    validity_date: str = "",
    lead_id: Optional[int] = None,
    appointment_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Generate a contract from template and send for digital signature
    
    Args:
        business_id: Business ID
        template_id: Contract template ID (e.g., 'treatment_series', 'rental', 'purchase')
        customer_name: Customer full name
        service_description: Service description (default "טיפולים")
        price: Price as string (default "0")
        treatment_count: Number of treatments (default "1")
        validity_date: Expiration date (optional)
        lead_id: Related lead ID (optional)
        appointment_id: Related appointment ID (optional)
        
    Returns:
        Dict with ok, contract_id, sign_url, reason
    """
    try:
        logger.info(f"📝 Generating contract template_id={template_id}, business_id={business_id}")
        logger.info(f"   Customer: {customer_name}, Service: {service_description}")
        
        # Import models
        from server.models_sql import db, Contract, Customer, Lead
        
        # Prepare variables for template
        variables = {
            "customer_name": customer_name,
            "service_description": service_description,
            "price": price,
            "treatment_count": treatment_count,
            "validity_date": validity_date or datetime.now().strftime("%Y-%m-%d"),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "business_name": "העסק"  # TODO: Load from business settings
        }
        
        # Get template (placeholder - would load from database)
        templates = {
            "treatment_series": {
                "name": "חוזה לסדרת טיפולים",
                "content": """
חוזה טיפולים

בין: {business_name}
לבין: {customer_name}

הלקוח מתחייב לרכישת סדרת טיפולים:
- סוג הטיפול: {service_description}
- מספר טיפולים: {treatment_count}
- מחיר כולל: {price} ₪
- תוקף: {validity_date}

תנאי ביטול: ניתן לבטל עד 24 שעות לפני הטיפול.

חתימת הלקוח: _______________
תאריך: {date}
                """
            },
            "rental": {
                "name": "חוזה שכירות",
                "content": f"חוזה שכירות עבור {customer_name} - {service_description}"
            },
            "purchase": {
                "name": "חוזה רכישה",
                "content": f"חוזה רכישה עבור {customer_name} - {service_description}"
            }
        }
        
        template = templates.get(template_id)
        if not template:
            return {
                "ok": False,
                "reason": f"תבנית {template_id} לא נמצאה"
            }
        
        # Fill template with variables
        try:
            contract_content = template["content"].format(**variables)
        except KeyError as e:
            return {
                "ok": False,
                "reason": f"חסר משתנה נדרש: {str(e)}"
            }
        
        # 🔥 FIX: Create or find Customer (not Lead!)
        # Contract.customer_id points to Customer table, not Lead table!
        customer = None
        customer_phone = None
        
        # Try to find from lead_id first
        if lead_id:
            lead = Lead.query.filter_by(id=lead_id).first()
            if lead and lead.phone_e164:
                customer_phone = lead.phone_e164
        
        # If no phone from lead, try to get from Flask context (for AI Agent calls)
        if not customer_phone:
            from flask import g
            if hasattr(g, 'agent_context'):
                customer_phone = g.agent_context.get('customer_phone') or g.agent_context.get('whatsapp_from')
                if customer_phone:
                    logger.info(f"✅ Got customer phone from context: {customer_phone}")
        
        # If we have a phone, find or create customer
        if customer_phone:
            # Try to find existing customer by phone
            customer = Customer.query.filter_by(
                tenant_id=business_id,
                phone=customer_phone
            ).first()
            
            if not customer:
                # Create new customer
                customer = Customer(
                    tenant_id=business_id,
                    name=customer_name,
                    phone=customer_phone,
                    source="ai_agent"
                )
                db.session.add(customer)
                db.session.flush()  # Get customer ID
                logger.info(f"✅ Created new Customer: ID={customer.id}, name={customer_name}, phone={customer_phone}")
            else:
                logger.info(f"✅ Found existing Customer: ID={customer.id}")
        
        # Create contract record
        contract = Contract()
        contract.business_id = business_id
        contract.customer_id = customer.id if customer else None  # Now uses real customer_id!
        contract.appointment_id = appointment_id
        contract.template_id = template_id
        contract.customer_name = customer_name
        contract.content = contract_content
        contract.status = "pending_signature"
        contract.variables = variables  # Store as JSON
        
        db.session.add(contract)
        db.session.commit()
        
        # Generate signature URL (placeholder - integrate with DocuSign/HelloSign/etc.)
        sign_url = f"https://sign.example.com/contract/{contract.id}"
        
        # TODO: Integrate with actual e-signature provider
        # sign_url = docusign_service.create_signature_request(contract.id, contract_content, customer_email)
        
        logger.info(f"✅ Contract created: ID={contract.id}, template={template_id}")
        logger.info(f"   Signature URL: {sign_url}")
        
        return {
            "ok": True,
            "contract_id": contract.id,
            "sign_url": sign_url
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating contract: {e}")
        db.session.rollback()
        return {
            "ok": False,
            "reason": str(e)[:160]
        }
