import React, { useState, useEffect } from 'react';
import { X, FileText, User, Phone, Mail } from 'lucide-react';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';

interface CreateContractModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

export function CreateContractModal({ onClose, onSuccess }: CreateContractModalProps) {
  const [formData, setFormData] = useState({
    title: '',
    lead_id: '',
    signer_name: '',
    signer_phone: '',
    signer_email: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!formData.title.trim()) {
      setError('כותרת חובה');
      return;
    }

    setLoading(true);

    try {
      const payload: any = {
        title: formData.title.trim(),
      };

      if (formData.lead_id) payload.lead_id = parseInt(formData.lead_id);
      if (formData.signer_name) payload.signer_name = formData.signer_name.trim();
      if (formData.signer_phone) payload.signer_phone = formData.signer_phone.trim();
      if (formData.signer_email) payload.signer_email = formData.signer_email.trim();

      const response = await fetch('/api/contracts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to create contract');
      }

      onSuccess();
    } catch (err: any) {
      console.error('Error creating contract:', err);
      setError(err.message || 'שגיאה ביצירת חוזה');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" dir="rtl">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 rounded-lg">
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <h2 className="text-xl font-bold text-gray-900">חוזה חדש</h2>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition"
            disabled={loading}
          >
            <X className="w-5 h-5 text-gray-500" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              כותרת <span className="text-red-500">*</span>
            </label>
            <Input
              type="text"
              value={formData.title}
              onChange={(e) => setFormData({ ...formData, title: e.target.value })}
              placeholder="לדוגמה: חוזה שירות לקוח ABC"
              required
              disabled={loading}
            />
          </div>

          {/* Lead ID (optional) */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">מזהה ליד (אופציונלי)</label>
            <Input
              type="number"
              value={formData.lead_id}
              onChange={(e) => setFormData({ ...formData, lead_id: e.target.value })}
              placeholder="123"
              disabled={loading}
            />
          </div>

          {/* Signer Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">שם החותם (אופציונלי)</label>
            <div className="relative">
              <User className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <Input
                type="text"
                value={formData.signer_name}
                onChange={(e) => setFormData({ ...formData, signer_name: e.target.value })}
                placeholder="ישראל ישראלי"
                className="pr-10"
                disabled={loading}
              />
            </div>
          </div>

          {/* Signer Phone */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">טלפון החותם (אופציונלי)</label>
            <div className="relative">
              <Phone className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <Input
                type="tel"
                value={formData.signer_phone}
                onChange={(e) => setFormData({ ...formData, signer_phone: e.target.value })}
                placeholder="050-1234567"
                className="pr-10"
                disabled={loading}
              />
            </div>
          </div>

          {/* Signer Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">אימייל החותם (אופציונלי)</label>
            <div className="relative">
              <Mail className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <Input
                type="email"
                value={formData.signer_email}
                onChange={(e) => setFormData({ ...formData, signer_email: e.target.value })}
                placeholder="example@email.com"
                className="pr-10"
                disabled={loading}
              />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-4">
            <Button type="submit" disabled={loading} className="flex-1">
              {loading ? 'יוצר...' : 'צור חוזה'}
            </Button>
            <Button type="button" onClick={onClose} variant="secondary" disabled={loading} className="flex-1">
              ביטול
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
