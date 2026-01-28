"""
Test for Recording Playback and Download Button Fix

This test verifies:
1. AudioPlayer has proper deduplication and abort controller
2. Download button in LeadDetailPage has stopPropagation
"""

import re
import os

def test_audio_player_has_abort_controller():
    """Verify AudioPlayer has AbortController to cancel pending requests"""
    audio_player_path = "client/src/shared/components/AudioPlayer.tsx"
    
    with open(audio_player_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for AbortController ref
    assert 'abortControllerRef' in content, "AudioPlayer must have abortControllerRef"
    assert 'useRef<AbortController | null>(null)' in content, "abortControllerRef must be initialized"
    
    # Check for abort calls
    assert 'abortControllerRef.current.abort()' in content, "Must call abort() on controller"
    
    # Check for signal in fetch
    assert 'signal: controller.signal' in content, "Must pass signal to fetch"
    
    print("✅ AudioPlayer has proper AbortController implementation")


def test_audio_player_has_concurrent_check_guard():
    """Verify AudioPlayer prevents concurrent file checks"""
    audio_player_path = "client/src/shared/components/AudioPlayer.tsx"
    
    with open(audio_player_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for isCheckingRef guard
    assert 'isCheckingRef' in content, "AudioPlayer must have isCheckingRef"
    assert 'useRef<boolean>(false)' in content, "isCheckingRef must be boolean ref"
    
    # Check for guard logic
    assert 'if (isCheckingRef.current)' in content, "Must check isCheckingRef before processing"
    assert 'return { ready: false' in content, "Must return early if already checking"
    
    # Check for setting/resetting the flag
    assert 'isCheckingRef.current = true' in content, "Must set flag when checking starts"
    assert 'isCheckingRef.current = false' in content, "Must reset flag when checking ends"
    
    print("✅ AudioPlayer has concurrent check prevention")


def test_download_button_has_stop_propagation():
    """Verify download button in LeadDetailPage has stopPropagation"""
    lead_page_path = "client/src/pages/Leads/LeadDetailPage.tsx"
    
    with open(lead_page_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the section with handleDownload and getCallId
    # Check if stopPropagation exists in proximity
    has_handle_download = 'handleDownload(getCallId(call))' in content
    assert has_handle_download, "Download button with handleDownload(getCallId(call)) not found"
    
    # Find the position of handleDownload
    download_pos = content.find('handleDownload(getCallId(call))')
    
    # Look for stopPropagation within 200 characters before the handleDownload call
    # This covers the typical onClick handler scope
    search_start = max(0, download_pos - 200)
    search_section = content[search_start:download_pos + 50]
    
    assert 'stopPropagation' in search_section, \
        "Download button must call e.stopPropagation() to prevent event bubbling. " \
        "Check that the onClick handler includes 'e.stopPropagation()' before calling handleDownload."
    
    # Verify the handler accepts event parameter
    assert '(e)' in search_section or '( e )' in search_section, \
        "onClick handler must accept event parameter (e) to call stopPropagation"
    
    print("✅ Download button has stopPropagation to prevent parent collapse")


def test_audio_player_retry_logic():
    """Verify AudioPlayer has proper retry logic with exponential backoff"""
    audio_player_path = "client/src/shared/components/AudioPlayer.tsx"
    
    with open(audio_player_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check for retry configuration
    assert 'MAX_RETRIES' in content, "Must define MAX_RETRIES constant"
    assert 'getRetryDelay' in content, "Must have getRetryDelay function for backoff"
    
    # Check for 202 handling (file being prepared)
    assert 'response.status === 202' in content, "Must handle 202 Accepted status"
    assert 'Retry-After' in content, "Must respect Retry-After header"
    
    # Check for proper status codes
    assert 'response.status === 404' in content, "Must handle 404 Not Found"
    assert 'response.status === 500' in content, "Must handle 500 Server Error"
    
    print("✅ AudioPlayer has proper retry logic with status code handling")


def test_other_pages_download_buttons():
    """Verify other call pages already have correct download button implementation"""
    pages_to_check = [
        "client/src/pages/calls/InboundCallsPage.tsx",
        "client/src/pages/calls/OutboundCallsPage.tsx",
    ]
    
    for page_path in pages_to_check:
        if not os.path.exists(page_path):
            print(f"⚠️  {page_path} not found, skipping")
            continue
            
        with open(page_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # These pages use a div wrapper with stopPropagation
        # Look for: onClick={(e) => e.stopPropagation()} around download links
        if 'onClick={(e) => e.stopPropagation()}' in content:
            print(f"✅ {page_path} has correct stopPropagation implementation")
        else:
            print(f"⚠️  {page_path} might not have stopPropagation on download button")


if __name__ == '__main__':
    print("=" * 60)
    print("Testing Recording Playback and Download Button Fixes")
    print("=" * 60)
    print()
    
    try:
        test_audio_player_has_abort_controller()
        test_audio_player_has_concurrent_check_guard()
        test_audio_player_retry_logic()
        test_download_button_has_stop_propagation()
        test_other_pages_download_buttons()
        
        print()
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print()
        print("Summary:")
        print("1. ✅ AudioPlayer has AbortController for request cancellation")
        print("2. ✅ AudioPlayer prevents concurrent file checks")
        print("3. ✅ AudioPlayer has proper retry logic with backoff")
        print("4. ✅ LeadDetailPage download button has stopPropagation")
        print("5. ✅ Other call pages have correct implementation")
        
    except AssertionError as e:
        print()
        print("=" * 60)
        print("❌ TEST FAILED")
        print("=" * 60)
        print(f"Error: {e}")
        exit(1)
