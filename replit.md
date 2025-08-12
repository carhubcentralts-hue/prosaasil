# Hebrew AI Call Center CRM

## Overview
A comprehensive Hebrew-language AI call center and CRM system. This platform automates voice responses, integrates with WhatsApp Business, and manages customer relationships. It leverages Whisper for Hebrew speech transcription, OpenAI for conversational AI, and Google Text-to-Speech for Hebrew audio generation. The system aims to automatically handle incoming calls, transcribe conversations, generate intelligent responses, and manage customer interactions across phone and WhatsApp channels. The business vision is to provide a robust, AI-powered solution for customer service in Hebrew, streamlining communication and enhancing CRM capabilities.

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18, functional components, hooks.
- **Routing**: Wouter.
- **Styling**: Tailwind CSS with Hebrew RTL support and custom typography.
- **Build Tool**: Vite.
- **Icons**: Lucide React.
- **Directory Structure**: Client-server separation (`client/` folder).

### Backend Architecture
- **Framework**: Flask with Blueprint-based modular architecture.
- **Language**: Python 3.9+ with Hebrew language support.
- **Database**: SQLAlchemy ORM (PostgreSQL for production, SQLite for development).
- **API Design**: RESTful JSON endpoints with CORS.
- **Authentication**: Session-based with role-based access control (admin/business).
- **Business Logic**: Service-oriented architecture.

### Voice Processing Pipeline
- **Speech Recognition**: OpenAI Whisper for Hebrew transcription with gibberish detection.
- **Text-to-Speech**: Google Cloud TTS optimized for Hebrew.
- **Audio Processing**: MP3 format, automatic cleanup of old voice files.
- **Quality Control**: Intelligent filtering to prevent nonsensical responses.

### AI Integration
- **Conversational AI**: OpenAI GPT-3.5-turbo with Hebrew-optimized prompts.
- **Response Generation**: Context-aware based on business type and customer history.
- **Fallback Handling**: Graceful degradation when AI services are unavailable.
- **Business Customization**: Per-business AI prompt configuration.

### Data Models
- **Core Entities**: Business, Customer, CallLog, ConversationTurn, AppointmentRequest.
- **CRM Extension**: Advanced customer segmentation, task management, and analytics.
- **Permissions**: Role-based access with business-specific permissions.
- **Audit Trail**: Comprehensive logging of customer interactions.

### WhatsApp Integration
- **Primary Method**: Baileys WebSocket client for WhatsApp Web.
- **Authentication**: QR code-based authentication with multi-device support.
- **Message Handling**: Real-time message processing with conversation threading.
- **Backup Method**: Twilio WhatsApp API.

### UI/UX Decisions
- Professional UI overhaul with AdminLayout component and responsive sidebar navigation.
- Hebrew Typography: Assistant font integration across all components.
- Modern Design System: Gradient backgrounds, rounded corners, improved UX.
- All main pages use consistent AdminLayout wrapper.
- Professional DataTables: TanStack Table with Hebrew RTL, sorting, filtering, CSV export.
- Permissions-Based Navigation: Role-specific sidebar menus (Admin/Business).
- Modern gradient-based UI with mobile responsiveness.

### System Design Choices
- Hybrid Flask (backend) + React (frontend) architecture.
- Service-oriented architecture for business logic.
- Robust error resilience and fallback systems for production.
- PWA functionality with Hebrew RTL support and offline capabilities.
- Comprehensive design tokens system.
- Real-time notifications and updates via Socket.IO.
- Optimized calls system for transcription-only (no recordings) with chat-style display, search, lead scoring, and sentiment analysis.
- Complete CRM Suite with advanced lead management, digital contracts, invoice system, task scheduler, and customer analytics.
- Smart Payment Integration with one-click payment link generation and tracking.

## External Dependencies

### Cloud Services
- **OpenAI API**: For conversational AI and response generation.
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
- **Build Scripts**: Custom deployment pipeline.
- **Static Assets**: Centralized management for voice responses and frontend builds.