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

  // 🔥 FIX: Increase retry patience for slow downloads
  const MAX_RETRIES = 20; // Max 20 retries (up to 60 seconds for large recordings)
  const RETRY_DELAY = 3000; // 3 seconds between retries (more patient)

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

  // 🔥 NEW: Load recording with retry logic for async downloads
  useEffect(() => {
    // If src is already a blob URL, use it directly
    if (src.startsWith('blob:')) {
      setBlobUrl(src);
      setIsLoading(false);
      return;
    }

    // If src points to /api/recordings/<call_sid>/stream, fetch with retry logic
    if (src.includes('/api/recordings/') && src.includes('/stream')) {
      loadRecordingWithRetry(src);
    } else {
      // For other URLs (like old /api/calls/<call_sid>/download), use directly
      setBlobUrl(src);
      setIsLoading(false);
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

  const loadRecordingWithRetry = async (url: string, currentRetry = 0) => {
    setPreparingRecording(true);
    setErrorMessage(null);
    
    try {
      const response = await fetch(url, {
        method: 'GET',
        credentials: 'include'
      });

      // Handle 202 Accepted - recording is being prepared
      if (response.status === 202) {
        if (currentRetry < MAX_RETRIES) {
          console.log(`Recording is being prepared, retrying in ${RETRY_DELAY/1000}s... (attempt ${currentRetry + 1}/${MAX_RETRIES})`);
          setRetryCount(currentRetry + 1);
          
          // Retry after delay
          retryTimeoutRef.current = setTimeout(() => {
            loadRecordingWithRetry(url, currentRetry + 1);
          }, RETRY_DELAY);
          return;
        } else {
          throw new Error('הכנת ההקלטה לקחה יותר מדי זמן. אנא נסה שוב מאוחר יותר.');
        }
      }

      // Handle 410 Gone - recording expired
      if (response.status === 410) {
        throw new Error('ההקלטה פגה תוקף (ישנה מ-7 ימים)');
      }

      // Handle other errors
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || 'שגיאה בטעינת ההקלטה');
      }

      // Success - load the blob
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      setBlobUrl(url);
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
    return (
      <div className="flex items-center justify-center py-4">
        <Loader2 className="w-5 h-5 animate-spin text-blue-500" />
        <span className="text-sm text-gray-500 mr-2">
          {preparingRecording && retryCount > 0 
            ? `מכין הקלטה... (נסיון ${retryCount}/${MAX_RETRIES})`
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
