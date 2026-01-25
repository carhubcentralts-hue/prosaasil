#!/usr/bin/env python3
"""
Test for Delete Receipts Job Import Fix

This test verifies that:
1. The job file no longer imports non-existent get_db_session
2. The job imports only valid dependencies
3. Error handling returns proper error dict instead of raising
"""

import unittest
import ast
import os


class TestDeleteReceiptsJobImportFix(unittest.TestCase):
    """Test that delete_receipts_job imports are correct"""
    
    def setUp(self):
        self.job_file_path = '/home/runner/work/prosaasil/prosaasil/server/jobs/delete_receipts_job.py'
        with open(self.job_file_path, 'r') as f:
            self.job_code = f.read()
    
    def test_no_get_db_session_import(self):
        """Verify that get_db_session is NOT imported"""
        self.assertNotIn(
            'get_db_session',
            self.job_code,
            "get_db_session should not be imported anywhere in the job file"
        )
    
    def test_valid_python_syntax(self):
        """Verify the file has valid Python syntax"""
        try:
            ast.parse(self.job_code)
        except SyntaxError as e:
            self.fail(f"Job file has syntax errors: {e}")
    
    def test_imports_correct_modules(self):
        """Verify that the job imports the correct modules"""
        # Parse the AST
        tree = ast.parse(self.job_code)
        
        # Find all import statements
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imports.append((node.module, [alias.name for alias in node.names]))
        
        # Check that we import from server.models_sql, not server.db
        models_sql_imports = [names for module, names in imports if module == 'server.models_sql']
        self.assertTrue(
            len(models_sql_imports) > 0,
            "Job should import from server.models_sql"
        )
        
        # Verify we import the necessary classes
        all_names = []
        for names in models_sql_imports:
            all_names.extend(names)
        
        required_imports = ['db', 'BackgroundJob', 'Receipt', 'Attachment']
        for required in required_imports:
            self.assertIn(
                required,
                all_names,
                f"Job should import {required} from server.models_sql"
            )
    
    def test_error_handling_returns_dict(self):
        """Verify that error handling returns a dict instead of raising"""
        # Check for proper error handling in import block
        self.assertIn(
            'return {',
            self.job_code,
            "Error handling should return a dict"
        )
        
        self.assertIn(
            '"success": False',
            self.job_code,
            "Error dict should have success: False"
        )
        
        self.assertIn(
            '"error"',
            self.job_code,
            "Error dict should have error key"
        )
    
    def test_separate_import_error_handling(self):
        """Verify that ImportError is handled separately"""
        self.assertIn(
            'except ImportError as e:',
            self.job_code,
            "ImportError should be caught separately"
        )
    
    def test_print_statements_for_visibility(self):
        """Verify that print statements are added for worker visibility"""
        # Check for print statements in error handling
        self.assertIn(
            'print(f"❌ FATAL IMPORT ERROR:',
            self.job_code,
            "Import errors should be printed for worker visibility"
        )
    
    def test_job_function_exists(self):
        """Verify that the main job function is defined"""
        self.assertIn(
            'def delete_receipts_batch_job(job_id: int):',
            self.job_code,
            "Main job function should be defined"
        )
    
    def test_immediate_logging_exists(self):
        """Verify that job logs immediately when picked"""
        # Check for immediate logging before imports
        self.assertIn(
            '🔨 JOB PICKED:',
            self.job_code,
            "Job should log immediately when picked"
        )
        
        # Verify it happens before the try block
        picked_index = self.job_code.index('🔨 JOB PICKED:')
        try_index = self.job_code.index('try:')
        
        self.assertLess(
            picked_index,
            try_index,
            "JOB PICKED log should happen before try block"
        )


class TestDeleteReceiptsJobStructure(unittest.TestCase):
    """Test the overall structure of the job"""
    
    def setUp(self):
        self.job_file_path = '/home/runner/work/prosaasil/prosaasil/server/jobs/delete_receipts_job.py'
        with open(self.job_file_path, 'r') as f:
            self.job_code = f.read()
    
    def test_has_required_constants(self):
        """Verify required constants are defined"""
        required_constants = [
            'BATCH_SIZE',
            'THROTTLE_MS',
            'MAX_RUNTIME_SECONDS',
            'MAX_BATCH_FAILURES'
        ]
        
        for const in required_constants:
            self.assertIn(
                const,
                self.job_code,
                f"Constant {const} should be defined"
            )
    
    def test_has_cursor_based_pagination(self):
        """Verify cursor-based pagination is implemented"""
        self.assertIn(
            'cursor',
            self.job_code,
            "Job should use cursor for pagination"
        )
        
        self.assertIn(
            'last_id',
            self.job_code,
            "Job should track last_id in cursor"
        )
    
    def test_has_progress_tracking(self):
        """Verify progress tracking is implemented"""
        progress_indicators = [
            'job.processed',
            'job.succeeded',
            'job.failed_count',
            'job.total'
        ]
        
        for indicator in progress_indicators:
            self.assertIn(
                indicator,
                self.job_code,
                f"Progress indicator {indicator} should be present"
            )
    
    def test_has_cancellation_check(self):
        """Verify job can be cancelled"""
        self.assertIn(
            'if job.status == \'cancelled\'',
            self.job_code,
            "Job should check for cancellation"
        )
    
    def test_has_heartbeat_updates(self):
        """Verify heartbeat is updated"""
        self.assertIn(
            'job.heartbeat_at',
            self.job_code,
            "Job should update heartbeat"
        )


if __name__ == '__main__':
    print("=" * 70)
    print("Testing Delete Receipts Job Import Fix")
    print("=" * 70)
    print()
    
    # Run tests
    suite = unittest.TestLoader().loadTestsFromModule(__import__(__name__))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    print()
    print("=" * 70)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print(f"❌ {len(result.failures)} test(s) failed")
        print(f"❌ {len(result.errors)} test(s) had errors")
    print("=" * 70)
    
    exit(0 if result.wasSuccessful() else 1)
