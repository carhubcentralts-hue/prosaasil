#!/usr/bin/env python3
"""
Gemini Voices Verification Script

Discovers and verifies all available Gemini/Google TTS voices.
Outputs a report of which voices work and which fail.

Usage:
    python scripts/gemini_voices_verify.py

🔒 Security: This script is for QA/CI only, not for production.
"""
import os
import sys
import json
import time
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def verify_gemini_voices():
    """Discover and verify all Gemini Hebrew voices"""
    
    print("=" * 60)
    print("🔍 GEMINI VOICE VERIFICATION")
    print(f"⏰ {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Check for API key
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        print("\n❌ ERROR: GEMINI_API_KEY not set")
        print("Set the environment variable and try again:")
        print("  export GEMINI_API_KEY=your-api-key")
        return 1
    
    print(f"\n✅ GEMINI_API_KEY found (length: {len(gemini_api_key)})")
    
    # Step 1: Discover voices via API
    print("\n" + "-" * 40)
    print("📋 STEP 1: Discovering voices via API")
    print("-" * 40)
    
    try:
        import requests
        
        url = f"https://texttospeech.googleapis.com/v1/voices?key={gemini_api_key}"
        response = requests.get(url, timeout=30)
        
        if response.status_code != 200:
            error_data = response.json() if response.text else {}
            error_msg = error_data.get('error', {}).get('message', f'HTTP {response.status_code}')
            print(f"❌ API Error: {error_msg}")
            return 1
        
        data = response.json()
        all_voices = data.get('voices', [])
        
        print(f"✅ Found {len(all_voices)} total voices")
        
        # Filter Hebrew voices
        hebrew_voices = []
        for voice in all_voices:
            lang_codes = voice.get('languageCodes', [])
            if 'he-IL' in lang_codes or any(lc.startswith('he') for lc in lang_codes):
                hebrew_voices.append({
                    'id': voice.get('name'),
                    'gender': voice.get('ssmlGender'),
                    'sample_rate': voice.get('naturalSampleRateHertz'),
                    'languages': lang_codes
                })
        
        print(f"✅ Found {len(hebrew_voices)} Hebrew voices")
        
    except Exception as e:
        print(f"❌ Discovery failed: {e}")
        return 1
    
    if not hebrew_voices:
        print("⚠️ No Hebrew voices found!")
        return 1
    
    # Step 2: Test each voice with TTS preview
    print("\n" + "-" * 40)
    print("🎤 STEP 2: Testing voice synthesis")
    print("-" * 40)
    
    test_text = "שלום, זוהי בדיקת קול"
    results = {
        'success': [],
        'failed': []
    }
    
    for voice in hebrew_voices:
        voice_id = voice['id']
        print(f"\n  Testing: {voice_id}...", end=" ")
        
        try:
            payload = {
                "input": {"text": test_text},
                "voice": {
                    "languageCode": "he-IL",
                    "name": voice_id
                },
                "audioConfig": {
                    "audioEncoding": "MP3",
                    "speakingRate": 1.0
                }
            }
            
            synth_url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={gemini_api_key}"
            synth_response = requests.post(synth_url, json=payload, timeout=30)
            
            if synth_response.status_code == 200:
                audio_content = synth_response.json().get('audioContent', '')
                if audio_content:
                    audio_size = len(audio_content) * 3 // 4  # Approximate decoded size
                    print(f"✅ OK ({audio_size} bytes)")
                    results['success'].append({
                        **voice,
                        'audio_size': audio_size
                    })
                else:
                    print("❌ No audio content")
                    results['failed'].append({
                        **voice,
                        'error': 'No audio content'
                    })
            else:
                error_data = synth_response.json() if synth_response.text else {}
                error_msg = error_data.get('error', {}).get('message', f'HTTP {synth_response.status_code}')
                print(f"❌ {error_msg}")
                results['failed'].append({
                    **voice,
                    'error': error_msg
                })
                
        except Exception as e:
            print(f"❌ {e}")
            results['failed'].append({
                **voice,
                'error': str(e)
            })
        
        # Rate limit protection
        time.sleep(0.5)
    
    # Step 3: Summary report
    print("\n" + "=" * 60)
    print("📊 VERIFICATION REPORT")
    print("=" * 60)
    
    print(f"\n✅ Working voices: {len(results['success'])}")
    for v in results['success']:
        print(f"   - {v['id']} ({v['gender']}, {v['audio_size']} bytes)")
    
    if results['failed']:
        print(f"\n❌ Failed voices: {len(results['failed'])}")
        for v in results['failed']:
            print(f"   - {v['id']}: {v['error']}")
    
    # Output JSON for catalog
    print("\n" + "-" * 40)
    print("📦 CATALOG OUTPUT (for gemini_voice_catalog.py)")
    print("-" * 40)
    
    catalog_voices = []
    for v in results['success']:
        catalog_voices.append({
            'id': v['id'],
            'gender': v['gender'],
            'language': 'he-IL'
        })
    
    print(json.dumps(catalog_voices, indent=2, ensure_ascii=False))
    
    print("\n" + "=" * 60)
    print(f"✅ Verification complete: {len(results['success'])}/{len(hebrew_voices)} voices working")
    print("=" * 60)
    
    return 0 if not results['failed'] else 1


if __name__ == '__main__':
    sys.exit(verify_gemini_voices())
