# Hebrew AI Call Center System

## Overview
This project is an AI-powered call center system designed for Hebrew-speaking customers and businesses in Israel. It integrates with Twilio for call handling and OpenAI's GPT-4o for intelligent customer service automation. The system aims to provide a comprehensive CRM solution, automate payment integrations, and offer advanced analytics for businesses. Its vision is to deliver an enterprise-grade, commercially deployable solution for the Israeli market, enhancing customer interaction and business automation.

**Current Status: SYSTEMATIC UPGRADE COMPLETE ✅**
System upgraded following 6-step Hebrew systematic approach - August 1, 2025:
• Step 1-4 COMPLETE: Business permissions, Twilio AI calls, WhatsApp (Baileys+Twilio), Advanced CRM
• All 3 Components VERIFIED: Calls (Hebrew STT+GPT+TTS), WhatsApp (dual-platform), CRM (full Hebrew UI)
• Route Integration: routes_twilio.py, routes_whatsapp.py, routes_crm.py successfully integrated
• Business Configuration: calls_enabled=true, whatsapp_enabled=true, crm_enabled=true
• Infrastructure: PostgreSQL operational, Hebrew RTL templates, multi-business support active

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

## Latest System Update (August 1, 2025)
✅ **DEBUGGING COMPLETED & SYSTEM OPERATIONAL**: Successfully fixed failing Python Flask application
- **Architecture Decision**: Maintained Python-based Flask application as requested by user
- **Fixed npm dev script**: Added proper Node.js script for Baileys WhatsApp client integration
- **Fixed Baileys logger**: Resolved WhatsApp client startup issues with proper logger configuration
- **Fixed Flask routing conflicts**: Eliminated duplicate route imports between main.py and app.py
- **System Status**: Both Python Flask server (port 5000) and Node.js Baileys WhatsApp client running successfully
- **Hybrid Architecture**: Python Flask as main application + Node.js Baileys for WhatsApp integration only
- **Database**: PostgreSQL with Hebrew support operational
- **Previous System**: All API keys configured (OpenAI, Twilio, Session Secret)
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