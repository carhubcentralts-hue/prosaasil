# 📊 OFFLINE RECORDING TRANSCRIPTION - FLOW DIAGRAM

## 🔄 Complete System Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         📞 PHONE CALL LIFECYCLE                             │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │ Call Starts  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────┐
    │  Realtime Processing │
    │  (OpenAI Realtime)   │
    │  - Low-latency STT   │
    │  - Live conversation │
    │  - Real-time TTS     │
    └──────┬───────────────┘
           │
           ▼
    ┌──────────────┐
    │  Call Ends   │
    └──────┬───────┘
           │
           ├─────────────────────────────────────────┐
           │                                         │
           ▼                                         ▼
    ┌─────────────────┐                    ┌────────────────────┐
    │ Twilio Records  │                    │   Realtime Data    │
    │ Audio + Sends   │                    │   Saved to DB      │
    │ Webhook         │                    │   - Transcript     │
    └─────────┬───────┘                    │   - Conversation   │
              │                            │   - Lead Info      │
              │                            └────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │             🎧 OFFLINE RECORDING WORKER (Background)                │
    └─────────────────────────────────────────────────────────────────────┘
              │
              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  1️⃣  DOWNLOAD RECORDING FROM TWILIO                                  │
    │  ────────────────────────────────────────────────────────────────   │
    │  ✅ NEW: Robust URL Handling                                         │
    │                                                                       │
    │  Input: recording_url from webhook                                   │
    │    Examples:                                                          │
    │    • /2010-04-01/Accounts/.../Recordings/RExxx.json                 │
    │    • /2010-04-01/Accounts/.../Recordings/RExxx.mp3                  │
    │    • https://api.twilio.com/.../Recordings/RExxx.json               │
    │                                                                       │
    │  Process:                                                             │
    │  ┌────────────────────────────────────────────────────────┐         │
    │  │ if url.startswith("/"):                                 │         │
    │  │     url = f"https://api.twilio.com{url}"               │         │
    │  │                                                          │         │
    │  │ if url.endswith(".json"):                               │         │
    │  │     url = url[:-5] + ".mp3"                             │         │
    │  │ elif url.endswith((".mp3", ".wav")):                    │         │
    │  │     pass  # OK                                           │         │
    │  │ else:                                                    │         │
    │  │     url = url + ".mp3"                                  │         │
    │  └────────────────────────────────────────────────────────┘         │
    │                                                                       │
    │  Output:                                                              │
    │    ✅ https://api.twilio.com/.../Recordings/RExxx.mp3               │
    │    ✅ No .mp3.mp3 duplication                                        │
    │    ✅ Logs both original and final URL                               │
    └─────────────────────────┬─────────────────────────────────────────┘
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼ Success              ▼ Failure (404, timeout, etc.)
    ┌─────────────────────────┐    ┌─────────────────────────────┐
    │ audio_file = "path.mp3" │    │ audio_file = None           │
    │ File saved to disk      │    │ Log: "Audio download failed"│
    └─────────┬───────────────┘    └─────────┬───────────────────┘
              │                              │
              │                              ▼
              │                    ┌─────────────────────────────┐
              │                    │ Skip offline processing     │
              │                    │ transcription = ""          │
              │                    │ final_transcript = None     │
              │                    │ Save to DB with empty fields│
              │                    └─────────┬───────────────────┘
              │                              │
              │                              │
              ▼                              │
    ┌─────────────────────────────────────────────────────────────────────┐
    │  2️⃣  WHISPER TRANSCRIPTION (High Quality)                           │◀─┘
    │  ────────────────────────────────────────────────────────────────   │
    │  Only runs if: audio_file AND os.path.exists(audio_file)            │
    │                                                                       │
    │  Process:                                                             │
    │  • Transcribe with Whisper API (OpenAI)                             │
    │  • Returns: final_transcript (string)                                │
    │                                                                       │
    │  Validation:                                                          │
    │  if not final_transcript or len(final_transcript.strip()) < 10:     │
    │      final_transcript = None  # Don't save empty                    │
    │      Log: "Empty transcript - NOT updating"                          │
    └─────────────────────────┬─────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  3️⃣  AI EXTRACTION (Service + City)                                 │
    │  ────────────────────────────────────────────────────────────────   │
    │  Only runs if: final_transcript is valid                             │
    │                                                                       │
    │  Process:                                                             │
    │  • Extract service_type from transcript                              │
    │  • Extract city from transcript                                      │
    │  • Calculate confidence score                                        │
    │                                                                       │
    │  Output:                                                              │
    │  • extracted_service: "פריצת לוטו"                                  │
    │  • extracted_city: "בית שאן"                                         │
    │  • extraction_confidence: 0.92                                       │
    └─────────────────────────┬─────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  4️⃣  SAVE TO DATABASE (CallLog)                                     │
    │  ────────────────────────────────────────────────────────────────   │
    │  Fields updated:                                                      │
    │  • final_transcript      (Whisper, high quality)                    │
    │  • extracted_service     (AI extracted)                              │
    │  • extracted_city        (AI extracted)                              │
    │  • extraction_confidence (AI confidence)                             │
    │  • transcription         (old STT, for summary)                      │
    │  • summary               (GPT-4 summary)                             │
    │                                                                       │
    │  Logs:                                                                │
    │  if final_transcript:                                                 │
    │      "✅ Saved final_transcript (X chars)"                           │
    │  else:                                                                │
    │      "ℹ️ No offline transcript saved (empty or failed)"             │
    └─────────────────────────┬─────────────────────────────────────────┘
                              │
                              │
        ┌─────────────────────┴─────────────────────┐
        │                                           │
        │  Meanwhile, webhook is waiting...         │
        │  (Retries 2 times with 5 sec delay)       │
        │                                           │
        └─────────────────────┬─────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  5️⃣  WEBHOOK TRANSCRIPT SELECTION                                   │
    │  ────────────────────────────────────────────────────────────────   │
    │  ✅ NEW: Explicit logic with clear logging                           │
    │                                                                       │
    │  Logic:                                                               │
    │  ┌────────────────────────────────────────────────────────┐         │
    │  │ final_transcript = full_conversation  # Default        │         │
    │  │                                                          │         │
    │  │ if call_log.final_transcript and                        │         │
    │  │    len(call_log.final_transcript) > 50:                 │         │
    │  │     final_transcript = call_log.final_transcript        │         │
    │  │     Log: "✅ Using offline (X chars)                   │         │
    │  │           instead of realtime (Y chars)"                │         │
    │  │ else:                                                    │         │
    │  │     Log: "ℹ️ Using realtime (Y chars)"                 │         │
    │  └────────────────────────────────────────────────────────┘         │
    │                                                                       │
    │  Priority:                                                            │
    │  1. Offline transcript (if > 50 chars) ← HIGH QUALITY                │
    │  2. Realtime transcript (fallback)     ← LOW LATENCY                 │
    └─────────────────────────┬─────────────────────────────────────────┘
                              │
                              ▼
    ┌─────────────────────────────────────────────────────────────────────┐
    │  6️⃣  SEND WEBHOOK TO EXTERNAL SYSTEM                                │
    │  ────────────────────────────────────────────────────────────────   │
    │  Payload includes:                                                    │
    │  • call_id                                                            │
    │  • phone                                                              │
    │  • transcript         ← Final transcript (offline or realtime)       │
    │  • summary            ← GPT-4 summary                                │
    │  • city               ← From extraction or conversation              │
    │  • service_category   ← From extraction or confirmation              │
    │  • customer_name      ← From CRM context                             │
    │  • preferred_time     ← From appointment detection                   │
    │  • duration_sec                                                       │
    │  • started_at / ended_at                                              │
    └─────────────────────────────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────────────────────┐
│                         🎯 KEY IMPROVEMENTS                                 │
└─────────────────────────────────────────────────────────────────────────────┘

BEFORE FIX:                          AFTER FIX:
────────────────────────────────     ────────────────────────────────────────
❌ URL: /2010-04-01/.../RExxx.json   ✅ URL: https://api.twilio.com/.../RExxx.mp3
❌ HTTP 404 Error                    ✅ HTTP 200 Success
❌ audio_file = None                 ✅ audio_file = "path.mp3"
❌ final_transcript = None           ✅ final_transcript = "שלום, אני צריך..."
❌ extracted_service = None          ✅ extracted_service = "פריצת לוטו"
❌ extracted_city = None             ✅ extracted_city = "בית שאן"
❌ Webhook uses realtime only        ✅ Webhook uses high-quality offline


┌─────────────────────────────────────────────────────────────────────────────┐
│                     🔍 FAILURE SCENARIOS & HANDLING                         │
└─────────────────────────────────────────────────────────────────────────────┘

1. DOWNLOAD FAILS (404, timeout, network error)
   └─→ audio_file = None
       └─→ Skip Whisper transcription
           └─→ final_transcript = None
               └─→ Webhook uses realtime transcript
                   └─→ ✅ Graceful degradation, no data loss


2. WHISPER TRANSCRIPTION FAILS (API error, timeout)
   └─→ Exception caught
       └─→ final_transcript = None
           └─→ Log: "Post-call processing failed"
               └─→ Webhook uses realtime transcript
                   └─→ ✅ Graceful degradation, no data loss


3. WHISPER RETURNS EMPTY/INVALID TRANSCRIPT
   └─→ Check: len(final_transcript.strip()) < 10
       └─→ final_transcript = None
           └─→ Log: "Empty transcript - NOT updating"
               └─→ Webhook uses realtime transcript
                   └─→ ✅ Prevents garbage data in database


4. RECORDING NOT READY YET (Twilio delay)
   └─→ First attempt: 404 error
       └─→ Webhook waits (2 retries × 5 sec)
           └─→ Second attempt: May succeed
               └─→ If still fails: Use realtime
                   └─→ ✅ Retry mechanism with fallback


5. NO REALTIME TRANSCRIPT AVAILABLE
   └─→ full_conversation = ""
       └─→ Webhook waits for offline
           └─→ Uses final_transcript if available
               └─→ ✅ Offline becomes primary source


┌─────────────────────────────────────────────────────────────────────────────┐
│                        📈 QUALITY COMPARISON                                │
└─────────────────────────────────────────────────────────────────────────────┘

REALTIME TRANSCRIPT:              OFFLINE TRANSCRIPT (Whisper):
───────────────────────────       ──────────────────────────────────────
• Low latency (~200-500ms)        • High latency (10-30 sec after call)
• Streaming, real-time            • Batch processing, post-call
• Good for Hebrew                 • Excellent for Hebrew
• Some transcription errors       • Higher accuracy
• 1500-2000 chars typical         • 1800-2500 chars typical
• Used during call                • Used in webhook/reporting
• NoiseGate may clip audio        • Full audio processed
• Model: gpt-4o-realtime          • Model: whisper-1 (large-v3)

BEST PRACTICE:
─────────────
Use realtime during call for low latency
Use offline in webhook for accuracy
✅ System now does BOTH automatically!


┌─────────────────────────────────────────────────────────────────────────────┐
│                    🎓 TECHNICAL ARCHITECTURE                                │
└─────────────────────────────────────────────────────────────────────────────┘

COMPONENTS:

1. Recording Worker
   • Language: Python
   • Framework: Threading (background daemon)
   • Queue: queue.Queue (FIFO)
   • Concurrency: Single worker, sequential processing
   • Persistence: PostgreSQL (SQLAlchemy ORM)

2. Download Handler
   • HTTP Client: requests library
   • Auth: Basic Auth (Twilio credentials)
   • Timeout: 20 seconds
   • Streaming: Yes (stream=True)
   • Retry: No (single attempt, graceful failure)

3. Transcription Engine
   • Provider: OpenAI Whisper API
   • Model: whisper-1 (large-v3)
   • Language: Hebrew (he)
   • Format: MP3 input → Text output
   • Average latency: 10-15 seconds

4. Extraction Engine
   • Provider: OpenAI GPT-4
   • Task: Named Entity Recognition (NER)
   • Entities: service_type, city
   • Context: Business prompt + transcript
   • Output: JSON with confidence score

5. Database Schema
   • Table: call_log
   • Fields:
     - call_sid (PK, indexed)
     - final_transcript (TEXT, nullable)
     - extracted_service (VARCHAR, nullable)
     - extracted_city (VARCHAR, nullable)
     - extraction_confidence (FLOAT, nullable)
     - transcription (TEXT, nullable, legacy)
     - summary (TEXT, nullable)
     - created_at / updated_at (TIMESTAMP)

6. Webhook System
   • Trigger: Call end + finalization
   • Timing: Waits for offline processing (2 retries)
   • Format: JSON payload
   • Delivery: Async HTTP POST
   • Retry: Yes (webhook service handles)


┌─────────────────────────────────────────────────────────────────────────────┐
│                         🚀 DEPLOYMENT NOTES                                 │
└─────────────────────────────────────────────────────────────────────────────┘

ENVIRONMENT VARIABLES REQUIRED:
• TWILIO_ACCOUNT_SID      (Twilio account identifier)
• TWILIO_AUTH_TOKEN       (Twilio API authentication)
• OPENAI_API_KEY          (For Whisper + GPT-4)

SYSTEM REQUIREMENTS:
• Python 3.8+
• PostgreSQL 12+
• Network access to:
  - api.twilio.com (HTTPS, port 443)
  - api.openai.com (HTTPS, port 443)

DISK SPACE:
• Recordings stored temporarily in server/recordings/
• Average file size: ~200KB per minute of call
• Cleanup: Auto-deleted after 7 days (separate job)

PERFORMANCE:
• Worker processes 1 recording at a time (sequential)
• Average processing time: 20-40 seconds per call
• No blocking of main app (background thread)
• Queue size unlimited (memory bounded)

MONITORING:
• Logs: stdout + file logger
• Metrics: Turn around time, success rate
• Alerts: 404 errors, processing failures
• Health: Worker alive check (heartbeat)
