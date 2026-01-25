"""
Test USE_REALTIME_API Environment Variable Removal
Validates that routing is based solely on ai_provider, not ENV variables
"""
import re


def test_no_global_use_realtime_api_checks():
    """Test that media_ws_ai.py doesn't use global USE_REALTIME_API for routing decisions"""
    print("\n" + "=" * 80)
    print("Validating USE_REALTIME_API Removal in media_ws_ai.py")
    print("=" * 80)
    
    # Read the file
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        lines = f.readlines()
    
    # Find all lines that check USE_REALTIME_API
    problematic_lines = []
    for i, line in enumerate(lines, 1):
        # Skip comments and boot logging
        if '#' in line and 'USE_REALTIME_API' in line.split('#')[0]:
            continue
        if i < 1070 and 'BOOT' in line:  # Allow boot logs
            continue
            
        # Check for direct USE_REALTIME_API checks without getattr
        if re.search(r'\bif\s+(not\s+)?USE_REALTIME_API\b', line) and 'getattr' not in line:
            # Skip if this is inside getattr on the next line
            if i < len(lines) and 'getattr' in lines[i]:
                continue
            problematic_lines.append((i, line.strip()))
        elif re.search(r'\band\s+(not\s+)?USE_REALTIME_API\b', line) and 'getattr' not in line:
            problematic_lines.append((i, line.strip()))
        elif re.search(r'\bor\s+(not\s+)?USE_REALTIME_API\b', line) and 'getattr' not in line:
            problematic_lines.append((i, line.strip()))
    
    # Filter out boot logs (line ~1058)
    problematic_lines = [(num, line) for num, line in problematic_lines if num > 1070]
    
    if problematic_lines:
        print("❌ Found direct USE_REALTIME_API checks (should use per-call override):")
        for line_num, line_text in problematic_lines:
            print(f"   Line {line_num}: {line_text}")
        return False
    else:
        print("✓ No direct USE_REALTIME_API checks found (all use per-call override)")
    
    # Test 2: Verify per-call override is used
    content = ''.join(lines)
    override_count = content.count('_USE_REALTIME_API_OVERRIDE')
    if override_count >= 8:
        print(f"✓ Per-call override (_USE_REALTIME_API_OVERRIDE) is used {override_count} times")
    else:
        print(f"❌ Per-call override found only {override_count} times (expected at least 8)")
        return False
    
    # Test 3: Verify guard in _hebrew_stt
    if 'if ai_provider == \'gemini\' and use_realtime_for_this_call:' in content:
        print("✓ Guard exists to prevent Gemini from using realtime")
    else:
        print("❌ Guard not found to prevent Gemini from using realtime")
        return False
    
    if 'raise RuntimeError("BUG: Gemini cannot use realtime' in content:
        print("✓ Guard raises RuntimeError (not just warning)")
    else:
        print("❌ Guard doesn't raise RuntimeError")
        return False
    
    # Test 4: Verify routing is set based on ai_provider
    if 'use_realtime_for_this_call = (ai_provider == \'openai\')' in content:
        print("✓ Routing is based on ai_provider (OpenAI = realtime, others = not)")
    else:
        print("❌ Routing not based on ai_provider")
        return False
    
    # Test 5: Verify _USE_REALTIME_API_OVERRIDE is set
    if 'self._USE_REALTIME_API_OVERRIDE = use_realtime_for_this_call' in content:
        print("✓ Per-call override is set based on ai_provider")
    else:
        print("❌ Per-call override not set")
        return False
    
    # Test 6: Verify getattr pattern is used consistently
    getattr_pattern = r'getattr\(self,\s*[\'"]_USE_REALTIME_API_OVERRIDE[\'"]\s*,\s*USE_REALTIME_API\)'
    getattr_matches = re.findall(getattr_pattern, content)
    if len(getattr_matches) >= 8:
        print(f"✓ Consistent getattr pattern for per-call override ({len(getattr_matches)} occurrences)")
    else:
        print(f"❌ Inconsistent use of getattr pattern ({len(getattr_matches)} found, expected >= 8)")
        return False
    
    print("\n" + "=" * 80)
    print("✅ ALL USE_REALTIME_API REMOVAL VALIDATIONS PASSED")
    print("=" * 80)
    return True


def test_provider_routing_logs():
    """Test that proper logging exists for provider routing"""
    print("\n" + "=" * 80)
    print("Validating Provider Routing Logs")
    print("=" * 80)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Test 1: CALL_ROUTING log includes provider
    if '[CALL_ROUTING]' in content and 'provider=' in content:
        print("✓ [CALL_ROUTING] log includes provider")
    else:
        print("❌ [CALL_ROUTING] log missing or incomplete")
        return False
    
    # Test 2: Gemini pipeline log
    if '[GEMINI_PIPELINE]' in content:
        print("✓ [GEMINI_PIPELINE] log exists")
    else:
        print("❌ [GEMINI_PIPELINE] log not found")
        return False
    
    # Test 3: OpenAI pipeline log
    if '[OPENAI_PIPELINE]' in content:
        print("✓ [OPENAI_PIPELINE] log exists")
    else:
        print("❌ [OPENAI_PIPELINE] log not found")
        return False
    
    print("\n" + "=" * 80)
    print("✅ ALL PROVIDER ROUTING LOG VALIDATIONS PASSED")
    print("=" * 80)
    return True


def test_no_env_dependency():
    """Test that ENV variables don't affect routing"""
    print("\n" + "=" * 80)
    print("Validating No ENV Dependency for Routing")
    print("=" * 80)
    
    with open('/home/runner/work/prosaasil/prosaasil/server/media_ws_ai.py', 'r') as f:
        content = f.read()
    
    # Look for the routing decision
    routing_section = content[content.find('use_realtime_for_this_call = (ai_provider'):
                              content.find('use_realtime_for_this_call = (ai_provider') + 500]
    
    # Verify no getenv in routing decision
    if 'getenv' not in routing_section[:200]:
        print("✓ Routing decision doesn't use getenv()")
    else:
        print("❌ Routing decision uses getenv()")
        return False
    
    # Verify routing is purely based on ai_provider
    if "use_realtime_for_this_call = (ai_provider == 'openai')" in content:
        print("✓ Routing is purely based on ai_provider value")
    else:
        print("❌ Routing not purely based on ai_provider")
        return False
    
    print("\n" + "=" * 80)
    print("✅ ALL ENV DEPENDENCY VALIDATIONS PASSED")
    print("=" * 80)
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 80)
    print("USE_REALTIME_API REMOVAL - COMPREHENSIVE VALIDATION")
    print("=" * 80)
    
    all_passed = True
    
    # Test 1: No global USE_REALTIME_API checks
    if not test_no_global_use_realtime_api_checks():
        all_passed = False
        print("\n❌ Global USE_REALTIME_API check tests FAILED")
    
    # Test 2: Provider routing logs
    if not test_provider_routing_logs():
        all_passed = False
        print("\n❌ Provider routing log tests FAILED")
    
    # Test 3: No ENV dependency
    if not test_no_env_dependency():
        all_passed = False
        print("\n❌ ENV dependency tests FAILED")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("✅✅✅ ALL TESTS PASSED ✅✅✅")
        print("=" * 80)
        print("\nSummary of Validations:")
        print("1. ✓ USE_REALTIME_API checks replaced with per-call override")
        print("2. ✓ Guard prevents Gemini from using realtime (raises exception)")
        print("3. ✓ Routing based solely on ai_provider (no ENV)")
        print("4. ✓ Per-call override set and used consistently")
        print("5. ✓ Proper logging for routing decisions")
        print("\n🎯 The fix correctly addresses the problem:")
        print("   - Gemini calls won't use realtime path ✓")
        print("   - OpenAI calls use Realtime API ✓")
        print("   - ENV changes don't affect routing ✓")
        print("   - Clear error if misconfiguration occurs ✓")
        return 0
    else:
        print("❌❌❌ SOME TESTS FAILED ❌❌❌")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
