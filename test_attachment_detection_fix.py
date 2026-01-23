#!/usr/bin/env python3
"""
Test for Gmail attachment detection and duplicate removal fixes

Verifies:
1. Attachment detection logging shows actual has_attachment value (not hardcoded False)
2. Duplicate checking has been removed from all sync paths
3. Counters properly separate skipped_non_receipts from deprecated skipped
4. Gmail API uses format='full' by default
"""

import sys
import re


def test_attachment_logging_fix():
    """
    Test that has_attachment logging uses actual value from metadata
    """
    print("=" * 80)
    print("TEST: Attachment detection logging fix")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Find the logging statement in check_is_receipt_email
        pattern = r'logger\.info\(f"📧 Receipt detection:.*has_attachment=([^,}]+)'
        matches = re.findall(pattern, content)
        
        if not matches:
            print("❌ FAIL: Could not find receipt detection logging statement")
            return False
        
        # Check the first match (should be the one we care about)
        has_attachment_expr = matches[0]
        
        if has_attachment_expr == "False":
            print(f"❌ FAIL: has_attachment is hardcoded to False: {has_attachment_expr}")
            return False
        elif "metadata.get('has_attachment'" in has_attachment_expr or "metadata['has_attachment']" in has_attachment_expr:
            print(f"✅ PASS: has_attachment uses actual value from metadata: {has_attachment_expr}")
            return True
        else:
            print(f"⚠️  WARNING: Unexpected has_attachment expression: {has_attachment_expr}")
            return False
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_duplicate_checks_removed():
    """
    Test that duplicate checking has been removed from all sync paths
    """
    print("\n" + "=" * 80)
    print("TEST: Duplicate checking removal")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Look for duplicate checking patterns
        duplicate_check_count = 0
        removed_comment_count = 0
        
        for i, line in enumerate(lines, start=1):
            # Check for actual duplicate query code
            if 'Receipt.query.filter_by' in line and 'gmail_message_id' in line:
                # Look at surrounding lines to see if it's checking for existing
                context_start = max(0, i-5)
                context_end = min(len(lines), i+10)
                context = ''.join(lines[context_start:context_end])
                
                if 'existing = Receipt.query' in context:
                    duplicate_check_count += 1
                    print(f"⚠️  Found duplicate check at line {i}: {line.strip()}")
            
            # Check for removed comments
            if 'REMOVED: Duplicate checking' in line:
                removed_comment_count += 1
                print(f"✅ Found removal comment at line {i}: {line.strip()}")
        
        if duplicate_check_count == 0:
            print(f"\n✅ PASS: No active duplicate checks found (all removed)")
            print(f"✅ Found {removed_comment_count} removal comments documenting the changes")
            return True
        else:
            print(f"\n❌ FAIL: Found {duplicate_check_count} active duplicate checks (should be 0)")
            return False
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_counter_separation():
    """
    Test that skipped_non_receipts counter has been added
    """
    print("\n" + "=" * 80)
    print("TEST: Counter separation (skipped_non_receipts)")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check for skipped_non_receipts counter
        if "'skipped_non_receipts': 0" in content:
            print("✅ PASS: Found 'skipped_non_receipts' counter initialization")
        else:
            print("❌ FAIL: Could not find 'skipped_non_receipts' counter initialization")
            return False
        
        # Check for usage of the counter
        if "result['skipped_non_receipts'] += 1" in content:
            print("✅ PASS: Found 'skipped_non_receipts' counter increment")
        else:
            print("❌ FAIL: Could not find 'skipped_non_receipts' counter increment")
            return False
        
        # Check for SKIP_NON_RECEIPT logging
        if "SKIP_NON_RECEIPT:" in content:
            print("✅ PASS: Found 'SKIP_NON_RECEIPT' log message")
        else:
            print("⚠️  WARNING: Could not find 'SKIP_NON_RECEIPT' log message")
        
        return True
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gmail_api_format_full():
    """
    Test that Gmail API get_message uses format='full' by default
    """
    print("\n" + "=" * 80)
    print("TEST: Gmail API format='full' usage")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/server/services/gmail_sync_service.py'
        
        with open(file_path, 'r') as f:
            lines = f.readlines()
        
        # Find the get_message method definition
        for i, line in enumerate(lines, start=1):
            if 'def get_message(self, message_id: str' in line:
                # Check if format parameter defaults to 'full'
                if "format: str = 'full'" in line:
                    print(f"✅ PASS: get_message defaults to format='full' at line {i}")
                    return True
                else:
                    print(f"❌ FAIL: get_message does not default to format='full' at line {i}")
                    print(f"   Line: {line.strip()}")
                    return False
        
        print("❌ FAIL: Could not find get_message method definition")
        return False
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_progress_bar_fix():
    """
    Test that duplicate progress bar component has been removed
    """
    print("\n" + "=" * 80)
    print("TEST: UI progress bar duplication fix")
    print("=" * 80)
    
    try:
        file_path = '/home/runner/work/prosaasil/prosaasil/client/src/pages/receipts/ReceiptsPage.tsx'
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Check that SyncProgressDisplay component is not defined
        if 'const SyncProgressDisplay = () => {' in content:
            print("❌ FAIL: SyncProgressDisplay component is still defined")
            return False
        else:
            print("✅ PASS: SyncProgressDisplay component has been removed")
        
        # Check that SyncProgressDisplay is not being used
        # Look for actual JSX usage (not in comments)
        # Split by lines and check each line that doesn't start with comment
        lines = content.split('\n')
        usage_count = 0
        for line_num, line in enumerate(lines, 1):
            # Skip comment lines
            stripped = line.strip()
            if stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*') or stripped.startswith('{/*'):
                continue
            # Look for JSX usage
            if '<SyncProgressDisplay' in line and not '{/*' in line:
                usage_count += 1
                print(f"⚠️  Found usage at line {line_num}: {line.strip()}")
        
        if usage_count > 0:
            print(f"❌ FAIL: SyncProgressDisplay component is still being used ({usage_count} times)")
            return False
        else:
            print("✅ PASS: SyncProgressDisplay component usage has been removed")
        
        # Check for removal comments
        if 'REMOVED: SyncProgressDisplay' in content or 'REMOVED: <SyncProgressDisplay' in content:
            print("✅ PASS: Found removal comments documenting the change")
        else:
            print("⚠️  WARNING: No removal comments found")
        
        return True
            
    except FileNotFoundError:
        print(f"❌ File not found: {file_path}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = True
    
    # Run all tests
    success = test_attachment_logging_fix() and success
    success = test_duplicate_checks_removed() and success
    success = test_counter_separation() and success
    success = test_gmail_api_format_full() and success
    success = test_ui_progress_bar_fix() and success
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 All attachment detection fix tests passed!")
        print("=" * 80)
        print("\n✅ Verified fixes:")
        print("   1. Attachment detection logging uses actual metadata value")
        print("   2. All duplicate checking code has been removed")
        print("   3. New skipped_non_receipts counter properly separates non-receipts from duplicates")
        print("   4. Gmail API uses format='full' by default to fetch attachment data")
        print("   5. Duplicate progress bar component has been removed from UI")
        print("\n📝 Summary of changes:")
        print("   - has_attachment will now be logged correctly (not always False)")
        print("   - Emails will be re-processed even if previously synced (no duplicate skip)")
        print("   - Logs will show 'Skipped (non-receipts)' instead of 'Skipped (duplicates)'")
        print("   - Only one progress bar with cancel button in UI")
        sys.exit(0)
    else:
        print("❌ Some tests failed - please review the output above")
        print("=" * 80)
        sys.exit(1)
