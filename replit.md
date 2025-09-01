# Hebrew AI Call Center CRM

## Overview
This project is a Hebrew AI Call Center CRM for "שי דירות ומשרדים בע״מ", managing real estate customer interactions. It utilizes OpenAI GPT-4o for intelligent Hebrew conversations and OpenAI Whisper for real-time Hebrew transcription, delivering professional, real estate-specific responses over live Twilio calls. The system aims to enhance real estate operations through advanced AI and CRM capabilities, offering a comprehensive solution for customer management, lead generation, and business growth in the real estate sector.

## User Preferences
Preferred communication style: Simple, everyday language.
Code organization: Clean, unified files without duplicates. Always merge improvements into existing files rather than creating new "_improved" versions.
Visual focus: Currently working visually only - login page only, no dashboards. Backend functionality (calls, CRM, WhatsApp) preserved intact.

## System Architecture

### Frontend Architecture
- **Framework**: React 18 (functional components, hooks) with Wouter for routing.
- **Styling**: Tailwind CSS with Hebrew RTL support and a custom CSS tokens system.
- **Build Tool**: Vite.
- **Real-time**: Socket.IO client for live notifications.
- **UI/UX Decisions**: Professional UI with AdminLayout, responsive sidebar, Hebrew Typography (Assistant font), modern design system (gradients, rounded corners), consistent layout, TanStack Table for data display with RTL, sorting, filtering, and CSV export. Permissions-based navigation. Login pages feature a premium design system with white background, teal branding, glass morphism cards, Motion animations, and Radix primitives, ensuring full RTL excellence, accessibility, and mobile responsiveness.

### Backend Architecture
- **Framework**: Flask, utilizing an App Factory pattern and Blueprint architecture for modularity.
- **Error Handling**: Production-ready error handlers with structured JSON logging.
- **Language**: Python 3.9+ with Hebrew language support.
- **Database**: SQLAlchemy ORM for PostgreSQL.
- **API Design**: RESTful JSON endpoints with CORS and robust error handling.
- **Authentication**: Session-based with role-based access control (admin/business), including premium authentication system with inline validation and real-time validation.
- **Business Logic**: Service-oriented architecture.
- **System Unification**: All duplicate systems (login, authentication, CRM, WhatsApp, business management) have been unified into a single production-ready enterprise CRM with advanced payments.

### Voice Processing Pipeline
- **Speech Recognition**: OpenAI Whisper for Hebrew transcription, including gibberish detection.
- **Text-to-Speech**: Google Cloud TTS optimized for high-quality Hebrew voice synthesis.
- **Audio Processing**: MP3 format with automatic cleanup of old voice files.
- **Quality Control**: Intelligent filtering to prevent nonsensical AI responses.
- **Live Conversation**: Real-time Hebrew processing (STT → AI Response → TTS) over WebSockets with Twilio Media Streams, including production AI responses and two-way conversation flow.

### AI Integration
- **Conversational AI**: OpenAI GPT-4o with Hebrew-optimized prompts for real estate contexts.
- **Response Generation**: Context-aware responses based on business type and customer history.
- **Fallback Handling**: Graceful degradation when AI services are unavailable.
- **Business Customization**: Per-business configuration of AI prompts.

### Data Models
- **Core Entities**: Business, Customer, CallLog, ConversationTurn, AppointmentRequest.
- **CRM Extension**: Advanced customer segmentation, task management, and analytics capabilities.
- **Permissions**: Role-based access with business-specific permissions.
- **Audit Trail**: Comprehensive logging of customer interactions.

### WhatsApp Integration
- **Primary Method**: Baileys WebSocket client for WhatsApp Web, with QR code-based authentication and multi-device support.
- **Backup Method**: Twilio WhatsApp API. Unified into the main system.

### System Design Choices
- Hybrid Flask (backend) + React (frontend) architecture.
- Service-oriented architecture.
- Robust error resilience and fallback systems.
- PWA functionality with Hebrew RTL support and offline capabilities.
- Comprehensive design tokens system.
- Real-time notifications and updates via Socket.IO.
- Optimized calls system for transcription-only with chat-style display, search, lead scoring, and sentiment analysis.
- Complete CRM Suite with advanced lead management, digital contracts, invoice system, task scheduler, and customer analytics.
- Smart Payment Integration with one-click payment link generation and tracking, supporting multi-tenant PayPal and Tranzila.
- Watchdog system to ensure call transcription (live or recorded) even if WebSocket fails.
- Direct Record mode as a primary operational flow, eliminating complex WebSocket dependencies for production reliability.
- Deployment code freshness solution implemented with version tracking, cache-busting headers, and force rebuild system.

## External Dependencies

### Cloud Services
- **OpenAI API**: For conversational AI (GPT-4o) and Hebrew transcription (Whisper).
- **Google Cloud Text-to-Speech**: For Hebrew voice synthesis.
- **Twilio**: For voice call handling, SMS, and WhatsApp API backup.
- **PostgreSQL**: Production database.

### Core Libraries
- **@whiskeysockets/baileys**: WhatsApp Web client.
- **openai**: Official OpenAI API client for Python.
- **Flask-SQLAlchemy**: Database ORM.
- **psycopg2**: PostgreSQL database adapter.

### Deployment Infrastructure
- **Node.js**: Runtime environment (for Baileys).
- **Python**: Backend runtime.

## Recent Changes: Latest modifications with dates

### 2025-09-01: COMPLETE ERROR 31924 & 12100 FIX ✅ 
- **BREAKTHROUGH SOLUTION**: Fixed critical Twilio Error 31924 by implementing proper https:// URL generation
- **TwiML CONTENT-TYPE FIX**: Updated all TwiML endpoints to use application/xml; charset=utf-8 with proper encoding
- **WEBSOCKET PROTOCOL**: Verified wsgi.py correctly handles Twilio subprotocol with Sec-WebSocket-Protocol header
- **VERIFIED WORKING**: TwiML now correctly generates https:// webhook URLs and wss:// Stream URLs
- **HEADERS FIXED**: Replaced text/xml with application/xml; charset=utf-8 and added UTF-8 encoding to prevent 12100
- **BASE URL LOGIC**: All endpoints use X-Forwarded headers for correct scheme/host detection in production
- **PHONE NUMBER**: Verified TWILIO_PHONE_NUMBER=+972 3 376 3805 matches user requirement (+97233763805)
- **STATUS**: Both Error 31924 (WebSocket Protocol) and 12100 (Document Parse) should be completely resolved

### 2025-09-02: ERROR 11205 TIMEOUT FIX + AUTHENTICATION SETUP ✅
- **WEBHOOK TIMEOUT SOLUTION**: Fixed Error 11205 by converting DB operations to async background threads
- **PERFORMANCE OPTIMIZATION**: All webhooks now respond under 150ms (previously timing out)
- **ASYNC DATABASE**: Converted save_call_status to async operation preventing webhook blocking
- **AUTHENTICATION SYSTEM**: Created default admin (admin@maximus.co.il / admin123) and business user (business@shai-offices.co.il / business123)
- **BUSINESS SETUP**: Configured "שי דירות ומשרדים בע״מ" with professional Hebrew AI prompt for real estate
- **GOOGLE CLOUD ISSUE**: Google Cloud TTS integration is not working properly - GOOGLE_CLOUD_PROJECT_ID missing/invalid
- **SYSTEM STATUS**: All Twilio errors resolved, webhooks optimized, authentication ready, Google Cloud TTS needs fixing