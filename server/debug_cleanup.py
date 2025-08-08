#!/usr/bin/env python3
"""
AgentLocator v42 - Debug Cleanup Utility
מסיר כל הדפסות debug ו-console.log מהקוד
"""

import os
import re
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

class DebugCleaner:
    """מנקה קוד debug מקבצי הפרוייקט"""
    
    def __init__(self, root_dir: str = "."):
        self.root_dir = root_dir
        self.cleaned_files = []
        self.python_debug_patterns = [
            r'print\s*\([^)]*debug[^)]*\)',  # print statements with 'debug'
            r'print\s*\([^)]*DEBUG[^)]*\)',  # print statements with 'DEBUG'  
            r'logger\.debug\s*\([^)]*\)',     # logger.debug calls
            r'console\.log\s*\([^)]*\)',     # console.log in Python strings
            r'#\s*DEBUG:.*',                 # DEBUG comments
            r'#\s*FIXME:.*',                 # FIXME comments
            r'#\s*TODO:.*debug.*',           # TODO debug comments
        ]
        
        self.js_debug_patterns = [
            r'console\.log\s*\([^)]*\)',     # console.log calls
            r'console\.debug\s*\([^)]*\)',   # console.debug calls
            r'console\.warn\s*\([^)]*debug[^)]*\)', # console.warn with debug
            r'console\.error\s*\([^)]*debug[^)]*\)', # console.error with debug
            r'//\s*DEBUG:.*',                # DEBUG comments
            r'//\s*FIXME:.*',                # FIXME comments
            r'/\*\s*DEBUG.*?\*/',            # Multi-line DEBUG comments
        ]

    def clean_python_file(self, filepath: str) -> Tuple[int, int]:
        """ניקוי קובץ Python מ-debug prints"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_lines = len(content.split('\n'))
            modified_content = content
            removals = 0
            
            # Remove debug patterns
            for pattern in self.python_debug_patterns:
                matches = re.findall(pattern, modified_content, re.IGNORECASE | re.MULTILINE)
                removals += len(matches)
                modified_content = re.sub(pattern, '', modified_content, flags=re.IGNORECASE | re.MULTILINE)
            
            # Clean up empty lines (max 2 consecutive)
            modified_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', modified_content)
            
            # Write back if changes made
            if removals > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                new_lines = len(modified_content.split('\n'))
                return removals, original_lines - new_lines
            
            return 0, 0
            
        except Exception as e:
            logger.error(f"Error cleaning Python file {filepath}: {e}")
            return 0, 0

    def clean_js_file(self, filepath: str) -> Tuple[int, int]:
        """ניקוי קובץ JavaScript מ-console.log"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_lines = len(content.split('\n'))
            modified_content = content
            removals = 0
            
            # Remove debug patterns but keep important logs
            for pattern in self.js_debug_patterns:
                # Skip console.error for actual errors
                if 'console.error' in pattern:
                    # Only remove debug-related console.error
                    matches = re.findall(pattern, modified_content, re.IGNORECASE | re.MULTILINE)
                else:
                    matches = re.findall(pattern, modified_content, re.IGNORECASE | re.MULTILINE)
                
                removals += len(matches)
                modified_content = re.sub(pattern, '', modified_content, flags=re.IGNORECASE | re.MULTILINE)
            
            # Clean up empty lines
            modified_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', modified_content)
            
            if removals > 0:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                new_lines = len(modified_content.split('\n'))
                return removals, original_lines - new_lines
            
            return 0, 0
            
        except Exception as e:
            logger.error(f"Error cleaning JS file {filepath}: {e}")
            return 0, 0

    def scan_and_clean(self) -> dict:
        """סריקה וניקוי של כל הפרוייקט"""
        stats = {
            'files_scanned': 0,
            'files_cleaned': 0,
            'debug_statements_removed': 0,
            'lines_removed': 0,
            'cleaned_files': []
        }
        
        # Python files
        for root, dirs, files in os.walk(self.root_dir):
            # Skip common directories to ignore
            dirs[:] = [d for d in dirs if d not in {'.git', '__pycache__', 'node_modules', '.pytest_cache', 'venv', 'env'}]
            
            for file in files:
                filepath = os.path.join(root, file)
                relative_path = os.path.relpath(filepath, self.root_dir)
                
                # Python files
                if file.endswith('.py'):
                    stats['files_scanned'] += 1
                    removals, lines_removed = self.clean_python_file(filepath)
                    
                    if removals > 0:
                        stats['files_cleaned'] += 1
                        stats['debug_statements_removed'] += removals
                        stats['lines_removed'] += lines_removed
                        stats['cleaned_files'].append({
                            'file': relative_path,
                            'type': 'python',
                            'removals': removals,
                            'lines_removed': lines_removed
                        })
                
                # JavaScript/TypeScript files  
                elif file.endswith(('.js', '.jsx', '.ts', '.tsx')):
                    stats['files_scanned'] += 1
                    removals, lines_removed = self.clean_js_file(filepath)
                    
                    if removals > 0:
                        stats['files_cleaned'] += 1
                        stats['debug_statements_removed'] += removals
                        stats['lines_removed'] += lines_removed
                        stats['cleaned_files'].append({
                            'file': relative_path,
                            'type': 'javascript',
                            'removals': removals,
                            'lines_removed': lines_removed
                        })
        
        return stats

    def generate_report(self, stats: dict) -> str:
        """יוצר דוח ניקוי"""
        report = [
            "🧹 AgentLocator v42 - Debug Cleanup Report",
            "=" * 50,
            f"📁 Files Scanned: {stats['files_scanned']}",
            f"✅ Files Cleaned: {stats['files_cleaned']}",
            f"🗑️ Debug Statements Removed: {stats['debug_statements_removed']}",
            f"📝 Lines Removed: {stats['lines_removed']}",
            ""
        ]
        
        if stats['cleaned_files']:
            report.append("📋 Cleaned Files:")
            report.append("-" * 20)
            
            for file_info in stats['cleaned_files']:
                report.append(f"  • {file_info['file']} ({file_info['type']})")
                report.append(f"    - Removals: {file_info['removals']}")
                report.append(f"    - Lines removed: {file_info['lines_removed']}")
                report.append("")
        else:
            report.append("✨ No debug statements found - code is already clean!")
        
        return "\n".join(report)

def main():
    """הפעלת ניקוי הקוד"""

    cleaner = DebugCleaner()
    stats = cleaner.scan_and_clean()
    
    # Generate and display report
    report = cleaner.generate_report(stats)
    print(report)
    
    # Save report to file
    with open('cleanup_report.txt', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n📊 Report saved to: cleanup_report.txt")
    
    if stats['files_cleaned'] > 0:
        print(f"✅ Cleanup complete! {stats['files_cleaned']} files were cleaned.")
    else:

if __name__ == '__main__':
    main()