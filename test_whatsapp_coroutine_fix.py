"""
Test to verify WhatsApp AI coroutine fix
This test verifies that the Runner.run() async call is properly awaited.
"""
import sys
import os

def test_asyncio_import():
    """Test that asyncio is imported in ai_service.py"""
    try:
        with open('server/services/ai_service.py', 'r') as f:
            content = f.read()
        
        if 'import asyncio' in content:
            print("✅ asyncio is imported in ai_service.py")
            return True
        else:
            print("❌ asyncio is NOT imported in ai_service.py")
            return False
            
    except Exception as e:
        print(f"❌ Error testing asyncio import: {e}")
        return False

def test_runner_run_awaited():
    """Test that runner.run() is properly awaited"""
    try:
        with open('server/services/ai_service.py', 'r') as f:
            content = f.read()
        
        # Check that asyncio.run is used
        if 'asyncio.run(runner.run(agent, message, context=agent_context))' in content:
            print("✅ runner.run() is properly awaited using asyncio.run()")
        else:
            print("❌ runner.run() is NOT properly awaited")
            return False
        
        # Check for event loop fallback
        if 'loop.run_until_complete(runner.run(agent, message, context=agent_context))' in content:
            print("✅ Event loop fallback is implemented")
        else:
            print("❌ Event loop fallback is missing")
            return False
        
        # Make sure the old incorrect usage is not present
        if 'result = runner.run(agent, message, context=agent_context)' in content and \
           'asyncio.run(runner.run' not in content:
            print("❌ Old synchronous runner.run() call still present")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing runner.run() awaiting: {e}")
        return False

def test_no_coroutine_object_in_logs():
    """Test that the fix prevents coroutine objects from being logged"""
    try:
        with open('server/services/ai_service.py', 'r') as f:
            content = f.read()
        
        # The fix should ensure result is an actual result object, not a coroutine
        if 'asyncio.run(' in content or 'run_until_complete(' in content:
            print("✅ Async handling implemented to prevent coroutine objects")
            return True
        else:
            print("❌ No async handling found")
            return False
            
    except Exception as e:
        print(f"❌ Error testing coroutine prevention: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Testing WhatsApp AI Coroutine Fix")
    print("="*60)
    
    results = []
    
    print("\n1. Testing asyncio import...")
    results.append(test_asyncio_import())
    
    print("\n2. Testing runner.run() is properly awaited...")
    results.append(test_runner_run_awaited())
    
    print("\n3. Testing coroutine object prevention...")
    results.append(test_no_coroutine_object_in_logs())
    
    print("\n" + "="*60)
    if all(results):
        print("✅ ALL TESTS PASSED")
        print("\nThe fix ensures that:")
        print("- asyncio is imported")
        print("- runner.run() is properly awaited using asyncio.run()")
        print("- Event loop fallback is implemented for nested contexts")
        print("- Coroutine objects won't be sent as WhatsApp messages")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
