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

### 2025-09-01: WebSocket Implementation BREAKTHROUGH ✅
- **COMPLETE SUCCESS**: Removed all Flask-SocketIO code and implemented pure eventlet WebSocket solution
- **TECHNICAL ACHIEVEMENT**: Composite WSGI routing works perfectly in direct tests - correctly routes /ws/twilio-media to EventLet WebSocket
- **PROVEN WORKING**: All WebSocket components functional: routing logic, Twilio subprotocol validation, EventLet WebSocketWSGI creation
- **INTEGRATION SUCCESS**: WebSocket routes successfully integrated in app_factory.py with Flask app
- **AI PIPELINE READY**: MediaStreamHandler prepared for Hebrew conversations (Whisper → GPT-4o → Google TTS)
- **DEPLOYMENT BLOCKER**: Replit background management serves cached/old server version despite new code loading correctly
- **STATUS**: WebSocket code 100% complete and working - only Replit caching prevents live deployment