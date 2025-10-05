"""
Customer Intelligence Service - מערכת זיהוי ויצירת לקוחות אוטומטית
מחברת בין שיחות, WhatsApp, ולידים עם זיהוי חכם ויצירה אוטומטית
"""
import re
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from server.db import db
from server.models_sql import (
    Customer, Lead, CallLog, WhatsAppMessage, 
    LeadActivity, LeadStatus, Business
)

log = logging.getLogger(__name__)

class CustomerIntelligence:
    """מחלקה למיטוב זיהוי לקוחות ויצירת לידים אוטומטית"""
    
    def __init__(self, business_id: int):
        self.business_id = business_id
        self.business = Business.query.get(business_id)
        
    def find_or_create_customer_from_whatsapp(
        self, 
        phone_number: str, 
        message_text: str
    ) -> Tuple[Customer, Lead, bool]:
        """
        זיהוי או יצירת לקוח מתוך הודעת WhatsApp
        ✅ תמיד נרמל טלפון לפני בדיקה - מונע כפילויות!
        
        Returns:
            Tuple[Customer, Lead, bool]: (לקוח, ליד, האם נוצר חדש)
        """
        try:
            # ✅ נרמל טלפון קודם כל - תמיד +972 format
            phone_e164 = self._normalize_phone(phone_number)
            
            if not phone_e164 or not phone_e164.startswith('+972'):
                log.error(f"❌ Failed to normalize phone: {phone_number} -> {phone_e164}")
                raise ValueError(f"Invalid phone number format: {phone_number}")
            
            log.info(f"📱 WhatsApp from {phone_e164}")
            
            # חפש לקוח קיים לפי מספר טלפון מנורמל
            customer = Customer.query.filter_by(
                business_id=self.business_id,
                phone_e164=phone_e164
            ).first()
            
            was_created = False
            
            if not customer:
                # יצירת לקוח חדש
                extracted_info = self._extract_info_from_transcription(message_text)
                
                customer = Customer()
                customer.business_id = self.business_id
                customer.phone_e164 = phone_e164  # ✅ מנורמל!
                customer.name = extracted_info.get('name') or f"WhatsApp {phone_e164[-4:]}"
                customer.created_at = datetime.utcnow()
                
                db.session.add(customer)
                db.session.flush()
                was_created = True
                log.info(f"🆕 Created new customer: {customer.name} ({phone_e164})")
            
            # ✅ חפש ליד קיים לפי מספר מנורמל - מונע כפילויות!
            existing_lead = Lead.query.filter_by(
                tenant_id=self.business_id,
                phone_e164=phone_e164  # ✅ משתמש במספר מנורמל!
            ).filter(Lead.status.in_(['new', 'attempting', 'contacted', 'qualified'])).first()
            
            if not existing_lead:
                lead = self._create_lead_from_whatsapp(customer, message_text)
                log.info(f"🆕 Created new lead for {phone_e164}")
            else:
                lead = existing_lead
                # עדכון הליד הקיים עם מידע חדש
                self._update_lead_from_message(lead, message_text)
                log.info(f"♻️ Updated existing lead {lead.id} for {phone_e164}")
            
            db.session.commit()
            return customer, lead, was_created
            
        except Exception as e:
            db.session.rollback()
            log.error(f"❌ Error in WhatsApp customer/lead creation: {e}")
            # יצירת לקוח ליד fallback במקרה של שגיאה
            fallback_customer = self._create_fallback_customer(phone_number)
            fallback_lead = self._create_fallback_lead(fallback_customer, "whatsapp")
            return fallback_customer, fallback_lead, True

    def find_or_create_customer_from_call(
        self, 
        phone_number: str, 
        call_sid: str, 
        transcription: str = "",
        conversation_data: Optional[Dict] = None
    ) -> Tuple[Customer, Lead, bool]:
        """
        זיהוי או יצירת לקוח מתוך שיחה טלפונית
        
        Returns:
            (Customer, Lead, was_created): הלקוח, הליד, והאם נוצר חדש
        """
        try:
            # נקה מספר טלפון ל-E164
            clean_phone = self._normalize_phone(phone_number)
            
            # חפש לקוח קיים
            existing_customer = Customer.query.filter_by(
                business_id=self.business_id,
                phone_e164=clean_phone
            ).first()
            
            # חלץ מידע מתוך השיחה
            extracted_info = self._extract_info_from_transcription(transcription, conversation_data)
            
            if existing_customer:
                # לקוח קיים - עדכן/צור ליד חדש אם צריך
                lead = self._update_or_create_lead_for_existing_customer(
                    existing_customer, call_sid, extracted_info
                )
                log.info(f"🔍 Found existing customer: {existing_customer.name} (ID: {existing_customer.id})")
                return existing_customer, lead, False
            else:
                # לקוח חדש - צור הכל
                customer, lead = self._create_new_customer_and_lead(
                    clean_phone, call_sid, extracted_info
                )
                log.info(f"🆕 Created new customer: {customer.name} (ID: {customer.id})")
                return customer, lead, True
                
        except Exception as e:
            log.error(f"❌ Error in find_or_create_customer_from_call: {e}")
            # Return fallback Customer/Lead
            fallback_customer = self._create_fallback_customer(phone_number)
            fallback_lead = self._create_fallback_lead(fallback_customer, call_sid)
            return fallback_customer, fallback_lead, True
    
    def find_or_create_customer_from_whatsapp_with_direction(
        self,
        phone_number: str,
        message_body: str,
        direction: str = "in"
    ) -> Tuple[Customer, Lead, bool]:
        """
        זיהוי או יצירת לקוח מתוך הודעת WhatsApp
        
        Returns:
            (Customer, Lead, was_created): הלקוח, הליד, והאם נוצר חדש  
        """
        try:
            # נקה מספר טלפון ל-E164
            clean_phone = self._normalize_phone(phone_number)
            
            # חפש לקוח קיים
            existing_customer = Customer.query.filter_by(
                business_id=self.business_id,
                phone_e164=clean_phone
            ).first()
            
            # חלץ מידע מההודעה
            extracted_info = self._extract_info_from_whatsapp(message_body, direction)
            
            if existing_customer:
                # לקוח קיים - עדכן ליד
                lead = self._update_lead_from_whatsapp(existing_customer, message_body, extracted_info)
                log.info(f"📱 WhatsApp from existing customer: {existing_customer.name}")
                return existing_customer, lead, False
            else:
                # לקוח חדש מ-WhatsApp
                customer, lead = self._create_customer_and_lead_from_whatsapp(
                    clean_phone, message_body, extracted_info
                )
                log.info(f"📱🆕 New customer from WhatsApp: {customer.name}")
                return customer, lead, True
                
        except Exception as e:
            log.error(f"❌ Error in find_or_create_customer_from_whatsapp: {e}")
            # Return fallback
            fallback_customer = self._create_fallback_customer(phone_number)
            fallback_lead = self._create_fallback_lead(fallback_customer, "whatsapp")
            return fallback_customer, fallback_lead, True
    
    def generate_conversation_summary(
        self, 
        transcription: str = "", 
        conversation_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        יצירת סיכום חכם של השיחה עם זיהוי כוונות ומידע
        """
        try:
            if not transcription and not conversation_data:
                return {"summary": "שיחה ללא תוכן", "intent": "unknown", "next_action": ""}
            
            # טקסט מלא לניתוח
            full_text = transcription or ""
            if conversation_data and isinstance(conversation_data, dict):
                if "conversation_history" in conversation_data:
                    history_text = self._extract_text_from_conversation_history(
                        conversation_data["conversation_history"]
                    )
                    full_text += " " + history_text
            
            # ניתוח תוכן
            analysis = {
                "summary": self._generate_text_summary(full_text),
                "intent": self._classify_intent(full_text),
                "extracted_info": self._extract_structured_info(full_text),
                "next_action": self._suggest_next_action(full_text),
                "sentiment": self._analyze_sentiment(full_text),
                "urgency_level": self._assess_urgency(full_text)
            }
            
            return analysis
            
        except Exception as e:
            log.error(f"❌ Error generating conversation summary: {e}")
            return {
                "summary": "תקלה בניתוח השיחה",
                "intent": "error",
                "next_action": "בדיקה ידנית נדרשת"
            }
    
    def auto_update_lead_status(self, lead: Lead, conversation_analysis: Dict) -> str:
        """
        עדכון סטטוס ליד אוטומטית לפי תוכן השיחה
        
        Returns:
            new_status: הסטטוס החדש שנקבע
        """
        try:
            current_status = lead.status
            suggested_status = current_status
            
            # כללי עדכון סטטוס לפי תוכן
            intent = conversation_analysis.get("intent", "unknown")
            extracted_info = conversation_analysis.get("extracted_info", {})
            urgency = conversation_analysis.get("urgency_level", "normal")
            
            # לוגיקה לקביעת סטטוס חדש
            if intent == "meeting_request" or "פגישה" in conversation_analysis.get("summary", ""):
                suggested_status = "qualified"  # מוכשר - ביקש פגישה
                
            elif intent == "interested" and extracted_info.get("property_details"):
                suggested_status = "contacted"  # נוצר קשר - הביע עניין עם פרטים
                
            elif intent == "not_interested" or "לא מעוניין" in conversation_analysis.get("summary", ""):
                suggested_status = "unqualified"  # לא מוכשר
                
            elif urgency == "high" and current_status == "new":
                suggested_status = "attempting"  # בניסיון קשר - דחיפות גבוהה
                
            elif extracted_info.get("budget") and extracted_info.get("area"):
                suggested_status = "attempting"  # בניסיון קשר - יש מידע בסיסי
            
            # עדכון הסטטוס אם שונה
            if suggested_status != current_status:
                # וודא שהסטטוס קיים בעסק
                status_exists = LeadStatus.query.filter_by(
                    business_id=self.business_id,
                    name=suggested_status,
                    is_active=True
                ).first()
                
                if status_exists:
                    old_status = lead.status
                    lead.status = suggested_status
                    lead.updated_at = datetime.utcnow()
                    
                    # צור פעילות לשינוי סטטוס
                    self._create_status_change_activity(lead, old_status, suggested_status)
                    
                    db.session.commit()
                    log.info(f"📊 Auto-updated lead {lead.id} status: {old_status} → {suggested_status}")
                else:
                    log.warning(f"⚠️ Status '{suggested_status}' not found for business {self.business_id}")
            
            return suggested_status
            
        except Exception as e:
            log.error(f"❌ Error auto-updating lead status: {e}")
            return lead.status
    
    # === PRIVATE HELPER METHODS ===
    
    def _normalize_phone(self, phone: str) -> str:
        """נקה וסדר מספר טלפון לפורמט E164 - תמיד +972XXXXXXXXX"""
        if not phone:
            return ""
        
        # הסר תווים לא נומריים (שמור +)
        digits_only = re.sub(r'[^\d+]', '', phone)
        
        # התמודד עם פורמטים שונים - תמיד החזר +972
        if digits_only.startswith('+972'):
            # כבר בפורמט נכון
            return digits_only
        elif digits_only.startswith('972'):
            # חסר + בהתחלה
            return '+' + digits_only
        elif digits_only.startswith('0') and len(digits_only) == 10:
            # פורמט ישראלי מקומי: 0501234567 -> +972501234567
            return '+972' + digits_only[1:]
        elif len(digits_only) == 9:
            # חסר 0 בהתחלה: 501234567 -> +972501234567
            return '+972' + digits_only
        else:
            # פורמט לא מזוהה - נסה להוסיף +972 בכל מקרה
            log.warning(f"⚠️ Unrecognized phone format: {phone}, attempting +972 prefix")
            clean = digits_only.lstrip('+')
            if clean.startswith('972'):
                return '+' + clean
            else:
                return '+972' + clean
    
    def _extract_info_from_transcription(self, transcription: str, conversation_data: Optional[Dict] = None) -> Dict:
        """חלץ מידע מתמלול השיחה"""
        info = {}
        text = transcription.lower() if transcription else ""
        
        # שם
        name_patterns = [
            r'אני ([א-ת]+)', r'קוראים לי ([א-ת]+)', 
            r'השם שלי ([א-ת]+)', r'השם ([א-ת]+)'
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text)
            if match:
                info['name'] = match.group(1).strip()
                break
        
        # אזור
        areas = ['תל אביב', 'רמת גן', 'רמלה', 'לוד', 'בית שמש', 'מודיעין', 
                'פתח תקווה', 'רחובות', 'הרצליה', 'ירושלים', 'חיפה', 'באר שבע']
        for area in areas:
            if area in text:
                info['area'] = area
                break
        
        # סוג נכס
        property_types = ['דירה', 'חדרים', '2 חדרים', '3 חדרים', '4 חדרים', 'משרד', 'דופלקס', 'פנטהאוס']
        for prop_type in property_types:
            if prop_type in text:
                info['property_type'] = prop_type
                break
        
        # תקציב - חפש מספרים עם שקל/אלף/מיליון
        budget_match = re.search(r'(\d+(?:,\d+)*)\s*(שקל|אלף|מיליון|₪)', text)
        if budget_match:
            info['budget'] = budget_match.group(0)
        
        return info
    
    def _extract_info_from_whatsapp(self, message_body: str, direction: str) -> Dict:
        """חלץ מידע מהודעת WhatsApp"""
        info = {"source": "whatsapp", "direction": direction}
        
        if not message_body:
            return info
        
        text = message_body.lower()
        
        # זיהוי כוונה בסיסי
        if any(word in text for word in ['מעוניין', 'רוצה', 'לקנות', 'למכור', 'לשכור']):
            info['intent'] = 'interested'
        elif any(word in text for word in ['לא מעוניין', 'תודה לא', 'לא רוצה']):
            info['intent'] = 'not_interested'
        elif any(word in text for word in ['פגישה', 'לפגוש', 'לבוא לראות']):
            info['intent'] = 'meeting_request'
        
        # שם - דפוסים בסיסיים
        if 'אני ' in text:
            name_match = re.search(r'אני ([א-ת]+)', text)
            if name_match:
                info['name'] = name_match.group(1)
        
        return info
    
    def _create_new_customer_and_lead(self, phone: str, call_sid: str, extracted_info: Dict) -> Tuple[Customer, Lead]:
        """צור לקוח וליד חדשים"""
        # צור לקוח
        customer = Customer()
        customer.business_id = self.business_id
        customer.phone_e164 = phone
        customer.name = extracted_info.get('name', f"לקוח {phone[-4:]}")  # השתמש ב-4 ספרות אחרונות אם אין שם
        customer.status = "new"
        customer.created_at = datetime.utcnow()
        
        db.session.add(customer)
        db.session.flush()  # כדי לקבל ID
        
        # צור ליד
        lead = Lead()
        lead.tenant_id = self.business_id
        lead.phone_e164 = phone
        lead.source = "call"
        lead.external_id = call_sid
        lead.status = "new"
        lead.first_name = extracted_info.get('name', "")
        lead.notes = f"נוצר מתוך שיחה {call_sid}"
        lead.created_at = datetime.utcnow()
        
        # הוסף מידע נוסף לפתקיות
        if extracted_info:
            tags = []
            if extracted_info.get('area'):
                tags.append(f"area:{extracted_info['area']}")
            if extracted_info.get('property_type'):
                tags.append(f"property:{extracted_info['property_type']}")
            if extracted_info.get('budget'):
                tags.append(f"budget:{extracted_info['budget']}")
            lead.tags = tags
        
        db.session.add(lead)
        db.session.commit()
        
        return customer, lead
    
    def _create_customer_and_lead_from_whatsapp(self, phone: str, message: str, extracted_info: Dict) -> Tuple[Customer, Lead]:
        """צור לקוח וליד מ-WhatsApp"""
        # צור לקוח
        customer = Customer()
        customer.business_id = self.business_id
        customer.phone_e164 = phone
        customer.name = extracted_info.get('name', f"WhatsApp {phone[-4:]}")
        customer.status = "new"
        customer.created_at = datetime.utcnow()
        
        db.session.add(customer)
        db.session.flush()
        
        # צור ליד
        lead = Lead()
        lead.tenant_id = self.business_id
        lead.phone_e164 = phone
        lead.source = "whatsapp"
        lead.external_id = f"wa_{int(datetime.utcnow().timestamp())}"
        lead.status = "new"
        lead.first_name = extracted_info.get('name', "")
        lead.notes = f"נוצר מתוך WhatsApp: {message[:100]}..."
        lead.created_at = datetime.utcnow()
        
        db.session.add(lead)
        db.session.commit()
        
        return customer, lead
    
    def _update_or_create_lead_for_existing_customer(self, customer: Customer, call_sid: str, extracted_info: Dict) -> Lead:
        """עדכן או צור ליד עבור לקוח קיים"""
        # חפש ליד קיים לשיחה זו
        existing_lead = Lead.query.filter_by(
            tenant_id=self.business_id,
            phone_e164=customer.phone_e164,
            external_id=call_sid
        ).first()
        
        if existing_lead:
            # עדכן ליד קיים
            existing_lead.updated_at = datetime.utcnow()
            existing_lead.last_contact_at = datetime.utcnow()
            db.session.commit()
            return existing_lead
        else:
            # צור ליד חדש לשיחה חדשה
            lead = Lead()
            lead.tenant_id = self.business_id
            lead.phone_e164 = customer.phone_e164
            lead.source = "call"
            lead.external_id = call_sid
            lead.status = "attempting"  # לקוח קיים - ניסיון קשר חוזר
            lead.first_name = customer.name
            lead.notes = f"שיחה חוזרת מלקוח קיים - {call_sid}"
            lead.created_at = datetime.utcnow()
            lead.last_contact_at = datetime.utcnow()
            
            db.session.add(lead)
            db.session.commit()
            return lead
    
    def _update_lead_from_whatsapp(self, customer: Customer, message: str, extracted_info: Dict) -> Lead:
        """עדכן ליד עבור לקוח קיים מ-WhatsApp"""
        # חפש ליד פעיל אחרון
        recent_lead = Lead.query.filter_by(
            tenant_id=self.business_id,
            phone_e164=customer.phone_e164
        ).order_by(Lead.updated_at.desc()).first()
        
        if recent_lead:
            # עדכן ליד קיים
            recent_lead.updated_at = datetime.utcnow()
            recent_lead.last_contact_at = datetime.utcnow()
            
            # הוסף הודעה לפתקיות
            if recent_lead.notes:
                recent_lead.notes += f"\n[WhatsApp]: {message[:100]}..."
            else:
                recent_lead.notes = f"[WhatsApp]: {message[:100]}..."
            
            db.session.commit()
            return recent_lead
        else:
            # צור ליד חדש
            return self._create_customer_and_lead_from_whatsapp(
                customer.phone_e164, message, extracted_info
            )[1]
    
    def _create_lead_from_whatsapp(self, customer: Customer, message_text: str) -> Lead:
        """יצירת ליד חדש מהודעת WhatsApp"""
        extracted_info = self._extract_info_from_transcription(message_text)
        
        lead = Lead()
        lead.tenant_id = self.business_id
        lead.phone_e164 = customer.phone_e164  # ✅ FIX: Associate lead with phone number!
        # lead.customer_id = customer.id  # Use phone_e164 matching instead
        lead.source = "whatsapp"
        lead.status = "new"
        # Store extracted info in tags since fields don't exist in model
        lead_tags = {
            'area': extracted_info.get('area'),
            'property_type': extracted_info.get('property_type'),
            'budget_min': extracted_info.get('budget_min'),
            'budget_max': extracted_info.get('budget_max')
        }
        lead.tags = {k: v for k, v in lead_tags.items() if v is not None}
        lead.notes = f"WhatsApp: {message_text[:200]}..."
        lead.created_at = datetime.utcnow()
        
        db.session.add(lead)
        return lead
    
    def _update_lead_from_message(self, lead: Lead, message_text: str):
        """עדכון ליד קיים עם מידע חדש מהודעה"""
        extracted_info = self._extract_info_from_transcription(message_text)
        
        # עדכון שדות רק אם יש מידע חדש
        # Update tags with new extracted info
        current_tags = lead.tags or {}
        if extracted_info.get('area') and not current_tags.get('area'):
            current_tags['area'] = extracted_info['area']
        if extracted_info.get('property_type') and not current_tags.get('property_type'):
            current_tags['property_type'] = extracted_info['property_type']
        if extracted_info.get('budget_min') and not current_tags.get('budget_min'):
            current_tags['budget_min'] = extracted_info['budget_min']
        if extracted_info.get('budget_max') and not current_tags.get('budget_max'):
            current_tags['budget_max'] = extracted_info['budget_max']
        lead.tags = current_tags
        
        lead.updated_at = datetime.utcnow()

    def _create_fallback_customer(self, phone: str) -> Customer:
        """צור לקוח fallback במקרה של שגיאה"""
        customer = Customer()
        customer.business_id = self.business_id
        customer.phone_e164 = self._normalize_phone(phone)
        customer.name = f"לקוח {phone[-4:] if phone else 'לא ידוע'}"
        customer.status = "new"
        customer.created_at = datetime.utcnow()
        
        db.session.add(customer)
        db.session.commit()
        return customer
    
    def _create_fallback_lead(self, customer: Customer, external_id: str) -> Lead:
        """צור ליד fallback"""
        lead = Lead()
        lead.tenant_id = self.business_id
        lead.phone_e164 = customer.phone_e164
        lead.source = "call" if "CA_" in external_id else "whatsapp"
        lead.external_id = external_id
        lead.status = "new"
        lead.first_name = customer.name
        lead.notes = "נוצר אוטומטית - דרוש עדכון ידני"
        lead.created_at = datetime.utcnow()
        
        db.session.add(lead)
        db.session.commit()
        return lead
    
    def _generate_text_summary(self, text: str) -> str:
        """צור סיכום טקסט בסיסי"""
        if not text or len(text) < 20:
            return "שיחה קצרה"
        
        # סיכום בסיסי לפי מילות מפתח
        if "פגישה" in text:
            return "בקשה לתיאום פגישה"
        elif "לא מעוניין" in text:
            return "הביע חוסר עניין"
        elif "תקציב" in text and "אזור" in text:
            return "דיון על תקציב ומיקום"
        elif "דירה" in text or "חדרים" in text:
            return "עניין בנכסי מגורים"
        else:
            return f"שיחה כללית ({len(text)} תווים)"
    
    def _classify_intent(self, text: str) -> str:
        """סווג כוונה מהטקסט"""
        if not text:
            return "unknown"
        
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['פגישה', 'לפגוש', 'לבוא לראות']):
            return "meeting_request"
        elif any(word in text_lower for word in ['לא מעוניין', 'תודה לא', 'לא רוצה']):
            return "not_interested"
        elif any(word in text_lower for word in ['מעוניין', 'רוצה', 'לקנות']):
            return "interested"
        elif any(word in text_lower for word in ['מידע', 'פרטים', 'לשאול']):
            return "information_request"
        else:
            return "general_inquiry"
    
    def _extract_structured_info(self, text: str) -> Dict:
        """חלץ מידע מובנה מטקסט"""
        return self._extract_info_from_transcription(text)
    
    def _suggest_next_action(self, text: str) -> str:
        """הצע פעולה הבאה"""
        intent = self._classify_intent(text)
        
        if intent == "meeting_request":
            return "תיאום פגישה דחוף"
        elif intent == "not_interested":
            return "סיום מעקב"
        elif intent == "interested":
            return "שליחת פרטים נוספים"
        elif intent == "information_request":
            return "מתן מידע מפורט"
        else:
            return "מעקב תוך 24 שעות"
    
    def _analyze_sentiment(self, text: str) -> str:
        """נתח סנטימנט בסיסי"""
        if not text:
            return "neutral"
        
        positive_words = ['מעוניין', 'רוצה', 'מעולה', 'טוב', 'מושלם']
        negative_words = ['לא מעוניין', 'לא רוצה', 'לא טוב', 'בעיה']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _assess_urgency(self, text: str) -> str:
        """העריך רמת דחיפות"""
        if not text:
            return "normal"
        
        urgent_words = ['דחוף', 'מיידי', 'עכשיו', 'היום', 'בהקדם']
        text_lower = text.lower()
        
        if any(word in text_lower for word in urgent_words):
            return "high"
        elif "פגישה" in text_lower:
            return "medium"
        else:
            return "normal"
    
    def _extract_text_from_conversation_history(self, history: List) -> str:
        """חלץ טקסט מהיסטוריית שיחה"""
        if not history or not isinstance(history, list):
            return ""
        
        text_parts = []
        for turn in history:
            if isinstance(turn, dict):
                user_text = turn.get('user', '')
                bot_text = turn.get('bot', '')
                text_parts.append(f"{user_text} {bot_text}")
        
        return " ".join(text_parts)
    
    def _create_status_change_activity(self, lead: Lead, old_status: str, new_status: str):
        """צור פעילות לשינוי סטטוס"""
        activity = LeadActivity()
        activity.lead_id = lead.id
        activity.type = "status_change"
        activity.payload = {
            "old_status": old_status,
            "new_status": new_status,
            "automated": True,
            "reason": "AI analysis"
        }
        activity.at = datetime.utcnow()
        activity.created_by = None  # אוטומטי
        
        db.session.add(activity)