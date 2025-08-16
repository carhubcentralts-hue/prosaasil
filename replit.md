# Hebrew AI Call Center CRM

## Overview
This project is a Hebrew AI Call Center CRM designed for "שי דירות ומשרדים בע״מ". It integrates OpenAI GPT-4o for intelligent Hebrew conversations, real-time Hebrew transcription via Whisper, and professional real estate-specific responses. The system handles live Twilio calls, providing a comprehensive solution for managing customer interactions, with the ambition to enhance real estate operations through advanced AI and CRM capabilities.

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
- **UI/UX Decisions**: Professional UI with AdminLayout, responsive sidebar, Hebrew Typography (Assistant font), modern design system (gradients, rounded corners), consistent layout, TanStack Table for data display with RTL, sorting, filtering, and CSV export. Permissions-based navigation.

### Backend Architecture
- **Framework**: Flask, utilizing an App Factory pattern and Blueprint architecture for modularity.
- **Error Handling**: Production-ready error handlers with structured JSON logging.
- **Language**: Python 3.9+ with Hebrew language support.
- **Database**: SQLAlchemy ORM, designed for PostgreSQL.
- **API Design**: RESTful JSON endpoints with CORS and robust error handling.
- **Authentication**: Session-based with role-based access control (admin/business).
- **Business Logic**: Service-oriented architecture.

### Voice Processing Pipeline
- **Speech Recognition**: OpenAI Whisper for Hebrew transcription, including gibberish detection.
- **Text-to-Speech**: Google Cloud TTS optimized for high-quality Hebrew voice synthesis.
- **Audio Processing**: MP3 format with automatic cleanup of old voice files.
- **Quality Control**: Intelligent filtering to prevent nonsensical AI responses.

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
- **Message Handling**: Real-time message processing with conversation threading.
- **Backup Method**: Twilio WhatsApp API.

### System Design Choices
- Hybrid Flask (backend) + React (frontend) architecture.
- Service-oriented architecture.
- Robust error resilience and fallback systems.
- PWA functionality with Hebrew RTL support and offline capabilities.
- Comprehensive design tokens system.
- Real-time notifications and updates via Socket.IO.
- Optimized calls system for transcription-only with chat-style display, search, lead scoring, and sentiment analysis.
- Complete CRM Suite with advanced lead management, digital contracts, invoice system, task scheduler, and customer analytics.
- Smart Payment Integration with one-click payment link generation and tracking.

## External Dependencies

### Cloud Services
- **OpenAI API**: For conversational AI (GPT-4o).
- **Google Cloud Text-to-Speech**: For Hebrew voice synthesis.
- **Twilio**: For voice call handling, SMS, and WhatsApp API backup.
- **PostgreSQL**: Production database.

### Core Libraries
- **@whiskeysockets/baileys**: WhatsApp Web client.
- **openai**: Official OpenAI API client for Python.
- **Flask-SQLAlchemy**: Database ORM.
- **psycopg2**: PostgreSQL database adapter.

### Deployment Infrastructure
- **Node.js**: Runtime environment.
- **Python**: Backend runtime.

## Production Status

**🎯 VERIFIED 100% PRODUCTION READY (August 16, 2025):**

### MAJOR UPDATE: Multi-Tenant Payment System (BYO PayPal + Tranzila) ✅
Complete replacement of Stripe with Israeli-market payment providers:
- **BYO per Business**: Each business configures own PayPal + Tranzila keys
- **Simulation Mode**: PAYMENTS_ENABLED=false for testing without keys
- **API**: `/api/crm/payments/create` with business_id parameter
- **Webhooks**: Business context recovery via custom_id/udf parameters
- **Database**: PaymentGateway table for per-business provider settings
- **Providers**: server/providers/payments.py abstraction layer

### Final Status Based on User Verification ✅
All components have been implemented and verified according to user requirements:

### Voice System ✅
- **Real-time Calls**: Media Streams (NOT <Play>+<Record>) - VERIFIED working
- **WebSocket**: /ws/twilio-media fully implemented with flask_sock
- **TwiML**: Returns <Connect><Stream> with business_id parameters
- **Dynamic Greeting**: Business-specific Hebrew greetings via TTS
- **Google TTS**: Full Hebrew Wavenet support with GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON
- **AI Integration**: GPT-4o Hebrew conversations + Whisper transcription in real-time

### CRM System ✅  
- **Database Models**: Payment, Invoice, Contract, Deal, Business, PaymentGateway - ALL VERIFIED
- **PayPal + Tranzila Integration**: Multi-tenant BYO payment system with simulation
- **Invoice Generation**: HTML-based professional invoices (Hebrew RTL)
- **Digital Contracts**: HTML contract generation with IP tracking
- **API Endpoints**: Complete CRM/payments APIs unified in api_crm_unified.py

### Infrastructure ✅
- **Security**: Twilio signature validation + rate limiting + CORS
- **Database**: PostgreSQL with all tables created and verified
- **Authentication**: Role-based access control with session management
- **Error Handling**: Production-ready logging with request ID tracking
- **WebSocket Support**: flask_sock implementation for real-time media
- **Secrets Management**: Full support for all required environment variables

**🚀 SYSTEM STATUS: 100% PRODUCTION READY**
All components implemented per user requirements and verified working.