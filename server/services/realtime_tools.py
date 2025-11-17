"""
OpenAI Realtime API Tools - Calendar & Leads
Convert agent tools to Realtime API function calling format
"""


def get_realtime_tools(business_id: int) -> list:
    """
    Get tools in OpenAI Realtime API format
    
    Tools:
    - calendar_find_slots: Find available appointment slots
    - calendar_create_appointment: Book appointments
    - leads_upsert: Create or update leads
    
    Returns:
        List of tool definitions for Realtime API
    """
    tools = [
        {
            "type": "function",
            "name": "calendar_find_slots",
            "description": "חפש שעות פנויות לתור. השתמש בכלי הזה כשלקוח שואל 'מתי יש פנוי?' או 'אפשר לראות שעות?'",
            "parameters": {
                "type": "object",
                "properties": {
                    "date_iso": {
                        "type": "string",
                        "description": "התאריך בפורמט YYYY-MM-DD (למשל: '2025-11-20'). 'מחר' = התאריך המחר."
                    },
                    "preferred_time": {
                        "type": "string",
                        "description": "שעה מועדפת בפורמט HH:MM (למשל: '14:00'). אם לקוח ביקש שעה ספציפית - שלח אותה כאן!"
                    }
                },
                "required": ["date_iso"]
            }
        },
        {
            "type": "function",
            "name": "calendar_create_appointment",
            "description": "קבע תור חדש. השתמש רק אחרי שהלקוח אישר תאריך, שעה ושם מלא!",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "שם מלא של הלקוח (לא 'לקוח' או 'unknown'!). חובה לשאול אם לא ניתן."
                    },
                    "treatment_type": {
                        "type": "string",
                        "description": "סוג הטיפול/שירות (למשל: 'ייעוץ נדלן', 'צפייה בדירה')"
                    },
                    "start_iso": {
                        "type": "string",
                        "description": "זמן התחלה בפורמט ISO עם timezone (למשל: '2025-11-20T14:00:00+02:00')"
                    },
                    "end_iso": {
                        "type": "string",
                        "description": "זמן סיום בפורמט ISO עם timezone (למשל: '2025-11-20T15:00:00+02:00')"
                    },
                    "notes": {
                        "type": "string",
                        "description": "הערות נוספות (אופציונלי)"
                    }
                },
                "required": ["customer_name", "treatment_type", "start_iso", "end_iso"]
            }
        },
        {
            "type": "function",
            "name": "leads_upsert",
            "description": "צור או עדכן lead (פרטי לקוח). השתמש אם לקוח נתן פרטים או שאלת שאלה שדורשת חיפוש.",
            "parameters": {
                "type": "object",
                "properties": {
                    "first_name": {
                        "type": "string",
                        "description": "שם פרטי"
                    },
                    "last_name": {
                        "type": "string",
                        "description": "שם משפחה"
                    },
                    "summary": {
                        "type": "string",
                        "description": "תקציר קצר של השיחה (10-30 מילים)"
                    },
                    "notes": {
                        "type": "string",
                        "description": "הערות מהשיחה"
                    }
                },
                "required": []
            }
        }
    ]
    
    return tools
