#!/usr/bin/env python3
"""
CSRF Exemptions Audit Script

This script analyzes all @csrf.exempt usages in the codebase and categorizes them.
It helps identify which exemptions are legitimate (webhooks, internal APIs with secret auth)
and which should be removed (internal CRUD operations).
"""

import os
import re
import sys
from pathlib import Path

# Color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Patterns for legitimate exemptions
WEBHOOK_PATTERNS = [
    'webhook', 'twilio', 'whatsapp', 'baileys', 'n8n', 
    'status_callback', 'inbound', 'incoming', 'external'
]

INTERNAL_SECRET_PATTERNS = [
    'internal_secret', 'x-internal-token', 'internal_token',
    'authentication_required', 'validate_internal'
]

def check_endpoint_category(file_path, line_num, function_name, decorator_context):
    """Determine if a CSRF exemption is legitimate"""
    file_content = Path(file_path).read_text()
    
    # Extract the function to analyze
    lines = file_content.split('\n')
    func_start = line_num
    func_code = []
    
    # Get function code (next ~50 lines)
    for i in range(func_start, min(func_start + 50, len(lines))):
        func_code.append(lines[i].lower())
        if i > func_start and lines[i].strip().startswith('def '):
            break
    
    func_text = '\n'.join(func_code)
    
    # Check for webhook patterns
    for pattern in WEBHOOK_PATTERNS:
        if pattern in func_text or pattern in file_path.lower():
            return 'webhook', f"Contains '{pattern}'"
    
    # Check for internal secret authentication
    for pattern in INTERNAL_SECRET_PATTERNS:
        if pattern in func_text:
            return 'internal_secret', f"Uses '{pattern}'"
    
    # Check for GET-only endpoints (safe from CSRF)
    if '@app.route' in decorator_context or '@bp.route' in decorator_context:
        if "methods=['GET']" in decorator_context or 'methods=["GET"]' in decorator_context:
            return 'get_only', "GET-only endpoint (safe)"
    
    # Check for auth/login endpoints
    if 'login' in function_name.lower() or '/auth/' in func_text:
        return 'auth', "Authentication endpoint"
    
    # Default: Suspicious - needs review
    return 'suspicious', "Internal API - may need CSRF protection"


def analyze_csrf_exemptions(server_path):
    """Find and analyze all CSRF exemptions"""
    
    exemptions = {
        'webhook': [],
        'internal_secret': [],
        'get_only': [],
        'auth': [],
        'suspicious': []
    }
    
    # Find all Python files
    for root, dirs, files in os.walk(server_path):
        # Skip test directories
        if 'test' in root or '__pycache__' in root:
            continue
            
        for file in files:
            if not file.endswith('.py'):
                continue
                
            file_path = os.path.join(root, file)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for i, line in enumerate(lines, 1):
                    if '@csrf.exempt' in line:
                        # Get context (previous and next lines)
                        context_start = max(0, i - 5)
                        context_end = min(len(lines), i + 3)
                        context = ''.join(lines[context_start:context_end])
                        
                        # Find function name
                        func_name = "Unknown"
                        for j in range(i, min(i + 5, len(lines))):
                            if 'def ' in lines[j]:
                                match = re.search(r'def\s+(\w+)', lines[j])
                                if match:
                                    func_name = match.group(1)
                                break
                        
                        # Categorize
                        category, reason = check_endpoint_category(
                            file_path, i, func_name, context
                        )
                        
                        exemptions[category].append({
                            'file': file_path.replace(server_path, 'server'),
                            'line': i,
                            'function': func_name,
                            'reason': reason
                        })
                        
            except Exception as e:
                print(f"Warning: Could not process {file_path}: {e}")
    
    return exemptions


def print_report(exemptions):
    """Print formatted report"""
    print("\n" + "=" * 80)
    print(f"{BLUE}CSRF Exemptions Audit Report{RESET}")
    print("=" * 80 + "\n")
    
    total = sum(len(v) for v in exemptions.values())
    print(f"Total exemptions found: {total}\n")
    
    # Legitimate exemptions
    print(f"\n{GREEN}✅ LEGITIMATE EXEMPTIONS{RESET}")
    print("-" * 80)
    
    for category in ['webhook', 'internal_secret', 'get_only']:
        if exemptions[category]:
            print(f"\n{category.upper().replace('_', ' ')} ({len(exemptions[category])} exemptions):")
            for item in exemptions[category]:
                print(f"  • {item['file']}:{item['line']} - {item['function']}")
                print(f"    Reason: {item['reason']}")
    
    # Auth endpoints
    if exemptions['auth']:
        print(f"\n{YELLOW}⚠️  AUTHENTICATION ENDPOINTS{RESET} ({len(exemptions['auth'])} exemptions)")
        print("These may be legitimate but should be reviewed:")
        print("-" * 80)
        for item in exemptions['auth']:
            print(f"  • {item['file']}:{item['line']} - {item['function']}")
            print(f"    Reason: {item['reason']}")
    
    # Suspicious exemptions
    if exemptions['suspicious']:
        print(f"\n{RED}🚨 SUSPICIOUS EXEMPTIONS{RESET} ({len(exemptions['suspicious'])} exemptions)")
        print("These should be reviewed and potentially removed:")
        print("-" * 80)
        for item in exemptions['suspicious']:
            print(f"  • {item['file']}:{item['line']} - {item['function']}")
            print(f"    Reason: {item['reason']}")
    
    print("\n" + "=" * 80)
    print(f"{BLUE}Recommendation:{RESET}")
    print("  1. Keep webhook and internal_secret exemptions")
    print("  2. Review auth endpoints for proper CSRF handling")
    print("  3. Remove suspicious exemptions from internal CRUD endpoints")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    # Get server path
    script_dir = Path(__file__).parent
    server_path = script_dir.parent / 'server'
    
    if not server_path.exists():
        print(f"Error: Server directory not found at {server_path}")
        sys.exit(1)
    
    print(f"Analyzing CSRF exemptions in {server_path}...")
    
    exemptions = analyze_csrf_exemptions(str(server_path))
    print_report(exemptions)
