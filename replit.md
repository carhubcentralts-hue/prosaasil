# Overview

This is AgentLocator, a Hebrew CRM system with AI-powered real-time call processing integrated with Twilio and WhatsApp. The system combines a Flask backend with React frontend to provide a complete customer relationship management solution for Hebrew-speaking businesses. The application handles incoming calls through Twilio's Media Streams, processes audio in real-time, manages WhatsApp communications, and provides a comprehensive CRM interface for business operations.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM for database operations
- **WebSocket Support**: Eventlet-based WebSocket handling for Twilio Media Streams with `simple-websocket` library
- **WSGI Server**: Gunicorn with eventlet worker for production deployment
- **Database**: PostgreSQL (with SQLite fallback for development) using SQLAlchemy models
- **Authentication**: JWT-based authentication with role-based access control (admin, business_owner, business_agent, read_only)

## Frontend Architecture
- **Framework**: React with Vite as the build tool
- **Styling**: Tailwind CSS 4.1 with RTL (right-to-left) support for Hebrew
- **UI Components**: Custom components with planned Radix Primitives integration
- **Font**: Heebo font for Hebrew and Latin text support
- **Routing**: Client-side routing with SPA fallback handling

## Real-time Communication
- **Twilio Integration**: Media Streams WebSocket connection for real-time audio processing
- **Audio Processing**: μ-law to PCM conversion utilities for audio stream handling
- **WebSocket Protocol**: Custom protocol implementation supporting Twilio's `audio.twilio.com` subprotocol
- **Call Management**: TwiML generation for call routing and recording

## CRM Features
- **Multi-tenant Architecture**: Business-based data isolation with role-based permissions
- **Call Logging**: Comprehensive call tracking with transcription and status management
- **WhatsApp Integration**: Both Twilio and Baileys (direct WhatsApp Web API) support
- **Lead Management**: Customer and lead tracking with business context

## External Dependencies

- **Twilio**: Primary telephony service for voice calls and WhatsApp Business API
- **OpenAI**: AI processing for call transcription and analysis
- **Google Cloud Platform**: Speech-to-Text and Text-to-Speech services
- **PostgreSQL**: Production database system
- **WhatsApp Business API**: Message handling through Twilio's WhatsApp integration
- **Baileys Library**: Alternative WhatsApp Web API client for direct WhatsApp connectivity

The system is designed for deployment on cloud platforms like Replit with environment-based configuration and supports both development and production modes with appropriate WebSocket and HTTP handling.