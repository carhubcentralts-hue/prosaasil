"""
Recurring Scheduled Messages Job
Runs every hour to check for recurring schedule rules and create messages for leads
"""
import logging
from datetime import datetime
from server.db import db
from server.models_sql import ScheduledMessageRule, Lead, LeadStatus, Business, ScheduledMessagesQueue
from server.services import scheduled_messages_service
from server.agent_tools.phone_utils import normalize_phone

logger = logging.getLogger(__name__)


def recurring_scheduled_messages_job():
    """
    Job that runs every hour to process recurring scheduled message rules
    
    This job:
    1. Finds all active rules with schedule_type="RECURRING_TIME"
    2. Checks if current time matches any of the recurring_times
    3. Checks if current day matches any of the active_weekdays
    4. Creates scheduled messages for all leads in the matching statuses
    """
    logger.info("[RECURRING-MSG-JOB] Starting recurring messages job")
    
    try:
        # Get current time (hour:minute) and weekday (0=Sunday, 6=Saturday)
        now = datetime.utcnow()
        current_time = now.strftime("%H:%M")
        current_weekday = (now.weekday() + 1) % 7  # Convert Python weekday to our format
        
        logger.info(f"[RECURRING-MSG-JOB] Current time: {current_time}, weekday: {current_weekday}")
        
        # Find all active RECURRING_TIME rules
        rules = db.session.query(ScheduledMessageRule).filter(
            ScheduledMessageRule.is_active == True,
            ScheduledMessageRule.schedule_type == 'RECURRING_TIME'
        ).all()
        
        if not rules:
            logger.debug("[RECURRING-MSG-JOB] No active recurring rules found")
            return {
                'status': 'success',
                'rules_checked': 0,
                'messages_created': 0
            }
        
        logger.info(f"[RECURRING-MSG-JOB] Found {len(rules)} active recurring rule(s)")
        
        messages_created = 0
        rules_matched = 0
        
        for rule in rules:
            try:
                # Check if this rule should run at current time
                if not rule.recurring_times or current_time not in rule.recurring_times:
                    logger.debug(f"[RECURRING-MSG-JOB] Rule {rule.id} - time {current_time} not in recurring_times")
                    continue
                
                # Check if this rule should run on current weekday
                if rule.active_weekdays and current_weekday not in rule.active_weekdays:
                    logger.debug(f"[RECURRING-MSG-JOB] Rule {rule.id} - weekday {current_weekday} not in active_weekdays")
                    continue
                
                rules_matched += 1
                logger.info(f"[RECURRING-MSG-JOB] Rule {rule.id} ('{rule.name}') matched - processing...")
                
                # Get all status IDs for this rule
                status_ids = [s.id for s in rule.statuses]
                
                # Get all leads in these statuses for this business
                leads = db.session.query(Lead).filter(
                    Lead.tenant_id == rule.business_id,
                    Lead.status.in_([s.name for s in rule.statuses])
                ).all()
                
                if not leads:
                    logger.info(f"[RECURRING-MSG-JOB] Rule {rule.id} - no leads in target statuses")
                    continue
                
                logger.info(f"[RECURRING-MSG-JOB] Rule {rule.id} - found {len(leads)} lead(s) in target statuses")
                
                # Create messages for each lead
                for lead in leads:
                    try:
                        # Determine WhatsApp JID
                        remote_jid = lead.whatsapp_jid or lead.reply_jid
                        if not remote_jid:
                            # Try to construct JID from phone number
                            phone_to_use = lead.phone_e164 or lead.phone_raw
                            if phone_to_use:
                                phone_normalized = normalize_phone(phone_to_use)
                                if phone_normalized:
                                    phone_clean = ''.join(c for c in phone_normalized if c.isdigit())
                                    if phone_clean:
                                        remote_jid = f"{phone_clean}@s.whatsapp.net"
                                    else:
                                        logger.warning(f"[RECURRING-MSG-JOB] Lead {lead.id} phone normalized but contains no digits - skipping")
                                        continue
                                else:
                                    logger.warning(f"[RECURRING-MSG-JOB] Lead {lead.id} phone could not be normalized - skipping")
                                    continue
                            else:
                                logger.warning(f"[RECURRING-MSG-JOB] Lead {lead.id} has no WhatsApp JID or phone - skipping")
                                continue
                        
                        # Get status info
                        current_status = db.session.query(LeadStatus).filter_by(
                            business_id=rule.business_id,
                            name=lead.status
                        ).first()
                        status_name = current_status.name if current_status else lead.status
                        status_label = current_status.label if current_status else lead.status
                        
                        # Check if we already created a message for this lead+rule today
                        # (to avoid duplicates if job runs multiple times)
                        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                        existing_message = db.session.query(ScheduledMessagesQueue).filter(
                            ScheduledMessagesQueue.business_id == rule.business_id,
                            ScheduledMessagesQueue.rule_id == rule.id,
                            ScheduledMessagesQueue.lead_id == lead.id,
                            ScheduledMessagesQueue.created_at >= today_start
                        ).first()
                        
                        if existing_message:
                            logger.debug(f"[RECURRING-MSG-JOB] Message already created today for lead {lead.id}, rule {rule.id}")
                            continue
                        
                        # Render message template
                        business = db.session.query(Business).get(rule.business_id)
                        message_text = scheduled_messages_service.render_message_template(
                            template=rule.message_text,
                            lead=lead,
                            business=business,
                            status_name=status_name,
                            status_label=status_label
                        )
                        
                        # Create dedupe key
                        dedupe_key = f"{rule.business_id}:{lead.id}:{rule.id}:recurring:{now.strftime('%Y%m%d')}"
                        
                        # Create queue entry scheduled for now (send immediately)
                        queue_entry = ScheduledMessagesQueue(
                            business_id=rule.business_id,
                            rule_id=rule.id,
                            lead_id=lead.id,
                            channel='whatsapp',
                            provider=rule.provider or "baileys",
                            message_text=message_text,
                            remote_jid=remote_jid,
                            scheduled_for=now,  # Send immediately
                            status='pending',
                            dedupe_key=dedupe_key,
                            status_sequence_token=lead.status_sequence_token
                        )
                        
                        db.session.add(queue_entry)
                        messages_created += 1
                        
                        logger.info(f"[RECURRING-MSG-JOB] Created message for lead {lead.id} ({lead.name})")
                        
                    except Exception as e:
                        logger.error(f"[RECURRING-MSG-JOB] Error creating message for lead {lead.id}: {e}", exc_info=True)
                        db.session.rollback()
                        continue
                
                # Commit after processing each rule
                db.session.commit()
                logger.info(f"[RECURRING-MSG-JOB] Rule {rule.id} - created {messages_created} message(s)")
                
            except Exception as e:
                logger.error(f"[RECURRING-MSG-JOB] Error processing rule {rule.id}: {e}", exc_info=True)
                db.session.rollback()
                continue
        
        logger.info(f"[RECURRING-MSG-JOB] ✅ Job complete: {rules_matched} rule(s) matched, {messages_created} message(s) created")
        
        return {
            'status': 'success',
            'rules_checked': len(rules),
            'rules_matched': rules_matched,
            'messages_created': messages_created
        }
        
    except Exception as e:
        logger.error(f"[RECURRING-MSG-JOB] ❌ Critical error: {e}", exc_info=True)
        db.session.rollback()
        return {
            'status': 'error',
            'error': str(e)
        }
