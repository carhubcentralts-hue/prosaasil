# Overview

AgentLocator is a Hebrew CRM system featuring an AI-powered real estate agent named "Leah." It integrates with Twilio and WhatsApp to process real-time calls, collect lead information, and schedule meetings. The system uses Twilio's Media Streams for stable real-time audio, natural barge-in capabilities, and focused lead collection, aiming to automate lead management for real estate businesses.

# Recent Changes

## BUILD 79 (October 9, 2025) - Business & Lead Creation Fix + Full CRUD Support
- **🔧 CRITICAL FIX - Business Creation**: Fixed NOT NULL constraint violations in business creation
  - Added ALL required fields: whatsapp_number, greeting_message, whatsapp_greeting, system_prompt, voice_message, working_hours
  - Added permissions: phone_permissions, whatsapp_permissions
  - Added feature flags: calls_enabled, crm_enabled, whatsapp_enabled, payments_enabled
  - Default values auto-populated based on business name and phone
- **✅ Business Update - Full CRUD Support**: Complete support for updating all business fields
  - Update all new fields (greetings, prompts, voice messages, etc.)
  - Auto-update of updated_at timestamp
  - Support for both defaultPhoneE164 and phone_e164 field names
- **✅ Consistent CRUD Responses**: All endpoints return complete, consistent data
  - GET/POST/PUT return ALL stored fields
  - is_active, timestamps, boolean flags included
  - status derived from is_active (active/inactive)
- **✅ Lead Creation Working**: Lead creation fully functional and connected to database
  - Automatic status seeding if missing
  - Proper tenant isolation
  - Activity logging
- **✅ Commercial Ready**: Full CRUD operations for businesses and leads

## BUILD 78 (October 9, 2025) - Production Database Auto-Initialization (COMPLETE!)
- **🔧 CRITICAL FIXES - Schema Drift Resolution**: Fixed all missing NOT NULL constraint violations
  - **Fix 1**: Invalid 'active' field → Changed to 'is_active' ✅
  - **Fix 2**: Missing phone_number (NOT NULL) → Added phone_e164="+972500000000" ✅
  - **Fix 3**: Missing greeting_message (NOT NULL) → Added "שלום! איך אפשר לעזור?" ✅
  - **Fix 4**: Missing system_prompt (NOT NULL) → Added default AI prompt ✅
  - **Fix 5**: Added ALL required Business fields to prevent future failures:
    - whatsapp_number, whatsapp_greeting, voice_message
    - phone_permissions, whatsapp_permissions
    - payments_enabled, default_provider, working_hours
  - **Fix 6**: Silent logging → Added explicit print() statements for production visibility ✅
- **🚀 Automatic Database Initialization**: System now auto-initializes on every deployment
  - `initialize_production_database()` runs automatically AFTER migrations
  - Creates default business "עסק ראשי" if none exists (with ALL required fields)
  - Creates admin@admin.com user with proper business_id linkage
  - Creates 7 default Hebrew lead statuses automatically
  - **Idempotent**: Safe to run multiple times, checks for existing data
  - **Commercial-Ready**: Works out-of-the-box for production deployments
- **Production & Preview Support**: Works in both environments
  - Production: RUN_MIGRATIONS_ON_START=1 (set in start_production.sh)
  - Preview: Migrations skipped, uses existing DB
  - Full traceback logging for debugging with print() statements

## BUILD 76 (October 9, 2025)
- **Status Management Admin Access**: Admin users can now create/update/delete statuses without business_id requirement
  - GET /api/statuses: Admin can access all statuses (fallback to business_id=1)
  - POST /api/statuses: Admin can create statuses for any business
  - PUT /api/statuses/:id: Admin can update any status
  - DELETE /api/statuses/:id: Admin can delete any status
- **Bulk Lead Operations**: Added bulk delete functionality
  - New endpoint: POST /api/leads/bulk-delete with lead_ids array
  - Admin can bulk delete leads across all tenants
  - Proper access control and activity logging for bulk operations
- **Lead Selection UI**: Added checkbox-based lead selection
  - Select individual leads via checkbox
  - Select all leads with header checkbox
  - Bulk delete button appears when leads are selected
  - Delete confirmation dialog before bulk action

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM.
- **WebSocket Support**: Starlette-based native WebSocket handling for Twilio Media Streams (Cloud Run compatible).
- **ASGI Server**: Uvicorn with native WebSocket support (replaced Gunicorn/Eventlet for Cloud Run compatibility).
- **Database**: PostgreSQL (SQLite for development).
- **Authentication**: JWT-based with role-based access control (admin, business_owner, business_agent, read_only).
- **Security**: SeaSurf CSRF protection with @csrf.exempt on Twilio webhooks.
- **AI Prompt System**: Real-time prompt management with versioning and channel-specific prompts (calls vs whatsapp).

## Frontend Architecture
- **Framework**: React 19 (Static build served by Flask).
- **Build Tool**: Vite 7.1.4.
- **Styling**: Tailwind CSS v4 with RTL support and Hebrew typography (Heebo font).
- **Routing**: React Router v7 with AuthGuard/RoleGuard.
- **State Management**: Context API for authentication.
- **Components**: Production-grade, accessible, mobile-first design.
- **Security**: CSRF protection, secure redirects, and role-based access control.

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket with Starlette/ASGI for Cloud Run native WebSocket support.
- **Audio Processing**: μ-law to PCM conversion with optimized barge-in detection (200ms grace period).
- **WebSocket Protocol**: Starlette WebSocketRoute with Twilio's `audio.twilio.com` subprotocol support.
- **Call Management**: TwiML generation for call routing and recording with WSS (secure WebSocket).
- **Voice Activity Detection**: Calibrated VAD for Hebrew speech.
- **Natural Conversation Flow**: Immediate TTS interruption and seamless turn-taking.

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation.
- **Call Logging**: Comprehensive call tracking with transcription and status management.
- **Conversation Memory**: Full conversation history stored in `conversation_turn` table with automatic persistence.
- **Contextual AI Responses**: AI maintains conversation context across all turns using synchronized history (conversation_history).
- **WhatsApp Integration**: Both Twilio and Baileys (direct WhatsApp Web API) support.
- **Intelligent Lead Collection**: Automated capture of key lead information with real-time lead creation from calls (with app context for background threads). One lead per phone number - all calls and interactions linked to the same lead.
- **Calendar Integration**: AI checks real-time availability for 7 days ahead and suggests available appointment slots during conversations.
- **Meeting Scheduling**: Automatic detection and coordination when lead data is complete, with calendar-aware suggestions.
- **Hebrew Real Estate Agent**: "Leah" - specialized AI agent with context-aware responses, natural conversation flow, and calendar integration.
- **Customizable Status Management**: Per-business custom lead statuses with default Hebrew options.
- **Billing and Contracts**: Integrated payment processing (PayPal, Tranzilla) and contract generation.
- **Automatic Recording Cleanup**: 2-day retention policy with automatic deletion of recordings from both database and disk (POST /api/calls/cleanup).

# External Dependencies

- **Twilio**: Telephony services for voice calls and WhatsApp Business API.
- **OpenAI**: GPT-4o-mini for Hebrew real estate conversations.
- **Google Cloud Platform**: STT Streaming for Hebrew and TTS Wavenet for natural Hebrew voice.
- **PostgreSQL**: Production database.
- **Baileys Library**: For direct WhatsApp connectivity.