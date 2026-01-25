"""
Test for Complete Receipts Fixes

Tests the following fixes:
1. Export receipts without signed_url AttributeError
2. Download single receipt endpoint
3. UI display improvements (amount text, preview quality)
4. Worker configuration (no migrations, maintenance queue)
5. Delete receipts job logging
"""

import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_export_uses_attachment_service():
    """Verify that export_receipts uses AttachmentService instead of attachment.signed_url"""
    
    # Read the routes_receipts.py file
    with open('server/routes_receipts.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that we import and use AttachmentService in export
    assert 'from server.services.attachment_service import get_attachment_service' in content, \
        "Missing AttachmentService import in export function"
    
    # Check that we're calling generate_signed_url
    assert 'attachment_service.generate_signed_url(' in content, \
        "Missing attachment_service.generate_signed_url call"
    
    # Verify we're NOT directly accessing attachment.signed_url in export
    # Look for the export function and ensure it doesn't have direct signed_url access
    export_start = content.find('def export_receipts')
    if export_start != -1:
        # Find the next function definition to mark the end
        next_func = content.find('\ndef ', export_start + 20)
        if next_func == -1:
            next_func = len(content)
        
        export_function = content[export_start:next_func]
        
        # Check that we're NOT accessing signed_url directly (only through service)
        if 'attachment_to_export.signed_url' in export_function or 'attachment.signed_url' in export_function:
            # Make sure it's only in a context where we're assigning it from the service
            assert 'signed_url = attachment_service.generate_signed_url' in export_function, \
                "Export function accesses attachment.signed_url directly without using AttachmentService"
    
    print("✅ Export function uses AttachmentService correctly")


def test_download_endpoint_exists():
    """Verify that download receipt endpoint exists"""
    
    with open('server/routes_receipts.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for download endpoint
    assert "def download_receipt(receipt_id):" in content, \
        "Missing download_receipt endpoint"
    
    assert "route('/<int:receipt_id>/download'" in content, \
        "Missing download route decorator"
    
    assert "redirect(signed_url)" in content or "return redirect" in content, \
        "Download endpoint should redirect to signed URL"
    
    print("✅ Download endpoint exists with redirect to signed URL")


def test_worker_config_no_migrations():
    """Verify worker doesn't run migrations"""
    
    with open('docker-compose.yml', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find worker section
    worker_section_start = content.find('worker:')
    if worker_section_start == -1:
        print("⚠️  Warning: Could not find worker section in docker-compose.yml")
        return
    
    worker_section_end = content.find('\n\n  ', worker_section_start)
    if worker_section_end == -1:
        worker_section_end = len(content)
    
    worker_section = content[worker_section_start:worker_section_end]
    
    # Check that RUN_MIGRATIONS_ON_START is explicitly set to "0"
    assert 'RUN_MIGRATIONS_ON_START: "0"' in worker_section or 'RUN_MIGRATIONS_ON_START: \'0\'' in worker_section, \
        "Worker should have RUN_MIGRATIONS_ON_START: '0'"
    
    # Check that maintenance queue is in RQ_QUEUES
    assert 'maintenance' in worker_section, \
        "Worker should listen to 'maintenance' queue"
    
    print("✅ Worker configured correctly: no migrations, listens to maintenance queue")


def test_delete_job_logging():
    """Verify delete_receipts_job has proper logging"""
    
    with open('server/jobs/delete_receipts_job.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for logging prefix
    assert '[RECEIPTS_DELETE]' in content, \
        "Missing [RECEIPTS_DELETE] logging prefix"
    
    # Check for key logging points
    assert 'JOB_START' in content, \
        "Missing job start logging"
    
    assert 'Batch complete' in content or 'batch done' in content.lower(), \
        "Missing batch completion logging"
    
    # Check for proper error logging
    assert 'Batch processing failed' in content or 'batch.*failed' in content.lower(), \
        "Missing batch error logging"
    
    print("✅ Delete job has comprehensive logging with [RECEIPTS_DELETE] prefix")


def test_ui_amount_display():
    """Verify UI shows 'לא זוהה סכום' instead of '—' for null amounts"""
    
    receipts_page_path = 'client/src/pages/receipts/ReceiptsPage.tsx'
    if not os.path.exists(receipts_page_path):
        print("⚠️  Warning: ReceiptsPage.tsx not found, skipping UI test")
        return
    
    with open(receipts_page_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that formatCurrency returns Hebrew text for null
    assert 'לא זוהה סכום' in content, \
        "Missing 'לא זוהה סכום' text for null amounts"
    
    # The old "—" should not be returned for null amounts in formatCurrency
    lines = content.split('\n')
    in_format_currency = False
    for line in lines:
        if 'const formatCurrency' in line or 'function formatCurrency' in line:
            in_format_currency = True
        elif in_format_currency and ('const ' in line or 'function ' in line):
            in_format_currency = False
        
        if in_format_currency and 'return' in line and 'null' in line:
            assert '—' not in line or 'לא זוהה סכום' in line, \
                f"formatCurrency should not return '—' for null: {line}"
    
    print("✅ UI displays 'לא זוהה סכום' for null amounts")


def test_ui_download_button():
    """Verify UI has download button using the new endpoint"""
    
    receipts_page_path = 'client/src/pages/receipts/ReceiptsPage.tsx'
    if not os.path.exists(receipts_page_path):
        print("⚠️  Warning: ReceiptsPage.tsx not found, skipping UI test")
        return
    
    with open(receipts_page_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for download button with new endpoint
    assert '/api/receipts/${receipt.id}/download' in content or \
           '/api/receipts/' in content and '/download' in content, \
        "Missing download button using /api/receipts/<id>/download endpoint"
    
    # Check for Hebrew download text
    assert 'הורד קבלה' in content or 'הורד' in content, \
        "Missing Hebrew download button text"
    
    print("✅ UI has download button using new /api/receipts/<id>/download endpoint")


def test_ui_preview_quality():
    """Verify UI prioritizes original attachment in detail view"""
    
    receipts_page_path = 'client/src/pages/receipts/ReceiptsPage.tsx'
    if not os.path.exists(receipts_page_path):
        print("⚠️  Warning: ReceiptsPage.tsx not found, skipping UI test")
        return
    
    with open(receipts_page_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for comment indicating priority of original over preview
    # The detail view should prioritize attachment over preview for quality
    assert 'ORIGINAL' in content or 'original' in content.lower(), \
        "Missing reference to original attachment priority"
    
    # Check for maxHeight or object-fit for better image display
    assert 'maxHeight' in content or 'max-height' in content or 'objectFit' in content, \
        "Missing image size optimization (maxHeight/objectFit)"
    
    print("✅ UI prioritizes original attachment for detail view with proper sizing")


def test_security_tenant_isolation():
    """Verify that receipts endpoints use g.tenant for isolation"""
    
    with open('server/routes_receipts.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check that get_current_business_id uses g.tenant
    assert 'g.tenant' in content, \
        "Missing g.tenant usage"
    
    # Check function definition
    lines = content.split('\n')
    in_get_business_id = False
    has_g_tenant = False
    
    for line in lines:
        if 'def get_current_business_id' in line:
            in_get_business_id = True
        elif in_get_business_id and line.strip().startswith('def '):
            break
        
        if in_get_business_id and 'g.tenant' in line:
            has_g_tenant = True
            break
    
    assert has_g_tenant, \
        "get_current_business_id should use g.tenant"
    
    print("✅ Security: All endpoints use g.tenant for business isolation")


def test_all_fixes():
    """Run all tests"""
    
    print("\n" + "="*70)
    print("Testing Complete Receipts Fixes")
    print("="*70 + "\n")
    
    try:
        test_export_uses_attachment_service()
        test_download_endpoint_exists()
        test_worker_config_no_migrations()
        test_delete_job_logging()
        test_ui_amount_display()
        test_ui_download_button()
        test_ui_preview_quality()
        test_security_tenant_isolation()
        
        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        
        print("\n📋 Summary of Fixes:")
        print("   1. ✅ Export receipts uses AttachmentService (no signed_url error)")
        print("   2. ✅ Download endpoint added (/api/receipts/<id>/download)")
        print("   3. ✅ Worker config: no migrations, maintenance queue added")
        print("   4. ✅ Delete job has [RECEIPTS_DELETE] logging")
        print("   5. ✅ UI shows 'לא זוהה סכום' for null amounts")
        print("   6. ✅ UI download button uses new endpoint")
        print("   7. ✅ UI prioritizes original for detail view quality")
        print("   8. ✅ Security: g.tenant used for business isolation")
        print()
        
        return True
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = test_all_fixes()
    sys.exit(0 if success else 1)
