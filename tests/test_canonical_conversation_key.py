"""
Test canonical conversation key functionality

BUILD 138: Conversation Deduplication Tests
"""
import pytest
from server.utils.whatsapp_utils import get_canonical_conversation_key


def test_canonical_key_with_lead_id():
    """Test canonical key generation with lead_id"""
    key = get_canonical_conversation_key(
        business_id=1,
        lead_id=123,
        phone_e164="+972501234567"
    )
    assert key == "lead:1:123"
    # lead_id takes priority over phone


def test_canonical_key_with_phone_only():
    """Test canonical key generation with phone_e164 only"""
    key = get_canonical_conversation_key(
        business_id=1,
        phone_e164="+972501234567"
    )
    assert key == "phone:1:+972501234567"


def test_canonical_key_normalizes_phone():
    """Test that phone without + gets normalized"""
    key = get_canonical_conversation_key(
        business_id=1,
        phone_e164="972501234567"
    )
    assert key == "phone:1:+972501234567"
    # Should add + prefix


def test_canonical_key_same_for_same_lead():
    """Test that same lead always generates same key"""
    key1 = get_canonical_conversation_key(
        business_id=1,
        lead_id=123,
        phone_e164="+972501234567"
    )
    key2 = get_canonical_conversation_key(
        business_id=1,
        lead_id=123,
        phone_e164="+972509999999"  # Different phone
    )
    assert key1 == key2 == "lead:1:123"
    # Lead ID should be consistent regardless of phone changes


def test_canonical_key_different_for_different_business():
    """Test that same lead in different business gets different key"""
    key1 = get_canonical_conversation_key(business_id=1, lead_id=123)
    key2 = get_canonical_conversation_key(business_id=2, lead_id=123)
    assert key1 != key2
    assert key1 == "lead:1:123"
    assert key2 == "lead:2:123"


def test_canonical_key_requires_identifier():
    """Test that at least one identifier is required"""
    with pytest.raises(ValueError, match="Either lead_id or phone_e164 is required"):
        get_canonical_conversation_key(business_id=1)


def test_canonical_key_requires_business_id():
    """Test that business_id is required"""
    with pytest.raises(ValueError, match="business_id is required"):
        get_canonical_conversation_key(
            business_id=None,
            lead_id=123
        )
