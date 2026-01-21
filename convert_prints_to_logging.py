#!/usr/bin/env python3
"""
Convert print() statements to proper logging in Python files.
This script systematically converts all print() statements to logger methods.
"""
import re
import sys
from pathlib import Path
from typing import List, Tuple

def has_logging_import(content: str) -> bool:
    """Check if file already has logging import"""
    return bool(re.search(r'^import logging\b', content, re.MULTILINE))

def has_logger_definition(content: str) -> bool:
    """Check if file already has logger definition"""
    return bool(re.search(r'^logger\s*=\s*logging\.getLogger', content, re.MULTILINE))

def add_logging_imports(content: str) -> str:
    """Add logging imports and logger definition if not present"""
    lines = content.split('\n')
    
    # Find the position after the docstring and existing imports
    import_insert_idx = 0
    logger_insert_idx = 0
    in_docstring = False
    docstring_char = None
    last_import_idx = 0
    
    for i, line in enumerate(lines):
        stripped = line.strip()
        
        # Handle docstrings
        if not in_docstring:
            if stripped.startswith('"""') or stripped.startswith("'''"):
                in_docstring = True
                docstring_char = '"""' if stripped.startswith('"""') else "'''"
                if stripped.count(docstring_char) >= 2:
                    in_docstring = False
                continue
        else:
            if docstring_char in line:
                in_docstring = False
            continue
        
        # Track imports
        if stripped.startswith('import ') or stripped.startswith('from '):
            last_import_idx = i
        
        # Stop at first non-import, non-comment, non-blank line
        if stripped and not stripped.startswith('#') and not stripped.startswith('import ') and not stripped.startswith('from '):
            import_insert_idx = last_import_idx + 1 if last_import_idx > 0 else i
            logger_insert_idx = import_insert_idx
            break
    
    # Check what we need to add
    has_import = has_logging_import(content)
    has_logger = has_logger_definition(content)
    
    if not has_import and not has_logger:
        # Add both import and logger
        lines.insert(import_insert_idx, 'import logging')
        lines.insert(import_insert_idx + 1, '')
        lines.insert(import_insert_idx + 2, "logger = logging.getLogger(__name__)")
        lines.insert(import_insert_idx + 3, '')
    elif has_import and not has_logger:
        # Add only logger (after imports)
        # Find position after all imports
        for i in range(import_insert_idx, len(lines)):
            stripped = lines[i].strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('import ') and not stripped.startswith('from '):
                lines.insert(i, '')
                lines.insert(i + 1, "logger = logging.getLogger(__name__)")
                lines.insert(i + 2, '')
                break
    
    return '\n'.join(lines)

def convert_print_to_logger(print_statement: str) -> str:
    """Convert a single print() statement to appropriate logger method"""
    
    # Extract the print content
    match = re.match(r'(\s*)print\((.*)\)\s*$', print_statement, re.DOTALL)
    if not match:
        return print_statement
    
    indent = match.group(1)
    args = match.group(2).strip()
    
    # Determine log level based on content
    args_lower = args.lower()
    
    # Check for special markers
    if '# KEEP' in print_statement or '_orig_print' in print_statement:
        return print_statement  # Don't convert
    
    # Determine log level by emoji or keywords (check in order of priority)
    if '❌' in args or 'error' in args_lower or 'failed' in args_lower or 'exception' in args_lower:
        log_method = 'logger.error'
    elif '⚠️' in args or 'warning' in args_lower or 'warn' in args_lower:
        log_method = 'logger.warning'
    elif '✅' in args or '🚀' in args or '✓' in args or 'success' in args_lower or 'starting' in args_lower or 'started' in args_lower or 'completed' in args_lower:
        log_method = 'logger.info'
    elif 'debug' in args_lower or 'trace' in args_lower:
        log_method = 'logger.debug'
    else:
        # Default to info for most cases
        log_method = 'logger.info'
    
    # Build the logger call
    return f'{indent}{log_method}({args})'

def convert_file(filepath: Path) -> Tuple[int, int]:
    """
    Convert all print() statements in a file to logging.
    Returns (total_prints, converted_prints)
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return 0, 0
    
    # Count prints
    total_prints = len(re.findall(r'^\s*print\(', original_content, re.MULTILINE))
    if total_prints == 0:
        return 0, 0
    
    # Add logging imports if needed
    content = add_logging_imports(original_content)
    
    # Convert print statements line by line
    lines = content.split('\n')
    converted_count = 0
    
    for i, line in enumerate(lines):
        # Skip comments and _orig_print
        if re.match(r'^\s*#', line) or '_orig_print' in line or '# KEEP' in line:
            continue
        
        # Check if line has print(
        if re.match(r'^\s*print\(', line):
            # Handle multi-line print statements
            if line.count('(') > line.count(')'):
                # Multi-line print - need to find the end
                full_statement = line
                j = i + 1
                while j < len(lines) and full_statement.count('(') > full_statement.count(')'):
                    full_statement += '\n' + lines[j]
                    j += 1
                
                converted = convert_print_to_logger(full_statement)
                if converted != full_statement:
                    converted_lines = converted.split('\n')
                    for k, conv_line in enumerate(converted_lines):
                        lines[i + k] = conv_line
                    converted_count += 1
            else:
                # Single-line print
                converted = convert_print_to_logger(line)
                if converted != line:
                    lines[i] = converted
                    converted_count += 1
    
    # Write back
    new_content = '\n'.join(lines)
    
    if new_content != original_content:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            return total_prints, converted_count
        except Exception as e:
            print(f"❌ Error writing {filepath}: {e}")
            return total_prints, 0
    
    return total_prints, 0

def main():
    """Main conversion process"""
    # Read file list
    with open('/tmp/files_with_prints.txt', 'r') as f:
        files = [line.strip() for line in f if line.strip()]
    
    print(f"🚀 Starting conversion of {len(files)} files...")
    print()
    
    total_prints = 0
    total_converted = 0
    files_processed = 0
    
    for filepath_str in files:
        filepath = Path(filepath_str)
        if not filepath.exists():
            continue
        
        # Skip test files
        if filepath.name.startswith('test_'):
            continue
        
        prints, converted = convert_file(filepath)
        if prints > 0:
            total_prints += prints
            total_converted += converted
            files_processed += 1
            print(f"✅ {filepath_str}: {converted}/{prints} prints converted")
    
    print()
    print(f"📊 Summary:")
    print(f"   Files processed: {files_processed}")
    print(f"   Total prints found: {total_prints}")
    print(f"   Prints converted: {total_converted}")
    print()

if __name__ == '__main__':
    main()
