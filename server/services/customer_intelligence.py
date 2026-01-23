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
from server.agent_tools.phone_utils import normalize_phone

log = logging.getLogger(__name__)

# ✅ FIX: Default lead names as constants to avoid duplication
DEFAULT_LEAD_NAME_CALL = "ליד חדש - שיחה נכנסת"
DEFAULT_LEAD_NAME_WHATSAPP = "ליד חדש - WhatsApp"

class CustomerIntelligence:
    """מחלקה למיטוב זיהוי לקוחות ויצירת לידים אוטומטית"""
    
    def __init__(self, business_id: int):
        self.business_id = business_id
        self.business = Business.query.get(business_id)
        
    def find_or_create_customer_from_whatsapp(
        self, 
        phone_number: str, 
        message_text: str,
        whatsapp_jid: str = None,
        whatsapp_jid_alt: str = None,
        phone_raw: str = None,
        push_name: str = None
    ) -> Tuple[Customer, Lead, bool]:
        """
        זיהוי או יצירת לקוח מתוך הודעת WhatsApp
        ✅ תמיד נרמל טלפון לפני בדיקה - מונע כפילויות!
        🔥 FIX #3 & #6: Support @lid identifiers and WhatsApp JID mapping
        🆕 Name saving: Save pushName from WhatsApp with smart upsert logic
        
        Args:
            phone_number: Phone number or external ID (may be @lid)
            message_text: Message content
            whatsapp_jid: Primary WhatsApp identifier (remoteJid)
            whatsapp_jid_alt: Alternative WhatsApp identifier (sender_pn/participant)
            phone_raw: Original phone input before normalization
            push_name: WhatsApp pushName (display name)
        
        Returns:
            Tuple[Customer, Lead, bool]: (לקוח, ליד, האם נוצר חדש)
        """
        try:
            # 🔥 FIX #6: Check if this is @lid or other non-phone identifier
            if not phone_number or '_at_lid' in str(phone_number) or '@lid' in str(phone_number):
                # @lid format - no real phone number available
                # Use external_id for deduplication instead of phone_e164
                log.info(f"📱 WhatsApp @lid identifier detected: {phone_number}")
                return self._handle_lid_message(phone_number, message_text, whatsapp_jid, whatsapp_jid_alt)
            
            # ✅ נרמל טלפון קודם כל - תמיד E.164 format
            phone_e164 = self._normalize_phone(phone_number)
            
            if not phone_e164:
                log.error(f"❌ Failed to normalize phone: {phone_number} -> {phone_e164}")
                # If normalization fails, try to use as external ID
                if whatsapp_jid:
                    return self._handle_lid_message(phone_number, message_text, whatsapp_jid, whatsapp_jid_alt)
                raise ValueError(f"Invalid phone number format: {phone_number}")
            
            log.info(f"📱 WhatsApp from {phone_e164}")
            
            # 🔥 FIX #3: Calculate reply_jid - prefer @s.whatsapp.net over @lid
            # Rule: Always reply to the most specific identifier
            reply_jid = whatsapp_jid  # Default: use remoteJid
            reply_jid_type = 'unknown'
            
            if whatsapp_jid_alt and whatsapp_jid_alt.endswith('@s.whatsapp.net'):
                # Prefer participant/sender_pn if it's a standard WhatsApp number
                reply_jid = whatsapp_jid_alt
                reply_jid_type = 's.whatsapp.net'
                log.debug(f"[WA] Using whatsapp_jid_alt as reply_jid: {reply_jid}")
            elif whatsapp_jid:
                if whatsapp_jid.endswith('@s.whatsapp.net'):
                    reply_jid_type = 's.whatsapp.net'
                elif whatsapp_jid.endswith('@lid'):
                    reply_jid_type = 'lid'
                elif whatsapp_jid.endswith('@g.us'):
                    reply_jid_type = 'g.us'
                log.debug(f"[WA] Using whatsapp_jid as reply_jid: {reply_jid} (type={reply_jid_type})")
            
            # 🔥 FIX #7: Upsert priority - ALWAYS prefer phone over JID
            # Reason: JID can change (LID/Android) but phone is stable
            # Priority: 1) phone_e164  2) reply_jid  3) whatsapp_jid_alt  4) whatsapp_jid
            existing_lead = None
            
            # Priority 1: Search by normalized phone (most reliable)
            if phone_e164:
                existing_lead = Lead.query.filter_by(
                    tenant_id=self.business_id,
                    phone_e164=phone_e164
                ).order_by(Lead.updated_at.desc()).first()
                
                if existing_lead:
                    log.info(f"♻️ Found existing lead by phone_e164: {phone_e164}")
            
            # Priority 2: Search by reply_jid (if no phone match)
            if not existing_lead and reply_jid:
                existing_lead = Lead.query.filter_by(
                    tenant_id=self.business_id,
                    reply_jid=reply_jid
                ).order_by(Lead.updated_at.desc()).first()
                
                if existing_lead:
                    log.info(f"♻️ Found existing lead by reply_jid: {reply_jid}")
            
            # Priority 3: Search by whatsapp_jid_alt (if no phone or reply_jid match)
            if not existing_lead and whatsapp_jid_alt:
                existing_lead = Lead.query.filter_by(
                    tenant_id=self.business_id,
                    whatsapp_jid_alt=whatsapp_jid_alt
                ).order_by(Lead.updated_at.desc()).first()
                
                if existing_lead:
                    log.info(f"♻️ Found existing lead by whatsapp_jid_alt: {whatsapp_jid_alt}")
            
            # Priority 4: Search by whatsapp_jid (last resort)
            if not existing_lead and whatsapp_jid:
                existing_lead = Lead.query.filter_by(
                    tenant_id=self.business_id,
                    whatsapp_jid=whatsapp_jid
                ).order_by(Lead.updated_at.desc()).first()
                
                if existing_lead:
                    log.info(f"♻️ Found existing lead by whatsapp_jid: {whatsapp_jid}")
            
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
                customer.name = extracted_info.get('name') or DEFAULT_LEAD_NAME_WHATSAPP
                customer.created_at = datetime.utcnow()
                
                db.session.add(customer)
                db.session.flush()
                was_created = True
                log.info(f"🆕 Created new customer: {customer.name} ({phone_e164})")
            
            if not existing_lead:
                lead = self._create_lead_from_whatsapp(
                    customer, message_text, 
                    whatsapp_jid=whatsapp_jid, 
                    whatsapp_jid_alt=whatsapp_jid_alt,
                    reply_jid=reply_jid,
                    reply_jid_type=reply_jid_type,
                    phone_raw=phone_raw
                )
                log.info(f"🆕 Created new lead for {phone_e164} with reply_jid={reply_jid} (type={reply_jid_type})")
            else:
                lead = existing_lead
                # 🔥 FIX #3 & #4: ALWAYS update reply_jid and type to last seen (critical for Android/LID)
                # Only update from actual client messages, not system/protocol messages
                lead.reply_jid = reply_jid
                lead.reply_jid_type = reply_jid_type
                log.info(f"♻️ Updated reply_jid to latest: {reply_jid} (type={reply_jid_type})")
                
                # 🔥 FIX #6: Update WhatsApp JID fields if they've changed
                if whatsapp_jid and not lead.whatsapp_jid:
                    lead.whatsapp_jid = whatsapp_jid
                if whatsapp_jid_alt and not lead.whatsapp_jid_alt:
                    lead.whatsapp_jid_alt = whatsapp_jid_alt
                if phone_raw and not lead.phone_raw:
                    lead.phone_raw = phone_raw
                    
                # עדכון הליד הקיים עם מידע חדש
                self._update_lead_from_message(lead, message_text)
                log.info(f"♻️ Updated existing lead {lead.id} for {phone_e164}")
            
            # 🆕 Name saving: Update lead name from pushName if available
            if push_name:
                from server.utils.name_utils import normalize_name, is_name_better
                normalized_name = normalize_name(push_name)
                
                if normalized_name:
                    # Check if we should update the name
                    should_update = is_name_better(
                        new_name=normalized_name,
                        old_name=lead.name or "",
                        new_source='whatsapp',
                        old_source=lead.name_source or ""
                    )
                    
                    if should_update:
                        lead.name = normalized_name
                        lead.name_source = 'whatsapp'
                        lead.name_updated_at = datetime.utcnow()
                        log.info(f"lead_upsert: phone={phone_e164} source=whatsapp pushName=\"{push_name}\" applied=true reason=name_improved")
                    else:
                        log.info(f"lead_upsert: phone={phone_e164} source=whatsapp pushName=\"{push_name}\" applied=false reason=existing_name_better old_name=\"{lead.name}\" old_source={lead.name_source}")
                else:
                    log.debug(f"lead_upsert: phone={phone_e164} source=whatsapp pushName=\"{push_name}\" applied=false reason=invalid_name")
            
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
        conversation_data: Optional[Dict] = None,
        caller_name: str = None
    ) -> Tuple[Customer, Lead, bool]:
        """
        זיהוי או יצירת לקוח מתוך שיחה טלפונית
        🆕 Caller name: Save caller name with smart upsert logic
        
        Args:
            phone_number: E.164 phone number
            call_sid: Twilio call SID
            transcription: Call transcription
            conversation_data: Conversation context
            caller_name: Caller ID name (if available)
        
        Returns:
            (Customer, Lead, was_created): הלקוח, הליד, והאם נוצר חדש
        """
        try:
            # נקה מספר טלפון ל-E164
            clean_phone = self._normalize_phone(phone_number)
            
            # 🔍 TRACE: Generate trace_id for phone call
            trace_id = f"{self.business_id}:{clean_phone}:{call_sid}"
            
            # 🔍 TRACE: Log lead upsert for phone call
            log.info(f"🔍 [LEAD_UPSERT_START] trace_id={trace_id} business_id={self.business_id} phone={clean_phone} source=call")
            
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
                
                # 🆕 Name saving: Update lead name from caller_name if available
                if caller_name and lead:
                    from server.utils.name_utils import normalize_name, is_name_better
                    normalized_name = normalize_name(caller_name)
                    
                    if normalized_name:
                        # Check if we should update the name
                        should_update = is_name_better(
                            new_name=normalized_name,
                            old_name=lead.name or "",
                            new_source='call',
                            old_source=lead.name_source or ""
                        )
                        
                        if should_update:
                            lead.name = normalized_name
                            lead.name_source = 'call'
                            lead.name_updated_at = datetime.utcnow()
                            log.info(f"lead_upsert: phone={clean_phone} source=call caller_name=\"{caller_name}\" applied=true reason=name_improved")
                        else:
                            log.info(f"lead_upsert: phone={clean_phone} source=call caller_name=\"{caller_name}\" applied=false reason=existing_name_better old_name=\"{lead.name}\" old_source={lead.name_source}")
                    else:
                        log.debug(f"lead_upsert: phone={clean_phone} source=call caller_name=\"{caller_name}\" applied=false reason=invalid_name")
                
                log.info(f"✅ [LEAD_UPSERT_DONE] trace_id={trace_id} lead_id={lead.id if lead else 'N/A'} action=updated phone={clean_phone}")
                log.info(f"🔍 Found existing customer: {existing_customer.name} (ID: {existing_customer.id})")
                return existing_customer, lead, False
            else:
                # לקוח חדש - צור הכל
                customer, lead = self._create_new_customer_and_lead(
                    clean_phone, call_sid, extracted_info
                )
                
                # 🆕 Name saving: Update lead name from caller_name if available
                if caller_name and lead:
                    from server.utils.name_utils import normalize_name
                    normalized_name = normalize_name(caller_name)
                    
                    if normalized_name:
                        lead.name = normalized_name
                        lead.name_source = 'call'
                        lead.name_updated_at = datetime.utcnow()
                        log.info(f"lead_upsert: phone={clean_phone} source=call caller_name=\"{caller_name}\" applied=true reason=new_lead")
                    else:
                        log.debug(f"lead_upsert: phone={clean_phone} source=call caller_name=\"{caller_name}\" applied=false reason=invalid_name")
                
                log.info(f"✅ [LEAD_UPSERT_DONE] trace_id={trace_id} lead_id={lead.id if lead else 'N/A'} action=created phone={clean_phone}")
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
        """
        🔥 FIX #6: Use universal normalize_phone function - Single source of truth
        
        Normalizes phone numbers to E.164 format (+972... for Israeli, +... for others)
        Handles @lid and other non-phone identifiers gracefully.
        
        Returns:
            - Normalized E.164 phone (+972...) for valid phone numbers
            - Original string for @lid or invalid formats (NOT a phone number)
        """
        if not phone:
            return ""
        
        # 🔥 FIX #6: Use the universal normalize_phone function
        normalized = normalize_phone(phone)
        
        if normalized:
            # Successfully normalized to E.164
            log.debug(f"📱 Phone normalized: {phone} -> {normalized}")
            return normalized
        else:
            # Not a valid phone number (could be @lid or other identifier)
            log.info(f"📱 Not a phone number or invalid format: {phone} - returning as-is")
            return phone  # Return original for @lid or external IDs
            # Validate that it could be a valid phone number before adding prefix
            if len(digits_only) > 15 or len(digits_only) < 8:
                # Invalid phone length - return as-is
                log.warning(f"⚠️ Invalid phone length ({len(digits_only)} digits): {phone} - not normalizing")
                return phone
            
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
        
        # אזור - 🔥 BUILD 186: Use dynamic lexicon instead of hardcoded list
        try:
            from server.services.hebrew_stt_validator import load_hebrew_lexicon
            cities_set, _, _ = load_hebrew_lexicon()
            for area in cities_set:
                if len(area) > 2 and area in text:
                    info['area'] = area
                    break
        except Exception:
            pass  # If lexicon not available, skip area detection
        
        # 🔥 BUILD 200: REMOVED hardcoded property_type detection
        # Property types are business-specific (real estate, medical, etc.)
        # This is now handled dynamically by AI prompts per business
        
        # 🔥 BUILD 200: REMOVED hardcoded budget detection
        # Budget is a business-specific field, not all businesses need it
        # This is now handled dynamically by AI prompts per business
        
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
        # ✅ בדיקה כפולה: וודא שאין ליד קיים לפני יצירה
        # 🔥 SIMPLIFIED: Just check by phone number, no status filtering
        existing_lead = Lead.query.filter_by(
            tenant_id=self.business_id,
            phone_e164=phone
        ).order_by(Lead.updated_at.desc()).first()
        
        # אם יש ליד קיים - רק צור לקוח ועדכן ליד
        if existing_lead:
            log.warning(f"⚠️ Found existing lead {existing_lead.id} for {phone}, updating instead of creating new")
            customer = Customer()
            customer.business_id = self.business_id
            customer.phone_e164 = phone
            customer.name = extracted_info.get('name', DEFAULT_LEAD_NAME_CALL)
            customer.status = "new"
            customer.created_at = datetime.utcnow()
            db.session.add(customer)
            db.session.flush()
            
            # עדכן ליד קיים
            existing_lead.updated_at = datetime.utcnow()
            existing_lead.last_contact_at = datetime.utcnow()
            if existing_lead.notes:
                existing_lead.notes += f"\n[שיחה {call_sid}]: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
            db.session.commit()
            return customer, existing_lead
        
        # צור לקוח חדש
        customer = Customer()
        customer.business_id = self.business_id
        customer.phone_e164 = phone
        customer.name = extracted_info.get('name', DEFAULT_LEAD_NAME_CALL)
        customer.status = "new"
        customer.created_at = datetime.utcnow()
        
        db.session.add(customer)
        db.session.flush()  # כדי לקבל ID
        
        # צור ליד חדש
        lead = Lead()
        lead.tenant_id = self.business_id
        lead.phone_e164 = phone
        lead.source = "call"
        lead.external_id = call_sid
        lead.status = "new"
        lead.first_name = extracted_info.get('name', DEFAULT_LEAD_NAME_CALL)
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
        log.info(f"🆕 Created new customer and lead for {phone}")
        
        return customer, lead
    
    def _create_customer_and_lead_from_whatsapp(self, phone: str, message: str, extracted_info: Dict) -> Tuple[Customer, Lead]:
        """צור לקוח וליד מ-WhatsApp"""
        # צור לקוח
        customer = Customer()
        customer.business_id = self.business_id
        customer.phone_e164 = phone
        customer.name = extracted_info.get('name', DEFAULT_LEAD_NAME_WHATSAPP)
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
        lead.first_name = extracted_info.get('name', DEFAULT_LEAD_NAME_WHATSAPP)
        lead.notes = f"נוצר מתוך WhatsApp: {message[:100]}..."
        lead.created_at = datetime.utcnow()
        
        db.session.add(lead)
        db.session.commit()
        
        return customer, lead
    
    def _update_or_create_lead_for_existing_customer(self, customer: Customer, call_sid: str, extracted_info: Dict) -> Lead:
        """
        🔥 FIX: עדכן ליד קיים במקום ליצור חדש - מונע כפילויות!
        
        כל מספר טלפון = ליד אחד בלבד!
        אם יש ליד קיים, נעדכן אותו גם אם הוא סגור או הושלם.
        """
        # ✅ חפש ליד קיים לאותו מספר טלפון בלבד (לא לפי call_sid!)
        # 🔥 FIX: Always update existing lead, never create duplicate
        existing_lead = Lead.query.filter_by(
            tenant_id=self.business_id,
            phone_e164=customer.phone_e164
        ).order_by(Lead.updated_at.desc()).first()
        
        if existing_lead:
            # ✅ עדכן ליד קיים - הוסף call_sid לפתקיות
            existing_lead.updated_at = datetime.utcnow()
            existing_lead.last_contact_at = datetime.utcnow()
            
            # הוסף הערה על השיחה החדשה
            if existing_lead.notes:
                existing_lead.notes += f"\n[שיחה {call_sid}]: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
            else:
                existing_lead.notes = f"[שיחה {call_sid}]: {datetime.utcnow().strftime('%d/%m/%Y %H:%M')}"
            
            db.session.commit()
            log.info(f"♻️ Updated existing lead {existing_lead.id} for phone {customer.phone_e164}")
            return existing_lead
        else:
            # 🔥 FIX: צור ליד חדש רק אם אין בכלל ליד לטלפון זה
            # זה המקרה הראשון שהלקוח מתקשר
            lead = Lead()
            lead.tenant_id = self.business_id
            lead.phone_e164 = customer.phone_e164
            lead.source = "call"
            lead.external_id = call_sid
            lead.status = "new"  # 🔥 FIX: שיחה ראשונה = סטטוס "new" ולא "attempting"
            lead.first_name = customer.name
            lead.notes = f"שיחה ראשונה - {call_sid}"
            lead.created_at = datetime.utcnow()
            lead.last_contact_at = datetime.utcnow()
            
            db.session.add(lead)
            db.session.commit()
            log.info(f"🆕 Created first lead for customer phone {customer.phone_e164}")
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
    
    def _create_lead_from_whatsapp(
        self, 
        customer: Customer, 
        message_text: str,
        whatsapp_jid: str = None,
        whatsapp_jid_alt: str = None,
        reply_jid: str = None,
        reply_jid_type: str = None,
        phone_raw: str = None
    ) -> Lead:
        """
        יצירת ליד חדש מהודעת WhatsApp
        🔥 FIX #3 & #4 & #6: Store WhatsApp JID, reply_jid, reply_jid_type, and phone_raw
        """
        extracted_info = self._extract_info_from_transcription(message_text)
        
        lead = Lead()
        lead.tenant_id = self.business_id
        lead.phone_e164 = customer.phone_e164  # ✅ FIX: Associate lead with phone number!
        lead.phone_raw = phone_raw  # 🔥 FIX #6: Store original phone for debugging
        lead.whatsapp_jid = whatsapp_jid  # 🔥 FIX #3: Store WhatsApp identifier
        lead.whatsapp_jid_alt = whatsapp_jid_alt  # 🔥 FIX #3: Store alternative identifier
        lead.reply_jid = reply_jid  # 🔥 FIX #3: Store EXACT JID to reply to
        lead.reply_jid_type = reply_jid_type  # 🔥 FIX #4: Store JID type
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
        customer.name = DEFAULT_LEAD_NAME_CALL
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
        source = "call" if "CA_" in external_id else "whatsapp"
        lead.source = source
        lead.external_id = external_id
        lead.status = "new"
        # ✅ FIX: Set appropriate default name based on source
        lead.first_name = DEFAULT_LEAD_NAME_WHATSAPP if source == "whatsapp" else DEFAULT_LEAD_NAME_CALL
        lead.notes = "נוצר אוטומטית - דרוש עדכון ידני"
        lead.created_at = datetime.utcnow()
        
        db.session.add(lead)
        db.session.commit()
        return lead
    
    def _handle_lid_message(
        self, 
        lid_identifier: str, 
        message_text: str,
        whatsapp_jid: str = None,
        whatsapp_jid_alt: str = None
    ) -> Tuple[None, Lead, bool]:
        """
        🔥 FIX #3: Handle WhatsApp @lid messages (non-phone identifiers)
        
        @lid is used for:
        - WhatsApp Business accounts without phone numbers
        - Channel messages
        - Other non-standard WhatsApp identifiers
        
        Since there's no phone number, we:
        1. Store lid_identifier as external_id for deduplication
        2. Store whatsapp_jid/whatsapp_jid_alt for proper routing
        3. Calculate reply_jid for sending responses
        4. Don't create Customer (no phone = no customer)
        5. Create Lead with source="whatsapp_lid"
        
        Args:
            lid_identifier: The @lid identifier (e.g., "135871961501772@lid")
            message_text: The message content
            whatsapp_jid: Primary WhatsApp identifier (remoteJid)
            whatsapp_jid_alt: Alternative identifier (sender_pn/participant)
            
        Returns:
            (None, Lead, was_created): No customer, the lead, and whether it was newly created
        """
        try:
            # 🔥 FIX #3 & #4: Calculate reply_jid and type for sending
            reply_jid = whatsapp_jid or lid_identifier
            reply_jid_type = 'lid'  # Default for @lid
            
            if whatsapp_jid_alt and whatsapp_jid_alt.endswith('@s.whatsapp.net'):
                reply_jid = whatsapp_jid_alt
                reply_jid_type = 's.whatsapp.net'
            elif whatsapp_jid and whatsapp_jid.endswith('@s.whatsapp.net'):
                reply_jid_type = 's.whatsapp.net'
            
            # Look for existing lead with this external_id or whatsapp_jid
            existing_lead = None
            if whatsapp_jid:
                existing_lead = Lead.query.filter_by(
                    tenant_id=self.business_id,
                    whatsapp_jid=whatsapp_jid
                ).order_by(Lead.updated_at.desc()).first()
            
            if not existing_lead:
                existing_lead = Lead.query.filter_by(
                    tenant_id=self.business_id,
                    external_id=lid_identifier
                ).order_by(Lead.updated_at.desc()).first()
            
            if existing_lead:
                # Update existing lead
                existing_lead.updated_at = datetime.utcnow()
                # 🔥 FIX #3 & #4: ALWAYS update reply_jid and type to latest
                existing_lead.reply_jid = reply_jid
                existing_lead.reply_jid_type = reply_jid_type
                if whatsapp_jid and not existing_lead.whatsapp_jid:
                    existing_lead.whatsapp_jid = whatsapp_jid
                if whatsapp_jid_alt and not existing_lead.whatsapp_jid_alt:
                    existing_lead.whatsapp_jid_alt = whatsapp_jid_alt
                    
                if existing_lead.notes:
                    existing_lead.notes += f"\n[WhatsApp @lid]: {message_text[:100]}..."
                else:
                    existing_lead.notes = f"[WhatsApp @lid]: {message_text[:100]}..."
                
                db.session.commit()
                log.info(f"♻️ Updated existing @lid lead {existing_lead.id} with reply_jid={reply_jid} (type={reply_jid_type})")
                return None, existing_lead, False
            else:
                # Create new lead for @lid
                extracted_info = self._extract_info_from_transcription(message_text)
                
                lead = Lead()
                lead.tenant_id = self.business_id
                lead.external_id = lid_identifier  # Use @lid as unique identifier
                lead.phone_e164 = None  # No phone number for @lid
                lead.whatsapp_jid = whatsapp_jid  # 🔥 FIX #3: Store WhatsApp identifier
                lead.whatsapp_jid_alt = whatsapp_jid_alt  # 🔥 FIX #3: Store alternative identifier
                lead.reply_jid = reply_jid  # 🔥 FIX #3: Store reply target
                lead.reply_jid_type = reply_jid_type  # 🔥 FIX #4: Store JID type
                lead.source = "whatsapp_lid"  # Special source to identify @lid leads
                lead.status = "new"
                lead.first_name = extracted_info.get('name') or DEFAULT_LEAD_NAME_WHATSAPP
                lead.notes = f"WhatsApp @lid: {message_text[:200]}... (זיהוי: {lid_identifier})"
                lead.created_at = datetime.utcnow()
                
                db.session.add(lead)
                db.session.commit()
                log.info(f"🆕 Created new @lid lead with reply_jid={reply_jid} (type={reply_jid_type})")
                return None, lead, True
                
        except Exception as e:
            log.error(f"❌ Error handling @lid message: {e}")
            db.session.rollback()
            # Don't use fallback - just skip this message
            raise
    
    def _generate_text_summary(self, text: str) -> str:
        """BUILD 147: סיכום טקסט דינמי באמצעות GPT-4o-mini
        BUILD 183: Returns empty string if no user speech (don't hallucinate!)
        """
        if not text or len(text) < 20:
            return ""  # 🔥 BUILD 183: Return empty, not fake text!
        
        try:
            # Use the dynamic summary service for AI-powered summaries
            from server.services.summary_service import summarize_conversation
            
            # Get business context for better summaries
            business = Business.query.get(self.business_id) if self.business_id else None
            business_name = business.name if business else None
            business_type = business.business_type if business else None
            
            # Generate dynamic AI summary
            summary = summarize_conversation(
                transcription=text,
                call_sid=f"summary_{self.business_id}",
                business_type=business_type,
                business_name=business_name
            )
            
            # 🔥 BUILD 183: summarize_conversation returns "" if no user speech
            # Respect that and return empty - don't hallucinate!
            if summary and len(summary) > 10:
                return summary
            else:
                return ""  # No summary generated = return empty
                
        except Exception as e:
            log.warning(f"⚠️ Dynamic summary failed: {e}")
            return ""  # 🔥 BUILD 183: On error, return empty, not fake text
    
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