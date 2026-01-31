"""
Test to verify AgentKit Runner fix
"""
import sys
import os

def test_runner_import():
    """Test that Runner can be imported and instantiated correctly"""
    try:
        from agents import Runner
        
        # Test that Runner can be instantiated without arguments
        runner = Runner()
        print("✅ Runner() instantiation successful")
        
        # Verify run method signature
        import inspect
        sig = inspect.signature(Runner.run)
        params = list(sig.parameters.keys())
        
        if 'starting_agent' in params:
            print("✅ Runner.run() has 'starting_agent' parameter")
        else:
            print("❌ Runner.run() missing 'starting_agent' parameter")
            return False
        
        if 'input' in params:
            print("✅ Runner.run() has 'input' parameter")
        else:
            print("❌ Runner.run() missing 'input' parameter")
            return False
        
        if 'context' in params:
            print("✅ Runner.run() has 'context' parameter")
        else:
            print("❌ Runner.run() missing 'context' parameter")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Runner: {e}")
        return False

def test_gemini_model_name():
    """Test that Gemini model name is updated"""
    try:
        import re
        
        # Check ai_service.py
        with open('server/services/ai_service.py', 'r') as f:
            content = f.read()
            
        if 'gemini-2.0-flash-exp' in content:
            print("❌ ai_service.py still contains gemini-2.0-flash-exp")
            return False
        
        if 'gemini-2.0-flash' in content:
            print("✅ ai_service.py uses gemini-2.0-flash")
        else:
            print("⚠️  ai_service.py doesn't contain gemini-2.0-flash")
        
        # Check google_clients.py
        with open('server/services/providers/google_clients.py', 'r') as f:
            content = f.read()
            
        if 'gemini-2.0-flash-exp' in content:
            print("❌ google_clients.py still contains gemini-2.0-flash-exp")
            return False
        
        if "os.getenv('GEMINI_LLM_MODEL', 'gemini-2.0-flash')" in content:
            print("✅ google_clients.py uses gemini-2.0-flash as default")
        else:
            print("⚠️  google_clients.py default might be different")
        
        # Check routes_live_call.py
        with open('server/routes_live_call.py', 'r') as f:
            content = f.read()
            
        if 'gemini-2.0-flash-exp' in content:
            print("❌ routes_live_call.py still contains gemini-2.0-flash-exp")
            return False
        
        if 'gemini-2.0-flash' in content:
            print("✅ routes_live_call.py uses gemini-2.0-flash")
        else:
            print("⚠️  routes_live_call.py doesn't contain gemini-2.0-flash")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Gemini model name: {e}")
        return False

def test_runner_usage_in_ai_service():
    """Test that Runner is used correctly in ai_service.py"""
    try:
        with open('server/services/ai_service.py', 'r') as f:
            content = f.read()
        
        # Check for correct instantiation
        if 'runner = Runner()' in content:
            print("✅ Runner instantiation is correct: Runner()")
        else:
            print("❌ Runner instantiation might be incorrect")
            return False
        
        # Check for correct run call
        if 'runner.run(agent, message, context=agent_context)' in content:
            print("✅ Runner.run() call is correct: runner.run(agent, message, context=agent_context)")
        else:
            print("❌ Runner.run() call might be incorrect")
            return False
        
        # Make sure old incorrect usage is not present
        if 'Runner(agent)' in content:
            print("❌ Old incorrect usage Runner(agent) still present")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Runner usage: {e}")
        return False

if __name__ == "__main__":
    print("="*60)
    print("Testing AgentKit Runner Fix")
    print("="*60)
    
    results = []
    
    print("\n1. Testing Runner import and signature...")
    results.append(test_runner_import())
    
    print("\n2. Testing Gemini model name updates...")
    results.append(test_gemini_model_name())
    
    print("\n3. Testing Runner usage in ai_service.py...")
    results.append(test_runner_usage_in_ai_service())
    
    print("\n" + "="*60)
    if all(results):
        print("✅ ALL TESTS PASSED")
        sys.exit(0)
    else:
        print("❌ SOME TESTS FAILED")
        sys.exit(1)
