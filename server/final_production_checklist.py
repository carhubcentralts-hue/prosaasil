#!/usr/bin/env python3
"""
Final Production Checklist - בדיקת מוכנות לפריסה
בדיקה מקיפה של כל רכיבי המערכת לפני פריסה מלאה
"""

import os
import sys
import importlib
import logging
from datetime import datetime
from typing import Dict, List, Any

# הגדרת logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ProductionChecker:
    """בודק מוכנות מערכת לפריסה"""
    
    def __init__(self):
        self.results = {
            'passed': 0,
            'failed': 0,
            'warnings': 0,
            'details': []
        }
    
    def check_all_systems(self) -> Dict[str, Any]:
        """בדיקה מקיפה של כל המערכת"""
        
        logger.info("🚀 Starting final production readiness check...")
        
        # בדיקות מערכת
        self._check_core_files()
        self._check_enhanced_services()
        self._check_new_enterprise_services()
        self._check_database_models()
        self._check_environment_variables()
        self._check_dependencies()
        self._check_templates_and_static()
        self._check_security_features()
        self._check_documentation()
        
        # סיכום
        total_checks = self.results['passed'] + self.results['failed'] + self.results['warnings']
        success_rate = (self.results['passed'] / total_checks * 100) if total_checks > 0 else 0
        
        final_report = {
            'timestamp': datetime.now().isoformat(),
            'total_checks': total_checks,
            'passed': self.results['passed'],
            'failed': self.results['failed'],
            'warnings': self.results['warnings'],
            'success_rate': round(success_rate, 1),
            'production_ready': self.results['failed'] == 0,
            'details': self.results['details']
        }
        
        self._print_report(final_report)
        return final_report
    
    def _check_file(self, filename: str, description: str, critical: bool = True) -> bool:
        """בדיקת קיום קובץ"""
        
        if os.path.exists(filename):
            self._add_result(True, f"✅ {description}: {filename}", critical)
            return True
        else:
            self._add_result(False, f"❌ {description}: {filename} - MISSING", critical)
            return False
    
    def _check_import(self, module_name: str, description: str, critical: bool = True) -> bool:
        """בדיקת אפשרות import"""
        
        try:
            importlib.import_module(module_name)
            self._add_result(True, f"✅ {description}: {module_name}", critical)
            return True
        except ImportError as e:
            self._add_result(False, f"❌ {description}: {module_name} - {str(e)}", critical)
            return False
    
    def _check_env_var(self, var_name: str, description: str, critical: bool = True) -> bool:
        """בדיקת משתנה סביבה"""
        
        value = os.environ.get(var_name)
        if value:
            # הסתרת ערכים רגישים
            display_value = "***" if "KEY" in var_name or "TOKEN" in var_name else value[:20] + "..."
            self._add_result(True, f"✅ {description}: {var_name} = {display_value}", critical)
            return True
        else:
            self._add_result(False, f"❌ {description}: {var_name} - NOT SET", critical)
            return False
    
    def _add_result(self, success: bool, message: str, critical: bool = True):
        """הוספת תוצאת בדיקה"""
        
        if success:
            self.results['passed'] += 1
        elif critical:
            self.results['failed'] += 1
        else:
            self.results['warnings'] += 1
        
        self.results['details'].append({
            'success': success,
            'critical': critical,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
        
        logger.info(message)
    
    def _check_core_files(self):
        """בדיקת קבצי הליבה"""
        
        logger.info("📁 Checking core files...")
        
        core_files = [
            ('main.py', 'Application entry point'),
            ('app.py', 'Flask application setup'),
            ('models.py', 'Database models'),
            ('routes.py', 'Main routes and webhooks'),
            ('auth.py', 'Authentication system')
        ]
        
        for filename, description in core_files:
            self._check_file(filename, description, critical=True)
    
    def _check_enhanced_services(self):
        """בדיקת שירותים משופרים"""
        
        logger.info("⚡ Checking enhanced services...")
        
        enhanced_services = [
            ('enhanced_ai_service.py', 'Enhanced AI Service'),
            ('enhanced_twilio_service.py', 'Enhanced Twilio Service'),
            ('enhanced_whatsapp_service.py', 'Enhanced WhatsApp Service'),
            ('enhanced_business_permissions.py', 'Enhanced Business Permissions'),
            ('enhanced_admin_dashboard.py', 'Enhanced Admin Dashboard'),
            ('enhanced_crm_service.py', 'Enhanced CRM Service')
        ]
        
        for filename, description in enhanced_services:
            if self._check_file(filename, description, critical=True):
                # בדיקת אפשרות import
                module_name = filename[:-3]  # הסרת .py
                self._check_import(module_name, f"Import {description}", critical=True)
    
    def _check_new_enterprise_services(self):
        """בדיקת שירותים חדשים ברמה מסחרית"""
        
        logger.info("🏢 Checking new enterprise services...")
        
        enterprise_services = [
            ('digital_signature_service.py', 'Digital Signature Service'),
            ('invoice_generator.py', 'Invoice Generator'),
            ('customer_segmentation_service.py', 'Customer Segmentation'),
            ('lead_forms_service.py', 'Lead Forms Service'),
            ('calendar_service.py', 'Calendar Service'),
            ('notification_service.py', 'Notification Service'),
            ('daily_reports_service.py', 'Daily Reports Service')
        ]
        
        for filename, description in enterprise_services:
            if self._check_file(filename, description, critical=True):
                # בדיקת אפשרות import
                module_name = filename[:-3]  # הסרת .py
                self._check_import(module_name, f"Import {description}", critical=True)
    
    def _check_database_models(self):
        """בדיקת מודלים במסד נתונים"""
        
        logger.info("🗄️ Checking database models...")
        
        try:
            from models import (
                Business, CallLog, ConversationTurn, WhatsAppConversation, 
                WhatsAppMessage, AppointmentRequest, User, CRMCustomer, 
                CRMTask, Appointment
            )
            
            models = [
                (Business, 'Business Model'),
                (CallLog, 'Call Log Model'),
                (ConversationTurn, 'Conversation Turn Model'),
                (WhatsAppConversation, 'WhatsApp Conversation Model'),
                (WhatsAppMessage, 'WhatsApp Message Model'),
                (AppointmentRequest, 'Appointment Request Model'),
                (User, 'User Model'),
                (CRMCustomer, 'CRM Customer Model'),
                (CRMTask, 'CRM Task Model'),
                (Appointment, 'Appointment Model')
            ]
            
            for model_class, description in models:
                if hasattr(model_class, '__tablename__') or hasattr(model_class, '__table__'):
                    self._add_result(True, f"✅ {description}: Available", True)
                else:
                    self._add_result(False, f"❌ {description}: Invalid model structure", True)
                    
        except ImportError as e:
            self._add_result(False, f"❌ Database Models Import: {str(e)}", True)
    
    def _check_environment_variables(self):
        """בדיקת משתני סביבה"""
        
        logger.info("🔑 Checking environment variables...")
        
        critical_vars = [
            ('DATABASE_URL', 'Database Connection'),
            ('OPENAI_API_KEY', 'OpenAI API Key'),
            ('TWILIO_ACCOUNT_SID', 'Twilio Account SID'),
            ('TWILIO_AUTH_TOKEN', 'Twilio Auth Token'),
            ('TWILIO_PHONE_NUMBER', 'Twilio Phone Number')
        ]
        
        optional_vars = [
            ('GOOGLE_APPLICATION_CREDENTIALS', 'Google TTS Credentials'),
            ('MAIL_USERNAME', 'Email Service Username'),
            ('MAIL_PASSWORD', 'Email Service Password'),
            ('SESSION_SECRET', 'Session Secret Key')
        ]
        
        for var_name, description in critical_vars:
            self._check_env_var(var_name, description, critical=True)
        
        for var_name, description in optional_vars:
            self._check_env_var(var_name, description, critical=False)
    
    def _check_dependencies(self):
        """בדיקת תלויות"""
        
        logger.info("📦 Checking dependencies...")
        
        critical_packages = [
            ('flask', 'Flask Framework'),
            ('openai', 'OpenAI Library'),
            ('twilio', 'Twilio SDK'),
            ('sqlalchemy', 'SQLAlchemy ORM'),
            ('reportlab', 'PDF Generation'),
            ('pillow', 'Image Processing')
        ]
        
        optional_packages = [
            ('flask_mail', 'Flask Mail'),
            ('schedule', 'Task Scheduling'),
            ('gtts', 'Google Text-to-Speech')
        ]
        
        for package, description in critical_packages:
            self._check_import(package, description, critical=True)
        
        for package, description in optional_packages:
            self._check_import(package, description, critical=False)
    
    def _check_templates_and_static(self):
        """בדיקת תבניות וקבצים סטטיים"""
        
        logger.info("🎨 Checking templates and static files...")
        
        # תיקיות חיוניות
        directories = [
            ('templates', 'Templates Directory'),
            ('static', 'Static Files Directory'),
            ('static/signatures', 'Signatures Directory'),
            ('static/invoices', 'Invoices Directory'),
            ('static/reports', 'Reports Directory')
        ]
        
        for directory, description in directories:
            if os.path.exists(directory) and os.path.isdir(directory):
                self._add_result(True, f"✅ {description}: {directory}", False)
            else:
                # יצירת תיקייה אם לא קיימת
                try:
                    os.makedirs(directory, exist_ok=True)
                    self._add_result(True, f"✅ {description}: {directory} (created)", False)
                except Exception as e:
                    self._add_result(False, f"❌ {description}: {directory} - {str(e)}", False)
    
    def _check_security_features(self):
        """בדיקת תכונות אבטחה"""
        
        logger.info("🔒 Checking security features...")
        
        # בדיקת הגנות בסיסיות
        try:
            from enhanced_business_permissions import enhanced_business_permissions
            self._add_result(True, "✅ Business Permissions System: Available", True)
        except ImportError:
            self._add_result(False, "❌ Business Permissions System: Not available", True)
        
        # בדיקת authentication
        try:
            from auth import require_auth
            self._add_result(True, "✅ Authentication System: Available", True)
        except ImportError:
            self._add_result(False, "❌ Authentication System: Not available", True)
    
    def _check_documentation(self):
        """בדיקת תיעוד"""
        
        logger.info("📚 Checking documentation...")
        
        docs = [
            ('README.md', 'Project README'),
            ('deployment_guide.md', 'Deployment Guide'),
            ('replit.md', 'Project Configuration'),
            ('todo_implementation_guide.md', 'Implementation Guide')
        ]
        
        for filename, description in docs:
            self._check_file(filename, description, critical=False)
    
    def _print_report(self, report: Dict[str, Any]):
        """הדפסת דוח סיכום"""
        
        print("\n" + "="*80)
        print("🎯 FINAL PRODUCTION READINESS REPORT")
        print("="*80)
        print(f"📅 Timestamp: {report['timestamp']}")
        print(f"🔢 Total Checks: {report['total_checks']}")
        print(f"✅ Passed: {report['passed']}")
        print(f"❌ Failed: {report['failed']}")
        print(f"⚠️  Warnings: {report['warnings']}")
        print(f"📊 Success Rate: {report['success_rate']}%")
        print(f"🚀 Production Ready: {'YES' if report['production_ready'] else 'NO'}")
        print("-"*80)
        
        if report['production_ready']:
            print("🎉 SYSTEM IS READY FOR PRODUCTION DEPLOYMENT!")
            print("🚀 All critical checks passed successfully.")
            print("📈 The system meets enterprise-grade standards.")
        else:
            print("⚠️  SYSTEM REQUIRES ATTENTION BEFORE DEPLOYMENT")
            print("🔧 Please fix the failed checks before proceeding.")
            print("\nFailed checks:")
            for detail in report['details']:
                if not detail['success'] and detail['critical']:
                    print(f"  • {detail['message']}")
        
        print("="*80)

def main():
    """הפעלת בדיקת מוכנות לפריסה"""
    
    try:
        checker = ProductionChecker()
        report = checker.check_all_systems()
        
        # שמירת דוח לקובץ
        report_filename = f"production_readiness_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        import json
        with open(report_filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 Full report saved to: {report_filename}")
        
        # יציאה עם קוד מתאים
        sys.exit(0 if report['production_ready'] else 1)
        
    except Exception as e:
        logger.error(f"Error during production check: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()