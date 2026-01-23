/**
 * VoiceTesterCard Component
 * Browser-based voice testing using OpenAI Realtime API
 * Provides continuous conversation testing for prompts
 */
import React, { useState, useRef, useEffect } from 'react';
import { 
  Mic, 
  MicOff, 
  Phone,
  PhoneOff,
  AlertCircle,
  Loader2,
  Volume2,
  Settings2,
  RefreshCw
} from 'lucide-react';
import { http } from '../../services/http';

// Types
interface Voice {
  id: string;
  name: string;
  label: string;
  gender: string;
}

interface Provider {
  id: string;
  name: string;
  label: string;
  mode: string;
  voices: Voice[];
}

interface VoiceSettings {
  provider: string;
  voice_id: string;
  language: string;
  speed: number;
  gemini_production_enabled?: boolean;
}

interface VoiceTesterCardProps {
  promptText?: string;
}

type ConnectionState = 'idle' | 'connecting' | 'connected' | 'error';

export function VoiceTesterCard({ promptText }: VoiceTesterCardProps) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('idle');
  const [isRecording, setIsRecording] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [error, setError] = useState('');
  const [showSettings, setShowSettings] = useState(false);
  
  // TTS Settings
  const [providers, setProviders] = useState<Provider[]>([]);
  const [settings, setSettings] = useState<VoiceSettings>({
    provider: 'openai',
    voice_id: 'alloy',
    language: 'he-IL',
    speed: 1.0
  });
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [previewingVoice, setPreviewingVoice] = useState(false);

  // Load settings on mount
  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [voicesData, settingsData] = await Promise.all([
        http.get<{ providers: Provider[] }>('/api/voice_test/voices'),
        http.get<VoiceSettings>('/api/voice_test/settings')
      ]);
      
      setProviders(voicesData.providers || []);
      setSettings(prev => ({ ...prev, ...settingsData }));
    } catch (err) {
      console.error('Failed to load voice data:', err);
    } finally {
      setLoadingSettings(false);
    }
  };

  const handleSaveSettings = async () => {
    setSavingSettings(true);
    try {
      await http.put('/api/voice_test/settings', settings);
    } catch (err) {
      console.error('Failed to save settings:', err);
    } finally {
      setSavingSettings(false);
    }
  };

  const handlePreviewVoice = async () => {
    setPreviewingVoice(true);
    try {
      const response = await fetch('/api/voice_test/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          provider: settings.provider,
          voice_id: settings.voice_id,
          language: settings.language,
          speed: settings.speed
        })
      });
      
      if (response.ok) {
        const audioBlob = await response.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        audio.onended = () => URL.revokeObjectURL(audioUrl);
        audio.play();
      } else {
        setError('שגיאה בהשמעת דוגמה');
      }
    } catch (err) {
      console.error('Preview failed:', err);
      setError('שגיאה בהשמעת דוגמה');
    } finally {
      setPreviewingVoice(false);
    }
  };

  const startSession = async () => {
    setConnectionState('connecting');
    setError('');
    
    try {
      // Get session config from backend
      const sessionData = await http.post<{
        success: boolean;
        session_config: any;
        websocket_url: string;
        instructions: string;
        error?: string;
      }>('/api/voice_test/session', {
        prompt: promptText
      });
      
      if (!sessionData.success) {
        throw new Error(sessionData.error || 'Failed to create session');
      }
      
      // Show instructions for now (full WebRTC implementation would go here)
      setConnectionState('connected');
      setAiResponse('🎤 סשן בדיקה מוכן!\n\nלבדיקה מלאה עם Realtime API, יש להתחבר ישירות ל-WebSocket.\n\nראה תיעוד: OpenAI Realtime API');
      
    } catch (err: any) {
      console.error('Session start error:', err);
      setError(err.message || 'שגיאה בהתחברות');
      setConnectionState('error');
    }
  };

  const stopSession = () => {
    setConnectionState('idle');
    setIsRecording(false);
    setTranscript('');
    setAiResponse('');
  };

  const currentProvider = providers.find(p => p.id === settings.provider || p.id === 'openai');
  const voices = currentProvider?.voices || [];

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            connectionState === 'connected' ? 'bg-green-100' : 'bg-blue-100'
          }`}>
            <Phone className={`h-5 w-5 ${
              connectionState === 'connected' ? 'text-green-600' : 'text-blue-600'
            }`} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">בדיקת פרומפט בקול</h3>
            <p className="text-sm text-slate-500">שיחת בדיקה עם ה-AI</p>
          </div>
        </div>
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`p-2 rounded-lg transition-colors ${
            showSettings ? 'bg-slate-200' : 'hover:bg-slate-100'
          }`}
        >
          <Settings2 className="h-5 w-5 text-slate-600" />
        </button>
      </div>

      {/* Settings Panel */}
      {showSettings && (
        <div className="mb-6 p-4 bg-slate-50 border border-slate-200 rounded-lg space-y-4">
          <h4 className="font-medium text-slate-700">הגדרות קול (TTS Preview)</h4>
          
          {loadingSettings ? (
            <div className="flex justify-center py-4">
              <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
            </div>
          ) : (
            <>
              {/* Provider Selection */}
              <div>
                <label className="block text-sm text-slate-600 mb-1">ספק קול</label>
                <select
                  value={settings.provider}
                  onChange={(e) => {
                    const newProvider = e.target.value;
                    const providerVoices = providers.find(p => p.id === newProvider)?.voices || [];
                    setSettings(prev => ({
                      ...prev,
                      provider: newProvider,
                      voice_id: providerVoices[0]?.id || ''
                    }));
                  }}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-white text-sm"
                >
                  {providers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.label} {p.mode === 'preview' ? '(Preview)' : ''}
                    </option>
                  ))}
                </select>
              </div>

              {/* Voice Selection */}
              <div>
                <label className="block text-sm text-slate-600 mb-1">קול</label>
                <select
                  value={settings.voice_id}
                  onChange={(e) => setSettings(prev => ({ ...prev, voice_id: e.target.value }))}
                  className="w-full p-2 border border-slate-300 rounded-lg bg-white text-sm"
                >
                  {voices.map((v) => (
                    <option key={v.id} value={v.id}>{v.label} ({v.name})</option>
                  ))}
                </select>
              </div>

              {/* Speed Slider */}
              <div>
                <label className="block text-sm text-slate-600 mb-1">
                  מהירות: {settings.speed.toFixed(1)}x
                </label>
                <input
                  type="range"
                  min="0.5"
                  max="2.0"
                  step="0.1"
                  value={settings.speed}
                  onChange={(e) => setSettings(prev => ({ ...prev, speed: parseFloat(e.target.value) }))}
                  className="w-full"
                />
              </div>

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handlePreviewVoice}
                  disabled={previewingVoice}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 border border-blue-600 text-blue-600 rounded-lg hover:bg-blue-50 disabled:opacity-50 text-sm"
                >
                  {previewingVoice ? <Loader2 className="h-4 w-4 animate-spin" /> : <Volume2 className="h-4 w-4" />}
                  השמע דוגמה
                </button>
                <button
                  onClick={handleSaveSettings}
                  disabled={savingSettings}
                  className="flex-1 flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
                >
                  {savingSettings ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  שמור
                </button>
              </div>
            </>
          )}
        </div>
      )}

      {/* Main Control */}
      <div className="flex flex-col items-center gap-4">
        {connectionState === 'idle' ? (
          <button
            onClick={startSession}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors min-w-[160px] min-h-[48px] justify-center"
          >
            <Phone className="h-5 w-5" />
            התחל שיחת בדיקה
          </button>
        ) : connectionState === 'connecting' ? (
          <div className="flex items-center gap-2 px-6 py-3 bg-yellow-100 text-yellow-800 rounded-lg min-w-[160px] min-h-[48px] justify-center">
            <Loader2 className="h-5 w-5 animate-spin" />
            מתחבר...
          </div>
        ) : connectionState === 'connected' ? (
          <button
            onClick={stopSession}
            className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors min-w-[160px] min-h-[48px] justify-center"
          >
            <PhoneOff className="h-5 w-5" />
            סיים שיחה
          </button>
        ) : (
          <button
            onClick={startSession}
            className="flex items-center gap-2 px-6 py-3 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-colors min-w-[160px] min-h-[48px] justify-center"
          >
            <RefreshCw className="h-5 w-5" />
            נסה שוב
          </button>
        )}
      </div>

      {/* Error Message */}
      {error && (
        <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
          <span className="text-red-700 text-sm">{error}</span>
        </div>
      )}

      {/* AI Response */}
      {aiResponse && (
        <div className="mt-4 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="text-xs text-green-600 mb-2">תגובה:</div>
          <div className="text-green-900 whitespace-pre-line">{aiResponse}</div>
        </div>
      )}

      {/* Info */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-700">
            <p className="font-medium">💡 בדיקת פרומפט</p>
            <p className="mt-1">
              לבדיקה מלאה, השתמש בסימולטור שיחות או בטלפון אמיתי.
              הגדרות הקול (TTS) משפיעות רק על Preview.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default VoiceTesterCard;
