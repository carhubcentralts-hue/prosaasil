/**
 * LiveCallCard Component
 * Browser-based voice chat with phone-call-style UI
 * Real-time voice conversation directly in browser using WebAudio
 * 
 * 🎯 Purpose:
 * - Live voice chat in Prompt Studio
 * - Phone-call-style UI: Timer, Mute, Speaker, Hangup
 * - Same logic as phone calls (no shortcuts)
 * 
 * 🔧 Features:
 * - Client-side VAD (Voice Activity Detection)
 * - Call timer (00:00 format)
 * - Mute/Unmute microphone
 * - Speaker/Audio boost
 * - Hangup button
 * 
 * 📱 Mobile Support:
 * - Full RTL
 * - Minimum 48px touch targets
 * - Responsive design
 */
import React, { useState, useRef, useEffect } from 'react';
import { 
  Mic, 
  MicOff,
  Volume2,
  VolumeX,
  Phone,
  PhoneOff,
  AlertCircle,
  Loader2
} from 'lucide-react';
import { http } from '../../services/http';

// Types
type ConnectionState = 'idle' | 'active' | 'error';

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
  const [isMuted, setIsMuted] = useState(false);
  const [isSpeakerOn, setIsSpeakerOn] = useState(true);
  const [callDuration, setCallDuration] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Timer
  const timerIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const callStartTimeRef = useRef<number>(0);
  
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

  // Timer effect
  useEffect(() => {
    if (state === 'active' && !timerIntervalRef.current) {
      callStartTimeRef.current = Date.now();
      timerIntervalRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - callStartTimeRef.current) / 1000);
        setCallDuration(elapsed);
      }, 1000);
    } else if (state !== 'active' && timerIntervalRef.current) {
      clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
      setCallDuration(0);
    }
    
    return () => {
      if (timerIntervalRef.current) {
        clearInterval(timerIntervalRef.current);
        timerIntervalRef.current = null;
      }
    };
  }, [state]);

  // Format timer display (MM:SS)
  const formatTimer = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

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
    setConversation([]);
    setConversationHistory([]);
    setIsMuted(false);
    setCallDuration(0);
    
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
      
      // Move to active state
      setState('active');
      
    } catch (err: any) {
      console.error('Microphone access error:', err);
      setError('לא ניתן לגשת למיקרופון. אנא אפשר גישה במכשיר שלך.');
      setState('error');
    }
  };

  /**
   * Toggle mute/unmute
   */
  const toggleMute = () => {
    if (mediaStreamRef.current) {
      const audioTracks = mediaStreamRef.current.getAudioTracks();
      audioTracks.forEach(track => {
        track.enabled = !track.enabled;
      });
      setIsMuted(!isMuted);
    }
  };

  /**
   * Toggle speaker on/off (audio boost)
   * Note: Actual audio output device control is limited in browsers.
   * This mainly serves as UI indicator for user awareness.
   */
  const toggleSpeaker = () => {
    setIsSpeakerOn(!isSpeakerOn);
    // Browser limitations: Cannot actually change output device
    // This is a UI indicator only
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
    setCallDuration(0);
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
    setIsProcessing(true);
    
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
        setIsProcessing(false);
        restartListening();
        return;
      }
      
      setCurrentTranscript(transcript);
      
      // Step 2: Chat (OpenAI or Gemini based on business settings)
      const aiResponse = await chatWithAI(transcript);
      
      // Step 3: TTS (OpenAI or Gemini - same logic as phone calls!)
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
      setIsProcessing(false);
      
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
      setIsProcessing(false);
      
      // 🔥 CRITICAL: Return to listening after 3 seconds if media stream still exists
      setTimeout(() => {
        const streamStillExists = mediaStreamRef.current !== null;
        const shouldRecover = streamStillExists && (state === 'active' || state === 'idle');
        
        if (shouldRecover && state === 'active') {
          console.log('[LIVE_CALL] Recovering from error, restarting listening...');
          setError('');
          restartListening();
        } else {
          console.log('[LIVE_CALL] Cannot recover - stopping call');
          if (streamStillExists) {
            stopSession(); // Clean shutdown
          }
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
    if (!mediaStreamRef.current || state !== 'active') {
      console.log('[LIVE_CALL] Cannot restart - no stream or not active');
      return;
    }
    
    setIsProcessing(false);
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

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden" dir="rtl">
      {/* Phone Call Style UI */}
      {state === 'idle' || state === 'error' ? (
        // Start Call Screen
        <div className="p-8">
          <div className="text-center mb-8">
            <div className="w-20 h-20 mx-auto mb-4 rounded-full bg-gradient-to-br from-green-400 to-green-600 flex items-center justify-center shadow-lg">
              <Phone className="h-10 w-10 text-white" />
            </div>
            <h3 className="text-2xl font-bold text-slate-900 mb-2">שיחה חיה</h3>
            <p className="text-slate-500">שיחה ישירה עם ה-AI בדפדפן</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0" />
              <span className="text-red-700">{error}</span>
            </div>
          )}

          {/* Start Button */}
          <button
            onClick={startSession}
            className="w-full flex items-center justify-center gap-3 px-8 py-5 bg-gradient-to-br from-green-500 to-green-600 text-white rounded-2xl hover:from-green-600 hover:to-green-700 transition-all shadow-lg hover:shadow-xl font-semibold text-lg"
          >
            <Phone className="h-6 w-6" />
            התחל שיחה
          </button>

          {/* Info */}
          <div className="mt-8 p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertCircle className="h-4 w-4 text-blue-600 flex-shrink-0 mt-0.5" />
              <div className="text-sm text-blue-700">
                <p className="font-medium">💡 שיחה חיה בדפדפן</p>
                <p className="mt-1">
                  השיחה משתמשת בהגדרות הפרומפט והקול השמורים.
                  דבר למיקרופון והמערכת תזהה אוטומטית מתי סיימת ותענה בקול.
                </p>
              </div>
            </div>
          </div>
        </div>
      ) : (
        // Active Call Screen
        <div>
          {/* Call Header */}
          <div className="bg-gradient-to-br from-green-500 to-green-600 text-white p-6">
            <div className="text-center">
              <div className="text-sm font-medium opacity-90 mb-1">שיחה פעילה</div>
              <div className="text-3xl font-bold mb-1">{formatTimer(callDuration)}</div>
              <div className="text-sm opacity-80">
                {isProcessing ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    מעבד...
                  </span>
                ) : isMuted ? (
                  '🔇 מושתק'
                ) : (
                  '🎤 מקשיב...'
                )}
              </div>
            </div>
          </div>

          {/* Call Controls */}
          <div className="p-6 bg-slate-50">
            <div className="flex items-center justify-center gap-4 mb-6">
              {/* Mute Button */}
              <button
                onClick={toggleMute}
                className={`w-16 h-16 rounded-full flex items-center justify-center transition-all shadow-lg ${
                  isMuted
                    ? 'bg-red-500 hover:bg-red-600 text-white'
                    : 'bg-white hover:bg-slate-100 text-slate-700 border-2 border-slate-200'
                }`}
                title={isMuted ? 'בטל השתקה' : 'השתק'}
              >
                {isMuted ? <MicOff className="h-7 w-7" /> : <Mic className="h-7 w-7" />}
              </button>

              {/* Speaker Button */}
              <button
                onClick={toggleSpeaker}
                className={`w-16 h-16 rounded-full flex items-center justify-center transition-all shadow-lg ${
                  isSpeakerOn
                    ? 'bg-blue-500 hover:bg-blue-600 text-white'
                    : 'bg-white hover:bg-slate-100 text-slate-700 border-2 border-slate-200'
                }`}
                title={isSpeakerOn ? 'כבה רמקול' : 'הדלק רמקול'}
              >
                {isSpeakerOn ? <Volume2 className="h-7 w-7" /> : <VolumeX className="h-7 w-7" />}
              </button>

              {/* Hangup Button */}
              <button
                onClick={stopSession}
                className="w-16 h-16 rounded-full bg-gradient-to-br from-red-500 to-red-600 hover:from-red-600 hover:to-red-700 text-white flex items-center justify-center transition-all shadow-lg"
                title="ניתוק"
              >
                <PhoneOff className="h-7 w-7" />
              </button>
            </div>

            {/* Current Transcript */}
            {currentTranscript && (
              <div className="p-4 bg-white border border-slate-200 rounded-lg shadow-sm">
                <div className="text-xs text-slate-500 mb-1">אתה אמרת:</div>
                <div className="text-slate-900 font-medium">{currentTranscript}</div>
              </div>
            )}
          </div>

          {/* Conversation History */}
          {conversation.length > 0 && (
            <div className="p-6 pt-0 bg-slate-50">
              <div className="space-y-3 max-h-[300px] overflow-y-auto">
                <div className="text-sm font-semibold text-slate-700 mb-3">היסטוריית שיחה:</div>
                {conversation.map((turn, index) => (
                  <div key={index} className="space-y-2">
                    {/* User said */}
                    <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
                      <div className="text-xs text-blue-600 mb-1 font-medium">🧑 אתה:</div>
                      <div className="text-blue-900">{turn.userSaid}</div>
                    </div>
                    
                    {/* AI said */}
                    <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                      <div className="text-xs text-green-600 mb-1 font-medium">🤖 AI:</div>
                      <div className="text-green-900">{turn.aiSaid}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default LiveCallCard;
