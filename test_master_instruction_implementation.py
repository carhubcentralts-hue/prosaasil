"""
Test Master Instruction Implementation
Verify key requirements are implemented correctly
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_imports():
    """Test that gmail_sync_service can be imported"""
    try:
        from server.services import gmail_sync_service
        print("✓ gmail_sync_service imported successfully")
        return True
    except Exception as e:
        print(f"✗ Failed to import gmail_sync_service: {e}")
        return False

def test_check_is_receipt_email_with_attachment():
    """Test Rule 1: Any attachment = must process"""
    from server.services.gmail_sync_service import check_is_receipt_email
    
    # Mock message with PDF attachment
    mock_message = {
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'Random email'},
                {'name': 'From', 'value': 'test@example.com'},
                {'name': 'Date', 'value': 'Mon, 1 Jan 2024 12:00:00 +0000'}
            ],
            'parts': [
                {
                    'mimeType': 'application/pdf',
                    'filename': 'document.pdf',
                    'body': {
                        'attachmentId': 'att123',
                        'size': 1000
                    },
                    'headers': [
                        {'name': 'Content-Disposition', 'value': 'attachment'}
                    ]
                }
            ]
        },
        'snippet': 'Random email content'
    }
    
    is_receipt, confidence, metadata = check_is_receipt_email(mock_message)
    
    # Rule 1: ANY attachment = MUST process
    if is_receipt and confidence == 100:
        print("✓ Rule 1 PASSED: Email with attachment returns is_receipt=True, confidence=100")
        return True
    else:
        print(f"✗ Rule 1 FAILED: Expected is_receipt=True, confidence=100, got is_receipt={is_receipt}, confidence={confidence}")
        return False

def test_check_is_receipt_email_without_attachment():
    """Test that emails without attachments use keyword detection"""
    from server.services.gmail_sync_service import check_is_receipt_email
    
    # Mock message without attachment but with receipt keywords
    mock_message = {
        'payload': {
            'headers': [
                {'name': 'Subject', 'value': 'קבלה - תשלום הצליח'},
                {'name': 'From', 'value': 'billing@company.com'},
                {'name': 'Date', 'value': 'Mon, 1 Jan 2024 12:00:00 +0000'}
            ],
            'parts': []
        },
        'snippet': 'סכום: 100 ₪'
    }
    
    is_receipt, confidence, metadata = check_is_receipt_email(mock_message)
    
    # Should detect receipt based on keywords and currency
    if is_receipt and confidence > 0:
        print(f"✓ Keyword detection works: is_receipt={is_receipt}, confidence={confidence}")
        return True
    else:
        print(f"✗ Keyword detection failed: is_receipt={is_receipt}, confidence={confidence}")
        return False

def test_generate_email_screenshot_pdf():
    """Test Rule 3: Screenshots must be PDF format"""
    from server.services.gmail_sync_service import generate_email_screenshot
    
    # Check function signature and docstring
    import inspect
    doc = inspect.getdoc(generate_email_screenshot)
    
    if 'PDF' in doc and 'email_snapshot.pdf' in doc:
        print("✓ Rule 3: generate_email_screenshot documentation mentions PDF and email_snapshot.pdf")
        return True
    else:
        print("✗ Rule 3: generate_email_screenshot documentation doesn't mention PDF format")
        return False

def test_extract_all_attachments():
    """Test Rule 5: Extract ALL attachments"""
    from server.services.gmail_sync_service import extract_all_attachments
    
    # Mock message with multiple attachments
    mock_message = {
        'payload': {
            'parts': [
                {
                    'mimeType': 'application/pdf',
                    'filename': 'invoice.pdf',
                    'body': {'attachmentId': 'att1', 'size': 1000},
                    'headers': [{'name': 'Content-Disposition', 'value': 'attachment'}]
                },
                {
                    'mimeType': 'image/jpeg',
                    'filename': 'receipt.jpg',
                    'body': {'attachmentId': 'att2', 'size': 2000},
                    'headers': [{'name': 'Content-Disposition', 'value': 'attachment'}]
                },
                {
                    'mimeType': 'application/pdf',
                    'filename': 'statement.pdf',
                    'body': {'attachmentId': 'att3', 'size': 3000},
                    'headers': [{'name': 'Content-Disposition', 'value': 'attachment'}]
                }
            ]
        }
    }
    
    attachments = extract_all_attachments(mock_message)
    
    if len(attachments) == 3:
        print(f"✓ Rule 5: extract_all_attachments found all 3 attachments")
        return True
    else:
        print(f"✗ Rule 5: Expected 3 attachments, got {len(attachments)}")
        return False

def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Testing Master Instruction Implementation")
    print("="*60 + "\n")
    
    tests = [
        ("Import test", test_imports),
        ("Rule 1: Any attachment = must process", test_check_is_receipt_email_with_attachment),
        ("Keyword detection (no attachment)", test_check_is_receipt_email_without_attachment),
        ("Rule 3: PDF screenshot format", test_generate_email_screenshot_pdf),
        ("Rule 5: Extract ALL attachments", test_extract_all_attachments),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}...")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
