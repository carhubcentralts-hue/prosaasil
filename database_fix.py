#!/usr/bin/env python3
"""
Direct Database Recording Fix
This will be imported and monkey-patch existing webhook to force DB recording
"""
import os
import datetime
import psycopg2
from functools import wraps

def force_database_recording(f):
    """Decorator to force database recording for any webhook"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        # Get Flask request from args or global context
        try:
            from flask import request
            call_sid = request.form.get('CallSid', f'patch_{int(datetime.datetime.now().timestamp())}')
            from_number = request.form.get('From', '')
            to_number = request.form.get('To', '')
            
            print(f"🎯 FORCING DATABASE RECORDING: {call_sid}")
            
            # Force record to database
            try:
                conn = psycopg2.connect(os.getenv('DATABASE_URL'))
                cur = conn.cursor()
                
                # Insert call record with PATCH identifier
                cur.execute("""
                    INSERT INTO call_log (call_sid, from_number, to_number, business_id, created_at, call_status, transcription)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (call_sid, from_number, to_number, 1, datetime.datetime.now(), 'incoming', 'PATCH FORCED RECORDING - Call received'))
                
                conn.commit()
                cur.close()
                conn.close()
                
                print(f"✅ PATCH FORCED DATABASE SUCCESS: {call_sid}")
                
                # Write success to file for verification
                with open('/tmp/patch_success.log', 'w') as f:
                    f.write(f"PATCH SUCCESS: {call_sid} at {datetime.datetime.now()}\n")
                
                return f(*args, **kwargs)
                
            except Exception as e:
                print(f"❌ PATCH DATABASE FAILED: {e}")
                
                # Write failure to file
                with open('/tmp/patch_fail.log', 'w') as f:
                    f.write(f"PATCH FAILED: {call_sid} - {e} at {datetime.datetime.now()}\n")
                
                return f(*args, **kwargs)
                
        except Exception as e:
            print(f"❌ PATCH WRAPPER FAILED: {e}")
            return f(*args, **kwargs)
            
    return wrapper

def apply_patch():
    """Apply database recording patch to existing server"""
    try:
        # Import server components and patch them
        from server.routes_twilio import twilio_bp
        
        # Find and patch the incoming_call route
        for rule in twilio_bp.url_map.iter_rules():
            if 'incoming_call' in rule.rule:
                endpoint_name = rule.endpoint
                view_func = twilio_bp.view_functions.get(endpoint_name)
                if view_func:
                    # Patch the view function
                    twilio_bp.view_functions[endpoint_name] = force_database_recording(view_func)
                    print(f"✅ PATCHED: {endpoint_name}")
                    
        print("✅ DATABASE RECORDING PATCH APPLIED")
        return True
        
    except Exception as e:
        print(f"❌ PATCH FAILED: {e}")
        return False

if __name__ == '__main__':
    apply_patch()