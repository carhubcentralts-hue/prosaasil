"""
Default Appointment Automation Templates
Pre-built Hebrew message templates for common automation scenarios

🎯 TEMPLATES:
- Day before reminder: Send confirmation reminder 24 hours before appointment
- Day after follow-up: Thank you message after appointment
- Two hours before: Last minute reminder
- Immediate confirmation: Confirm appointment as soon as status changes to scheduled
"""

# Default Hebrew message templates
DEFAULT_TEMPLATES = {
    'day_before_reminder': {
        'name': 'תזכורת יום לפני',
        'message': """היי {first_name} 👋

תזכורת לפגישה שלנו מחר:
📅 {appointment_date}
⏰ שעה: {appointment_time}
📍 מיקום: {appointment_location}

מאשר/ת הגעה? 
אשמח לתשובה מהירה 🙏

בברכה,
{rep_name}
{business_name}""",
        'schedule_offsets': [
            {'type': 'before', 'minutes': 1440}  # 24 hours before
        ],
        'trigger_statuses': ['scheduled', 'confirmed']
    },
    
    'two_hours_before': {
        'name': 'תזכורת שעתיים לפני',
        'message': """שלום {first_name} 👋

מזכיר/ה לך שיש לנו פגישה היום:
⏰ בעוד שעתיים, בשעה {appointment_time}
📍 כתובת: {appointment_location}

מחכים לראות אותך! ✨

{business_name}""",
        'schedule_offsets': [
            {'type': 'before', 'minutes': 120}  # 2 hours before
        ],
        'trigger_statuses': ['scheduled', 'confirmed']
    },
    
    'immediate_confirmation': {
        'name': 'אישור מיידי',
        'message': """היי {first_name}! 🎉

הפגישה נקבעה בהצלחה:

📅 {appointment_date}
⏰ שעה: {appointment_time}
📍 מיקום: {appointment_location}

אני {rep_name} מ{business_name} ואשמח לראות אותך!

אם צריך לשנות משהו, פשוט כתוב/י לי כאן 💬

בברכה ✨""",
        'schedule_offsets': [
            {'type': 'immediate'}
        ],
        'trigger_statuses': ['scheduled']
    },
    
    'day_after_followup': {
        'name': 'מעקב יום אחרי',
        'message': """היי {first_name}! 😊

תודה רבה שהגעת אתמול!

אשמח לדעת איך היה לך וכמובן נשמח לעזור בכל שאלה 🙏

אם תרצה/י לקבוע פגישה נוספת או שיש משהו שאני יכול לעזור בו - פשוט כתוב/י לי כאן.

{rep_name}
{business_name} 💙""",
        'schedule_offsets': [
            {'type': 'after', 'minutes': 1440}  # 24 hours after
        ],
        'trigger_statuses': ['completed']
    },
    
    'confirm_and_remind': {
        'name': 'אישור + תזכורת (מלא)',
        'message': """היי {first_name}! 👋

הפגישה נקבעה בהצלחה:
📅 {appointment_date}
⏰ שעה: {appointment_time}
📍 מיקום: {appointment_location}

אשמח לאישור הגעה 🙏

{rep_name}
{business_name}""",
        'schedule_offsets': [
            {'type': 'immediate'},
            {'type': 'before', 'minutes': 1440}  # Both immediate and day before
        ],
        'trigger_statuses': ['scheduled', 'confirmed']
    }
}


def get_template(template_key: str) -> dict:
    """
    Get a default template by key.
    
    Args:
        template_key: Template identifier (e.g., 'day_before_reminder')
    
    Returns:
        Dict with template configuration, or None if not found
    """
    return DEFAULT_TEMPLATES.get(template_key)


def list_templates() -> list:
    """
    Get list of all available default templates.
    
    Returns:
        List of template dicts with keys and names
    """
    return [
        {
            'key': key,
            'name': template['name'],
            'description': f"{len(template['schedule_offsets'])} אופציות תזמון"
        }
        for key, template in DEFAULT_TEMPLATES.items()
    ]


def create_default_automations(business_id: int, created_by: int = None) -> list:
    """
    Create all default automations for a business.
    
    This is useful for onboarding new businesses with pre-configured automations.
    
    Args:
        business_id: Business ID to create automations for
        created_by: User ID who created the automations
    
    Returns:
        List of created AppointmentAutomation objects
    """
    from server.models_sql import AppointmentAutomation
    from server.db import db
    
    created = []
    
    for key, template in DEFAULT_TEMPLATES.items():
        automation = AppointmentAutomation(
            business_id=business_id,
            name=template['name'],
            enabled=False,  # Created disabled by default - user must enable
            trigger_status_ids=template['trigger_statuses'],
            schedule_offsets=template['schedule_offsets'],
            channel='whatsapp',
            message_template=template['message'],
            send_once_per_offset=True,
            cancel_on_status_exit=True,
            created_by=created_by
        )
        db.session.add(automation)
        created.append(automation)
    
    db.session.commit()
    
    return created
