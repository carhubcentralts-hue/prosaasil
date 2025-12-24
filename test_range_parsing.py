#!/usr/bin/env python3
"""
Test Range header parsing - verifies fix for bytes=-500 suffix ranges
"""

def parse_range(range_header, file_size):
    """Parse Range header exactly as routes_calls.py does"""
    byte_range = range_header.replace('bytes=', '').split('-')
    
    # Handle suffix-byte-range-spec: bytes=-500 (last N bytes)
    if not byte_range[0] and byte_range[1]:
        # Request for last N bytes
        suffix_length = int(byte_range[1])
        start = max(0, file_size - suffix_length)
        end = file_size - 1
    else:
        # Normal range or open-ended range
        start = int(byte_range[0]) if byte_range[0] else 0
        end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
    
    # Ensure valid range
    if start >= file_size:
        return None  # 416 Range Not Satisfiable
    
    end = min(end, file_size - 1)
    length = end - start + 1
    
    return (start, end, length)

# Test cases
tests = [
    ("bytes=0-999", 10000, (0, 999, 1000), "First 1000 bytes"),
    ("bytes=0-", 10000, (0, 9999, 10000), "From start to end"),
    ("bytes=-500", 10000, (9500, 9999, 500), "Last 500 bytes (suffix)"),
    ("bytes=-100", 50, (0, 49, 50), "Last 100 of 50 byte file"),
    ("bytes=5000-", 10000, (5000, 9999, 5000), "From middle to end"),
]

print("Testing Range Header Parsing")
print("=" * 70)

all_passed = True
for range_str, file_size, expected, desc in tests:
    result = parse_range(range_str, file_size)
    passed = result == expected
    
    status = "✅" if passed else "❌"
    print(f"\n{status} {desc}")
    print(f"   Input: {range_str} (file_size={file_size})")
    print(f"   Expected: start={expected[0]}, end={expected[1]}, length={expected[2]}")
    print(f"   Got:      start={result[0]}, end={result[1]}, length={result[2]}")
    
    if not passed:
        all_passed = False

print("\n" + "=" * 70)
if all_passed:
    print("✅ All tests passed! Range parsing is correct.")
    exit(0)
else:
    print("❌ Some tests failed!")
    exit(1)
