# Hebrew AI Call Center CRM - Deployment Guide
## מדריך פריסה - מערכת CRM מוקד שיחות AI בעברית

### Current Status
This is a **Python Flask Application** with supplementary Node.js WhatsApp service (Baileys).

### Deployment Configuration Issues Fixed

#### 1. Project Type Identification ✅
- **Primary Application**: Python Flask (`main.py`)
- **Secondary Service**: Node.js WhatsApp Service (`baileys_client.js`)
- **Dependencies**: Listed in `pyproject.toml` (Python) and `package.json` (Node.js)

#### 2. Build Process ✅
Created `build.sh` script that:
- Sets up Python environment
- Installs dependencies from `pyproject.toml`
- Creates necessary directories
- Sets up database tables
- Installs Node.js dependencies for WhatsApp service

#### 3. Start Process ✅
Created `start.sh` script that:
- Sets production environment variables
- Starts the main Python Flask application via `python main.py`

### Deployment Instructions

#### For Replit Deployments:
1. **Manual Build**: Run `./build.sh` to prepare the application
2. **Manual Start**: Run `./start.sh` to start in production mode
3. **Environment Variables**: Ensure all required secrets are set in Replit Secrets:
   - `SESSION_SECRET`
   - `OPENAI_API_KEY`
   - `TWILIO_ACCOUNT_SID`
   - `TWILIO_AUTH_TOKEN`
   - `DATABASE_URL` (automatically provided by Replit)

#### Required Environment Variables:
```bash
SESSION_SECRET=your_session_secret
OPENAI_API_KEY=your_openai_key
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
DATABASE_URL=postgresql://... (provided by Replit)
FLASK_ENV=production
FLASK_DEBUG=false
PORT=5000
HOST=0.0.0.0
```

### Architecture
- **Web Framework**: Flask (Python)
- **Database**: PostgreSQL (via DATABASE_URL)
- **AI Services**: OpenAI GPT-4o for Hebrew AI responses
- **Communication**: Twilio for voice calls
- **WhatsApp**: Baileys (Node.js) + Twilio integration
- **Frontend**: Integrated Flask templates with React components

### Production Readiness Features
- Automatic database table creation
- Logging configuration
- Background cleanup services
- Hebrew language support
- Production security settings
- Error handling and recovery

### Next Steps for Deployment
1. Ensure all environment variables are configured in Replit Secrets
2. Use the deployment panel in Replit
3. The application will start via `python main.py`
4. WhatsApp service can be started separately if needed: `node baileys_client.js`

### Support
- Main application logs: Check Flask application logs
- WhatsApp service logs: `tail -f baileys.log`
- Database: PostgreSQL via DATABASE_URL