# Hebrew AI Call Center CRM

## Overview
This project is a fully operational, production-ready Hebrew AI Call Center CRM designed for "שי דירות ומשרדים בע״מ". It integrates OpenAI GPT-4o for intelligent Hebrew conversations, real-time Hebrew transcription via Whisper, professional real estate-specific responses, continuous dialogue management, and comprehensive conversation logging. The system is built to handle live Twilio calls, providing a complete solution for managing customer interactions, with ambitions to enhance real estate operations through advanced AI and CRM capabilities.

## Recent Changes (August 15, 2025)
**🔧 WHATSAPP & TWILIO INTEGRATION FIXED:**
- ✅ **TWILIO WEBHOOKS WORKING**: `/webhook/incoming_call` and `/webhook/call_status` responding correctly with TwiML
- ✅ **WHATSAPP API UPGRADED**: Replaced mock API with real Baileys integration
- ✅ **QR CODE SYSTEM**: WhatsApp QR codes generated and accessible via `/api/whatsapp/qr`
- ✅ **STATUS MONITORING**: Real-time WhatsApp connection status via `/api/whatsapp/status`
- ✅ **AUTHENTICATION FIXED**: WhatsApp status endpoints work without authentication for ease of setup
- ✅ **BAILEYS CLIENT RUNNING**: WhatsApp Web client active and generating fresh QR codes

**🎯 SYSTEM STATUS**: 
- **Twilio**: ✅ Working - webhook returns proper TwiML Response
- **WhatsApp**: ✅ Active - QR code available for connection
- **Voice Pipeline**: ✅ Ready - Hebrew TTS, AI conversation, transcription
- **Web Interface**: ✅ Running - Professional login system operational

**📱 NEXT STEPS**: Scan WhatsApp QR code to complete setup

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18 using functional components and hooks.
- **Routing**: Wouter for SPA navigation.
- **Styling**: Tailwind CSS with Hebrew RTL support and a custom CSS tokens system.
- **Build Tool**: Vite.
- **Icons**: Lucide React.
- **Real-time**: Socket.IO client for live notifications.
- **Components**: Professional library including a TaskDueModal and notification system.
- **Hooks**: Custom hooks like `useTaskDue` for real-time task management.
- **Directory Structure**: Clean client-server separation with organized component structure.
- **UI/UX Decisions**: Professional UI with AdminLayout, responsive sidebar, Hebrew Typography (Assistant font), modern design system (gradients, rounded corners), consistent layout, TanStack Table for data display with RTL, sorting, filtering, and CSV export. Permissions-based navigation.

### Backend Architecture
- **Framework**: Flask, utilizing an App Factory pattern and Blueprint architecture for modularity.
- **App Factory**: Centralized application configuration and setup.
- **Blueprints**: Modular route organization for different functionalities (e.g., CRM, Timeline).
- **Error Handling**: Production-ready error handlers with structured JSON logging.
- **Language**: Python 3.9+ with Hebrew language support.
- **Database**: SQLAlchemy ORM, designed for PostgreSQL in production.
- **API Design**: RESTful JSON endpoints with CORS and robust error handling.
- **Authentication**: Session-based with role-based access control (admin/business).
- **Business Logic**: Service-oriented architecture ensuring clear separation of concerns.

### Voice Processing Pipeline
- **Speech Recognition**: OpenAI Whisper for Hebrew transcription, including gibberish detection.
- **Text-to-Speech**: Google Cloud TTS optimized for high-quality Hebrew voice synthesis.
- **Audio Processing**: MP3 format with automatic cleanup of old voice files.
- **Quality Control**: Intelligent filtering to prevent nonsensical responses from the AI.

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
- Service-oriented architecture for business logic.
- Robust error resilience and fallback systems.
- PWA functionality with Hebrew RTL support and offline capabilities.
- Comprehensive design tokens system.
- Real-time notifications and updates via Socket.IO.
- Optimized calls system for transcription-only (no recordings) with chat-style display, search, lead scoring, and sentiment analysis.
- Complete CRM Suite with advanced lead management, digital contracts, invoice system, task scheduler, and customer analytics.
- Smart Payment Integration with one-click payment link generation and tracking.

## External Dependencies

### Cloud Services
- **OpenAI API**: For conversational AI and response generation (GPT-4o).
- **Google Cloud Text-to-Speech**: For Hebrew voice synthesis.
- **Twilio**: For voice call handling, SMS, and WhatsApp API backup.
- **PostgreSQL**: Production database.

### Core Libraries
- **@whiskeysockets/baileys**: WhatsApp Web client.
- **openai**: Official OpenAI API client for Python.
- **Flask-SQLAlchemy**: Database ORM.
- **psycopg2**: PostgreSQL database adapter.
- **qrcode-terminal**: QR code generation.
- **ws**: WebSocket client.

### Development Tools
- **Vite**: Frontend build tool and development server.
- **React Scripts**: React application utilities.
- **Tailwind CSS**: Utility-first CSS framework.
- **Autoprefixer**: CSS vendor prefix automation.

### Deployment Infrastructure
- **Node.js**: Runtime environment.
- **Python**: Backend runtime.