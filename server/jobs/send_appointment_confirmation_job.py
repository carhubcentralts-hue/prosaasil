"""
Send Appointment Confirmation Job
Worker job that sends automated WhatsApp messages for appointment confirmations

🎯 RESPONSIBILITIES:
- Load automation run and appointment data
- Validate appointment still exists and status is valid
- Render message template with placeholders
- Send WhatsApp message via unified send service
- Mark run as sent or failed with error details

⚠️ USAGE:
    from server.jobs.send_appointment_confirmation_job import send_appointment_confirmation
    from server.services.jobs import enqueue
    
    enqueue('default', send_appointment_confirmation, run_id=123, business_id=456)
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from server.db import db
from server.models_sql import (
    AppointmentAutomationRun,
    AppointmentAutomation,
    Appointment,
    Business,
    Lead,
    Customer,
    User
)
from server.services.whatsapp_send_service import send_message

logger = logging.getLogger(__name__)


def render_template(template: str, context: Dict[str, Any]) -> str:
    """
    Render message template by replacing placeholders with actual values.
    
    Supported placeholders:
    - {first_name}: Lead/customer first name
    - {business_name}: Business name
    - {appointment_date}: Appointment date in Hebrew format
    - {appointment_time}: Appointment time in HH:MM format
    - {appointment_location}: Appointment location
    - {rep_name}: Representative/user name who created appointment
    
    Args:
        template: Message template with placeholders
        context: Dict with placeholder values
    
    Returns:
        Rendered message string
    """
    try:
        message = template
        
        # Replace all placeholders
        for key, value in context.items():
            placeholder = "{" + key + "}"
            if placeholder in message:
                message = message.replace(placeholder, str(value or ''))
        
        return message
        
    except Exception as e:
        logger.error(f"Error rendering template: {e}", exc_info=True)
        return template


def format_hebrew_date(dt: datetime) -> str:
    """
    Format datetime to Hebrew-friendly date string.
    
    Args:
        dt: Datetime object
    
    Returns:
        Formatted date string (e.g., "יום שני, 15 ינואר 2024")
    """
    try:
        # Hebrew day names (Sunday = index 0)
        hebrew_days = ['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת']
        # Hebrew month names (January = index 0, so use month-1 for indexing)
        hebrew_months = [
            'ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני',
            'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר'
        ]
        
        day_name = hebrew_days[dt.weekday()]
        month_name = hebrew_months[dt.month - 1]  # month is 1-12, array is 0-11
        
        return f"יום {day_name}, {dt.day} {month_name} {dt.year}"
        
    except Exception as e:
        logger.error(f"Error formatting Hebrew date: {e}", exc_info=True)
        return dt.strftime('%d/%m/%Y')


def send_appointment_confirmation(run_id: int, business_id: int) -> Dict[str, Any]:
    """
    Send appointment confirmation message via WhatsApp.
    
    This function:
    1. Loads the automation run and validates it's still pending
    2. Loads appointment and checks it still exists and status is valid
    3. Gets contact information (phone number)
    4. Renders message template with placeholders
    5. Sends WhatsApp message
    6. Updates run status to sent or failed
    
    Args:
        run_id: AppointmentAutomationRun ID
        business_id: Business ID (for security validation)
    
    Returns:
        Dict with execution results
    """
    logger.info(f"[APPOINTMENT_CONFIRMATION] Starting job for run {run_id}, business {business_id}")
    
    try:
        # Load automation run
        run = AppointmentAutomationRun.query.filter_by(
            id=run_id,
            business_id=business_id
        ).first()
        
        if not run:
            error_msg = f"Automation run {run_id} not found for business {business_id}"
            logger.error(f"[APPOINTMENT_CONFIRMATION] {error_msg}")
            return {'success': False, 'error': error_msg}
        
        # Check if run is still pending
        if run.status != 'pending':
            logger.info(f"[APPOINTMENT_CONFIRMATION] Run {run_id} already processed (status: {run.status})")
            return {'success': False, 'error': f'Run already {run.status}'}
        
        # Load appointment
        appointment = Appointment.query.filter_by(
            id=run.appointment_id,
            business_id=business_id
        ).first()
        
        if not appointment:
            error_msg = f"Appointment {run.appointment_id} not found"
            logger.error(f"[APPOINTMENT_CONFIRMATION] {error_msg}")
            run.status = 'failed'
            run.last_error = error_msg
            run.attempts += 1
            db.session.commit()
            return {'success': False, 'error': error_msg}
        
        # Load automation
        automation = AppointmentAutomation.query.filter_by(
            id=run.automation_id,
            business_id=business_id
        ).first()
        
        if not automation:
            error_msg = f"Automation {run.automation_id} not found"
            logger.error(f"[APPOINTMENT_CONFIRMATION] {error_msg}")
            run.status = 'failed'
            run.last_error = error_msg
            run.attempts += 1
            db.session.commit()
            return {'success': False, 'error': error_msg}
        
        # Check if automation is still enabled
        if not automation.enabled:
            logger.info(f"[APPOINTMENT_CONFIRMATION] Automation {automation.id} is disabled, canceling run")
            run.status = 'canceled'
            run.canceled_at = datetime.utcnow()
            run.last_error = 'Automation disabled'
            db.session.commit()
            return {'success': False, 'error': 'Automation disabled'}
        
        # Check if appointment status is still in trigger list
        if appointment.status not in (automation.trigger_status_ids or []):
            logger.info(f"[APPOINTMENT_CONFIRMATION] Appointment status '{appointment.status}' no longer in trigger list")
            run.status = 'canceled'
            run.canceled_at = datetime.utcnow()
            run.last_error = f'Status changed to {appointment.status}'
            db.session.commit()
            return {'success': False, 'error': 'Status no longer matches'}
        
        # Get contact phone number
        phone = None
        first_name = None
        
        # Try to get from linked lead
        if appointment.lead_id:
            lead = Lead.query.get(appointment.lead_id)
            if lead:
                phone = lead.phone_e164 or lead.phone_raw
                first_name = lead.first_name or lead.name
        
        # Try to get from linked customer
        if not phone and appointment.customer_id:
            customer = Customer.query.get(appointment.customer_id)
            if customer:
                phone = customer.phone
                first_name = customer.name
        
        # Fallback to contact_phone from appointment
        if not phone:
            phone = appointment.contact_phone
            first_name = appointment.contact_name
        
        # Validate phone number exists
        if not phone:
            error_msg = "No phone number available for contact"
            logger.error(f"[APPOINTMENT_CONFIRMATION] {error_msg} for appointment {appointment.id}")
            run.status = 'failed'
            run.last_error = error_msg
            run.attempts += 1
            db.session.commit()
            return {'success': False, 'error': error_msg}
        
        # Load business
        business = Business.query.get(business_id)
        if not business:
            error_msg = f"Business {business_id} not found"
            logger.error(f"[APPOINTMENT_CONFIRMATION] {error_msg}")
            run.status = 'failed'
            run.last_error = error_msg
            run.attempts += 1
            db.session.commit()
            return {'success': False, 'error': error_msg}
        
        # Get representative name if available
        rep_name = business.name  # Default to business name
        if appointment.created_by:
            user = User.query.get(appointment.created_by)
            if user:
                rep_name = user.name or rep_name
        
        # Build template context
        context = {
            'first_name': first_name or 'לקוח יקר',
            'business_name': business.name,
            'appointment_date': format_hebrew_date(appointment.start_time),
            'appointment_time': appointment.start_time.strftime('%H:%M'),
            'appointment_location': appointment.location or 'המשרד שלנו',
            'rep_name': rep_name
        }
        
        # Render message
        message = render_template(automation.message_template, context)
        
        logger.info(f"[APPOINTMENT_CONFIRMATION] Sending WhatsApp to {phone} for appointment {appointment.id}")
        
        # Send WhatsApp message
        send_result = send_message(
            business_id=business_id,
            to_phone=phone,
            text=message,
            context='appointment_confirmation'
        )
        
        # Check if message was sent successfully
        # send_message returns: {"status": "sent|queued|accepted|error", ...}
        if send_result.get('status') in ['sent', 'queued', 'accepted']:
            # Mark as sent
            run.status = 'sent'
            run.sent_at = datetime.utcnow()
            run.attempts += 1
            db.session.commit()
            
            logger.info(f"[APPOINTMENT_CONFIRMATION] ✅ Message sent successfully for run {run_id}")
            return {
                'success': True,
                'run_id': run_id,
                'appointment_id': appointment.id,
                'phone': phone,
                'message_sent': True
            }
        else:
            # Mark as failed
            error_msg = send_result.get('error', 'Unknown error sending WhatsApp')
            run.status = 'failed'
            run.last_error = error_msg
            run.attempts += 1
            db.session.commit()
            
            logger.error(f"[APPOINTMENT_CONFIRMATION] ❌ Failed to send message for run {run_id}: {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'run_id': run_id
            }
        
    except Exception as e:
        logger.error(f"[APPOINTMENT_CONFIRMATION] Exception in job for run {run_id}: {e}", exc_info=True)
        
        # Try to update run status
        try:
            run = AppointmentAutomationRun.query.get(run_id)
            if run:
                run.status = 'failed'
                run.last_error = str(e)
                run.attempts += 1
                db.session.commit()
        except Exception as update_error:
            logger.error(f"[APPOINTMENT_CONFIRMATION] Could not update run status: {update_error}")
        
        return {
            'success': False,
            'error': str(e),
            'run_id': run_id
        }
