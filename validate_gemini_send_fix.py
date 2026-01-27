"""
Simple validation for Gemini Live API send_realtime_input fix
Verifies the code structure without needing pytest
"""
import sys
import os
import inspect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

def validate_imports():
    """Validate that types module is imported"""
    print("🧪 Validating imports...")
    
    try:
        from server.services import gemini_realtime_client
        
        # Check that types is imported
        assert hasattr(gemini_realtime_client, 'types'), "types module not imported"
        
        # Check genai is imported
        assert hasattr(gemini_realtime_client, 'genai'), "genai module not imported"
        
        print("✅ Imports are correct (types and genai)")
        return True
    except Exception as e:
        print(f"❌ Import validation failed: {e}")
        return False


def validate_send_audio_method():
    """Validate send_audio method signature and implementation"""
    print("\n🧪 Validating send_audio method...")
    
    try:
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        # Get the source code of send_audio
        source = inspect.getsource(GeminiRealtimeClient.send_audio)
        
        # Check that it uses types.Blob
        assert 'types.Blob' in source, "send_audio should create a types.Blob object"
        
        # Check that it uses send_realtime_input
        assert 'send_realtime_input' in source, "send_audio should call send_realtime_input"
        
        # Check MIME type is correct
        assert 'audio/pcm;rate=16000' in source, "send_audio should use audio/pcm;rate=16000 MIME type"
        
        # Check that audio= parameter is used
        assert 'audio=' in source or 'audio =' in source, "send_audio should use audio= parameter"
        
        # Check that old send() is NOT used with positional args
        if 'self.session.send(' in source:
            # Make sure it's not the problematic pattern
            assert 'self.session.send({' not in source, "Old send() pattern with dict should not be present"
        
        print("✅ send_audio method uses correct API:")
        print("   - Creates types.Blob with audio data")
        print("   - Uses send_realtime_input(audio=blob)")
        print("   - Uses correct MIME type: audio/pcm;rate=16000")
        return True
        
    except Exception as e:
        print(f"❌ send_audio validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_send_text_method():
    """Validate send_text method signature and implementation"""
    print("\n🧪 Validating send_text method...")
    
    try:
        from server.services.gemini_realtime_client import GeminiRealtimeClient
        
        # Get the source code of send_text
        source = inspect.getsource(GeminiRealtimeClient.send_text)
        
        # Check that it uses send_realtime_input
        assert 'send_realtime_input' in source, "send_text should call send_realtime_input"
        
        # Check that text= parameter is used
        assert 'text=' in source or 'text =' in source, "send_text should use text= parameter"
        
        # Check that old send() with positional args is NOT used
        if 'self.session.send(' in source:
            # The new pattern should be send_realtime_input only
            lines = source.split('\n')
            for line in lines:
                if 'self.session.send(' in line and 'send_realtime_input' not in line:
                    raise AssertionError(f"Old send() pattern found: {line.strip()}")
        
        print("✅ send_text method uses correct API:")
        print("   - Uses send_realtime_input(text=...)")
        return True
        
    except Exception as e:
        print(f"❌ send_text validation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_no_positional_dict_in_send():
    """Ensure the problematic send() pattern is removed"""
    print("\n🧪 Validating no problematic send() patterns...")
    
    try:
        with open('server/services/gemini_realtime_client.py', 'r') as f:
            content = f.read()
        
        # Check for the old problematic pattern
        problematic_patterns = [
            'await self.session.send({',
            'session.send({\n',
            'session.send(dict',
        ]
        
        for pattern in problematic_patterns:
            if pattern in content:
                print(f"❌ Found problematic pattern: {pattern}")
                return False
        
        print("✅ No problematic send() patterns found")
        return True
        
    except Exception as e:
        print(f"❌ Validation failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 70)
    print("Validating Gemini Live API send_realtime_input Fix")
    print("=" * 70)
    
    all_passed = True
    
    all_passed &= validate_imports()
    all_passed &= validate_send_audio_method()
    all_passed &= validate_send_text_method()
    all_passed &= validate_no_positional_dict_in_send()
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL VALIDATIONS PASSED")
        print("=" * 70)
        print("\nThe fix correctly:")
        print("1. Imports types module from google.genai")
        print("2. Uses types.Blob for audio data")
        print("3. Uses send_realtime_input(audio=...) for audio")
        print("4. Uses send_realtime_input(text=...) for text")
        print("5. Removes the problematic send() pattern")
        sys.exit(0)
    else:
        print("❌ SOME VALIDATIONS FAILED")
        print("=" * 70)
        sys.exit(1)
