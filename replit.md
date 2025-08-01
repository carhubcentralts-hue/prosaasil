# Hebrew AI Call Center System

## Overview
This project is an AI-powered call center system designed for Hebrew-speaking customers and businesses in Israel. It integrates with Twilio for call handling and OpenAI's GPT-4o for intelligent customer service automation. The system aims to provide a comprehensive CRM solution, automate payment integrations, and offer advanced analytics for businesses. Its vision is to deliver an enterprise-grade, commercially deployable solution for the Israeli market, enhancing customer interaction and business automation.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Principles
The system is built as a Flask web application designed for multi-business support, with each business having customized AI configurations and segregated data. It emphasizes real-time voice processing, comprehensive conversation tracking, and role-based access control.

### Technical Implementation
-   **Backend Framework**: Flask with SQLAlchemy ORM.
-   **Database**: SQLite for development, with PostgreSQL recommended for production.
-   **AI Integration**: OpenAI GPT-4o for Hebrew conversation processing, intent recognition, and structured data extraction. OpenAI Whisper is exclusively used for Hebrew speech-to-text, bypassing Twilio's STT.
-   **Telephony**: Twilio for voice calls (TwiML generation, webhook handling, call recording), and SMS/WhatsApp services.
-   **CRM System**: Includes modules for customer management, lead tracking, task management, appointment scheduling, and analytics. Features automated customer creation, digital signatures, invoice generation, and customer segmentation.
-   **WhatsApp Integration**: Supports both Twilio WhatsApp Business API and Baileys WhatsApp Web, with a dual-platform system for robust messaging and smart routing.
-   **Authentication**: Role-based access control for admin (managing all businesses) and business users (accessing their specific data).
-   **Deployment**: Designed for Dockerized deployment with `docker-compose.yml` and `Dockerfile`. Proxy fix middleware is configured for reverse proxy environments.
-   **Security**: Includes Twilio signature verification, login rate limiting, and cross-business data protection.

### UI/UX Decisions
-   **Templates**: Jinja2 templating with full Hebrew RTL (Right-to-Left) support.
-   **Styling**: Bootstrap 5 with a professional, unified design system, including a specific color palette (navy, teal, soft green accents) and modern typography (Inter/Assistant fonts).
-   **Components**: Features professional CRM base templates, collapsible sidebars, KPI cards, clean tables, and consistent iconography (Font Awesome).
-   **Interactivity**: Vanilla JS for UI interactions, auto-refreshing dashboards, and visual feedback for user actions.
-   **CRM Dashboard Design**: Fireberry/Monday.com-style interface with a professional sidebar, KPI cards, and clear data visualization. Includes advanced analytics with Chart.js and interactive elements like floating action buttons and modal forms.

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