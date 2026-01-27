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
 * AudioPlayer with Playback Speed Controls and Direct File Serving
 * 
 * Features:
 * - 1x, 1.5x, 2x playback speed toggle buttons
 * - Persists speed preference in localStorage
 * - Applies speed automatically on load
 * - 🔥 Uses /api/recordings/file/<call_sid> endpoint for direct file serving
 * - 🔥 NO worker interaction - worker handles downloads, API just serves files
 * - 🔥 Handles 404 gracefully with user-friendly message
 */
export function AudioPlayer({ src, loading = false, className = '' }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);
  const [isLoading, setIsLoading] = useState(true);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [preparingRecording, setPreparingRecording] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [manualRetryAvailable, setManualRetryAvailable] = useState(false);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSrcRef = useRef<string>(''); // Track last src to prevent duplicate processing
  const abortControllerRef = useRef<AbortController | null>(null); // 🔥 FIX: Cancel pending requests
  const isCheckingRef = useRef<boolean>(false); // 🔥 FIX: Prevent concurrent checks

  // 🔥 FIX: Increased retry limit and patience for large recording downloads
  // Large recordings can take 2-3 minutes to download from Twilio
  const MAX_RETRIES = 12; // 12 retries with exponential backoff (up to ~3 minutes)
  const getRetryDelay = (retryCount: number) => {
    // Progressive backoff: 3s → 5s → 8s → 10s → 15s → 15s... (capped at 15s)
    // Total wait time: ~2.5-3 minutes before giving up
    const delays = [3000, 5000, 8000, 10000, 15000, 15000, 15000, 15000, 15000, 15000, 15000, 15000];
    return delays[Math.min(retryCount, delays.length - 1)];
  };

  // 🔥 CHECK: Use HEAD request to check if recording file exists
  const checkFileAvailable = async (fileUrl: string, currentRetry = 0): Promise<boolean> => {
    // 🔥 FIX: Prevent concurrent checks - only one check at a time
    if (isCheckingRef.current) {
      console.log('[AudioPlayer] Check already in progress, skipping...');
      return false;
    }
    
    isCheckingRef.current = true;
    
    // 🔥 FIX: Create and store AbortController BEFORE fetch to prevent race condition
    const controller = new AbortController();
    abortControllerRef.current = controller;
    
    try {
      const response = await fetch(fileUrl, {
        method: 'HEAD', // Just check if file exists
        credentials: 'include',
        signal: controller.signal
      });

      if (response.ok || response.status === 206) {
        // File exists and is ready
        isCheckingRef.current = false;
        return true;
      }

      if (response.status === 404 && currentRetry < MAX_RETRIES) {
        // 404 - file not yet downloaded by worker, retry with backoff
        const delay = getRetryDelay(currentRetry);
        const totalWaitSoFar = Array.from({length: currentRetry}, (_, i) => getRetryDelay(i)).reduce((a, b) => a + b, 0) / 1000;
        console.log(`[AudioPlayer] File not ready (404), retrying in ${delay/1000}s... (attempt ${currentRetry + 1}/${MAX_RETRIES}, waited ${Math.floor(totalWaitSoFar)}s so far)`);
        setRetryCount(currentRetry + 1);
        setPreparingRecording(true);
        
        return new Promise((resolve) => {
          retryTimeoutRef.current = setTimeout(async () => {
            isCheckingRef.current = false; // Reset before next check
            const ready = await checkFileAvailable(fileUrl, currentRetry + 1);
            resolve(ready);
          }, delay);
        });
      }

      // Other error or max retries reached
      isCheckingRef.current = false;
      return false;
    } catch (error) {
      // 🔥 FIX: Don't log abort errors as errors
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('[AudioPlayer] Request aborted');
      } else {
        console.error('[AudioPlayer] Error checking recording:', error);
      }
      isCheckingRef.current = false;
      return false;
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
      console.error('[AudioPlayer] Error loading playback speed preference:', error);
    }
  }, []);

  // 🔥 CRITICAL FIX: Use /file endpoint directly - no worker interaction
  // Worker handles downloads, API just serves files that exist
  useEffect(() => {
    const loadRecording = async () => {
      try {
        // Skip if src hasn't changed
        if (lastSrcRef.current === src) {
          return;
        }
        lastSrcRef.current = src;

        // 🔥 FIX: Abort any pending requests
        if (abortControllerRef.current) {
          abortControllerRef.current.abort();
          abortControllerRef.current = null;
        }

        // Clean up any existing timeouts
        if (retryTimeoutRef.current) {
          clearTimeout(retryTimeoutRef.current);
          retryTimeoutRef.current = null;
        }

        // Reset state
        isCheckingRef.current = false;
        setPreparingRecording(false);
        setIsLoading(true);
        setRetryCount(0);
        setErrorMessage(null);
        setManualRetryAvailable(false);
        setStreamUrl(null);

        // Use src directly - should already be /api/recordings/file/<call_sid> format
        const fileUrl = src;
        
        // Check if recording file exists (HEAD request)
        const isReady = await checkFileAvailable(fileUrl, 0);
        
        if (isReady) {
          // Recording file exists - use it directly
          setStreamUrl(fileUrl);
          setPreparingRecording(false);
          setIsLoading(false);
          console.log(`[AudioPlayer] Playing from: ${fileUrl}`);
        } else {
          // Recording file not available after all retries
          // Show user-friendly message with retry option
          const totalWaitTime = Array.from({length: retryCount}, (_, i) => getRetryDelay(i)).reduce((a, b) => a + b, 0) / 1000;
          setErrorMessage(
            `ההקלטה עדיין בתהליך הורדה (חיכינו ${Math.floor(totalWaitTime)} שניות). ` +
            `זה יכול לקחת עד 3 דקות להקלטות ארוכות.`
          );
          setManualRetryAvailable(true);
          setPreparingRecording(false);
          setIsLoading(false);
        }
      } catch (err) {
        console.error('[AudioPlayer] Error in loadRecording:', err);
        setErrorMessage('שגיאה בטעינת ההקלטה');
        setPreparingRecording(false);
        setIsLoading(false);
      }
    };

    loadRecording();

    // Cleanup on unmount
    return () => {
      // 🔥 FIX: Abort pending requests on cleanup
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
      
      isCheckingRef.current = false;
    };
  }, [src]);

  // Apply playback speed to audio element
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed, streamUrl]);

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
      console.error('[AudioPlayer] Error saving playback speed preference:', error);
    }
  };

  // Handle manual retry
  const handleManualRetry = () => {
    // Reset state and trigger reload by updating lastSrcRef
    lastSrcRef.current = '';
    setErrorMessage(null);
    setManualRetryAvailable(false);
    setRetryCount(0);
    setIsLoading(true);
    setPreparingRecording(true);
    
    // Trigger reload by changing the src ref
    checkFileAvailable(src, 0);
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
    // Calculate estimated seconds elapsed
    let secondsElapsed = 0;
    for (let i = 0; i < retryCount; i++) {
      secondsElapsed += getRetryDelay(i) / 1000;
    }
    
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
        <span className="text-sm text-gray-500 mr-2">
          {preparingRecording && retryCount > 0 
            ? `ממתין להקלטה... (${Math.floor(secondsElapsed)}s)`
            : preparingRecording
            ? 'בודק זמינות הקלטה...'
            : 'טוען הקלטה...'
          }
        </span>
      </div>
    );
  }

  if (errorMessage) {
    return (
      <div className="py-4 text-center space-y-3">
        <p className="text-sm text-red-600">{errorMessage}</p>
        {manualRetryAvailable && (
          <button
            onClick={handleManualRetry}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm font-medium"
          >
            נסה שוב
          </button>
        )}
      </div>
    );
  }

  if (!streamUrl) {
    return null;
  }

  return (
    <div className={`space-y-2 ${className}`}>
      {/* Audio element with direct streaming */}
      <audio
        ref={audioRef}
        controls
        playsInline
        preload="metadata"
        className="w-full"
        src={streamUrl}
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
