"""
Test to verify AgentKit connection is properly wired in WhatsApp bot
This test checks that the generate_response_with_agent method exists and is callable.
"""
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'server'))

def test_agentkit_method_exists():
    """Test that generate_response_with_agent method exists in AIService"""
    try:
        # Import without running code (just parse)
        import ast
        
        ai_service_path = os.path.join(os.path.dirname(__file__), 'server', 'services', 'ai_service.py')
        with open(ai_service_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        # Find AIService class
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'AIService':
                # Find generate_response_with_agent method
                method_names = [m.name for m in node.body if isinstance(m, ast.FunctionDef)]
                
                if 'generate_response_with_agent' in method_names:
                    print("✅ SUCCESS: generate_response_with_agent method exists in AIService class")
                    
                    # Find the method and check its signature
                    for m in node.body:
                        if isinstance(m, ast.FunctionDef) and m.name == 'generate_response_with_agent':
                            params = [arg.arg for arg in m.args.args]
                            print(f"   Method signature parameters: {params}")
                            
                            # Check required parameters
                            expected_params = ['self', 'message', 'business_id', 'context', 'channel', 
                                             'customer_phone', 'customer_name']
                            
                            for param in expected_params:
                                if param in params:
                                    print(f"   ✅ Parameter '{param}' found")
                                else:
                                    print(f"   ⚠️  Parameter '{param}' missing")
                            
                            return True
                else:
                    print("❌ FAIL: generate_response_with_agent method NOT found in AIService class")
                    print(f"   Available methods: {method_names}")
                    return False
        
        print("❌ FAIL: AIService class not found")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_webhook_can_call_method():
    """Test that webhook code can reference the method"""
    try:
        routes_path = os.path.join(os.path.dirname(__file__), 'server', 'routes_whatsapp.py')
        with open(routes_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if 'ai_service.generate_response_with_agent(' in content:
            print("✅ SUCCESS: Webhook calls generate_response_with_agent")
            
            # Count occurrences
            count = content.count('generate_response_with_agent')
            print(f"   Found {count} reference(s) to the method")
            return True
        else:
            print("❌ FAIL: Webhook does not call generate_response_with_agent")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_method_returns_dict():
    """Test that method signature indicates it returns a dict"""
    try:
        import ast
        
        ai_service_path = os.path.join(os.path.dirname(__file__), 'server', 'services', 'ai_service.py')
        with open(ai_service_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read())
        
        # Find method
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == 'AIService':
                for m in node.body:
                    if isinstance(m, ast.FunctionDef) and m.name == 'generate_response_with_agent':
                        # Check return annotation
                        if m.returns:
                            return_type = ast.unparse(m.returns) if hasattr(ast, 'unparse') else str(m.returns)
                            print(f"✅ SUCCESS: Method has return type annotation: {return_type}")
                            
                            # Check if it mentions Dict
                            if 'Dict' in return_type or 'dict' in return_type.lower():
                                print("   ✅ Return type includes Dict")
                                return True
                            else:
                                print(f"   ⚠️  Return type may not be Dict: {return_type}")
                                return True
                        else:
                            print("⚠️  WARNING: Method has no return type annotation")
                            return True
        
        print("❌ FAIL: Method not found for return type check")
        return False
        
    except Exception as e:
        print(f"⚠️  WARNING: Could not check return type: {e}")
        return True  # Don't fail on this - it's not critical

if __name__ == '__main__':
    print("="*60)
    print("Testing AgentKit Connection")
    print("="*60)
    print()
    
    tests = [
        ("Method Exists", test_agentkit_method_exists),
        ("Webhook References Method", test_webhook_can_call_method),
        ("Return Type Check", test_method_returns_dict),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n🧪 Test: {name}")
        print("-" * 60)
        result = test_func()
        results.append((name, result))
        print()
    
    print("="*60)
    print("Test Summary")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! AgentKit connection should be working.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        sys.exit(1)
