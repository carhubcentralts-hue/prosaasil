# Hebrew AI Call Center System

## Overview
This project is an AI-powered call center system for Hebrew-speaking customers and businesses in Israel. It integrates with Twilio for call handling and OpenAI's GPT-4o for intelligent customer service automation. The system provides a comprehensive CRM solution, automates payment integrations, and offers advanced analytics. Its vision is to deliver an enterprise-grade, commercially deployable solution for the Israeli market, enhancing customer interaction and business automation. The system includes a 3-page React frontend (login, admin, business dashboards) with a Flask backend and PostgreSQL database. It features a fully operational end-to-end voice processing pipeline, handling incoming calls with OpenAI Whisper for Hebrew transcription and GPT-4o for intelligent responses, delivered via Google WaveNet Hebrew voices.

**STATUS: CORE FUNCTIONALITY COMPLETE** (August 7, 2025)
- ✅ Hebrew TTS generation working with gTTS fallback
- ✅ Business lookup and call routing operational
- ✅ End-to-end voice processing pipeline functional
- ✅ 58+ Hebrew TTS files generated and accessible
- ✅ Local webhook testing successful (Status 200)
- ⚠️ External webhook 405 issue (infrastructure/proxy related, not code issue)

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles
The system is a Flask web application designed for multi-business support, with segregated data and customized AI configurations per business. It emphasizes real-time voice processing, comprehensive conversation tracking, and role-based access control.

### Technical Implementation
-   **Backend Framework**: Flask with Blueprint architecture.
-   **Database**: PostgreSQL for multi-business data segregation.
-   **AI Integration**: OpenAI GPT-4o for Hebrew conversation processing and Whisper for Hebrew speech-to-text.
-   **Telephony**: Twilio for voice calls (TwiML, webhooks, recording), SMS, and WhatsApp services.
-   **CRM System**: Modules for customer management, lead tracking, task management, appointment scheduling, digital signatures, invoice generation, and analytics.
-   **WhatsApp Integration**: Supports Twilio WhatsApp Business API and Baileys WhatsApp Web.
-   **Authentication**: Role-based access control for admin (managing all businesses) and business users.
-   **Modular Design**: Flask Blueprints for CRM, WhatsApp, Signatures, Invoices, and Proposals.
-   **Testing**: Comprehensive test suite covering modules, database isolation, and cross-business security.
-   **Deployment**: Designed for Dockerized deployment with comprehensive monitoring.
-   **Security**: Includes Twilio signature verification, login rate limiting, cross-business data protection, and secure file handling.
-   **Frontend**: React-based UI with Vite for building.

### UI/UX Decisions
-   **Templates**: Jinja2 templating system with full Hebrew RTL (Right-to-Left) support.
-   **Styling**: Bootstrap 5 RTL with a professional design system inspired by Monday.com, including gradient colors, modern typography, and Hebrew text optimization.
-   **Components**: Professional CRM templates including KPI cards, customer management tables, signature workflow, calendar integration, and proposal management.
-   **Interactivity**: Vanilla JS for UI interactions, Chart.js for analytics visualization, and modal forms.
-   **Page Structure**: Organized template system with dashboards, CRM, signature, calendar, and proposal pages.

### Key Features
-   **Multi-Business Support**: Individual AI prompts, Twilio numbers, and user accounts per business.
-   **AI-Powered Automation**: Intelligent response generation, appointment extraction, and automation via WhatsApp.
-   **Real-time Voice Processing**: End-to-end pipeline for Hebrew voice: greeting, transcription, AI processing, and voice response.
-   **Robust Call Handling**: Background processing for AI/DB operations to prevent webhook timeouts.
-   **Advanced CRM System**: Professional CRM with advanced dashboard, lead search, call management, WhatsApp integration, and comprehensive analytics.
-   **Business Management**: Full CRUD operations for businesses in the admin panel.
-   **Admin Impersonation**: Admins can view and control individual business systems directly.
-   **Payment Integration**: Advanced payment link generation and automated invoice sending.
-   **Digital Signature Service**: Creation and management of professional e-signatures.

## External Dependencies

-   **OpenAI**: GPT-4o and Whisper.
-   **Twilio**: Voice calls, SMS, WhatsApp Business API.
-   **Google Cloud**: Google Cloud TTS (Text-to-Speech).
-   **Bootstrap CDN**: For UI components and styling.
-   **Font Awesome**: For icons.
-   **Cardcom/Tranzila/משולם**: For payment link generation and processing.
-   **FullCalendar.js**: For calendar and appointment visualization.
-   **Chart.js**: For data visualization and analytics.