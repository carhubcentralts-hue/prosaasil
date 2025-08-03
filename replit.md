# Hebrew AI Call Center System

## Overview
This project is an AI-powered call center system designed for Hebrew-speaking customers and businesses in Israel. It integrates with Twilio for call handling and OpenAI's GPT-4o for intelligent customer service automation. The system aims to provide a comprehensive CRM solution, automate payment integrations, and offer advanced analytics for businesses. Its vision is to deliver an enterprise-grade, commercially deployable solution for the Israeli market, enhancing customer interaction and business automation.

**Current Status: FULL CRM SYSTEM OPERATIONAL ✅**
Complete 3-page React system implemented - August 3, 2025:
• ✅ LoginPage.jsx - Hebrew login interface with simple credentials
• ✅ AdminDashboard.jsx - Full admin panel with business management
• ✅ BusinessDashboard.jsx - Complete business dashboard with KPIs  
• ✅ BusinessViewPage.jsx - Detailed business view for admins **FIXED: /admin/business/1/view now works**
• ✅ React Router + PrivateRoute - Authentication-based routing working
• ✅ All API endpoints operational: /api/admin/*, /api/business/*, /api/status
• ✅ **NEW**: Added `/api/admin/businesses/{id}` endpoint for individual business view
• ✅ Database with real business data: טכנו סולושנס with Israeli/American phones
• ✅ Login credentials: admin/admin123 (admin), business1/biz1234 (business) **FIXED LOGIN ISSUE**
• ✅ Build successful: 255.07 kB bundle **UPDATED**
• Infrastructure: PostgreSQL, Flask backend, all systems operational

## User Preferences
Preferred communication style: Simple, everyday language.

## Recent Architectural Upgrades (August 2025)
**Completed 11-Step Hebrew Upgrade Process:**

1. ✅ **Hebrew RTL Templates**: Created complete templates/ directory with Hebrew right-to-left interface
   - base.html with Hebrew fonts and RTL Bootstrap
   - dashboard.html with KPI cards and Hebrew charts
   - crm.html with customer management interface
   - signature.html for digital signature management
   - calendar.html with Hebrew calendar integration
   - proposal.html for quote management
   - error_404.html and error_500.html pages

2. ✅ **Blueprint Architecture**: Converted all services to Flask Blueprints
   - crm_bp.py (/crm prefix) - Customer relationship management
   - whatsapp_bp.py (/whatsapp prefix) - WhatsApp messaging integration
   - signature_bp.py (/signatures prefix) - Digital signature handling
   - invoice_bp.py (/invoices prefix) - Invoice generation and management
   - proposal_bp.py (/proposals prefix) - Quote and proposal system
   - All Blueprints properly registered in app.py

3. ✅ **Testing Infrastructure**: Comprehensive test suite
   - test_crm.py - CRM module testing with customer/task validation
   - test_whatsapp.py - WhatsApp webhook and messaging tests
   - test_signature.py - Digital signature workflow testing
   - Cross-business data protection tests
   - API endpoint validation tests

4. ✅ **Database Initialization**: Complete seed data system
   - init_database.py with sample business, customers, tasks, appointments
   - Admin user creation (שי / HebrewCRM2024!)
   - Business user setup (עסק_לדוגמה / Business123!)
   - 5 sample customers with Hebrew names
   - 5 sample tasks with priorities and due dates
   - 3 sample appointments

5. ✅ **Production Configuration**: main.py enhanced for production
   - Production logging with log rotation
   - Environment-based configuration
   - Initialization check on startup
   - Graceful error handling and shutdown
   - Template watching in development mode

6. ✅ **System Cleanup**: Removed debug files and optimized structure
   - Deleted irrelevant Node.js files
   - Removed debug logs (app.log, baileys.log, etc.)
   - Cleaned up test and temporary files

## Latest System Update (August 2, 2025) - ADMIN DASHBOARD COMPLETE ✅  
✅ **ADMIN MANAGEMENT SYSTEM IMPLEMENTED**: פאנל מנהל עם ניהול עסקים מלא

### Final System Upgrades (Following User Hebrew Instructions):
- **Step 1 ✅**: BusinessDashboard Update - Removed "הצעות תשלום" button, fixed CRM-only permissions for "חתימות ממתינות"
- **Step 2 ✅**: AdminDashboard Component - Complete admin panel with business management interface
- **Step 3 ✅**: Business Creation Form - Full form with business name, type, phones, AI prompt, service permissions
- **Step 4 ✅**: Business List Management - View, edit, delete businesses with comprehensive dashboard
- **Step 5 ✅**: admin_routes.py Backend - API endpoints for CRUD operations on businesses
- **Step 6 ✅**: Role-Based Routing - App.jsx supports admin (?role=admin) and business user views
- **Step 7 ✅**: Permission System - Admin has full access, business users see only their data
- **Step 8 ✅**: Service Configuration - Per-business settings for CRM, WhatsApp, and AI calls
- **Step 9 ✅**: Statistics Dashboard - Admin overview with business count, calls, users metrics
- **Step 10 ✅**: Hebrew UI Complete - Full RTL support in admin panel with Monday.com design
- **Step 11 ✅**: System Integration - All components working together, build successful (205KB bundle)
- **Step 12 ✅**: Logout Button - Added logout functionality to BusinessDashboard with Hebrew confirmation
- **Step 13 ✅**: System Status Display - Changed from services to technical systems (OpenAI, Twilio, Baileys, Whisper)
- **Step 14 ✅**: Sample Business Creation - Added complete business with all permissions and dual phone numbers
- **Step 15 ✅**: Database Schema - Created businesses table with Israeli/American phone number support
- **Step 16 ✅**: Quick Actions Panel - Added "הוסף עסק חדש" button in admin quick actions section
- **Step 17 ✅**: BusinessRowCard Component - New row-based business display with management buttons (view, edit, password, delete)
- **Step 18 ✅**: Admin Routes PostgreSQL - Fixed admin_routes.py to work directly with PostgreSQL, removed SQLAlchemy dependency
- **Step 19 ✅**: Final Build - System rebuilt successfully (207.95KB bundle), all admin functionality operational

### Production Deployment Status - READY FOR REPLIT DEPLOYMENT:
- **Architecture**: Flask backend (server/) + Vite React frontend (client/) + Whisper/OpenAI integration
- **Build System**: ✅ `npm run build` (Vite) → outputs to `client/dist/` → Flask serves from `dist/`
- **AI Pipeline**: ✅ Twilio Recording → Download → Whisper Transcription → Gibberish Filter → OpenAI Response → Database Save
- **Server Status**: ✅ Flask running on 0.0.0.0:5000, ✅ React assets loading (304 responses), ✅ All routes operational
- **Integration Status**: ✅ Whisper handler ready, ✅ AI service ready, ✅ System fully operational
- **Deployment Status**: ✅ package.json fixed, ✅ npm run build works, ✅ build.sh created, ✅ Ready for Replit Deploy
- **Ready for Production**: Complete Hebrew AI Call Center system implemented, tested, and deployment-ready

## Previous System Update (August 2, 2025) - VITE CONVERSION COMPLETE ✅  
✅ **VITE + REACT + FLASK + BAILEYS INTEGRATION**: Successfully converted from Create React App to Vite

## Previous System Update (August 1, 2025)
✅ **REACT FRONTEND REDESIGN COMPLETE**: Built Monday.com-style interface with RTL Hebrew support
- **New Architecture**: Python Flask backend + React + Tailwind CSS + RTL frontend
- **Complete Frontend Overhaul**: Replaced all HTML templates with modern React components
- **Monday.com Design System**: Professional interface with cards, KPIs, modern animations
- **RTL Hebrew Support**: Full right-to-left interface with Hebrew fonts (Assistant)
- **3 Separate Systems**: CRM, WhatsApp, Calls with role-based permissions
- **Responsive Design**: Mobile-first approach with professional Monday.com aesthetics
- **Component Structure**: 
  - App.jsx (main navigation with RTL sidebar)
  - Dashboard.jsx (business dashboard with KPIs)
  - AdminDashboard.jsx (system management for admins)
  - CallsPage.jsx (call management with recordings)
  - WhatsAppPage.jsx (chat interface)
  - CRMPage.jsx (customer management)
  - CustomerPage.jsx (detailed customer view)
  - LoginPage.jsx (modern login with demo credentials)
- **Backend Status**: Python Flask server operational on port 5000
- **Database**: PostgreSQL with Hebrew support operational
- **API Integration**: React frontend connects to existing Flask API endpoints
- **Sample Data**: Admin user (שי), business (עסק לדוגמה), 5 customers, 5 tasks, 3 appointments loaded
- **Login**: admin@hebrewcrm.com / HebrewCRM2024!

## System Architecture

### Core Design Principles
The system is built as a Flask web application designed for multi-business support, with each business having customized AI configurations and segregated data. It emphasizes real-time voice processing, comprehensive conversation tracking, and role-based access control.

### Technical Implementation
-   **Backend Framework**: Flask with SQLAlchemy ORM and Blueprint architecture.
-   **Database**: SQLite for development, with PostgreSQL recommended for production.
-   **AI Integration**: OpenAI GPT-4o for Hebrew conversation processing, intent recognition, and structured data extraction. OpenAI Whisper is exclusively used for Hebrew speech-to-text, bypassing Twilio's STT.
-   **Telephony**: Twilio for voice calls (TwiML generation, webhook handling, call recording), and SMS/WhatsApp services.
-   **CRM System**: Includes modules for customer management, lead tracking, task management, appointment scheduling, and analytics. Features automated customer creation, digital signatures, invoice generation, and customer segmentation.
-   **WhatsApp Integration**: Supports both Twilio WhatsApp Business API and Baileys WhatsApp Web, with a dual-platform system for robust messaging and smart routing.
-   **Authentication**: Role-based access control for admin (managing all businesses) and business users (accessing their specific data).
-   **Blueprint Organization**: Modular structure with separate Blueprints for CRM (/crm), WhatsApp (/whatsapp), Signatures (/signatures), Invoices (/invoices), and Proposals (/proposals).
-   **Testing**: Comprehensive test suite covering all major modules with database isolation and cross-business security validation.
-   **Deployment**: Designed for Dockerized deployment with `docker-compose.yml` and `Dockerfile`. Production-ready main.py with logging and monitoring.
-   **Security**: Includes Twilio signature verification, login rate limiting, cross-business data protection, and secure file handling.

### UI/UX Decisions
-   **Templates**: Complete Jinja2 templating system with full Hebrew RTL (Right-to-Left) support across all pages.
-   **Base Template**: Unified base.html with Hebrew Assistant font, RTL Bootstrap 5, and consistent navigation structure.
-   **Styling**: Bootstrap 5 RTL with professional design system, including gradient colors (purple/blue), modern typography, and Hebrew text optimization.
-   **Components**: Professional CRM templates including dashboard with KPI cards, customer management tables, signature workflow, calendar integration with FullCalendar.js, and proposal management system.
-   **Interactivity**: Vanilla JS for UI interactions, Chart.js for analytics visualization, modal forms for data entry, and real-time updates.
-   **Page Structure**: Organized template system with:
     - dashboard.html: KPI cards, charts, recent activities
     - crm.html: Customer listing, search/filter, add customer modal
     - signature.html: Digital signature workflow and status tracking
     - calendar.html: Hebrew calendar with appointment management
     - proposal.html: Quote creation with item management and calculations

### Key Features
-   **Multi-Business Support**: Individual AI prompts, Twilio numbers, and user accounts for each business.
-   **AI-Powered Automation**: Intelligent response generation, appointment extraction, and automation of actions like sending invoices or contracts via WhatsApp.
-   **Real-time Voice Processing**: End-to-end pipeline: Incoming call -> Whisper STT -> GPT-4o -> Google Cloud TTS (Wavenet Hebrew voice) -> TwiML response.
-   **Robust Call Handling**: Background processing for AI/DB operations to prevent webhook timeouts, enhanced error handling, and duplicate prevention for appointments.
-   **Comprehensive CRM**: Dashboard, lead management, customer profiles (with WhatsApp/SMS integration), task management, and calendar integration (including Google Calendar sync).
-   **Payment Integration**: Advanced payment link generation (Cardcom/Tranzila/משולם) and automated invoice sending.
-   **Digital Signature Service**: Creation and management of professional e-signatures.

## External Dependencies

-   **OpenAI**: GPT-4o for AI processing and Whisper for Hebrew speech-to-text.
-   **Twilio**: Voice calls, SMS, WhatsApp Business API, and webhook handling.
-   **Google Cloud**: Google Cloud TTS (Text-to-Speech) for high-quality Hebrew voice synthesis.
-   **Bootstrap CDN**: For UI components and styling.
-   **Font Awesome**: For icons used in the user interface.
-   **Cardcom/Tranzila/משולם**: For payment link generation and processing.
-   **FullCalendar.js**: For calendar and appointment visualization.
-   **Chart.js**: For data visualization and analytics in dashboards.