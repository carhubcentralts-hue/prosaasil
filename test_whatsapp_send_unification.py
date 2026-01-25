"""
Test WhatsApp send unification - verify normalization works correctly
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from server.utils.whatsapp_utils import normalize_whatsapp_to


def test_normalize_with_reply_jid():
    """Test that reply_jid takes priority"""
    jid, source = normalize_whatsapp_to(
        to="+972509237456",
        lead_phone="972504294724",
        lead_reply_jid="972509237456@s.whatsapp.net",
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "reply_jid"
    print("✅ Test 1 passed: reply_jid takes priority")


def test_normalize_with_plus():
    """Test normalization removes + and adds @s.whatsapp.net"""
    jid, source = normalize_whatsapp_to(
        to="+972509237456",
        lead_phone=None,
        lead_reply_jid=None,
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "to"
    print("✅ Test 2 passed: + removed, @s.whatsapp.net added")


def test_normalize_without_plus():
    """Test normalization works without +"""
    jid, source = normalize_whatsapp_to(
        to="972509237456",
        lead_phone=None,
        lead_reply_jid=None,
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "to"
    print("✅ Test 3 passed: works without +")


def test_normalize_already_formatted():
    """Test normalization handles already formatted JID"""
    jid, source = normalize_whatsapp_to(
        to="972509237456@s.whatsapp.net",
        lead_phone=None,
        lead_reply_jid=None,
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "to"
    print("✅ Test 4 passed: already formatted JID preserved")


def test_normalize_with_spaces_dashes():
    """Test normalization removes spaces and dashes"""
    jid, source = normalize_whatsapp_to(
        to="+972-50-923-7456",
        lead_phone=None,
        lead_reply_jid=None,
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "to"
    print("✅ Test 5 passed: spaces and dashes removed")


def test_normalize_blocks_groups():
    """Test normalization blocks group JIDs"""
    try:
        jid, source = normalize_whatsapp_to(
            to="972509237456@g.us",
            lead_phone=None,
            lead_reply_jid=None,
            lead_id=123,
            business_id=4
        )
        print("❌ Test 6 failed: should have raised ValueError for group")
        assert False
    except ValueError as e:
        assert "Cannot send to groups" in str(e)
        print("✅ Test 6 passed: group JID blocked")


def test_normalize_fallback_to_phone():
    """Test fallback to lead_phone when to is empty"""
    jid, source = normalize_whatsapp_to(
        to="",
        lead_phone="+972509237456",
        lead_reply_jid=None,
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "phone"
    print("✅ Test 7 passed: fallback to lead_phone works")


def test_normalize_reply_jid_preferred_over_to():
    """Test that reply_jid is preferred even when 'to' is different"""
    jid, source = normalize_whatsapp_to(
        to="972504294724",  # Different number
        lead_phone=None,
        lead_reply_jid="972509237456@s.whatsapp.net",  # Correct JID
        lead_id=123,
        business_id=4
    )
    assert jid == "972509237456@s.whatsapp.net"
    assert source == "reply_jid"
    print("✅ Test 8 passed: reply_jid preferred over different 'to' number")


if __name__ == "__main__":
    print("\n🧪 Testing WhatsApp Send Unification\n")
    print("=" * 60)
    
    test_normalize_with_reply_jid()
    test_normalize_with_plus()
    test_normalize_without_plus()
    test_normalize_already_formatted()
    test_normalize_with_spaces_dashes()
    test_normalize_blocks_groups()
    test_normalize_fallback_to_phone()
    test_normalize_reply_jid_preferred_over_to()
    
    print("=" * 60)
    print("\n✅ All tests passed!\n")
    print("📝 Summary:")
    print("  - normalize_whatsapp_to() correctly prioritizes reply_jid")
    print("  - Phone formatting (+ removal, @s.whatsapp.net addition) works")
    print("  - Group JIDs are properly blocked")
    print("  - Fallback to lead_phone works when 'to' is empty")
    print("\n🎯 Ready for production testing")
