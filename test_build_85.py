#!/usr/bin/env python3
"""
BUILD 85 Verification Script
בודק שכל התיקונים עובדים:
1. Google credentials קיימים
2. Functions חדשות זמינות  
3. Database schema תקין
"""

import os
import sys

def test_google_credentials():
    """בדיקה: Google credentials"""
    print("=" * 80)
    print("TEST 1: Google Credentials")
    print("=" * 80)
    
    from server.app_factory import create_app
    app = create_app()
    
    # בדוק שהקובץ נוצר
    creds_path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    print(f"✓ GOOGLE_APPLICATION_CREDENTIALS: {creds_path}")
    
    if creds_path and os.path.exists(creds_path):
        print(f"✅ Credentials file exists: {creds_path}")
        with open(creds_path) as f:
            import json
            creds = json.load(f)
            print(f"✅ Project: {creds.get('project_id')}")
            print(f"✅ Type: {creds.get('type')}")
        return True
    else:
        print(f"❌ Credentials file NOT found: {creds_path}")
        return False

def test_websocket_functions():
    """בדיקה: פונקציות WebSocket חדשות"""
    print("\n" + "=" * 80)
    print("TEST 2: WebSocket Functions")
    print("=" * 80)
    
    from server.media_ws_ai import MediaStreamHandler
    
    # בדוק שהפונקציות החדשות קיימות
    funcs = [
        '_create_call_log_on_start',
        '_save_conversation_turn', 
        '_process_customer_intelligence',
        '_finalize_call_on_stop'
    ]
    
    all_exist = True
    for func_name in funcs:
        if hasattr(MediaStreamHandler, func_name):
            print(f"✅ {func_name} exists")
        else:
            print(f"❌ {func_name} NOT FOUND")
            all_exist = False
    
    return all_exist

def test_database_schema():
    """בדיקה: Database schema"""
    print("\n" + "=" * 80)
    print("TEST 3: Database Schema")
    print("=" * 80)
    
    from server.app_factory import create_app
    from server.db import db
    
    app = create_app()
    with app.app_context():
        # בדוק טבלאות
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        required_tables = ['call_log', 'conversation_turn', 'leads', 'customer']
        
        all_exist = True
        for table in required_tables:
            if table in tables:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' NOT FOUND")
                all_exist = False
        
        # בדוק שדות ב-call_log
        result = db.session.execute(db.text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='call_log'"
        )).fetchall()
        columns = [row[0] for row in result]
        
        required_columns = ['transcript', 'ai_summary', 'summary']
        for col in required_columns:
            if col in columns:
                print(f"✅ Column 'call_log.{col}' exists")
            else:
                print(f"❌ Column 'call_log.{col}' NOT FOUND")
                all_exist = False
        
        return all_exist

def main():
    print("🚀 BUILD 85 VERIFICATION")
    print("=" * 80)
    
    results = []
    
    try:
        results.append(("Google Credentials", test_google_credentials()))
    except Exception as e:
        print(f"❌ Google Credentials test failed: {e}")
        results.append(("Google Credentials", False))
    
    try:
        results.append(("WebSocket Functions", test_websocket_functions()))
    except Exception as e:
        print(f"❌ WebSocket Functions test failed: {e}")
        results.append(("WebSocket Functions", False))
    
    try:
        results.append(("Database Schema", test_database_schema()))
    except Exception as e:
        print(f"❌ Database Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Database Schema", False))
    
    # סיכום
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {name}")
        if not passed:
            all_passed = False
    
    print("=" * 80)
    if all_passed:
        print("🎉 ALL TESTS PASSED - BUILD 85 READY!")
        sys.exit(0)
    else:
        print("⚠️ SOME TESTS FAILED - CHECK ERRORS ABOVE")
        sys.exit(1)

if __name__ == "__main__":
    main()
