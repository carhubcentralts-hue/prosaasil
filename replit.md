# Hebrew AI Call Center CRM

## Overview  
**FULLY OPERATIONAL** Hebrew AI Call Center for "שי דירות ומשרדים בע״מ". Complete production-ready system with OpenAI GPT-4o integration for intelligent Hebrew conversations. Features real-time Hebrew transcription with Whisper, professional real estate responses, continuous dialogue management, and comprehensive conversation logging. All technical issues resolved - system ready for live Twilio calls.

## Recent Major Update (August 2025)
**✅ COMPLETE PROFESSIONAL ARCHITECTURE REBUILD** - Implemented comprehensive App Factory pattern:
- **App Factory Pattern**: Professional Flask architecture with Blueprint separation (`server/app_factory.py`)
- **Blueprint Organization**: Modular routes system (`server/routes/`, `server/api_*` files)
- **Error Handling**: Production-ready error handlers with JSON logging (`server/error_handlers.py`)
- **Logging System**: Professional JSON structured logging (`server/logging_setup.py`)
- **CRM API**: Advanced customer management with proper pagination (`server/api_crm_advanced.py`)
- **Timeline API**: Customer interaction tracking (`server/api_timeline.py`)
- **Real-time Features**: Socket.IO integration, task notifications (`client/src/lib/socket.ts`)
- **Frontend Components**: TaskDueModal, useTaskDue hook, service worker notifications
- **Design System**: CSS tokens, Hebrew typography, RTL support (`client/src/styles/tokens.css`)
- **Hebrew TTS System**: Using gTTS with 'iw' language code for Hebrew MP3 generation
- **Production Ready**: Environment variables, deployment configuration, comprehensive testing

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
- **Framework**: React 18, functional components, hooks.
- **Routing**: Wouter for SPA navigation.
- **Styling**: Tailwind CSS with Hebrew RTL support, custom CSS tokens system (`client/src/styles/tokens.css`).
- **Build Tool**: Vite with modern build pipeline.
- **Icons**: Lucide React for consistent iconography.
- **Real-time**: Socket.IO client integration for live notifications (`client/src/lib/socket.ts`).
- **Components**: Professional component library including TaskDueModal, notification system.
- **Hooks**: Custom hooks like useTaskDue for real-time task management.
- **Directory Structure**: Clean client-server separation with organized component structure.

### Backend Architecture
- **Framework**: Flask with professional App Factory pattern and Blueprint architecture.
- **App Factory**: `server/app_factory.py` - centralized application configuration and setup.
- **Blueprints**: Modular route organization - `server/routes/`, `server/api_crm_advanced.py`, `server/api_timeline.py`.
- **Error Handling**: Production-ready error handlers with structured JSON logging.
- **Language**: Python 3.9+ with Hebrew language support.
- **Database**: SQLAlchemy ORM (PostgreSQL for production, development models in `server/models.py`).
- **API Design**: RESTful JSON endpoints with CORS and proper error handling.
- **Authentication**: Session-based with role-based access control (admin/business).
- **Business Logic**: Service-oriented architecture with clean separation of concerns.

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