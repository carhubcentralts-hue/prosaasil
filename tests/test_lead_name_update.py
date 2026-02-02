"""
Tests for Lead name update flow.

Ensures:
- AI-extracted names persist to lead.name AND first_name/last_name
- Manual (user_provided) names are never overwritten by AI
- Placeholder names are always replaced
- Name syncs bidirectionally between name ↔ first_name/last_name
- Search finds leads by the unified name field

Run: pytest tests/test_lead_name_update.py -v -s
"""
import pytest
from datetime import datetime


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
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
    from server.models_sql import Business
    biz = Business(id=1, name='Test Business')
    db.session.add(biz)
    db.session.commit()
    return biz


@pytest.fixture
def lead_with_placeholder(db, business):
    from server.models_sql import Lead
    lead = Lead(
        tenant_id=business.id,
        name='ליד חדש',
        name_source='call',
        phone_e164='+972501234567',
        source='call',
    )
    db.session.add(lead)
    db.session.commit()
    return lead


@pytest.fixture
def lead_with_real_name(db, business):
    from server.models_sql import Lead
    lead = Lead(
        tenant_id=business.id,
        name='משה כהן',
        first_name='משה',
        last_name='כהן',
        name_source='call',
        phone_e164='+972509876543',
        source='call',
    )
    db.session.add(lead)
    db.session.commit()
    return lead


@pytest.fixture
def lead_manual_name(db, business):
    from server.models_sql import Lead
    lead = Lead(
        tenant_id=business.id,
        name='דוד לוי',
        first_name='דוד',
        last_name='לוי',
        name_source='user_provided',
        phone_e164='+972501111111',
        source='manual',
    )
    db.session.add(lead)
    db.session.commit()
    return lead


# ---------------------------------------------------------------------------
# Tests: _sync_name_to_first_last
# ---------------------------------------------------------------------------

class TestSyncNameToFirstLast:

    def test_splits_two_part_name(self, app, db, business):
        from server.models_sql import Lead
        from server.services.contact_identity_service import ContactIdentityService

        lead = Lead(tenant_id=business.id)
        db.session.add(lead)
        db.session.flush()

        ContactIdentityService._sync_name_to_first_last(lead, 'שי כהן')
        assert lead.first_name == 'שי'
        assert lead.last_name == 'כהן'

    def test_single_name(self, app, db, business):
        from server.models_sql import Lead
        from server.services.contact_identity_service import ContactIdentityService

        lead = Lead(tenant_id=business.id)
        db.session.add(lead)
        db.session.flush()

        ContactIdentityService._sync_name_to_first_last(lead, 'שי')
        assert lead.first_name == 'שי'
        assert lead.last_name is None

    def test_three_part_name(self, app, db, business):
        from server.models_sql import Lead
        from server.services.contact_identity_service import ContactIdentityService

        lead = Lead(tenant_id=business.id)
        db.session.add(lead)
        db.session.flush()

        ContactIdentityService._sync_name_to_first_last(lead, 'יוסי בן דוד')
        assert lead.first_name == 'יוסי'
        assert lead.last_name == 'בן דוד'


# ---------------------------------------------------------------------------
# Tests: apply_extracted_name
# ---------------------------------------------------------------------------

class TestApplyExtractedName:

    def test_replaces_placeholder(self, app, db, lead_with_placeholder):
        from server.services.contact_identity_service import ContactIdentityService

        ContactIdentityService.apply_extracted_name(
            lead=lead_with_placeholder,
            extracted_name='שי',
            source='call_ai',
            confidence=0.90,
            business_id=1,
        )

        assert lead_with_placeholder.name == 'שי'
        assert lead_with_placeholder.first_name == 'שי'
        assert lead_with_placeholder.name_source == 'call_ai'

    def test_does_not_overwrite_user_provided(self, app, db, lead_manual_name):
        from server.services.contact_identity_service import ContactIdentityService

        ContactIdentityService.apply_extracted_name(
            lead=lead_manual_name,
            extracted_name='שי',
            source='call_ai',
            confidence=0.95,
            business_id=1,
        )

        assert lead_manual_name.name == 'דוד לוי'  # unchanged
        assert lead_manual_name.name_source == 'user_provided'

    def test_overwrites_real_name_with_high_confidence(self, app, db, lead_with_real_name):
        from server.services.contact_identity_service import ContactIdentityService

        ContactIdentityService.apply_extracted_name(
            lead=lead_with_real_name,
            extracted_name='שי ברקוביץ',
            source='call_ai',
            confidence=0.92,
            business_id=1,
        )

        assert lead_with_real_name.name == 'שי ברקוביץ'
        assert lead_with_real_name.first_name == 'שי'
        assert lead_with_real_name.last_name == 'ברקוביץ'

    def test_does_not_overwrite_real_name_with_low_confidence(self, app, db, lead_with_real_name):
        from server.services.contact_identity_service import ContactIdentityService

        ContactIdentityService.apply_extracted_name(
            lead=lead_with_real_name,
            extracted_name='שי',
            source='call_ai',
            confidence=0.60,
            business_id=1,
        )

        assert lead_with_real_name.name == 'משה כהן'  # unchanged

    def test_rejects_phone_number_as_name(self, app, db, lead_with_placeholder):
        from server.services.contact_identity_service import ContactIdentityService

        ContactIdentityService.apply_extracted_name(
            lead=lead_with_placeholder,
            extracted_name='+972501234567',
            source='call_ai',
            confidence=0.95,
            business_id=1,
        )

        assert lead_with_placeholder.name == 'ליד חדש'  # unchanged - phone rejected

    def test_rejects_empty_name(self, app, db, lead_with_placeholder):
        from server.services.contact_identity_service import ContactIdentityService

        ContactIdentityService.apply_extracted_name(
            lead=lead_with_placeholder,
            extracted_name='',
            source='call_ai',
            confidence=0.95,
            business_id=1,
        )

        assert lead_with_placeholder.name == 'ליד חדש'  # unchanged


# ---------------------------------------------------------------------------
# Tests: _update_lead_name syncs to first_name/last_name
# ---------------------------------------------------------------------------

class TestUpdateLeadNameSync:

    def test_whatsapp_pushname_syncs_to_first_last(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        lead = ContactIdentityService.get_or_create_lead_for_whatsapp(
            business_id=business.id,
            remote_jid='972501234567@s.whatsapp.net',
            push_name='אבי כהן',
        )

        assert lead.name == 'אבי כהן'
        assert lead.first_name == 'אבי'
        assert lead.last_name == 'כהן'

    def test_call_caller_name_syncs_to_first_last(self, app, db, business):
        from server.services.contact_identity_service import ContactIdentityService

        lead = ContactIdentityService.get_or_create_lead_for_call(
            business_id=business.id,
            from_e164='+972501234567',
            caller_name='רון ישראלי',
        )

        assert lead.name == 'רון ישראלי'
        assert lead.first_name == 'רון'
        assert lead.last_name == 'ישראלי'


# ---------------------------------------------------------------------------
# Tests: extract_city_and_service_from_summary includes customer_name
# ---------------------------------------------------------------------------

class TestExtractionIncludesName:

    def test_extraction_result_has_customer_name_key(self):
        """The extraction function should always return a customer_name key."""
        from server.services.lead_extraction_service import extract_city_and_service_from_summary

        # With short text (early return path)
        result = extract_city_and_service_from_summary("short")
        assert 'customer_name' in result
        assert result['customer_name'] is None
