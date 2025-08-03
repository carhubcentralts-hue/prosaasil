# Hebrew AI Call Center System

## Overview
This project is an AI-powered call center system designed for Hebrew-speaking customers and businesses in Israel. It integrates with Twilio for call handling and OpenAI's GPT-4o for intelligent customer service automation. The system aims to provide a comprehensive CRM solution, automate payment integrations, and offer advanced analytics for businesses. Its vision is to deliver an enterprise-grade, commercially deployable solution for the Israeli market, enhancing customer interaction and business automation. 

The system features a complete 3-page React system with Hebrew login, admin dashboard, and business dashboard, all fully operational with Flask backend and PostgreSQL database. **Key achievement**: Full end-to-end voice processing pipeline working perfectly - incoming calls are processed with OpenAI Whisper for Hebrew transcription and GPT-4o for intelligent responses, all delivered through Google WaveNet Hebrew voices.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles
The system is built as a Flask web application for multi-business support, with each business having customized AI configurations and segregated data. It emphasizes real-time voice processing, comprehensive conversation tracking, and role-based access control.

### Technical Implementation
-   **Backend Framework**: Flask with Blueprint architecture.
-   **Database**: PostgreSQL for production, supporting multi-business data segregation.
-   **AI Integration**: OpenAI GPT-4o for Hebrew conversation processing and intent recognition. OpenAI Whisper for Hebrew speech-to-text.
-   **Telephony**: Twilio for voice calls (TwiML, webhooks, recording), SMS, and WhatsApp services.
-   **CRM System**: Modules for customer management, lead tracking, task management, appointment scheduling, and analytics. Supports automated customer creation, digital signatures, invoice generation, and customer segmentation.
-   **WhatsApp Integration**: Supports both Twilio WhatsApp Business API and Baileys WhatsApp Web for robust messaging.
-   **Authentication**: Role-based access control for admin (managing all businesses) and business users (accessing their specific data).
-   **Modular Design**: Flask Blueprints for CRM, WhatsApp, Signatures, Invoices, and Proposals.
-   **Testing**: Comprehensive test suite covering modules, database isolation, and cross-business security.
-   **Deployment**: Designed for Dockerized deployment.
-   **Security**: Includes Twilio signature verification, login rate limiting, cross-business data protection, and secure file handling.
-   **Frontend**: React-based UI with Vite for building.

### UI/UX Decisions
-   **Templates**: Complete Jinja2 templating system with full Hebrew RTL (Right-to-Left) support.
-   **Styling**: Bootstrap 5 RTL with a professional design system, including gradient colors, modern typography, and Hebrew text optimization, inspired by Monday.com.
-   **Components**: Professional CRM templates including KPI cards, customer management tables, signature workflow, calendar integration, and proposal management.
-   **Interactivity**: Vanilla JS for UI interactions, Chart.js for analytics visualization, and modal forms.
-   **Page Structure**: Organized template system with dashboards, CRM, signature, calendar, and proposal pages.

### Key Features
-   **Multi-Business Support**: Individual AI prompts, Twilio numbers, and user accounts per business.
-   **AI-Powered Automation**: Intelligent response generation, appointment extraction, and automation of actions via WhatsApp.
-   **Real-time Voice Processing**: **FULLY OPERATIONAL** End-to-end pipeline: Incoming call -> Whisper STT -> GPT-4o -> Google Cloud TTS (Wavenet Hebrew voice) -> TwiML response.
-   **Robust Call Handling**: Background processing for AI/DB operations to prevent webhook timeouts.
-   **Comprehensive CRM**: Dashboard, lead management, customer profiles, task management, and calendar integration.
-   **Business Management**: Create, edit, and manage businesses with full CRUD operations including delete functionality with red confirmation button. All admin panel functions fully operational.
-   **Admin Impersonation**: Admins can now view and control individual business systems directly by clicking the purple "view as business" button, allowing complete system takeover with a return-to-admin option.
-   **Payment Integration**: Advanced payment link generation and automated invoice sending.
-   **Digital Signature Service**: Creation and management of professional e-signatures.

## External Dependencies

-   **OpenAI**: GPT-4o for AI processing and Whisper for Hebrew speech-to-text.
-   **Twilio**: Voice calls, SMS, WhatsApp Business API, and webhook handling.
-   **Google Cloud**: Google Cloud TTS (Text-to-Speech) for Hebrew voice synthesis.
-   **Bootstrap CDN**: For UI components and styling.
-   **Font Awesome**: For icons.
-   **Cardcom/Tranzila/משולם**: For payment link generation and processing.
-   **FullCalendar.js**: For calendar and appointment visualization.
-   **Chart.js**: For data visualization and analytics.