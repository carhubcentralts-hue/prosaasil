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
 * AudioPlayer with Playback Speed Controls and Direct Streaming
 * 
 * Features:
 * - 1x, 1.5x, 2x playback speed toggle buttons
 * - Persists speed preference in localStorage
 * - Applies speed automatically on load
 * - 🔥 NEW: Direct streaming from /api/recordings/file/<call_sid> with Range support
 * - 🔥 FIX: No blob URLs - uses native browser streaming for stability
 * - 🔥 FIX: Handles 404/waiting with retry logic for recordings being downloaded
 */
export function AudioPlayer({ src, loading = false, className = '' }: AudioPlayerProps) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [playbackSpeed, setPlaybackSpeed] = useState<PlaybackSpeed>(1);
  const [isLoading, setIsLoading] = useState(true);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);
  const [preparingRecording, setPreparingRecording] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const retryTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const lastSrcRef = useRef<string>(''); // Track last src to prevent duplicate processing

  // 🔥 PERFORMANCE FIX: Reduced retry limit and improved backoff
  const MAX_RETRIES = 5; // 5 retries with exponential backoff
  const getRetryDelay = (retryCount: number) => {
    // Exponential backoff: 3s → 5s → 8s → 12s → 20s (capped)
    const delays = [3000, 5000, 8000, 12000, 20000];
    return delays[Math.min(retryCount, delays.length - 1)];
  };

  // 🔥 NEW: Extract call_sid from URL to convert to /file endpoint
  const extractCallSidFromUrl = (url: string): string | null => {
    // Match: /api/recordings/<call_sid>/stream or /api/calls/<call_sid>/download
    const match = url.match(/\/api\/(?:recordings|calls)\/([A-Z0-9a-z]+)\//);
    return match ? match[1] : null;
  };

  // 🔥 NEW: Check if recording file is ready on server
  const checkRecordingReady = async (fileUrl: string, currentRetry = 0): Promise<boolean> => {
    try {
      const response = await fetch(fileUrl, {
        method: 'HEAD', // Just check if file exists without downloading
        credentials: 'include'
      });

      if (response.ok) {
        // File is ready!
        return true;
      }

      if (response.status === 404 && currentRetry < MAX_RETRIES) {
        // File not ready yet, retry with backoff
        const delay = getRetryDelay(currentRetry);
        console.log(`[AudioPlayer] Recording not ready, retrying in ${delay/1000}s... (attempt ${currentRetry + 1}/${MAX_RETRIES})`);
        setRetryCount(currentRetry + 1);
        setPreparingRecording(true);
        
        return new Promise((resolve) => {
          retryTimeoutRef.current = setTimeout(async () => {
            const ready = await checkRecordingReady(fileUrl, currentRetry + 1);
            resolve(ready);
          }, delay);
        });
      }

      // Other error or max retries reached
      return false;
    } catch (error) {
      console.error('[AudioPlayer] Error checking recording:', error);
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

  // 🔥 NEW: Direct streaming - convert src to /file endpoint and check availability
  useEffect(() => {
    const loadRecording = async () => {
      try {
        // Skip if src hasn't changed
        if (lastSrcRef.current === src) {
          return;
        }
        lastSrcRef.current = src;

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
        setStreamUrl(null);

        // If src is already a direct URL (not /stream), use it directly
        if (!src.includes('/stream')) {
          setStreamUrl(src);
          setIsLoading(false);
          return;
        }

        // Extract call_sid and convert to /file endpoint
        const callSid = extractCallSidFromUrl(src);
        if (!callSid) {
          console.error('[AudioPlayer] Could not extract call_sid from URL:', src);
          setErrorMessage('שגיאה בכתובת ההקלטה');
          setIsLoading(false);
          return;
        }

        // Use /file endpoint for direct streaming with Range support
        const fileUrl = `/api/recordings/file/${callSid}`;
        
        // Check if file is ready (with retry logic)
        const isReady = await checkRecordingReady(fileUrl, 0);
        
        if (isReady) {
          // File is ready - set URL for direct streaming
          setStreamUrl(fileUrl);
          setPreparingRecording(false);
          setIsLoading(false);
          console.log(`[AudioPlayer] Streaming directly from: ${fileUrl}`);
        } else {
          // File not available after retries
          setErrorMessage('ההקלטה לא זמינה. אנא נסה שוב מאוחר יותר.');
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
      if (retryTimeoutRef.current) {
        clearTimeout(retryTimeoutRef.current);
        retryTimeoutRef.current = null;
      }
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
      <div className="py-4 text-center">
        <p className="text-sm text-red-600">{errorMessage}</p>
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
