#!/usr/bin/env python3
"""
Test URL normalization for Twilio recording downloads
"""

def normalize_recording_url(recording_url: str) -> str:
    """Normalize Twilio recording URL - same logic as download_recording()"""
    download_url = recording_url or ""
    
    # 1) Ensure we have a full https URL with api.twilio.com
    if download_url.startswith("/"):
        download_url = f"https://api.twilio.com{download_url}"
    
    # 2) Normalize extension
    if download_url.endswith(".json"):
        download_url = download_url[:-5] + ".mp3"
    elif download_url.endswith(".mp3") or download_url.endswith(".wav"):
        pass
    else:
        download_url = download_url + ".mp3"
    
    return download_url


def test_url_normalization():
    """Test all URL formats"""
    
    test_cases = [
        {
            "name": "Relative JSON URL",
            "input": "/2010-04-01/Accounts/ACxxx/Recordings/RExxx.json",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
        },
        {
            "name": "Relative media URL (mp3)",
            "input": "/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
        },
        {
            "name": "Relative media URL (wav)",
            "input": "/2010-04-01/Accounts/ACxxx/Recordings/RExxx.wav",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.wav"
        },
        {
            "name": "Absolute JSON URL",
            "input": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.json",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
        },
        {
            "name": "Absolute media URL (mp3)",
            "input": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
        },
        {
            "name": "Relative URL without extension",
            "input": "/2010-04-01/Accounts/ACxxx/Recordings/RExxx",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
        },
        {
            "name": "Absolute URL without extension",
            "input": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx",
            "expected": "https://api.twilio.com/2010-04-01/Accounts/ACxxx/Recordings/RExxx.mp3"
        },
    ]
    
    print("=" * 80)
    print("🧪 TESTING URL NORMALIZATION FOR TWILIO RECORDINGS")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        result = normalize_recording_url(test["input"])
        is_pass = result == test["expected"]
        
        if is_pass:
            passed += 1
            status = "✅ PASS"
        else:
            failed += 1
            status = "❌ FAIL"
        
        print(f"\n{status} - {test['name']}")
        print(f"  Input:    {test['input']}")
        print(f"  Expected: {test['expected']}")
        print(f"  Got:      {result}")
        
        if not is_pass:
            print(f"  ⚠️  MISMATCH!")
    
    print("\n" + "=" * 80)
    print(f"📊 RESULTS: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print("=" * 80)
    
    return failed == 0


if __name__ == "__main__":
    success = test_url_normalization()
    exit(0 if success else 1)
