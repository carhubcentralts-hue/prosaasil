"""
Tests for WhatsApp @lid identity resolution.

Ensures:
- No fake phone numbers are ever created from LID digits.
- If Baileys provides participant/resolved JID, lead stores real E164.
- If not provided, system uses stored DB mapping if exists; otherwise leaves
  phone null but still tracks conversation by JID.
- Multi-tenant safety: all DB queries scoped by business_id.

Run: pytest tests/test_lid_identity_resolution.py -v -s
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a minimal Flask app with in-memory SQLite for testing."""
    from flask import Flask
    from server.db import db as _db

    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['TESTING'] = True

    _db.init_app(app)

    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def db(app):
    from server.db import db as _db
    with app.app_context():
        yield _db


@pytest.fixture
def business(db):
    """Create a test business."""
    from server.models_sql import Business
    biz = Business(id=1, name='Test Business')
    db.session.add(biz)
    db.session.commit()
    return biz


# ---------------------------------------------------------------------------
# Unit tests: extract_phone_from_jid
# ---------------------------------------------------------------------------

class TestExtractPhoneFromJid:
    """extract_phone_from_jid must NEVER return a phone from @lid JIDs."""

    def test_standard_jid_returns_phone(self):
        from server.services.contact_identity_service import ContactIdentityService
        result = ContactIdentityService.extract_phone_from_jid('972525951893@s.whatsapp.net')
        assert result == '+972525951893'

    def test_lid_jid_returns_none(self):
        from server.services.contact_identity_service import ContactIdentityService
        result = ContactIdentityService.extract_phone_from_jid('82399031480511@lid')
        assert result is None, f"Expected None for @lid JID, got {result}"

    def test_lid_jid_with_device_suffix_returns_none(self):
        from server.services.contact_identity_service import ContactIdentityService
        result = ContactIdentityService.extract_phone_from_jid('82399031480511:55@lid')
        assert result is None

    def test_broadcast_returns_none(self):
        from server.services.contact_identity_service import ContactIdentityService
        assert ContactIdentityService.extract_phone_from_jid('status@broadcast') is None

    def test_group_returns_none(self):
        from server.services.contact_identity_service import ContactIdentityService
        assert ContactIdentityService.extract_phone_from_jid('120363123456@g.us') is None

    def test_empty_returns_none(self):
        from server.services.contact_identity_service import ContactIdentityService
        assert ContactIdentityService.extract_phone_from_jid('') is None
        assert ContactIdentityService.extract_phone_from_jid(None) is None


# ---------------------------------------------------------------------------
# Integration tests: get_or_create_lead_for_whatsapp
# ---------------------------------------------------------------------------

class TestLidLeadResolution:
    """Lead resolution for @lid messages."""

    def test_lid_with_participant_sets_phone(self, app, db, business):
        """
        When remote_jid="@lid" + participant_jid="@s.whatsapp.net",
        the lead must have the real phone_e164 set.
        """
        from server.services.contact_identity_service import ContactIdentityService

        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            push_name='Test User',
            phone_e164_override='+972525951893',  # extracted from participant by Flask
        )

        assert lead is not None
        assert lead.phone_e164 == '+972525951893', \
            f"Expected +972525951893, got {lead.phone_e164}"
        assert lead.tenant_id == business.id

    def test_lid_without_participant_phone_is_null(self, app, db, business):
        """
        When remote_jid="@lid" with NO participant/resolved_jid,
        the lead must NOT have a fake phone. phone_e164 stays None.
        """
        from server.services.contact_identity_service import ContactIdentityService

        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            push_name='LID User',
            phone_e164_override=None,  # no participant available
        )

        assert lead is not None
        assert lead.phone_e164 is None, \
            f"Expected phone_e164=None for lid-only, got {lead.phone_e164}"
        assert lead.whatsapp_jid is not None  # still tracked by JID

    def test_lid_late_phone_discovery_updates_lead(self, app, db, business):
        """
        First message comes with @lid only (no phone). Second message
        comes with @lid + participant providing real phone. The lead
        should be updated with the real phone.
        """
        from server.services.contact_identity_service import ContactIdentityService

        # First message: lid only, no phone
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            push_name='User A',
            phone_e164_override=None,
        )
        assert lead.phone_e164 is None
        lead_id = lead.id

        # Second message: same lid, now with participant phone
        lead2 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            push_name='User A',
            phone_e164_override='+972525951893',
        )

        assert lead2.id == lead_id, "Should be the same lead"
        assert lead2.phone_e164 == '+972525951893', \
            f"Expected phone to be updated, got {lead2.phone_e164}"

    def test_lid_no_cross_tenant_leak(self, app, db, business):
        """
        A lead created for business_id=1 with @lid must not be returned
        when querying for business_id=2.
        """
        from server.models_sql import Business
        from server.services.contact_identity_service import ContactIdentityService

        # Create second business
        biz2 = Business(id=2, name='Other Business')
        db.session.add(biz2)
        db.session.commit()

        # Create lead for business 1
        lead1 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=1,
            remote_jid='82399031480511@lid',
            push_name='User',
            phone_e164_override='+972525951893',
        )

        # Query for business 2 with same lid
        lead2 = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=2,
            remote_jid='82399031480511@lid',
            push_name='User',
            phone_e164_override=None,
        )

        assert lead1.id != lead2.id, "Different businesses must not share leads"
        assert lead2.phone_e164 is None, "Business 2 has no phone for this lid"


# ---------------------------------------------------------------------------
# Integration tests: lookup_phone_by_lid
# ---------------------------------------------------------------------------

class TestLookupPhoneByLid:
    """DB mapping lookup for @lid JIDs."""

    def test_returns_phone_for_known_lid(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        # Create a lead with phone via participant
        ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            push_name='Known User',
            phone_e164_override='+972525951893',
        )

        # Now lookup should find it
        phone = ContactIdentityService.lookup_phone_by_lid(
            business_id=business.id,
            lid_jid='82399031480511@lid'
        )
        assert phone == '+972525951893'

    def test_returns_none_for_unknown_lid(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        phone = ContactIdentityService.lookup_phone_by_lid(
            business_id=business.id,
            lid_jid='999999999@lid'
        )
        assert phone is None

    def test_returns_none_for_lid_without_phone(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        # Create a lead with lid but no phone
        ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            push_name='No Phone User',
            phone_e164_override=None,
        )

        phone = ContactIdentityService.lookup_phone_by_lid(
            business_id=business.id,
            lid_jid='82399031480511@lid'
        )
        assert phone is None

    def test_scoped_by_business_id(self, app, db, business):
        from server.models_sql import Business
        from server.services.contact_identity_service import ContactIdentityService

        biz2 = Business(id=2, name='Biz2')
        db.session.add(biz2)
        db.session.commit()

        # Create mapping for business 1
        ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=1,
            remote_jid='82399031480511@lid',
            phone_e164_override='+972525951893',
        )

        # Business 2 should NOT see it
        phone = ContactIdentityService.lookup_phone_by_lid(
            business_id=2,
            lid_jid='82399031480511@lid'
        )
        assert phone is None


# ---------------------------------------------------------------------------
# Integration tests: update_lead_phone_for_lid
# ---------------------------------------------------------------------------

class TestUpdateLeadPhoneForLid:

    def test_updates_phone_for_phoneless_lead(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        # Create lead without phone
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            phone_e164_override=None,
        )
        assert lead.phone_e164 is None

        # Update phone
        result = ContactIdentityService.update_lead_phone_for_lid(
            business_id=business.id,
            lid_jid='82399031480511@lid',
            phone_e164='+972525951893',
        )
        assert result is True

        db.session.refresh(lead)
        assert lead.phone_e164 == '+972525951893'

    def test_does_not_overwrite_existing_phone(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        # Create lead with phone
        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='82399031480511@lid',
            phone_e164_override='+972525951893',
        )

        # Try to update with different phone - should not overwrite
        result = ContactIdentityService.update_lead_phone_for_lid(
            business_id=business.id,
            lid_jid='82399031480511@lid',
            phone_e164='+972501234567',
        )
        assert result is False

        db.session.refresh(lead)
        assert lead.phone_e164 == '+972525951893'  # unchanged
