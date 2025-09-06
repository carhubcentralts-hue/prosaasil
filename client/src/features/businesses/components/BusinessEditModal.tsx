import React, { useState, useEffect } from 'react';
import { X, Save, Loader2 } from 'lucide-react';
import { Business, BusinessEditData } from '../types';
import { validateBusinessData } from '../actions';

interface BusinessEditModalProps {
  business: Business | null;
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: BusinessEditData) => Promise<void>;
  isLoading?: boolean;
}

export function BusinessEditModal({ 
  business, 
  isOpen, 
  onClose, 
  onSave, 
  isLoading = false 
}: BusinessEditModalProps) {
  const [formData, setFormData] = useState<BusinessEditData>({
    name: '',
    domain: '',
    defaultPhoneE164: '',
    whatsappJid: '',
    timezone: 'Asia/Jerusalem',
    address: ''
  });
  const [errors, setErrors] = useState<string[]>([]);

  // Initialize form data when business changes
  useEffect(() => {
    if (business) {
      setFormData({
        name: business.name || '',
        domain: business.domain || '',
        defaultPhoneE164: business.defaultPhoneE164 || '',
        whatsappJid: business.whatsappJid || '',
        timezone: business.timezone || 'Asia/Jerusalem',
        address: business.address || ''
      });
      setErrors([]);
    }
  }, [business]);

  const handleInputChange = (field: keyof BusinessEditData) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => {
    const value = e.target.value;
    setFormData(prev => ({ ...prev, [field]: value }));
    // Clear errors when user starts typing
    if (errors.length > 0) {
      setErrors([]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Validate form data
    const validationErrors = validateBusinessData(formData);
    if (validationErrors.length > 0) {
      setErrors(validationErrors);
      return;
    }

    try {
      await onSave(formData);
      onClose();
    } catch (error) {
      setErrors([error instanceof Error ? error.message : 'שגיאה בעדכון העסק']);
    }
  };

  const handleClose = () => {
    if (!isLoading) {
      onClose();
      setErrors([]);
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <h2 className="text-xl font-semibold text-slate-900">
            {business ? `עריכת עסק: ${business.name}` : 'עסק חדש'}
          </h2>
          <button
            onClick={handleClose}
            disabled={isLoading}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg transition-colors disabled:opacity-50"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6">
          {/* Error Display */}
          {errors.length > 0 && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="text-red-800 text-sm">
                <p className="font-medium mb-2">יש לתקן את השגיאות הבאות:</p>
                <ul className="list-disc list-inside space-y-1">
                  {errors.map((error, index) => (
                    <li key={index}>{error}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {/* Business Name */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                שם העסק *
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={handleInputChange('name')}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:bg-slate-50 disabled:opacity-50"
                placeholder="שם העסק"
                required
              />
            </div>

            {/* Domain */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                דומיין *
              </label>
              <input
                type="text"
                value={formData.domain}
                onChange={handleInputChange('domain')}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:bg-slate-50 disabled:opacity-50"
                placeholder="example.co.il"
                required
                dir="ltr"
              />
            </div>

            {/* Phone */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                טלפון ראשי *
              </label>
              <input
                type="tel"
                value={formData.defaultPhoneE164}
                onChange={handleInputChange('defaultPhoneE164')}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:bg-slate-50 disabled:opacity-50"
                placeholder="+972-3-123-4567"
                required
                dir="ltr"
              />
            </div>

            {/* WhatsApp JID */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                WhatsApp JID *
              </label>
              <input
                type="text"
                value={formData.whatsappJid}
                onChange={handleInputChange('whatsappJid')}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:bg-slate-50 disabled:opacity-50"
                placeholder="972501234567@s.whatsapp.net"
                required
                dir="ltr"
              />
            </div>

            {/* Timezone */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                אזור זמן
              </label>
              <select
                value={formData.timezone}
                onChange={(e) => setFormData(prev => ({ ...prev, timezone: e.target.value }))}
                disabled={isLoading}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none disabled:bg-slate-50 disabled:opacity-50"
              >
                <option value="Asia/Jerusalem">Asia/Jerusalem (ישראל)</option>
                <option value="Europe/London">Europe/London (לונדון)</option>
                <option value="America/New_York">America/New_York (ניו יורק)</option>
                <option value="Europe/Paris">Europe/Paris (פריז)</option>
                <option value="Asia/Tokyo">Asia/Tokyo (טוקיו)</option>
              </select>
            </div>

            {/* Address */}
            <div className="md:col-span-2">
              <label className="block text-sm font-medium text-slate-700 mb-2">
                כתובת
              </label>
              <textarea
                value={formData.address}
                onChange={handleInputChange('address')}
                disabled={isLoading}
                rows={3}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none disabled:bg-slate-50 disabled:opacity-50"
                placeholder="כתובת העסק המלאה"
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center justify-end gap-4 mt-8 pt-6 border-t border-slate-200">
            <button
              type="button"
              onClick={handleClose}
              disabled={isLoading}
              className="px-6 py-2 text-slate-600 hover:text-slate-800 font-medium transition-colors disabled:opacity-50"
            >
              ביטול
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  שומר...
                </>
              ) : (
                <>
                  <Save className="h-4 w-4" />
                  שמור שינויים
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}