import React, { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { Button } from './Button';

interface WebhookConfirmPopupProps {
  isOpen: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  oldStatus: string;
  newStatus: string;
}

// LocalStorage keys for webhook preferences
const WEBHOOK_PREF_KEY = 'statusWebhookPreference'; // 'always' | 'never' | 'ask'

/**
 * Webhook Confirmation Popup
 * 
 * Shows after status change if business has status_webhook_url configured.
 * Allows user to:
 * - Send webhook for this change
 * - Skip webhook for this change
 * - Remember preference (always/never/ask)
 */
export function WebhookConfirmPopup({
  isOpen,
  onConfirm,
  onCancel,
  oldStatus,
  newStatus,
}: WebhookConfirmPopupProps) {
  const [rememberChoice, setRememberChoice] = useState(false);

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (rememberChoice) {
      localStorage.setItem(WEBHOOK_PREF_KEY, 'always');
    }
    onConfirm();
  };

  const handleCancel = () => {
    if (rememberChoice) {
      localStorage.setItem(WEBHOOK_PREF_KEY, 'never');
    }
    onCancel();
  };

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-30 z-[9998] transition-opacity"
        onClick={onCancel}
      />

      {/* Popup */}
      <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
        <div className="bg-white rounded-lg shadow-xl max-w-md w-full p-6 relative">
          {/* Close button */}
          <button
            onClick={onCancel}
            className="absolute top-4 left-4 p-1 hover:bg-gray-100 rounded-full transition-colors"
            aria-label="סגור"
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>

          {/* Content */}
          <div className="mb-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-3">
              שלח שינוי סטטוס ל-Webhook?
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              סטטוס הליד שונה מ-<span className="font-medium">{oldStatus}</span> ל-<span className="font-medium">{newStatus}</span>.
            </p>
            <p className="text-sm text-gray-600">
              האם תרצה לשלוח את שינוי הסטטוס גם לאינטגרציה החיצונית (Webhook)?
            </p>
          </div>

          {/* Remember choice checkbox */}
          <div className="mb-6">
            <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
              <input
                type="checkbox"
                checked={rememberChoice}
                onChange={(e) => setRememberChoice(e.target.checked)}
                className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <span>זכור את בחירתי לפעם הבאה</span>
            </label>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <Button
              onClick={handleConfirm}
              className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
            >
              כן, שלח
            </Button>
            <Button
              onClick={handleCancel}
              variant="outline"
              className="flex-1"
            >
              לא
            </Button>
          </div>
        </div>
      </div>
    </>
  );
}

/**
 * Get webhook preference from localStorage
 * Returns: 'always' | 'never' | 'ask'
 */
export function getWebhookPreference(): 'always' | 'never' | 'ask' {
  try {
    const pref = localStorage.getItem(WEBHOOK_PREF_KEY);
    if (pref === 'always' || pref === 'never') {
      return pref;
    }
  } catch (error) {
    console.error('Error reading webhook preference:', error);
  }
  return 'ask'; // Default to asking
}

/**
 * Clear webhook preference (reset to 'ask')
 */
export function clearWebhookPreference() {
  try {
    localStorage.removeItem(WEBHOOK_PREF_KEY);
  } catch (error) {
    console.error('Error clearing webhook preference:', error);
  }
}
