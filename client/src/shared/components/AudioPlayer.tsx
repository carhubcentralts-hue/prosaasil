import React, { useRef, useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

interface AudioPlayerProps {
  src: string;
  loading?: boolean;
  className?: string;
}

// Playback speed type
type PlaybackSpeed = 1 | 1.5 | 2;

// LocalStorage key for playback speed preference
const PLAYBACK_SPEED_KEY = 'audioPlaybackRate';

/**
 * AudioPlayer with Playback Speed Controls and Async Recording Support
 * 
 * Features:
 * - 1x, 1.5x, 2x playback speed toggle buttons
 * - Persists speed preference in localStorage
 * - Applies speed automatically on load
 * - Works with blob URLs and regular URLs
 * - 🔥 NEW: Handles 202 responses for async recording downloads with retry logic
 */
export function AudioPlayer({ src, loading = false, className = '' }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);
  const [isLoading, setIsLoading] = useState(true);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [preparingRecording, setPreparingRecording] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const [prepareTriggered, setPrepareTriggered] = useState(false);

  // 🔥 FIX: Exponential backoff for polling
  const MAX_RETRIES = 20; // Max 20 retries
  const getRetryDelay = (retryCount: number) => {
    // Exponential backoff: 3s → 5s → 8s → 12s → 15s (capped)
    const delays = [3000, 5000, 8000, 12000, 15000];
    return delays[Math.min(retryCount, delays.length - 1)];
  };

  // 🔥 NEW: Poll status endpoint (doesn't trigger enqueue)
  const pollRecordingStatus = async (statusUrl: string, currentRetry = 0) => {
    setPreparingRecording(true);
    setErrorMessage(null);
    
    try {
      const response = await fetch(statusUrl, {
        method: 'GET',
        credentials: 'include'
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'שגיאה בבדיקת סטטוס');
      }

      const data = await response.json();
      
      if (data.status === 'ready') {
        // Recording is ready! Now fetch it from /stream
        const streamUrl = statusUrl.replace('/status', '/stream');
        await loadRecordingDirect(streamUrl);
        return;
      }
      
      if (data.status === 'processing' || data.status === 'queued') {
        // Still processing/queued - continue polling with backoff
        if (currentRetry < MAX_RETRIES) {
          const delay = getRetryDelay(currentRetry);
          console.log(`Recording ${data.status}, checking again in ${delay/1000}s... (attempt ${currentRetry + 1}/${MAX_RETRIES})`);
          setRetryCount(currentRetry + 1);
          
          // Clear any existing timeout
          if (retryTimeoutRef.current) {
            clearTimeout(retryTimeoutRef.current);
          }
          
          // Schedule next poll with exponential backoff
          retryTimeoutRef.current = setTimeout(() => {
            pollRecordingStatus(statusUrl, currentRetry + 1);
          }, delay);
          return;
        } else {
          throw new Error('ההכנה של ההקלטה נמשכת זמן רב. אנא נסה שוב בעוד דקה.');
        }
      }
      
      if (data.status === 'unknown') {
        // Not started yet - trigger preparation
        if (!prepareTriggered) {
          setPrepareTriggered(true);
          const streamUrl = statusUrl.replace('/status', '/stream');
          await triggerRecordingPreparation(streamUrl, statusUrl);
        } else {
          throw new Error('שגיאה בהכנת ההקלטה');
        }
      }
    } catch (error) {
      console.error('Error polling recording status:', error);
      setErrorMessage((error as Error).message);
      setPreparingRecording(false);
      setIsLoading(false);
    }
  };

  // 🔥 NEW: Trigger recording preparation (call /stream once)
  const triggerRecordingPreparation = async (streamUrl: string, statusUrl: string) => {
    try {
      // 🔥 SECURITY: Add explicit_user_action parameter
      const urlWithParam = streamUrl.includes('?') 
        ? `${streamUrl}&explicit_user_action=true`
        : `${streamUrl}?explicit_user_action=true`;
      
      const response = await fetch(urlWithParam, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'X-User-Action': 'play'  // 🔥 SECURITY: Add header for double protection
        }
      });

      // 202 Accepted or 200 OK - start polling status
      if (response.status === 202 || response.status === 200) {
        if (response.status === 200) {
          // Got the file immediately!
          const blob = await response.blob();
          const blobUrl = window.URL.createObjectURL(blob);
          setBlobUrl(blobUrl);
          setPreparingRecording(false);
          setIsLoading(false);
          setRetryCount(0);
        } else {
          // 202 - enqueued, start polling
          pollRecordingStatus(statusUrl, 0);
        }
        return;
      }

      // Handle errors
      if (response.status === 410) {
        throw new Error('ההקלטה פגה תוקף (ישנה מ-7 ימים)');
      }

      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || 'שגיאה בהפעלת ההקלטה');
    } catch (error) {
      console.error('Error triggering recording preparation:', error);
      setErrorMessage((error as Error).message);
      setPreparingRecording(false);
      setIsLoading(false);
    }
  };

  // 🔥 NEW: Load recording directly (when ready)
  const loadRecordingDirect = async (streamUrl: string) => {
    try {
      const urlWithParam = streamUrl.includes('?') 
        ? `${streamUrl}&explicit_user_action=true`
        : `${streamUrl}?explicit_user_action=true`;
      
      const response = await fetch(urlWithParam, {
        method: 'GET',
        credentials: 'include',
        headers: {
          'X-User-Action': 'play'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'שגיאה בטעינת ההקלטה');
      }

      // Success - load the blob
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      setBlobUrl(blobUrl);
      setPreparingRecording(false);
      setIsLoading(false);
      setRetryCount(0);
    } catch (error) {
      console.error('Error loading recording:', error);
      setErrorMessage((error as Error).message);
      setPreparingRecording(false);
      setIsLoading(false);
    }
  };

  // Load saved playback speed preference from localStorage
  useEffect(() => {
    try {
      const savedSpeed = localStorage.getItem(PLAYBACK_SPEED_KEY);
      if (savedSpeed) {
        const parsed = parseFloat(savedSpeed);
        if (parsed === 1 || parsed === 1.5 || parsed === 2) {
          setPlaybackSpeed(parsed as PlaybackSpeed);
        }
      }
    } catch (error) {
      console.error('Error loading playback speed preference:', error);
    }
  }, []);

  // 🔥 NEW: Load recording with smart polling
  useEffect(() => {
    try {
      // Clean up any existing timeouts
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      
      // Reset state
      setPreparingRecording(false);
      setIsLoading(true);
      setRetryCount(0);
      setErrorMessage(null);
      setPrepareTriggered(false);
      
      // If src is already a blob URL, use it directly
      if (src.startsWith('blob:')) {
        setBlobUrl(src);
        setIsLoading(false);
        return;
      }

      // If src points to /api/recordings/<call_sid>/stream, use status polling
      if (src.includes('/api/recordings/') && src.includes('/stream')) {
        // Convert /stream URL to /status URL
        const statusUrl = src.replace('/stream', '/status');
        // Start with status check (doesn't trigger enqueue)
        pollRecordingStatus(statusUrl, 0);
      } else {
        // For other URLs (like old /api/calls/<call_sid>/download), use directly
        setBlobUrl(src);
        setIsLoading(false);
      }
    } catch (err) {
      // Handle only synchronous errors (e.g., from string methods)
      console.error('Error in AudioPlayer useEffect:', err);
      setErrorMessage('שגיאה בטעינת ההקלטה');
    }
  }, [src]);

  // Cleanup blob URL on unmount or when src changes
  useEffect(() => {
    return () => {
      if (blobUrl && blobUrl.startsWith('blob:')) {
        window.URL.revokeObjectURL(blobUrl);
      }
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
      }
    };
  }, [blobUrl]);

  // Apply playback speed to audio element
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed, blobUrl]);

  // Handle speed change
  const handleSpeedChange = (speed: PlaybackSpeed) => {
    setPlaybackSpeed(speed);
    
    // Apply immediately to playing audio
    if (audioRef.current) {
      audioRef.current.playbackRate = speed;
    }
    
    // Save to localStorage
    try {
      localStorage.setItem(PLAYBACK_SPEED_KEY, speed.toString());
    } catch (error) {
      console.error('Error saving playback speed preference:', error);
    }
  };

  // Handle audio ready
  const handleCanPlay = () => {
    setIsLoading(false);
  };

  // Handle audio error
  const handleError = () => {
    setIsLoading(false);
    setErrorMessage('שגיאה בטעינת ההקלטה');
  };

  if (loading || preparingRecording) {
    // Calculate estimated seconds elapsed with exponential backoff
    let secondsElapsed = 0;
    for (let i = 0; i < retryCount; i++) {
      secondsElapsed += getRetryDelay(i) / 1000;
    }
    
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
        <span className="text-sm text-gray-500 mr-2">
          {preparingRecording && retryCount > 0 
            ? `מכין הקלטה... (${Math.floor(secondsElapsed)}s)`
            : preparingRecording
            ? 'מוריד הקלטה מהשרת...'
            : 'טוען הקלטה...'
          }
        </span>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="py-4 text-center">
        <p className="text-sm text-red-600">{errorMessage}</p>
      </div>
    );
  }

  if (!blobUrl) {
    return null;
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Audio element */}
      <audio
        ref={audioRef}
        controls
        playsInline
        preload="none"
        className="w-full"
        src={blobUrl}
        onCanPlay={handleCanPlay}
        onError={handleError}
        onLoadedMetadata={() => {
          // Apply playback rate after metadata is loaded
          if (audioRef.current) {
            audioRef.current.playbackRate = playbackSpeed;
          }
        }}
      >
        הדפדפן שלך לא תומך בנגן אודיו
      </audio>

      {/* Playback speed controls */}
      <div className="flex items-center gap-2 justify-end">
        <span className="text-xs text-gray-600">מהירות נגינה:</span>
        {([1, 1.5, 2] as PlaybackSpeed[]).map((speed) => (
          <button
            key={speed}
            onClick={() => handleSpeedChange(speed)}
            className={`
              px-3 py-1 text-xs font-medium rounded-full transition-colors
              ${
                playbackSpeed === speed
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }
            `}
            title={`נגן במהירות ${speed}x`}
            aria-label={`נגן במהירות ${speed}x`}
            aria-pressed={playbackSpeed === speed}
          >
            {speed}x
          </button>
        ))}
      </div>
    </div>
  );
}
