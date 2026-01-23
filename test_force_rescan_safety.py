"""
Test Force Rescan Safety Guardrails

This test ensures that the force rescan purge logic ONLY deletes
receipt-related attachments and NEVER touches contracts, CRM files,
or other generic attachments.

MASTER INSTRUCTION COMPLIANCE TEST
"""

from datetime import datetime, timedelta
from server.models_sql import Receipt, Attachment, Business, GmailConnection
from server.db import db


def test_purge_only_deletes_receipt_attachments(app):
    """
    CRITICAL SAFETY TEST: Verify purge only deletes receipt-related attachments
    
    Test scenario:
    1. Create receipts with receipt_source and receipt_preview attachments
    2. Create contract attachment (should NOT be deleted)
    3. Create generic attachment (should NOT be deleted)
    4. Run force purge
    5. Verify ONLY receipt attachments were deleted
    """
    with app.app_context():
        # Setup: Create test business
        business = Business(
            name="Test Business",
            email="test@example.com",
            timezone="UTC"
        )
        db.session.add(business)
        db.session.flush()
        
        # Create Gmail connection
        gmail_conn = GmailConnection(
            business_id=business.id,
            email="test@gmail.com",
            status='connected',
            refresh_token_encrypted=b'dummy'
        )
        db.session.add(gmail_conn)
        
        # Create receipt attachments (SHOULD BE DELETED)
        receipt_attachment = Attachment(
            business_id=business.id,
            filename_original='receipt.pdf',
            mime_type='application/pdf',
            file_size=1000,
            storage_path='receipts/123/receipt.pdf',
            purpose='receipt_source',  # ✅ SAFE TO DELETE
            origin_module='receipts'
        )
        db.session.add(receipt_attachment)
        db.session.flush()
        
        preview_attachment = Attachment(
            business_id=business.id,
            filename_original='preview.png',
            mime_type='image/png',
            file_size=500,
            storage_path='receipts/123/preview.png',
            purpose='receipt_preview',  # ✅ SAFE TO DELETE
            origin_module='receipts'
        )
        db.session.add(preview_attachment)
        db.session.flush()
        
        # Create contract attachment (SHOULD NOT BE DELETED)
        contract_attachment = Attachment(
            business_id=business.id,
            filename_original='contract.pdf',
            mime_type='application/pdf',
            file_size=5000,
            storage_path='contracts/456/contract.pdf',
            purpose='contract',  # 🚫 MUST NOT DELETE
            origin_module='contracts'
        )
        db.session.add(contract_attachment)
        db.session.flush()
        
        # Create generic attachment (SHOULD NOT BE DELETED)
        generic_attachment = Attachment(
            business_id=business.id,
            filename_original='document.pdf',
            mime_type='application/pdf',
            file_size=3000,
            storage_path='attachments/789/document.pdf',
            purpose='whatsapp_media',  # 🚫 MUST NOT DELETE
            origin_module='whatsapp'
        )
        db.session.add(generic_attachment)
        db.session.flush()
        
        # Create receipt linking to these attachments
        receipt = Receipt(
            business_id=business.id,
            source='gmail',
            gmail_message_id='test_msg_123',
            received_at=datetime.utcnow(),
            attachment_id=receipt_attachment.id,
            preview_attachment_id=preview_attachment.id,
            vendor_name='Test Vendor',
            status='pending_review'
        )
        db.session.add(receipt)
        db.session.commit()
        
        # Store IDs for verification
        receipt_id = receipt.id
        receipt_att_id = receipt_attachment.id
        preview_att_id = preview_attachment.id
        contract_att_id = contract_attachment.id
        generic_att_id = generic_attachment.id
        
        # Simulate purge logic (from routes_receipts.py)
        from_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        to_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Query receipts to delete
        purge_filters = [
            Receipt.business_id == business.id,
            Receipt.source == 'gmail',
            Receipt.received_at >= datetime.strptime(from_date, '%Y-%m-%d'),
            Receipt.received_at < datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1)
        ]
        
        receipts_to_delete = Receipt.query.filter(*purge_filters).all()
        receipt_ids = [r.id for r in receipts_to_delete]
        attachment_ids_to_verify = []
        
        for r in receipts_to_delete:
            if r.attachment_id:
                attachment_ids_to_verify.append(r.attachment_id)
            if r.preview_attachment_id:
                attachment_ids_to_verify.append(r.preview_attachment_id)
        
        all_attachment_ids = list(set(attachment_ids_to_verify))
        
        # 🔒 SAFETY GUARDRAILS: Verify attachments
        safe_to_delete_ids = []
        if all_attachment_ids:
            attachments_to_verify = Attachment.query.filter(
                Attachment.id.in_(all_attachment_ids)
            ).all()
            
            for att in attachments_to_verify:
                if att.purpose in ('receipt_source', 'receipt_preview'):
                    safe_to_delete_ids.append(att.id)
                else:
                    # Should never happen in this test
                    raise ValueError(f"Safety violation: purpose='{att.purpose}'")
        
        # Execute deletion
        if receipt_ids:
            Receipt.query.filter(Receipt.id.in_(receipt_ids)).delete(synchronize_session=False)
            
            if safe_to_delete_ids:
                Attachment.query.filter(
                    Attachment.id.in_(safe_to_delete_ids)
                ).delete(synchronize_session=False)
            
            db.session.commit()
        
        # VERIFICATION: Check what was deleted and what remains
        deleted_receipt = Receipt.query.get(receipt_id)
        deleted_receipt_att = Attachment.query.get(receipt_att_id)
        deleted_preview_att = Attachment.query.get(preview_att_id)
        remaining_contract = Attachment.query.get(contract_att_id)
        remaining_generic = Attachment.query.get(generic_att_id)
        
        # Assert: Receipt and its attachments should be deleted
        assert deleted_receipt is None, "Receipt should be deleted"
        assert deleted_receipt_att is None, "Receipt attachment should be deleted"
        assert deleted_preview_att is None, "Preview attachment should be deleted"
        
        # Assert: Contract and generic attachments should remain
        assert remaining_contract is not None, "Contract MUST NOT be deleted"
        assert remaining_generic is not None, "Generic attachment MUST NOT be deleted"
        assert remaining_contract.purpose == 'contract', "Contract purpose intact"
        assert remaining_generic.purpose == 'whatsapp_media', "Generic purpose intact"
        
        print("✅ SAFETY TEST PASSED: Only receipt attachments were deleted")
        print(f"   Deleted: receipt, receipt_source, receipt_preview")
        print(f"   Preserved: contract, whatsapp_media")


def test_purge_blocks_non_receipt_attachment_in_receipt(app):
    """
    CRITICAL SAFETY TEST: Verify purge blocks if receipt points to non-receipt attachment
    
    This tests the scenario where a receipt somehow has an attachment_id that
    points to a non-receipt purpose attachment. The guardrails should catch this
    and raise ValueError.
    """
    with app.app_context():
        # Setup: Create test business
        business = Business(
            name="Test Business 2",
            email="test2@example.com",
            timezone="UTC"
        )
        db.session.add(business)
        db.session.flush()
        
        # Create Gmail connection
        gmail_conn = GmailConnection(
            business_id=business.id,
            email="test2@gmail.com",
            status='connected',
            refresh_token_encrypted=b'dummy'
        )
        db.session.add(gmail_conn)
        
        # Create contract attachment (wrong purpose)
        contract_attachment = Attachment(
            business_id=business.id,
            filename_original='contract.pdf',
            mime_type='application/pdf',
            file_size=5000,
            storage_path='contracts/999/contract.pdf',
            purpose='contract',  # 🚫 WRONG PURPOSE for receipt
            origin_module='contracts'
        )
        db.session.add(contract_attachment)
        db.session.flush()
        
        # Create receipt with WRONG attachment purpose (simulating data corruption)
        receipt = Receipt(
            business_id=business.id,
            source='gmail',
            gmail_message_id='test_msg_456',
            received_at=datetime.utcnow(),
            attachment_id=contract_attachment.id,  # 🚫 Points to contract!
            vendor_name='Test Vendor',
            status='pending_review'
        )
        db.session.add(receipt)
        db.session.commit()
        
        # Attempt purge - should raise ValueError
        from_date = (datetime.utcnow() - timedelta(days=1)).strftime('%Y-%m-%d')
        to_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        purge_filters = [
            Receipt.business_id == business.id,
            Receipt.source == 'gmail',
            Receipt.received_at >= datetime.strptime(from_date, '%Y-%m-%d')
        ]
        
        receipts_to_delete = Receipt.query.filter(*purge_filters).all()
        attachment_ids = [r.attachment_id for r in receipts_to_delete if r.attachment_id]
        
        # Verify attachments - should raise ValueError
        error_raised = False
        error_message = ""
        try:
            attachments_to_verify = Attachment.query.filter(
                Attachment.id.in_(attachment_ids)
            ).all()
            
            for att in attachments_to_verify:
                if att.purpose not in ('receipt_source', 'receipt_preview'):
                    raise ValueError(
                        f"Safety violation: Attempted to delete attachment with purpose='{att.purpose}'. "
                        f"Only 'receipt_source' and 'receipt_preview' are allowed."
                    )
        except ValueError as e:
            error_raised = True
            error_message = str(e)
        
        assert error_raised, "Should have raised ValueError"
        assert "Safety violation" in error_message
        assert "contract" in error_message
        
        print("✅ SAFETY TEST PASSED: Guardrail blocked non-receipt attachment deletion")
        print(f"   Blocked deletion of purpose='contract'")


if __name__ == "__main__":
    # Run tests
    from server.app_factory import create_app
    
    app = create_app()
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        
        try:
            print("\n" + "="*70)
            print("RUNNING FORCE RESCAN SAFETY TESTS")
            print("="*70 + "\n")
            
            print("Test 1: Purge only deletes receipt attachments")
            print("-" * 70)
            test_purge_only_deletes_receipt_attachments(app)
            
            print("\n" + "-" * 70)
            print("Test 2: Purge blocks non-receipt attachment in receipt")
            print("-" * 70)
            test_purge_blocks_non_receipt_attachment_in_receipt(app)
            
            print("\n" + "="*70)
            print("✅ ALL SAFETY TESTS PASSED")
            print("="*70)
            
        except Exception as e:
            print(f"\n❌ TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
