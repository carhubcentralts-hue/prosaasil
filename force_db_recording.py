#!/usr/bin/env python3
"""
Force DB Recording Patch
This will be imported by main.py to force database recording
"""
import os
import datetime
import psycopg2
from flask import request

def force_record_call():
    """Force record any incoming call to database"""
    try:
        call_sid = request.form.get('CallSid', f'force_{int(datetime.datetime.now().timestamp())}')
        from_number = request.form.get('From', '')
        to_number = request.form.get('To', '')
        
        print(f"🎯 FORCE RECORDING: {call_sid}")
        
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # Insert call record
        cur.execute("""
            INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (call_sid, from_number, to_number, 1, datetime.datetime.now(), 'incoming', 'FORCED RECORDING - Call received'))
        
        conn.commit()
        cur.close()
        conn.close()
        
        print(f"✅ FORCED DB RECORD SUCCESS: {call_sid}")
        
        # Write to verification file
        with open('/tmp/db_force.log', 'w') as f:
            f.write(f"FORCED: {call_sid} at {datetime.datetime.now()}\n")
        
        return True
        
    except Exception as e:
        print(f"❌ FORCE RECORDING FAILED: {e}")
        return False

# Auto-apply when imported
print("🎯 FORCE DB RECORDING MODULE LOADED")