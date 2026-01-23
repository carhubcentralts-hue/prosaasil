# Live Voice Chat - Implementation Guide

## Overview
Browser-based live voice chat feature in Prompt Studio. Allows real-time voice conversations with AI directly in the browser without any phone infrastructure.

## 🎯 Key Features

### Web App Only
- NO phone calls
- NO Twilio integration
- NO dialing or phone numbers
- Browser-only: microphone → STT → OpenAI Chat → TTS → speakers

### Architecture

#### Frontend (LiveCallCard Component)
- **Location**: `client/src/components/settings/LiveCallCard.tsx`
- **UI Components**:
  - Main control button: ▶️ "התחל שיחה" / ⏹️ "עצור שיחה"
  - Status indicator: 🟢 Listening / 🟡 Processing / 🔵 Speaking
  - Conversation display showing user/AI exchanges
  - Error messages with clear Hebrew explanations

#### Voice Activity Detection (VAD)
Client-side implementation using Web Audio API:
- **Noise calibration**: First 1.5 seconds to establish noise floor
- **Dynamic threshold**: `noise_floor × 2.2`
- **Silence detection**: 700ms of silence triggers end-of-speech
- **RMS calculation**: Every 20ms for real-time monitoring

#### Audio Pipeline
```
User speaks → VAD detects end → STT (Whisper) → 
OpenAI Chat (brain) → TTS (OpenAI/Gemini) → 
Audio playback → Auto-return to listening
```

### Backend API Endpoints

#### POST /api/live_call/stt
Speech-to-Text conversion using OpenAI Whisper

**Request**:
```json
{
  "audio": "base64-encoded audio data",
  "format": "webm"
}
```

**Response**:
```json
{
  "text": "המשתמש אמר...",
  "language": "he"
}
```

#### POST /api/live_call/chat
Chat processing with OpenAI (brain is always OpenAI)

**Request**:
```json
{
  "text": "user's transcribed text",
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**Response**:
```json
{
  "response": "AI's response text",
  "conversation_id": "live_call_123"
}
```

#### POST /api/live_call/tts
Text-to-Speech synthesis using saved voice settings

**Request**:
```json
{
  "text": "text to synthesize"
}
```

**Response**: Binary audio data (MP3)
- Content-Type: audio/mpeg
- Uses saved TTS provider (OpenAI or Gemini)
- Uses saved voice ID and speed settings

## 🔧 Configuration

### Settings Integration
The live call feature uses settings saved in Prompt Studio:
- **Prompt**: Business prompt from `BusinessSettings` (channel: 'calls')
- **TTS Provider**: `tts_provider` field (openai or gemini)
- **Voice ID**: `voice_id` field
- **Speed**: `tts_speed` field
- **Language**: `tts_language` field

### Brain (Chat Model)
- **Always OpenAI**: gpt-4o-mini model
- Uses saved prompt from Prompt Studio
- Maintains conversation context
- Max tokens: 500 per response

### Voice Providers

#### OpenAI TTS
- Default provider
- Uses existing voice configuration
- Fast and reliable
- Hebrew support

#### Gemini TTS
- Requires `GEMINI_API_KEY` environment variable
- Clear error if key not configured: "Gemini TTS unavailable - API key not configured"
- Uses Google Cloud Text-to-Speech
- Hebrew voices available

## 🔒 Security

### Authentication
- All endpoints require authentication (`@require_api_auth`)
- Uses Flask session for business_id
- CSRF protection exempted for API endpoints

### Input Validation
- Maximum audio size: 10MB
- Maximum text length: 2000 characters
- Audio format validation
- Base64 decoding validation

### Error Handling
- Generic error messages to clients
- Detailed logging server-side
- No API key leaks in responses
- Graceful degradation when Gemini unavailable

### Rate Limiting
- Rate limiter integration ready
- Prevents abuse of expensive operations
- STT/TTS/Chat all rate-limited

## 📱 Mobile Support

### Responsive Design
- Full RTL support
- Minimum 48px touch targets
- Optimized for mobile browsers
- Works on Chrome, Safari, Firefox
- iOS and Android compatible

### Browser Compatibility
- Chrome: ✅ Full support
- Safari: ✅ Full support
- Firefox: ✅ Full support
- Edge: ✅ Full support
- Mobile browsers: ✅ Full support

### Requirements
- Microphone access required
- HTTPS required for getUserMedia (production)
- Modern browser with Web Audio API support

## 🚀 Usage

### User Flow
1. Navigate to Prompt Studio → "שיחה חיה" tab
2. Click "התחל שיחה" button
3. Grant microphone permissions
4. System calibrates noise floor (1.5s)
5. Start speaking - status shows 🟢 "מקשיב..."
6. Stop speaking - VAD automatically detects end
7. Status changes to 🟡 "מעבד..." during STT/Chat/TTS
8. Status changes to 🔵 "מדבר..." during audio playback
9. Automatically returns to 🟢 "מקשיב..." after response
10. Conversation continues until user clicks "עצור שיחה"

### Conversation Context
- Maintains full conversation history
- Sends context to OpenAI for coherent dialogue
- History displayed in UI with alternating colors
- User messages: Blue background
- AI responses: Green background

## 🐛 Troubleshooting

### Microphone Not Working
- Check browser permissions
- Ensure HTTPS in production
- Verify no other app using microphone
- Try refreshing the page

### No Audio Output
- Check browser audio permissions
- Verify speakers/headphones connected
- Check system volume
- Verify TTS provider configured

### Gemini TTS Error
- Check `GEMINI_API_KEY` is set in environment
- Verify key is valid
- Check `DISABLE_GOOGLE` is not set to true
- Fallback to OpenAI if needed

### VAD Too Sensitive
- Adjust `VAD_NOISE_MULTIPLIER` (default: 2.2)
- Increase `VAD_SILENCE_THRESHOLD` (default: 700ms)
- Ensure quiet environment during calibration

### Conversation Not Flowing
- Check OpenAI API key
- Verify business has saved prompt
- Check network connectivity
- Review browser console for errors

## 📝 Development Notes

### Files Modified
- `server/routes_live_call.py` - NEW: API endpoints
- `server/app_factory.py` - Register live_call_bp
- `client/src/components/settings/LiveCallCard.tsx` - NEW: UI component
- `client/src/pages/Admin/PromptStudioPage.tsx` - Integration

### Dependencies Used
- **Backend**: Flask, OpenAI SDK, TTS Provider service
- **Frontend**: React, Lucide icons, HTTP service
- **Browser APIs**: getUserMedia, Web Audio API, MediaRecorder

### Testing Checklist
- [ ] Microphone access works
- [ ] VAD detects speech correctly
- [ ] STT transcribes Hebrew accurately
- [ ] Chat responds coherently
- [ ] TTS audio plays correctly
- [ ] Conversation context maintained
- [ ] Error handling works
- [ ] Mobile responsive
- [ ] RTL layout correct
- [ ] Gemini provider works when configured

## 🎓 Technical Details

### VAD Algorithm
```javascript
1. Calibration Phase (1.5s):
   - Sample RMS every 20ms
   - Calculate average = noise_floor
   
2. Detection Phase:
   - Calculate RMS every 20ms
   - If RMS > noise_floor × 2.2:
     - Mark as speech
     - Update last_speech_time
   - If silence > 700ms:
     - Trigger end-of-speech
     - Process audio
```

### Audio Format
- Recording: audio/webm with Opus codec
- Transmission: Base64-encoded
- STT: Supports webm, ogg, wav, mp3
- TTS Output: MP3 format
- Playback: HTML5 Audio element

### OpenAI Integration
- STT Model: whisper-1
- Chat Model: gpt-4o-mini
- TTS Model: tts-1
- Language: Hebrew (he)
- Temperature: 0.7

## 🔄 Future Enhancements

### Potential Improvements
- [ ] Add recording history/playback
- [ ] Support for multiple languages
- [ ] Voice command shortcuts
- [ ] Background noise suppression tuning
- [ ] Visual waveform display
- [ ] Session persistence/resume
- [ ] Export conversation transcript
- [ ] Custom VAD sensitivity settings
- [ ] Push-to-talk mode option
- [ ] WebSocket for lower latency

### Performance Optimizations
- [ ] Audio chunk streaming
- [ ] Parallel STT/TTS processing
- [ ] Response caching for common phrases
- [ ] WebRTC for reduced latency
- [ ] Server-side VAD option

## 📄 License
Part of the ProSaaSil CRM system.
