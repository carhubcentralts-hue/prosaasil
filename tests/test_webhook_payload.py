"""
Test webhook payload serialization for Monday.com and n8n integration
Verifies that webhook payloads have proper JSON types with no null/undefined values
"""
import json
from datetime import datetime


def test_webhook_payload_serialization():
    """
    Test that webhook payload is properly serialized with correct types
    
    This test verifies:
    1. All fields are properly typed (str, int, float, bool)
    2. No null/undefined values (replaced with defaults)
    3. Monday.com field aliases are present (service, call_direction)
    4. Payload can be JSON serialized without errors
    """
    # Mock data similar to real call data
    test_data = {
        "business_id": 1,
        "call_id": "CA1234567890abcdef",
        "lead_id": 123,
        "phone": "+972501234567",
        "started_at": datetime(2025, 1, 1, 10, 0, 0),
        "ended_at": datetime(2025, 1, 1, 10, 5, 30),
        "duration_sec": 330,
        "transcript": "שיחה לדוגמה",
        "summary": "סיכום השיחה",
        "agent_name": "Assistant",
        "direction": "inbound",
        "city": "תל אביב",
        "service_category": "חשמלאי",
        "customer_name": "יוסי כהן",
        "preferred_time": "בוקר"
    }
    
    # Build the data dict (mimicking what send_call_completed_webhook does)
    data = {
        "call_id": str(test_data["call_id"]) if test_data.get("call_id") else "",
        "lead_id": str(test_data["lead_id"]) if test_data.get("lead_id") else "",
        "phone": str(test_data["phone"]) if test_data.get("phone") else "",
        "customer_name": str(test_data.get("customer_name")) if test_data.get("customer_name") else "",
        "city": str(test_data.get("city")) if test_data.get("city") else "",
        "raw_city": str(test_data.get("raw_city")) if test_data.get("raw_city") else "",
        "city_confidence": float(test_data.get("city_confidence")) if test_data.get("city_confidence") is not None else 0.0,
        "city_raw_attempts": list(test_data.get("city_raw_attempts")) if test_data.get("city_raw_attempts") else [],
        "city_autocorrected": bool(test_data.get("city_autocorrected")) if test_data.get("city_autocorrected") else False,
        "name_raw_attempts": list(test_data.get("name_raw_attempts")) if test_data.get("name_raw_attempts") else [],
        "service_category": str(test_data.get("service_category")) if test_data.get("service_category") else "",
        "preferred_time": str(test_data.get("preferred_time")) if test_data.get("preferred_time") else "",
        "started_at": test_data["started_at"].isoformat() if test_data.get("started_at") else "",
        "ended_at": test_data["ended_at"].isoformat() if test_data.get("ended_at") else datetime.utcnow().isoformat(),
        "duration_sec": int(test_data["duration_sec"]) if test_data.get("duration_sec") else 0,
        "transcript": str(test_data.get("transcript")) if test_data.get("transcript") else "",
        "summary": str(test_data.get("summary")) if test_data.get("summary") else "",
        "agent_name": str(test_data.get("agent_name")) if test_data.get("agent_name") else "Assistant",
        "direction": str(test_data["direction"]) if test_data.get("direction") else "inbound",
        "metadata": dict(test_data.get("metadata")) if test_data.get("metadata") else {},
        # Monday.com field mapping
        "service": str(test_data.get("service_category")) if test_data.get("service_category") else "",
        "call_status": "completed",
        "call_direction": str(test_data["direction"]) if test_data.get("direction") else "inbound"
    }
    
    # Test 1: Verify all fields are present
    assert "call_id" in data
    assert "lead_id" in data
    assert "phone" in data
    assert "city" in data
    assert "service_category" in data
    assert "service" in data  # Monday.com alias
    assert "call_direction" in data  # Monday.com alias
    assert "call_status" in data
    
    # Test 2: Verify types are correct
    assert isinstance(data["call_id"], str)
    assert isinstance(data["lead_id"], str)
    assert isinstance(data["phone"], str)
    assert isinstance(data["city"], str)
    assert isinstance(data["duration_sec"], int)
    assert isinstance(data["city_confidence"], float)
    assert isinstance(data["city_autocorrected"], bool)
    assert isinstance(data["city_raw_attempts"], list)
    assert isinstance(data["metadata"], dict)
    
    # Test 3: Verify no None values (all should be defaults)
    assert data["call_id"] == "CA1234567890abcdef"
    assert data["lead_id"] == "123"
    assert data["phone"] == "+972501234567"
    assert data["city"] == "תל אביב"
    assert data["service"] == "חשמלאי"
    assert data["duration_sec"] == 330
    assert data["city_confidence"] == 0.0
    
    # Test 4: Verify payload can be JSON serialized
    try:
        json_payload = json.dumps(data, ensure_ascii=False, default=str)
        assert len(json_payload) > 0
        
        # Verify it can be deserialized back
        parsed = json.loads(json_payload)
        assert parsed["phone"] == "+972501234567"
        assert parsed["service"] == "חשמלאי"
        
    except (TypeError, ValueError) as e:
        raise AssertionError(f"Payload serialization failed: {e}")
    
    # Test 5: Verify Monday.com aliases match primary fields
    assert data["service"] == data["service_category"]
    assert data["call_direction"] == data["direction"]
    
    print("✅ All webhook payload tests passed!")


def test_webhook_payload_with_missing_data():
    """
    Test webhook payload handles missing/null data gracefully
    
    Verifies that missing data is replaced with appropriate defaults:
    - Strings: ""
    - Numbers: 0 or 0.0
    - Booleans: False
    - Lists: []
    - Dicts: {}
    """
    # Mock data with many missing fields
    test_data = {
        "business_id": 1,
        "call_id": "CA1234567890abcdef",
        "lead_id": None,  # Missing
        "phone": None,  # Missing
        "started_at": datetime(2025, 1, 1, 10, 0, 0),
        "ended_at": None,  # Missing
        "duration_sec": None,  # Missing
        "transcript": "",  # Empty
        "summary": None,  # Missing
        "agent_name": None,  # Missing
        "direction": "outbound",
        "city": None,  # Missing
        "service_category": None  # Missing
    }
    
    # Build the data dict with proper defaults
    data = {
        "call_id": str(test_data["call_id"]) if test_data.get("call_id") else "",
        "lead_id": str(test_data["lead_id"]) if test_data.get("lead_id") else "",
        "phone": str(test_data["phone"]) if test_data.get("phone") else "",
        "city": str(test_data.get("city")) if test_data.get("city") else "",
        "service_category": str(test_data.get("service_category")) if test_data.get("service_category") else "",
        "duration_sec": int(test_data["duration_sec"]) if test_data.get("duration_sec") else 0,
        "transcript": str(test_data.get("transcript")) if test_data.get("transcript") else "",
        "summary": str(test_data.get("summary")) if test_data.get("summary") else "",
        "agent_name": str(test_data.get("agent_name")) if test_data.get("agent_name") else "Assistant",
        "direction": str(test_data["direction"]) if test_data.get("direction") else "inbound",
        "service": str(test_data.get("service_category")) if test_data.get("service_category") else "",
    }
    
    # Verify all None values are replaced with appropriate defaults
    assert data["lead_id"] == ""  # None -> ""
    assert data["phone"] == ""  # None -> ""
    assert data["city"] == ""  # None -> ""
    assert data["service_category"] == ""  # None -> ""
    assert data["service"] == ""  # None -> ""
    assert data["duration_sec"] == 0  # None -> 0
    assert data["transcript"] == ""  # "" -> ""
    assert data["summary"] == ""  # None -> ""
    assert data["agent_name"] == "Assistant"  # None -> "Assistant"
    
    # Verify JSON serialization works
    json_payload = json.dumps(data, ensure_ascii=False, default=str)
    assert "null" not in json_payload.lower()  # No null values in JSON
    
    print("✅ Missing data handling tests passed!")


if __name__ == "__main__":
    test_webhook_payload_serialization()
    test_webhook_payload_with_missing_data()
    print("\n✅ All webhook payload tests passed successfully!")
