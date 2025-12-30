"""
Test call_limiter fix: OR logic for terminal statuses
This test verifies that calls are not counted as active if EITHER status field is terminal.
"""
import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from datetime import datetime, timedelta
from server.app_factory import create_app
from server.models_sql import db, CallLog
from server.services.call_limiter import count_active_calls, count_active_outbound_calls

def test_call_limiter_or_logic():
    """Test that OR logic correctly handles mixed status fields"""
    app = create_app()
    
    with app.app_context():
        # Clean up test data
        CallLog.query.filter(CallLog.call_sid.like('TEST_OR_%')).delete()
        db.session.commit()
        
        business_id = 1
        now = datetime.utcnow()
        
        # Scenario 1: status is terminal, call_status is not (should NOT count as active)
        call1 = CallLog(
            call_sid='TEST_OR_CALL1',
            business_id=business_id,
            status='completed',  # Terminal
            call_status='in-progress',  # Non-terminal (stale value)
            direction='outbound',
            created_at=now - timedelta(minutes=2)
        )
        
        # Scenario 2: call_status is terminal, status is not (should NOT count as active)
        call2 = CallLog(
            call_sid='TEST_OR_CALL2',
            business_id=business_id,
            status='in-progress',  # Non-terminal (stale value)
            call_status='completed',  # Terminal
            direction='outbound',
            created_at=now - timedelta(minutes=2)
        )
        
        # Scenario 3: Both are terminal (should NOT count as active)
        call3 = CallLog(
            call_sid='TEST_OR_CALL3',
            business_id=business_id,
            status='completed',  # Terminal
            call_status='completed',  # Terminal
            direction='outbound',
            created_at=now - timedelta(minutes=2)
        )
        
        # Scenario 4: Both are non-terminal (should count as active)
        call4 = CallLog(
            call_sid='TEST_OR_CALL4',
            business_id=business_id,
            status='in-progress',  # Non-terminal
            call_status='in-progress',  # Non-terminal
            direction='outbound',
            created_at=now - timedelta(minutes=2)
        )
        
        db.session.add_all([call1, call2, call3, call4])
        db.session.commit()
        
        # Test count_active_calls
        total_active = count_active_calls(business_id)
        print(f"✅ Total active calls: {total_active}")
        assert total_active == 1, f"Expected 1 active call, got {total_active}"
        
        # Test count_active_outbound_calls
        outbound_active = count_active_outbound_calls(business_id)
        print(f"✅ Active outbound calls: {outbound_active}")
        assert outbound_active == 1, f"Expected 1 active outbound call, got {outbound_active}"
        
        # Clean up
        CallLog.query.filter(CallLog.call_sid.like('TEST_OR_%')).delete()
        db.session.commit()
        
        print("\n✅ All tests passed!")
        print("🔥 FIX VERIFIED: OR logic correctly excludes calls with terminal status in either field")
        print("   - Calls with status='completed' and call_status='in-progress' are NOT counted")
        print("   - Calls with status='in-progress' and call_status='completed' are NOT counted")
        print("   - Only calls with BOTH fields non-terminal are counted as active")

if __name__ == '__main__':
    test_call_limiter_or_logic()
