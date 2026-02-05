#!/usr/bin/env python3
"""
Script to check appointment automation configuration and identify issues

This script will:
1. Check if automations exist and are enabled
2. Check if there are pending automation runs
3. Check if the scheduler is running
4. Check if there are any recent appointments without automation runs
"""
import sys
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from server.app_factory import create_app
from server.models_sql import (
    AppointmentAutomation,
    AppointmentAutomationRun,
    Appointment,
    Business,
    db
)
from datetime import datetime, timedelta
import pytz

def main():
    """Run automation checks"""
    app = create_app()
    
    with app.app_context():
        print("=" * 80)
        print("APPOINTMENT AUTOMATION DIAGNOSTICS")
        print("=" * 80)
        print()
        
        # 1. Check automations
        print("1. CHECKING AUTOMATIONS")
        print("-" * 80)
        automations = AppointmentAutomation.query.all()
        print(f"Total automations: {len(automations)}")
        
        if automations:
            for auto in automations:
                business = Business.query.get(auto.business_id)
                business_name = business.name if business else f"Unknown ({auto.business_id})"
                print(f"\n  ID: {auto.id}")
                print(f"  Business: {business_name}")
                print(f"  Name: {auto.name}")
                print(f"  Enabled: {'✅ YES' if auto.enabled else '❌ NO'}")
                print(f"  Trigger Statuses: {auto.trigger_status_ids}")
                print(f"  Schedule Offsets: {auto.schedule_offsets}")
                print(f"  Calendar IDs: {auto.calendar_ids or 'All'}")
                print(f"  Appointment Types: {auto.appointment_type_keys or 'All'}")
        else:
            print("  ⚠️  NO AUTOMATIONS FOUND!")
            print("  You need to create at least one automation for reminders to work.")
        
        print("\n" + "=" * 80)
        
        # 2. Check automation runs
        print("\n2. CHECKING AUTOMATION RUNS")
        print("-" * 80)
        
        # Pending runs
        pending_runs = AppointmentAutomationRun.query.filter_by(status='pending').all()
        print(f"Pending runs: {len(pending_runs)}")
        
        if pending_runs:
            now = datetime.utcnow()
            israel_tz = pytz.timezone('Asia/Jerusalem')
            
            print("\nPending runs details:")
            for run in pending_runs[:10]:  # Show first 10
                appointment = Appointment.query.get(run.appointment_id)
                scheduled_local = run.scheduled_for.replace(tzinfo=pytz.utc).astimezone(israel_tz)
                is_overdue = run.scheduled_for <= now
                
                print(f"\n  Run ID: {run.id}")
                print(f"  Appointment ID: {run.appointment_id}")
                if appointment:
                    appt_time_local = israel_tz.localize(appointment.start_time) if appointment.start_time.tzinfo is None else appointment.start_time.astimezone(israel_tz)
                    print(f"  Appointment Time: {appt_time_local.strftime('%Y-%m-%d %H:%M')} (Israel)")
                    print(f"  Appointment Status: {appointment.status}")
                print(f"  Scheduled For: {scheduled_local.strftime('%Y-%m-%d %H:%M')} (Israel)")
                print(f"  Status: {'🚨 OVERDUE' if is_overdue else '⏰ SCHEDULED'}")
                print(f"  Offset: {run.offset_signature}")
        
        # Recent sent runs
        sent_runs = AppointmentAutomationRun.query.filter_by(status='sent').order_by(
            AppointmentAutomationRun.sent_at.desc()
        ).limit(5).all()
        print(f"\n\nRecent sent runs: {len(sent_runs)}")
        if sent_runs:
            for run in sent_runs:
                print(f"  Run {run.id}: Sent at {run.sent_at}")
        
        # Failed runs
        failed_runs = AppointmentAutomationRun.query.filter_by(status='failed').order_by(
            AppointmentAutomationRun.created_at.desc()
        ).limit(5).all()
        print(f"\nRecent failed runs: {len(failed_runs)}")
        if failed_runs:
            for run in failed_runs:
                print(f"  Run {run.id}: {run.last_error}")
        
        print("\n" + "=" * 80)
        
        # 3. Check recent appointments without runs
        print("\n3. CHECKING RECENT APPOINTMENTS")
        print("-" * 80)
        
        # Get appointments from last 7 days
        since = datetime.utcnow() - timedelta(days=7)
        recent_appts = Appointment.query.filter(
            Appointment.created_at >= since
        ).order_by(Appointment.created_at.desc()).limit(20).all()
        
        print(f"Recent appointments (last 7 days): {len(recent_appts)}")
        
        israel_tz = pytz.timezone('Asia/Jerusalem')
        for appt in recent_appts[:5]:  # Show first 5
            runs = AppointmentAutomationRun.query.filter_by(appointment_id=appt.id).all()
            appt_time_local = israel_tz.localize(appt.start_time) if appt.start_time.tzinfo is None else appt.start_time.astimezone(israel_tz)
            
            print(f"\n  Appointment ID: {appt.id}")
            print(f"  Business ID: {appt.business_id}")
            print(f"  Title: {appt.title}")
            print(f"  Status: {appt.status}")
            print(f"  Time: {appt_time_local.strftime('%Y-%m-%d %H:%M')} (Israel)")
            print(f"  Created: {appt.created_at}")
            print(f"  Automation Runs: {len(runs)} ({'✅' if runs else '⚠️  NONE'})")
            if runs:
                for run in runs:
                    print(f"    - Run {run.id}: {run.status} ({run.offset_signature})")
        
        print("\n" + "=" * 80)
        
        # 4. Check scheduler
        print("\n4. CHECKING SCHEDULER")
        print("-" * 80)
        
        try:
            from redis import Redis
            from server.services.jobs import get_redis_connection
            
            redis_client = get_redis_connection()
            
            # Check scheduler lock
            lock_key = 'scheduler:global_lock'
            lock_value = redis_client.get(lock_key)
            
            if lock_value:
                print("✅ Scheduler lock exists")
                print(f"  Lock value: {lock_value.decode() if isinstance(lock_value, bytes) else lock_value}")
                ttl = redis_client.ttl(lock_key)
                print(f"  TTL: {ttl} seconds")
            else:
                print("⚠️  Scheduler lock NOT found - scheduler might not be running!")
            
            # Check recent scheduler activity
            last_tick_key = 'scheduler:last_tick'
            last_tick = redis_client.get(last_tick_key)
            if last_tick:
                print(f"\n✅ Last scheduler tick: {last_tick.decode() if isinstance(last_tick, bytes) else last_tick}")
            else:
                print("\n⚠️  No last tick record found")
            
        except Exception as e:
            print(f"❌ Failed to check scheduler: {e}")
        
        print("\n" + "=" * 80)
        
        # 5. Summary and recommendations
        print("\n5. SUMMARY & RECOMMENDATIONS")
        print("-" * 80)
        
        if not automations:
            print("\n❌ CRITICAL: No automations configured!")
            print("   → Create an automation in the Calendar UI:")
            print("      1. Go to Calendar page")
            print("      2. Click 'אוטומציות פגישות' button")
            print("      3. Create an automation with 'before' offset (e.g., 60 minutes)")
        elif not any(a.enabled for a in automations):
            print("\n❌ CRITICAL: All automations are disabled!")
            print("   → Enable at least one automation in the Calendar UI")
        else:
            enabled_count = sum(1 for a in automations if a.enabled)
            print(f"\n✅ {enabled_count} automation(s) are enabled")
        
        if pending_runs:
            overdue_count = sum(1 for r in pending_runs if r.scheduled_for <= datetime.utcnow())
            if overdue_count > 0:
                print(f"\n⚠️  {overdue_count} overdue automation runs!")
                print("   → This means the scheduler is not processing them")
                print("   → Check if the scheduler process is running:")
                print("      python -m server.scheduler.run_scheduler")
        
        if not lock_value:
            print("\n❌ CRITICAL: Scheduler not running!")
            print("   → Start the scheduler:")
            print("      python -m server.scheduler.run_scheduler")
        
        print("\n" + "=" * 80)

if __name__ == '__main__':
    main()
