const express = require('express');
const cors = require('cors');

const app = express();

// Middleware
app.use(cors());
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

/**
 * שלב 2: Twilio Voice Routes - TwiML מתאימים
 */
app.post('/webhook/incoming_call', (req, res) => {
    const host = process.env.HOST || `${req.protocol}://${req.get('host')}`;
    const twimlResponse = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>${host}/static/greeting.mp3</Play>
    <Record finishOnKey="*" timeout="5" maxLength="30" playBeep="true" action="/webhook/handle_recording"/>
</Response>`;
    
    res.set('Content-Type', 'text/xml');
    res.send(twimlResponse);
});

app.post('/webhook/handle_recording', (req, res) => {
    const recordingUrl = req.body.RecordingUrl || '';
    
    // בגרסה מלאה: transcribe_hebrew + generate_reply_tts
    const twimlResponse = `<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>http://localhost:5000/static/reply.mp3</Play>
</Response>`;
    
    res.set('Content-Type', 'text/xml');
    res.send(twimlResponse);
});

app.post('/webhook/call_status', (req, res) => {
    res.status(200).end();
});

/**
 * שלב 1: CRM API Routes - מבנה בסיסי
 */
app.get('/api/crm/customers', (req, res) => {
    const page = parseInt(req.query.page || '1', 10);
    const limit = Math.min(parseInt(req.query.limit || '25', 10), 100);
    
    res.json({
        page,
        limit,
        total: 0,
        items: []
    });
});

/**
 * Routes נוספים מ-Blueprints
 */
app.get('/signature/', (req, res) => {
    res.json({ message: 'Signature route placeholder' });
});

app.get('/calendar/', (req, res) => {
    res.json({ message: 'Calendar route placeholder' });
});

app.get('/proposal/', (req, res) => {
    res.json({ message: 'Proposal route placeholder' });
});

app.get('/reports/', (req, res) => {
    res.json({ message: 'Reports route placeholder' });
});

// Health check
app.get('/health', (req, res) => {
    res.json({ status: 'OK', message: 'AgentLocator v42 API Server Running' });
});

const PORT = process.env.PORT || 5000;

if (require.main === module) {
    app.listen(PORT, '0.0.0.0', () => {
        console.log(`🚀 AgentLocator v42 API Server running on http://0.0.0.0:${PORT}`);
        console.log(`✅ Twilio webhooks ready: /webhook/*`);
        console.log(`✅ CRM API ready: /api/crm/*`);
    });
}

module.exports = app;