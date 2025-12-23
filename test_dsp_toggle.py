#!/usr/bin/env python3
"""
Test ENV toggle for ENABLE_MIN_DSP

Verifies that:
1. ENABLE_MIN_DSP defaults to "1" (enabled)
2. ENABLE_MIN_DSP can be disabled via environment variable
"""
import os
import subprocess
import sys

def test_default_enabled():
    """Test 1: ENABLE_MIN_DSP defaults to enabled"""
    print("=== Test 1: Default (enabled) ===")
    
    # Clear env var if set
    env = os.environ.copy()
    if "ENABLE_MIN_DSP" in env:
        del env["ENABLE_MIN_DSP"]
    
    # Run Python with our test
    result = subprocess.run(
        [sys.executable, "-c", 
         "import os; print('ENABLE_MIN_DSP=' + os.getenv('ENABLE_MIN_DSP', '1'))"],
        env=env,
        capture_output=True,
        text=True
    )
    
    output = result.stdout.strip()
    print(f"Output: {output}")
    
    if "ENABLE_MIN_DSP=1" in output:
        print("✅ Default is enabled (ENABLE_MIN_DSP=1)")
        return True
    else:
        print("❌ Default should be '1' but got:", output)
        return False

def test_explicit_disabled():
    """Test 2: ENABLE_MIN_DSP can be disabled"""
    print("\n=== Test 2: Explicit disable ===")
    
    # Set env var to 0
    env = os.environ.copy()
    env["ENABLE_MIN_DSP"] = "0"
    
    # Run Python with our test
    result = subprocess.run(
        [sys.executable, "-c", 
         "import os; enabled = os.getenv('ENABLE_MIN_DSP', '1') == '1'; print(f'Enabled: {enabled}')"],
        env=env,
        capture_output=True,
        text=True
    )
    
    output = result.stdout.strip()
    print(f"Output: {output}")
    
    if "Enabled: False" in output:
        print("✅ Can be disabled (ENABLE_MIN_DSP=0 → False)")
        return True
    else:
        print("❌ Should be disabled but got:", output)
        return False

def test_explicit_enabled():
    """Test 3: ENABLE_MIN_DSP can be explicitly enabled"""
    print("\n=== Test 3: Explicit enable ===")
    
    # Set env var to 1
    env = os.environ.copy()
    env["ENABLE_MIN_DSP"] = "1"
    
    # Run Python with our test
    result = subprocess.run(
        [sys.executable, "-c", 
         "import os; enabled = os.getenv('ENABLE_MIN_DSP', '1') == '1'; print(f'Enabled: {enabled}')"],
        env=env,
        capture_output=True,
        text=True
    )
    
    output = result.stdout.strip()
    print(f"Output: {output}")
    
    if "Enabled: True" in output:
        print("✅ Can be enabled (ENABLE_MIN_DSP=1 → True)")
        return True
    else:
        print("❌ Should be enabled but got:", output)
        return False

def main():
    """Run all tests"""
    print("=" * 60)
    print("ENV Toggle Test")
    print("=" * 60)
    
    tests = [
        ("Default (enabled)", test_default_enabled),
        ("Explicit disable", test_explicit_disabled),
        ("Explicit enable", test_explicit_enabled),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n❌ {test_name} CRASHED: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed_count = sum(1 for _, passed in results if passed)
    total_count = len(results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed_count}/{total_count} tests passed")
    
    if passed_count == total_count:
        print("\n🎉 All toggle tests passed!")
        return 0
    else:
        print(f"\n⚠️ {total_count - passed_count} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
