import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Bot, 
  Wand2, 
  Mic, 
  MicOff, 
  Volume2, 
  Play, 
  Square, 
  Settings2, 
  Save,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Loader2,
  ChevronDown,
  X
} from 'lucide-react';
import { http } from '../../services/http';
import { useAuth } from '../../features/auth/hooks';

// Types
interface Question {
  id: string;
  question: string;
  placeholder: string;
  required: boolean;
  type: 'text' | 'textarea' | 'select';
  options?: { value: string; label: string }[];
}

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
  voices: Voice[];
}

interface ConversationTurn {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

// VAD (Voice Activity Detection) state machine
type VADState = 'idle' | 'calibrating' | 'listening' | 'speaking' | 'processing' | 'playing';

// =====================================
// Prompt Builder Wizard Component
// =====================================
function PromptBuilderWizard({ onClose, onSave }: { onClose: () => void; onSave: (prompt: string, channel: string) => void }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatedPrompt, setGeneratedPrompt] = useState('');
  const [promptTitle, setPromptTitle] = useState('');
  const [promptSummary, setPromptSummary] = useState('');
  const [step, setStep] = useState<'questions' | 'preview'>('questions');
  const [selectedChannel, setSelectedChannel] = useState<'calls' | 'whatsapp'>('calls');

  useEffect(() => {
    loadQuestions();
  }, []);

  const loadQuestions = async () => {
    try {
      const data = await http.get<{ questions: Question[] }>('/api/ai/prompt_builder/questions');
      setQuestions(data.questions || []);
    } catch (err) {
      console.error('Failed to load questions:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await http.post<{ success: boolean; prompt_text: string; title: string; summary: string }>(
        '/api/ai/prompt_builder/generate',
        { answers }
      );
      
      if (result.success) {
        setGeneratedPrompt(result.prompt_text);
        setPromptTitle(result.title);
        setPromptSummary(result.summary);
        setStep('preview');
      }
    } catch (err) {
      console.error('Failed to generate prompt:', err);
      alert('שגיאה ביצירת הפרומפט');
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = () => {
    onSave(generatedPrompt, selectedChannel);
    onClose();
  };

  if (loading) {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl p-8 max-w-2xl w-full mx-4">
          <div className="flex items-center justify-center">
            <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
            <span className="mr-3 text-slate-600">טוען...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-200">
          <div className="flex items-center gap-2">
            <Wand2 className="h-6 w-6 text-purple-600" />
            <h2 className="text-xl font-bold text-slate-900">מחולל פרומפטים אוטומטי</h2>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-slate-100 rounded-lg transition-colors">
            <X className="h-5 w-5 text-slate-500" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {step === 'questions' ? (
            <div className="space-y-6">
              <p className="text-slate-600">ענה על השאלות הבאות כדי ליצור פרומפט מותאם אישית לעסק שלך</p>
              
              {questions.map((q) => (
                <div key={q.id} className="space-y-2">
                  <label className="block text-sm font-medium text-slate-700">
                    {q.question}
                    {q.required && <span className="text-red-500 mr-1">*</span>}
                  </label>
                  
                  {q.type === 'select' ? (
                    <select
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    >
                      <option value="">בחר...</option>
                      {q.options?.map((opt) => (
                        <option key={opt.value} value={opt.value}>{opt.label}</option>
                      ))}
                    </select>
                  ) : q.type === 'textarea' ? (
                    <textarea
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder={q.placeholder}
                      className="w-full p-3 border border-slate-300 rounded-lg resize-none h-24 focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    />
                  ) : (
                    <input
                      type="text"
                      value={answers[q.id] || ''}
                      onChange={(e) => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
                      placeholder={q.placeholder}
                      className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                    />
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-6">
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <h3 className="font-semibold text-purple-900 mb-2">{promptTitle}</h3>
                <p className="text-purple-700 text-sm">{promptSummary}</p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  הפרומפט שנוצר:
                </label>
                <textarea
                  value={generatedPrompt}
                  onChange={(e) => setGeneratedPrompt(e.target.value)}
                  className="w-full p-4 border border-slate-300 rounded-lg resize-none h-64 text-sm leading-relaxed focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שמור עבור ערוץ:
                </label>
                <div className="flex gap-4">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="channel"
                      value="calls"
                      checked={selectedChannel === 'calls'}
                      onChange={() => setSelectedChannel('calls')}
                      className="w-4 h-4 text-purple-600"
                    />
                    <span>שיחות טלפון</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="radio"
                      name="channel"
                      value="whatsapp"
                      checked={selectedChannel === 'whatsapp'}
                      onChange={() => setSelectedChannel('whatsapp')}
                      className="w-4 h-4 text-purple-600"
                    />
                    <span>WhatsApp</span>
                  </label>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-4 border-t border-slate-200 bg-slate-50">
          {step === 'questions' ? (
            <>
              <button
                onClick={onClose}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
              >
                ביטול
              </button>
              <button
                onClick={handleGenerate}
                disabled={generating || !answers.business_area}
                className="flex items-center gap-2 px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {generating ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    מייצר...
                  </>
                ) : (
                  <>
                    <Wand2 className="h-4 w-4" />
                    צור פרומפט
                  </>
                )}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setStep('questions')}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 transition-colors"
              >
                חזרה
              </button>
              <button
                onClick={handleSave}
                className="flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
              >
                <Save className="h-4 w-4" />
                שמור פרומפט
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// =====================================
// Voice Provider Settings Component
// =====================================
function VoiceProviderSettings() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [settings, setSettings] = useState({
    provider: 'openai',
    voice_id: 'alloy',
    language: 'he-IL',
    speed: 1.0
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewing, setPreviewing] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const [voicesData, settingsData] = await Promise.all([
        http.get<{ providers: Provider[] }>('/api/voice_test/voices'),
        http.get<typeof settings>('/api/voice_test/settings')
      ]);
      
      setProviders(voicesData.providers || []);
      setSettings(prev => ({ ...prev, ...settingsData }));
    } catch (err) {
      console.error('Failed to load voice data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await http.put('/api/voice_test/settings', settings);
      alert('הגדרות הקול נשמרו בהצלחה');
    } catch (err) {
      console.error('Failed to save settings:', err);
      alert('שגיאה בשמירת הגדרות');
    } finally {
      setSaving(false);
    }
  };

  const handlePreview = async () => {
    setPreviewing(true);
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
        audio.play();
        audio.onended = () => URL.revokeObjectURL(audioUrl);
      } else {
        alert('שגיאה בהשמעת דוגמה');
      }
    } catch (err) {
      console.error('Preview failed:', err);
      alert('שגיאה בהשמעת דוגמה');
    } finally {
      setPreviewing(false);
    }
  };

  const currentProvider = providers.find(p => p.id === settings.provider);
  const voices = currentProvider?.voices || [];

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <div className="flex items-center justify-center py-8">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6" dir="rtl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-indigo-100 rounded-lg flex items-center justify-center">
          <Settings2 className="h-5 w-5 text-indigo-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-slate-900">הגדרות קול</h3>
          <p className="text-sm text-slate-500">בחר ספק וקול לבדיקת פרומפטים</p>
        </div>
      </div>

      <div className="space-y-4">
        {/* Provider Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">ספק קול</label>
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
            className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          >
            {providers.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </div>

        {/* Voice Selection */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">קול</label>
          <select
            value={settings.voice_id}
            onChange={(e) => setSettings(prev => ({ ...prev, voice_id: e.target.value }))}
            className="w-full p-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
          >
            {voices.map((v) => (
              <option key={v.id} value={v.id}>{v.label} ({v.name})</option>
            ))}
          </select>
        </div>

        {/* Speed Slider */}
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            מהירות דיבור: {settings.speed.toFixed(1)}x
          </label>
          <input
            type="range"
            min="0.5"
            max="2.0"
            step="0.1"
            value={settings.speed}
            onChange={(e) => setSettings(prev => ({ ...prev, speed: parseFloat(e.target.value) }))}
            className="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer"
          />
        </div>

        {/* Actions */}
        <div className="flex gap-3 pt-4">
          <button
            onClick={handlePreview}
            disabled={previewing}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 border border-indigo-600 text-indigo-600 rounded-lg hover:bg-indigo-50 disabled:opacity-50 transition-colors"
          >
            {previewing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Volume2 className="h-4 w-4" />
            )}
            השמע דוגמה
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors"
          >
            {saving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            שמור
          </button>
        </div>
      </div>
    </div>
  );
}

// =====================================
// Voice Tester Component (Continuous Mode)
// =====================================
function VoiceTester() {
  const [vadState, setVadState] = useState<VADState>('idle');
  const [transcript, setTranscript] = useState('');
  const [aiResponse, setAiResponse] = useState('');
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [error, setError] = useState('');
  const [rmsLevel, setRmsLevel] = useState(0);
  const [prompt, setPrompt] = useState('');
  
  // Audio refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const animationFrameRef = useRef<number>(0);
  
  // VAD parameters
  const noiseFloorRef = useRef(0);
  const inSpeechRef = useRef(false);
  const silenceStartRef = useRef(0);
  const calibrationSamplesRef = useRef<number[]>([]);
  
  const CALIBRATION_TIME = 1500; // 1.5 seconds for noise calibration
  const SILENCE_THRESHOLD_MS = 700; // 700ms of silence to end utterance
  const NOISE_MULTIPLIER = 2.2;

  const startVAD = async () => {
    try {
      setError('');
      setVadState('calibrating');
      
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: { 
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      mediaStreamRef.current = stream;
      
      // Setup audio context
      audioContextRef.current = new AudioContext();
      const source = audioContextRef.current.createMediaStreamSource(stream);
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 512;
      source.connect(analyserRef.current);
      
      // Setup media recorder
      mediaRecorderRef.current = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      audioChunksRef.current = [];
      
      mediaRecorderRef.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunksRef.current.push(e.data);
        }
      };
      
      mediaRecorderRef.current.onstop = handleRecordingComplete;
      
      // Start calibration
      calibrationSamplesRef.current = [];
      const calibrationStart = Date.now();
      
      const calibrate = () => {
        if (Date.now() - calibrationStart < CALIBRATION_TIME) {
          const rms = calculateRMS();
          calibrationSamplesRef.current.push(rms);
          requestAnimationFrame(calibrate);
        } else {
          // Calculate noise floor
          const avgNoise = calibrationSamplesRef.current.reduce((a, b) => a + b, 0) / calibrationSamplesRef.current.length;
          noiseFloorRef.current = Math.max(avgNoise * NOISE_MULTIPLIER, 10); // Minimum threshold of 10
          
          // Start listening
          setVadState('listening');
          mediaRecorderRef.current?.start();
          startVADLoop();
        }
      };
      
      calibrate();
      
    } catch (err: any) {
      setError(err.message || 'שגיאה בהפעלת המיקרופון');
      setVadState('idle');
    }
  };

  const calculateRMS = () => {
    if (!analyserRef.current) return 0;
    
    const dataArray = new Uint8Array(analyserRef.current.frequencyBinCount);
    analyserRef.current.getByteTimeDomainData(dataArray);
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const val = (dataArray[i] - 128) / 128;
      sum += val * val;
    }
    
    return Math.sqrt(sum / dataArray.length) * 100;
  };

  const startVADLoop = () => {
    const loop = () => {
      if (vadState === 'idle') return;
      
      const rms = calculateRMS();
      setRmsLevel(rms);
      
      const threshold = noiseFloorRef.current;
      const now = Date.now();
      
      if (rms > threshold) {
        // Speech detected
        inSpeechRef.current = true;
        silenceStartRef.current = 0;
        setVadState('speaking');
      } else if (inSpeechRef.current) {
        // Was speaking, now silent
        if (silenceStartRef.current === 0) {
          silenceStartRef.current = now;
        } else if (now - silenceStartRef.current >= SILENCE_THRESHOLD_MS) {
          // End of utterance detected
          inSpeechRef.current = false;
          silenceStartRef.current = 0;
          
          // Stop recording and process
          if (mediaRecorderRef.current?.state === 'recording') {
            setVadState('processing');
            mediaRecorderRef.current.stop();
            return; // Don't continue the loop
          }
        }
      }
      
      animationFrameRef.current = requestAnimationFrame(loop);
    };
    
    animationFrameRef.current = requestAnimationFrame(loop);
  };

  const handleRecordingComplete = async () => {
    try {
      const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
      audioChunksRef.current = [];
      
      if (audioBlob.size < 1000) {
        // Too short, restart listening
        restartListening();
        return;
      }
      
      // Send to STT
      const formData = new FormData();
      formData.append('audio', audioBlob, 'audio.webm');
      
      const sttResponse = await fetch('/api/voice_test/stt', {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (!sttResponse.ok) {
        throw new Error('STT failed');
      }
      
      const sttData = await sttResponse.json();
      const userText = sttData.text;
      
      if (!userText || userText.trim().length < 2) {
        restartListening();
        return;
      }
      
      setTranscript(userText);
      
      // Add to conversation
      const newConversation = [...conversation, { role: 'user' as const, content: userText, timestamp: new Date() }];
      setConversation(newConversation);
      
      // Send to Chat API
      const chatResponse = await http.post<{ reply: string }>('/api/voice_test/chat', {
        message: userText,
        history: newConversation.slice(-10).map(t => ({ role: t.role, content: t.content })),
        prompt
      });
      
      const aiText = chatResponse.reply;
      setAiResponse(aiText);
      
      // Add AI response to conversation
      setConversation(prev => [...prev, { role: 'assistant', content: aiText, timestamp: new Date() }]);
      
      // Play TTS
      setVadState('playing');
      
      const ttsResponse = await fetch('/api/voice_test/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ text: aiText })
      });
      
      if (ttsResponse.ok) {
        const audioBlob = await ttsResponse.blob();
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio(audioUrl);
        
        audio.onended = () => {
          URL.revokeObjectURL(audioUrl);
          restartListening();
        };
        
        audio.onerror = () => {
          URL.revokeObjectURL(audioUrl);
          restartListening();
        };
        
        audio.play();
      } else {
        restartListening();
      }
      
    } catch (err: any) {
      console.error('Processing error:', err);
      setError(err.message || 'שגיאה בעיבוד');
      restartListening();
    }
  };

  const restartListening = () => {
    if (mediaStreamRef.current && vadState !== 'idle') {
      setVadState('listening');
      audioChunksRef.current = [];
      mediaRecorderRef.current?.start();
      startVADLoop();
    }
  };

  const stopVAD = () => {
    setVadState('idle');
    
    // Clean up
    if (animationFrameRef.current) {
      cancelAnimationFrame(animationFrameRef.current);
    }
    
    if (mediaRecorderRef.current?.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopVAD();
    };
  }, []);

  const getStateLabel = () => {
    switch (vadState) {
      case 'calibrating': return 'מכייל רעש רקע...';
      case 'listening': return 'מקשיב...';
      case 'speaking': return 'מזהה דיבור...';
      case 'processing': return 'מעבד...';
      case 'playing': return 'מדבר...';
      default: return 'מוכן';
    }
  };

  const getStateColor = () => {
    switch (vadState) {
      case 'calibrating': return 'text-yellow-600';
      case 'listening': return 'text-blue-600';
      case 'speaking': return 'text-green-600';
      case 'processing': return 'text-purple-600';
      case 'playing': return 'text-indigo-600';
      default: return 'text-slate-600';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6" dir="rtl">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
          <Mic className="h-5 w-5 text-green-600" />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-slate-900">בדיקת קול (רציף)</h3>
          <p className="text-sm text-slate-500">דבר עם ה-AI לבדיקת הפרומפט</p>
        </div>
      </div>

      {/* Custom Prompt Input */}
      <div className="mb-4">
        <label className="block text-sm font-medium text-slate-700 mb-2">
          פרומפט לבדיקה (אופציונלי - ישתמש בפרומפט העסק אם ריק)
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="הזן פרומפט לבדיקה או השאר ריק לשימוש בפרומפט העסק"
          className="w-full p-3 border border-slate-300 rounded-lg resize-none h-20 text-sm focus:ring-2 focus:ring-green-500 focus:border-green-500"
          disabled={vadState !== 'idle'}
        />
      </div>

      {/* Control Button */}
      <div className="flex items-center gap-4 mb-6">
        {vadState === 'idle' ? (
          <button
            onClick={startVAD}
            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors min-w-[48px] min-h-[48px]"
          >
            <Mic className="h-5 w-5" />
            התחל בדיקה
          </button>
        ) : (
          <button
            onClick={stopVAD}
            className="flex items-center gap-2 px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors min-w-[48px] min-h-[48px]"
          >
            <Square className="h-5 w-5" />
            עצור
          </button>
        )}
        
        {/* Status */}
        <div className={`flex items-center gap-2 ${getStateColor()}`}>
          {vadState !== 'idle' && (
            <div className="w-3 h-3 rounded-full bg-current animate-pulse" />
          )}
          <span className="font-medium">{getStateLabel()}</span>
        </div>
      </div>

      {/* RMS Meter */}
      {vadState !== 'idle' && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs text-slate-500">עוצמת קול</span>
            <span className="text-xs text-slate-500">{rmsLevel.toFixed(1)}</span>
          </div>
          <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-100 ${rmsLevel > noiseFloorRef.current ? 'bg-green-500' : 'bg-blue-400'}`}
              style={{ width: `${Math.min(rmsLevel * 2, 100)}%` }}
            />
          </div>
          <div className="text-xs text-slate-400 mt-1">
            סף רעש: {noiseFloorRef.current.toFixed(1)}
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-3 mb-4 flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600" />
          <span className="text-red-700 text-sm">{error}</span>
        </div>
      )}

      {/* Transcript & Response */}
      {(transcript || aiResponse) && (
        <div className="space-y-4 mt-6 border-t border-slate-200 pt-6">
          {transcript && (
            <div className="bg-slate-50 rounded-lg p-4">
              <div className="text-xs text-slate-500 mb-1">אתה אמרת:</div>
              <div className="text-slate-900">{transcript}</div>
            </div>
          )}
          
          {aiResponse && (
            <div className="bg-green-50 rounded-lg p-4">
              <div className="text-xs text-green-600 mb-1">AI ענה:</div>
              <div className="text-green-900">{aiResponse}</div>
            </div>
          )}
        </div>
      )}

      {/* Conversation Log */}
      {conversation.length > 0 && (
        <div className="mt-6 border-t border-slate-200 pt-6">
          <h4 className="text-sm font-medium text-slate-700 mb-3">היסטוריית שיחה</h4>
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {conversation.map((turn, i) => (
              <div 
                key={i}
                className={`text-sm p-2 rounded ${
                  turn.role === 'user' 
                    ? 'bg-slate-100 text-slate-700' 
                    : 'bg-green-100 text-green-700'
                }`}
              >
                <span className="font-medium">{turn.role === 'user' ? 'אתה: ' : 'AI: '}</span>
                {turn.content}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// =====================================
// Main Prompt Studio Page
// =====================================
export function PromptStudioPage() {
  const { user } = useAuth();
  const [activeTab, setActiveTab] = useState<'prompts' | 'builder' | 'tester'>('prompts');
  const [showBuilderWizard, setShowBuilderWizard] = useState(false);
  const [saving, setSaving] = useState(false);

  const handleSaveGeneratedPrompt = async (promptText: string, channel: string) => {
    setSaving(true);
    try {
      await http.post('/api/ai/prompt_builder/save', {
        prompt_text: promptText,
        channel,
        update_existing: true
      });
      alert('הפרומפט נשמר בהצלחה!');
    } catch (err) {
      console.error('Failed to save prompt:', err);
      alert('שגיאה בשמירת הפרומפט');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Bot className="h-7 w-7 text-purple-600" />
          <h1 className="text-2xl font-bold text-slate-900">סטודיו פרומפטים</h1>
        </div>
        <p className="text-slate-600">יצירה, עריכה ובדיקת פרומפטים לסוכן AI</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 mb-6">
        <button
          onClick={() => setActiveTab('prompts')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'prompts'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          פרומפטים
        </button>
        <button
          onClick={() => setActiveTab('builder')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'builder'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          מחולל פרומפטים
        </button>
        <button
          onClick={() => setActiveTab('tester')}
          className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'tester'
              ? 'border-purple-600 text-purple-600'
              : 'border-transparent text-slate-500 hover:text-slate-700'
          }`}
        >
          בדיקת קול
        </button>
      </div>

      {/* Tab Content */}
      {activeTab === 'prompts' && (
        <div className="space-y-6">
          {/* Quick Actions Card */}
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">פעולות מהירות</h3>
            <div className="flex flex-wrap gap-4">
              <button
                onClick={() => setShowBuilderWizard(true)}
                className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
              >
                <Wand2 className="h-4 w-4" />
                יצירת פרומפט אוטומטית
              </button>
              <button
                onClick={() => setActiveTab('tester')}
                className="flex items-center gap-2 px-4 py-2 border border-green-600 text-green-600 rounded-lg hover:bg-green-50 transition-colors"
              >
                <Mic className="h-4 w-4" />
                בדיקת פרומפט בקול
              </button>
            </div>
          </div>

          {/* Info Card */}
          <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
              <div>
                <h4 className="font-medium text-blue-900">טיפ: יצירת פרומפט אוטומטי</h4>
                <p className="text-blue-700 text-sm mt-1">
                  לחץ על "יצירת פרומפט אוטומטית" כדי לענות על שאלון קצר שיעזור ל-AI ליצור פרומפט מותאם אישית לעסק שלך.
                  לאחר מכן תוכל לבדוק אותו בקול בכרטיסייה "בדיקת קול".
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'builder' && (
        <div className="space-y-6">
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
            <div className="text-center py-12">
              <Wand2 className="h-16 w-16 text-purple-300 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-slate-900 mb-2">מחולל פרומפטים חכם</h3>
              <p className="text-slate-600 mb-6 max-w-md mx-auto">
                ענה על מספר שאלות קצרות על העסק שלך, והמערכת תיצור פרומפט מקצועי מותאם אישית.
              </p>
              <button
                onClick={() => setShowBuilderWizard(true)}
                className="flex items-center gap-2 px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors mx-auto"
              >
                <Wand2 className="h-5 w-5" />
                התחל ליצור פרומפט
              </button>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'tester' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <VoiceTester />
          <VoiceProviderSettings />
        </div>
      )}

      {/* Prompt Builder Wizard Modal */}
      {showBuilderWizard && (
        <PromptBuilderWizard
          onClose={() => setShowBuilderWizard(false)}
          onSave={handleSaveGeneratedPrompt}
        />
      )}
    </div>
  );
}

export default PromptStudioPage;
