/**
 * LiveCallCard Component
 * Browser-based voice chat (Web App only)
 * Real-time voice conversation directly in browser using WebAudio
 * 
 * 🎯 Purpose:
 * - Live voice chat in Prompt Studio
 * - NO phone calls, NO Twilio, NO dialing
 * - Browser-only: microphone → STT → OpenAI Chat → TTS → speakers
 * 
 * 🔧 Features:
 * - Client-side VAD (Voice Activity Detection)
 * - Automatic end-of-speech detection
 * - Continuous conversation loop
 * - Uses saved Prompt Studio settings
 * 
 * 📱 Mobile Support:
 * - Full RTL
 * - Minimum 48px touch targets
 * - Responsive design
 */
import React, { useState, useRef, useEffect } from 'react';
import { 
  Mic, 
  Square,
  Play,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { http } from '../../services/http';

// Types
type ConnectionState = 'idle' | 'listening' | 'processing' | 'speaking' | 'error';

interface ConversationTurn {
  userSaid: string;
  aiSaid: string;
  timestamp: number;
}

export function LiveCallCard() {
  const [state, setState] = useState<ConnectionState>('idle');
  const [error, setError] = useState('');
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [conversationHistory, setConversationHistory] = useState<any[]>([]);
  
  // Audio refs
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const vadTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const noiseFloorRef = useRef<number>(0);
  const isRecordingRef = useRef<boolean>(false);
  const audioPlayerRef = useRef<HTMLAudioElement | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  
  // VAD Configuration
  const VAD_SILENCE_THRESHOLD = 700; // ms of silence to trigger end of speech
  const VAD_CALIBRATION_TIME = 1500; // ms to calibrate noise floor
  const VAD_NOISE_MULTIPLIER = 2.2; // Dynamic threshold multiplier
  const VAD_CHECK_INTERVAL = 20; // ms between RMS checks

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopSession();
    };
  }, []);

  /**
   * Start live call session
   */
  const startSession = async () => {
    setError('');
    setState('listening');
    setConversation([]);
    setConversationHistory([]);
    
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });
      
      mediaStreamRef.current = stream;
      
      // Setup Web Audio API for VAD
      setupVAD(stream);
      
      // Start recording
      startRecording(stream);
      
    } catch (err: any) {
      console.error('Microphone access error:', err);
      setError('לא ניתן לגשת למיקרופון. אנא אפשר גישה במכשיר שלך.');
      setState('error');
    }
  };

  /**
   * Stop live call session
   * ⚠️ CRITICAL: Cancel all pending requests and stop all audio
   */
  const stopSession = () => {
    // 🔥 Abort any pending HTTP requests (STT, Chat, TTS)
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    // Stop all audio processing
    if (vadTimeoutRef.current) {
      clearTimeout(vadTimeoutRef.current);
      vadTimeoutRef.current = null;
    }
    
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }
    
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // 🔥 Stop audio playback immediately
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current.src = '';
      audioPlayerRef.current = null;
    }
    
    analyserRef.current = null;
    audioChunksRef.current = [];
    isRecordingRef.current = false;
    
    setState('idle');
    setCurrentTranscript('');
  };

  /**
   * Setup Voice Activity Detection (VAD)
   */
  const setupVAD = (stream: MediaStream) => {
    const audioContext = new AudioContext();
    audioContextRef.current = audioContext;
    
    const source = audioContext.createMediaStreamSource(stream);
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;
    analyser.smoothingTimeConstant = 0.8;
    
    source.connect(analyser);
    analyserRef.current = analyser;
    
    // Calibrate noise floor
    calibrateNoiseFloor(analyser);
  };

  /**
   * Calibrate noise floor (first 1.5 seconds)
   */
  const calibrateNoiseFloor = (analyser: AnalyserNode) => {
    const samples: number[] = [];
    const startTime = Date.now();
    
    const calibrate = () => {
      if (Date.now() - startTime >= VAD_CALIBRATION_TIME) {
        // Calculate average noise floor
        const avgNoise = samples.reduce((a, b) => a + b, 0) / samples.length;
        noiseFloorRef.current = avgNoise;
        console.log('[VAD] Noise floor calibrated:', avgNoise);
        
        // Start monitoring for speech
        startVADMonitoring();
        return;
      }
      
      const rms = calculateRMS(analyser);
      samples.push(rms);
      
      setTimeout(calibrate, VAD_CHECK_INTERVAL);
    };
    
    calibrate();
  };

  /**
   * Calculate RMS (Root Mean Square) audio level
   */
  const calculateRMS = (analyser: AnalyserNode): number => {
    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(dataArray);
    
    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const normalized = (dataArray[i] - 128) / 128;
      sum += normalized * normalized;
    }
    
    return Math.sqrt(sum / dataArray.length);
  };

  /**
   * Monitor audio for speech/silence
   */
  const startVADMonitoring = () => {
    if (!analyserRef.current) return;
    
    let lastSpeechTime = Date.now();
    let isSpeaking = false;
    
    const threshold = noiseFloorRef.current * VAD_NOISE_MULTIPLIER;
    
    const monitor = () => {
      if (!analyserRef.current || !isRecordingRef.current) return;
      
      const rms = calculateRMS(analyserRef.current);
      const now = Date.now();
      
      if (rms > threshold) {
        // Speech detected
        lastSpeechTime = now;
        if (!isSpeaking) {
          isSpeaking = true;
          console.log('[VAD] Speech started');
        }
      } else {
        // Silence detected
        if (isSpeaking && now - lastSpeechTime > VAD_SILENCE_THRESHOLD) {
          // End of speech
          isSpeaking = false;
          console.log('[VAD] Speech ended');
          handleEndOfSpeech();
          return; // Stop monitoring, will restart after processing
        }
      }
      
      vadTimeoutRef.current = setTimeout(monitor, VAD_CHECK_INTERVAL);
    };
    
    monitor();
  };

  /**
   * Start recording audio
   */
  const startRecording = (stream: MediaStream) => {
    audioChunksRef.current = [];
    isRecordingRef.current = true;
    
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm;codecs=opus'
    });
    
    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunksRef.current.push(event.data);
      }
    };
    
    mediaRecorder.start();
    mediaRecorderRef.current = mediaRecorder;
  };

  /**
   * Handle end of speech (VAD triggered)
   */
  const handleEndOfSpeech = async () => {
    if (!isRecordingRef.current) return;
    
    isRecordingRef.current = false;
    setState('processing');
    
    // Stop recording
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      
      // Wait for data to be available
      await new Promise(resolve => {
        if (mediaRecorderRef.current) {
          mediaRecorderRef.current.onstop = resolve;
        }
      });
    }
    
    // Get audio blob
    const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
    audioChunksRef.current = [];
    
    // Process audio
    await processAudio(audioBlob);
  };

  /**
   * Process audio through STT → Chat → TTS pipeline
   * ⚠️ CRITICAL: Handles errors and returns to listening or stops cleanly
   */
  const processAudio = async (audioBlob: Blob) => {
    // Create new abort controller for this processing cycle
    abortControllerRef.current = new AbortController();
    
    try {
      // Step 1: STT (Speech-to-Text)
      const transcript = await speechToText(audioBlob);
      if (!transcript || !transcript.trim()) {
        // No speech detected, restart listening
        console.log('[LIVE_CALL] No speech detected, restarting...');
        restartListening();
        return;
      }
      
      setCurrentTranscript(transcript);
      
      // Step 2: Chat (OpenAI)
      setState('processing');
      const aiResponse = await chatWithAI(transcript);
      
      // Step 3: TTS (Text-to-Speech)
      setState('speaking');
      await textToSpeech(aiResponse);
      
      // Add to conversation history
      setConversation(prev => [...prev, {
        userSaid: transcript,
        aiSaid: aiResponse,
        timestamp: Date.now()
      }]);
      
      // Update conversation history for context
      setConversationHistory(prev => [
        ...prev,
        { role: 'user', content: transcript },
        { role: 'assistant', content: aiResponse }
      ]);
      
      setCurrentTranscript('');
      
      // Step 4: Return to listening
      restartListening();
      
    } catch (err: any) {
      console.error('Processing error:', err);
      
      // Check if this was an abort (user stopped session)
      if (err.name === 'AbortError') {
        console.log('[LIVE_CALL] Request aborted by user');
        return; // Don't show error, session already stopped
      }
      
      // Show error but try to recover
      const errorMessage = err.message || 'שגיאה בעיבוד השיחה';
      setError(errorMessage);
      
      // 🔥 CRITICAL: Return to listening after 3 seconds, or stop if no stream
      setTimeout(() => {
        if (mediaStreamRef.current) {
          console.log('[LIVE_CALL] Recovering from error, restarting listening...');
          setError('');
          restartListening();
        } else {
          console.log('[LIVE_CALL] Cannot recover, no media stream');
          setState('idle');
        }
      }, 3000);
    } finally {
      // Clear abort controller
      abortControllerRef.current = null;
    }
  };

  /**
   * Restart listening after processing
   */
  const restartListening = () => {
    if (!mediaStreamRef.current) {
      setState('error');
      setError('חיבור למיקרופון אבד');
      return;
    }
    
    setState('listening');
    audioChunksRef.current = [];
    isRecordingRef.current = true;
    
    // Restart MediaRecorder
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.start();
    }
    
    // Restart VAD monitoring
    startVADMonitoring();
  };

  /**
   * Convert speech to text using OpenAI Whisper
   * ⚠️ Uses AbortController for cancellation
   */
  const speechToText = async (audioBlob: Blob): Promise<string> => {
    // Convert blob to base64
    const arrayBuffer = await audioBlob.arrayBuffer();
    const base64Audio = btoa(
      new Uint8Array(arrayBuffer).reduce((data, byte) => data + String.fromCharCode(byte), '')
    );
    
    const response = await http.post<{ text: string; language: string }>(
      '/api/live_call/stt', 
      {
        audio: base64Audio,
        format: 'webm'
      },
      {
        signal: abortControllerRef.current?.signal
      }
    );
    
    return response.text;
  };

  /**
   * Chat with OpenAI (brain)
   * ⚠️ Uses AbortController for cancellation
   */
  const chatWithAI = async (text: string): Promise<string> => {
    const response = await http.post<{ response: string; conversation_id: string }>(
      '/api/live_call/chat', 
      {
        text,
        conversation_history: conversationHistory
      },
      {
        signal: abortControllerRef.current?.signal
      }
    );
    
    return response.response;
  };

  /**
   * Convert text to speech and play
   * ⚠️ Uses AbortController and pauses VAD during playback to prevent echo
   */
  const textToSpeech = async (text: string): Promise<void> => {
    const response = await fetch('/api/live_call/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ text }),
      signal: abortControllerRef.current?.signal
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'TTS failed');
    }
    
    const audioBlob = await response.blob();
    const audioUrl = URL.createObjectURL(audioBlob);
    
    // 🔥 CRITICAL: Pause VAD monitoring during TTS playback to prevent echo/feedback
    if (vadTimeoutRef.current) {
      clearTimeout(vadTimeoutRef.current);
      vadTimeoutRef.current = null;
    }
    
    // Play audio
    return new Promise((resolve, reject) => {
      const audio = new Audio(audioUrl);
      audioPlayerRef.current = audio;
      
      audio.onended = () => {
        URL.revokeObjectURL(audioUrl);
        audioPlayerRef.current = null;
        resolve();
      };
      
      audio.onerror = (err) => {
        URL.revokeObjectURL(audioUrl);
        audioPlayerRef.current = null;
        reject(new Error('Failed to play audio'));
      };
      
      audio.play().catch(reject);
    });
  };

  // Status indicator text
  const getStatusText = (): string => {
    switch (state) {
      case 'idle':
        return 'מוכן להתחלה';
      case 'listening':
        return '🟢 מקשיב...';
      case 'processing':
        return '🟡 מעבד...';
      case 'speaking':
        return '🔵 מדבר...';
      case 'error':
        return '❌ שגיאה';
      default:
        return '';
    }
  };

  // Status indicator color
  const getStatusColor = (): string => {
    switch (state) {
      case 'listening':
        return 'bg-green-100 text-green-700';
      case 'processing':
        return 'bg-yellow-100 text-yellow-700';
      case 'speaking':
        return 'bg-blue-100 text-blue-700';
      case 'error':
        return 'bg-red-100 text-red-700';
      default:
        return 'bg-slate-100 text-slate-700';
    }
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6" dir="rtl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
          state === 'listening' ? 'bg-green-100' : 
          state === 'processing' ? 'bg-yellow-100' :
          state === 'speaking' ? 'bg-blue-100' : 'bg-slate-100'
        }`}>
          <Mic className={`h-5 w-5 ${
            state === 'listening' ? 'text-green-600' : 
            state === 'processing' ? 'text-yellow-600' :
            state === 'speaking' ? 'text-blue-600' : 'text-slate-600'
          }`} />
        </div>
        <div>
          <h3 className="text-lg font-semibold text-slate-900">שיחה חיה</h3>
          <p className="text-sm text-slate-500">שיחה ישירה עם ה-AI בדפדפן</p>
        </div>
      </div>

      {/* Status Indicator */}
      <div className={`mb-6 px-4 py-3 rounded-lg font-medium text-center ${getStatusColor()}`}>
        {getStatusText()}
      </div>

      {/* Main Control Button */}
      <div className="flex justify-center mb-6">
        {state === 'idle' || state === 'error' ? (
          <button
            onClick={startSession}
            className="flex items-center gap-3 px-8 py-4 bg-green-600 text-white rounded-xl hover:bg-green-700 transition-colors min-h-[56px] min-w-[200px] justify-center font-semibold text-lg shadow-lg"
          >
            <Play className="h-6 w-6" />
            התחל שיחה
          </button>
        ) : (
          <button
            onClick={stopSession}
            className="flex items-center gap-3 px-8 py-4 bg-red-600 text-white rounded-xl hover:bg-red-700 transition-colors min-h-[56px] min-w-[200px] justify-center font-semibold text-lg shadow-lg"
          >
            <Square className="h-6 w-6" />
            עצור שיחה
          </button>
        )}
      </div>

      {/* Current Transcript */}
      {currentTranscript && (
        <div className="mb-4 p-3 bg-slate-50 border border-slate-200 rounded-lg">
          <div className="text-xs text-slate-500 mb-1">אתה אמרת:</div>
          <div className="text-slate-900">{currentTranscript}</div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2">
          <AlertCircle className="h-4 w-4 text-red-600 flex-shrink-0" />
          <span className="text-red-700 text-sm">{error}</span>
        </div>
      )}

      {/* Conversation History */}
      {conversation.length > 0 && (
        <div className="space-y-3 max-h-[400px] overflow-y-auto">
          <div className="text-sm font-medium text-slate-700 mb-2">היסטוריית שיחה:</div>
          {conversation.map((turn, index) => (
            <div key={index} className="space-y-2">
              {/* User said */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                <div className="text-xs text-blue-600 mb-1">אתה אמרת:</div>
                <div className="text-blue-900">{turn.userSaid}</div>
              </div>
              
              {/* AI said */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                <div className="text-xs text-green-600 mb-1">ה-AI ענה:</div>
                <div className="text-green-900">{turn.aiSaid}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Info */}
      <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <div className="flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
          <div className="text-sm text-blue-700">
            <p className="font-medium">💡 שיחה חיה בדפדפן</p>
            <p className="mt-1">
              לחץ "התחל שיחה" והתחל לדבר למיקרופון. המערכת תזהה אוטומטית מתי סיימת לדבר,
              תעבד את הדיבור שלך ותשיב בקול. השיחה תמשיך אוטומטית עד שתלחץ "עצור שיחה".
            </p>
            <p className="mt-2 text-xs">
              <strong>הערה:</strong> השיחה משתמשת בפרומפט והקול השמורים בהגדרות Prompt Studio.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default LiveCallCard;
