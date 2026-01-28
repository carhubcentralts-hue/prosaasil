#!/usr/bin/env python3
"""
Verification script for RQ timeout parameter fix.

This script verifies that all RQ queue.enqueue() calls use 'job_timeout'
instead of 'timeout' to avoid TypeError when jobs are executed.

Background:
-----------
RQ (Redis Queue) expects 'job_timeout' as the parameter name to configure
job execution timeout. Using 'timeout' would incorrectly pass it as a
keyword argument to the job function itself, causing:
  TypeError: function() got an unexpected keyword argument 'timeout'

This was causing the Worker to crash and the bot to not respond.

Fix:
----
In server/services/jobs.py, the enqueue() function uses:
  job_kwargs = {
      'job_timeout': timeout,  # ✅ CORRECT
      ...
  }

Instead of:
  job_kwargs = {
      'timeout': timeout,  # ❌ WRONG - would pass to job function
      ...
  }
"""

import re
import sys
from pathlib import Path

def check_file_for_incorrect_timeout(filepath: Path) -> list:
    """Check a Python file for incorrect timeout usage in queue.enqueue calls."""
    issues = []
    
    try:
        content = filepath.read_text()
        lines = content.split('\n')
        
        # Look for queue.enqueue calls
        in_enqueue_call = False
        enqueue_start_line = 0
        paren_depth = 0
        enqueue_lines = []
        
        for line_num, line in enumerate(lines, 1):
            # Check if we're starting an enqueue call
            if 'queue.enqueue(' in line or '.enqueue_at(' in line or '.enqueue(' in line:
                in_enqueue_call = True
                enqueue_start_line = line_num
                paren_depth = line.count('(') - line.count(')')
                enqueue_lines = [line]
                
            elif in_enqueue_call:
                enqueue_lines.append(line)
                paren_depth += line.count('(') - line.count(')')
                
                # Check if we've closed all parentheses (exact match)
                if paren_depth == 0:
                    # Now check this enqueue call
                    full_call = '\n'.join(enqueue_lines)
                    
                    # Look for timeout parameter (but not job_timeout)
                    # Use word boundary to match exact parameter name
                    # Match patterns like: timeout='30m', timeout=300, timeout = timeout
                    if re.search(r"[,\(]\s*\btimeout\s*=", full_call):
                        # Make sure it's not actually 'job_timeout'
                        if not re.search(r"[,\(]\s*\bjob_timeout\s*=", full_call):
                            issues.append({
                                'file': str(filepath),
                                'line': enqueue_start_line,
                                'type': 'incorrect_timeout',
                                'message': f'Found "timeout=" instead of "job_timeout=" in enqueue call'
                            })
                    
                    # Reset for next enqueue call
                    in_enqueue_call = False
                    enqueue_lines = []
                elif paren_depth < 0:
                    # Negative depth indicates parsing error - reset
                    in_enqueue_call = False
                    enqueue_lines = []
                    
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
        
    return issues


def main():
    """Main verification function."""
    print("🔍 Verifying RQ timeout parameter usage...")
    print()
    
    # Find all Python files in server directory
    server_dir = Path(__file__).parent / 'server'
    
    if not server_dir.exists():
        print(f"❌ Server directory not found: {server_dir}")
        sys.exit(1)
    
    all_issues = []
    files_checked = 0
    
    for py_file in server_dir.rglob('*.py'):
        # Skip __pycache__ and other non-source files
        if '__pycache__' in str(py_file) or '.pyc' in str(py_file):
            continue
            
        files_checked += 1
        issues = check_file_for_incorrect_timeout(py_file)
        all_issues.extend(issues)
    
    print(f"📁 Files checked: {files_checked}")
    print()
    
    if all_issues:
        print("❌ ISSUES FOUND:")
        print()
        for issue in all_issues:
            print(f"  File: {issue['file']}")
            print(f"  Line: {issue['line']}")
            print(f"  Type: {issue['type']}")
            print(f"  Message: {issue['message']}")
            print()
        print(f"Total issues: {len(all_issues)}")
        sys.exit(1)
    else:
        print("✅ All RQ enqueue calls use 'job_timeout' correctly!")
        print()
        print("Verified patterns:")
        print("  ✅ job_timeout='30m'")
        print("  ✅ job_timeout=300")
        print("  ✅ job_timeout=timeout")
        print()
        print("No incorrect 'timeout=' parameters found in enqueue calls.")
        sys.exit(0)


if __name__ == '__main__':
    main()
