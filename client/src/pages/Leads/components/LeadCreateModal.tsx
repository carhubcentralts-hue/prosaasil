import type * as React from "react";
import { useState } from 'react';
import { X, Phone, Mail, User, Tag } from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Card } from '../../../shared/components/ui/Card';
import { CreateLeadRequest, LeadSource, LeadStatus } from '../types';

interface LeadCreateModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (leadData: Partial<CreateLeadRequest>) => Promise<void>;
}

const SOURCES: { key: LeadSource; label: string }[] = [
  { key: 'form', label: 'טופס באתר' },
  { key: 'call', label: 'שיחה נכנסת' },
  { key: 'whatsapp', label: 'וואטסאפ' },
  { key: 'manual', label: 'הוספה ידנית' },
];

const STATUSES: { key: LeadStatus; label: string }[] = [
  { key: 'New', label: 'חדש' },
  { key: 'Attempting', label: 'בניסיון קשר' },
  { key: 'Contacted', label: 'נוצר קשר' },
  { key: 'Qualified', label: 'מוכשר' },
];

export default function LeadCreateModal({ isOpen, onClose, onSubmit }: LeadCreateModalProps) {
  const [formData, setFormData] = useState<Partial<CreateLeadRequest>>({
    first_name: '',
    last_name: '',
    phone_e164: '',
    email: '',
    source: 'manual',
    status: 'New',
    notes: '',
    tags: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState('');

  const handleInputChange = (field: keyof CreateLeadRequest, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleAddTag = () => {
    if (newTag.trim() && !formData.tags?.includes(newTag.trim())) {
      setFormData(prev => ({
        ...prev,
        tags: [...(prev.tags || []), newTag.trim()],
      }));
      setNewTag('');
    }
  };

  const handleRemoveTag = (tagToRemove: string) => {
    setFormData(prev => ({
      ...prev,
      tags: prev.tags?.filter(tag => tag !== tagToRemove) || [],
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.first_name?.trim()) {
      setError('שם פרטי הוא שדה חובה');
      return;
    }

    if (!formData.phone_e164?.trim() && !formData.email?.trim()) {
      setError('נדרש לפחות טלפון או מייל');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      // Format phone number if provided
      let phone_e164 = formData.phone_e164?.trim();
      if (phone_e164) {
        // Simple phone formatting for Israeli numbers
        if (phone_e164.startsWith('0')) {
          phone_e164 = '+972' + phone_e164.substring(1);
        } else if (!phone_e164.startsWith('+')) {
          phone_e164 = '+972' + phone_e164;
        }
      }

      const leadData = {
        ...formData,
        phone_e164,
        first_name: formData.first_name?.trim(),
        last_name: formData.last_name?.trim(),
        email: formData.email?.trim() || undefined,
        notes: formData.notes?.trim() || undefined,
      };

      await onSubmit(leadData);
      
      // Reset form
      setFormData({
        first_name: '',
        last_name: '',
        phone_e164: '',
        email: '',
        source: 'manual',
        status: 'New',
        notes: '',
        tags: [],
      });
      setNewTag('');
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה ביצירת הליד');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto bg-white">
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold">הוסף ליד חדש</h2>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-full"
              data-testid="button-close-modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Personal Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  שם פרטי *
                </label>
                <Input
                  value={formData.first_name || ''}
                  onChange={(e) => handleInputChange('first_name', e.target.value)}
                  placeholder="הכנס שם פרטי"
                  data-testid="input-first-name"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">
                  שם משפחה
                </label>
                <Input
                  value={formData.last_name || ''}
                  onChange={(e) => handleInputChange('last_name', e.target.value)}
                  placeholder="הכנס שם משפחה"
                  data-testid="input-last-name"
                />
              </div>
            </div>

            {/* Contact Info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  <Phone className="w-4 h-4 inline ml-1" />
                  טלפון
                </label>
                <Input
                  value={formData.phone_e164 || ''}
                  onChange={(e) => handleInputChange('phone_e164', e.target.value)}
                  placeholder="050-123-4567"
                  type="tel"
                  data-testid="input-phone"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">
                  <Mail className="w-4 h-4 inline ml-1" />
                  מייל
                </label>
                <Input
                  value={formData.email || ''}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  placeholder="example@domain.com"
                  type="email"
                  data-testid="input-email"
                />
              </div>
            </div>

            {/* Source and Status */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium mb-2">
                  מקור הליד
                </label>
                <select
                  value={formData.source || 'manual'}
                  onChange={(e) => handleInputChange('source', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="select-source"
                >
                  {SOURCES.map(source => (
                    <option key={source.key} value={source.key}>
                      {source.label}
                    </option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium mb-2">
                  סטטוס ראשוני
                </label>
                <select
                  value={formData.status || 'New'}
                  onChange={(e) => handleInputChange('status', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  data-testid="select-status"
                >
                  {STATUSES.map(status => (
                    <option key={status.key} value={status.key}>
                      {status.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* Tags */}
            <div>
              <label className="block text-sm font-medium mb-2">
                <Tag className="w-4 h-4 inline ml-1" />
                תגיות
              </label>
              
              {/* Current tags */}
              {formData.tags && formData.tags.length > 0 && (
                <div className="flex flex-wrap gap-2 mb-2">
                  {formData.tags.map((tag, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full"
                    >
                      {tag}
                      <button
                        type="button"
                        onClick={() => handleRemoveTag(tag)}
                        className="mr-2 hover:text-blue-600"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                </div>
              )}
              
              {/* Add new tag */}
              <div className="flex gap-2">
                <Input
                  value={newTag}
                  onChange={(e) => setNewTag(e.target.value)}
                  placeholder="הוסף תגית"
                  onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                  data-testid="input-new-tag"
                />
                <Button
                  type="button"
                  onClick={handleAddTag}
                  variant="secondary"
                  size="sm"
                  data-testid="button-add-tag"
                >
                  הוסף
                </Button>
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="block text-sm font-medium mb-2">
                הערות
              </label>
              <textarea
                value={formData.notes || ''}
                onChange={(e) => handleInputChange('notes', e.target.value)}
                placeholder="הערות נוספות על הליד..."
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                data-testid="textarea-notes"
              />
            </div>

            {/* Submit Buttons */}
            <div className="flex justify-end gap-3 pt-4 border-t">
              <Button
                type="button"
                variant="secondary"
                onClick={onClose}
                disabled={loading}
                data-testid="button-cancel"
              >
                ביטול
              </Button>
              <Button
                type="submit"
                disabled={loading}
                data-testid="button-submit"
              >
                {loading ? 'יוצר...' : 'צור ליד'}
              </Button>
            </div>
          </form>
        </div>
      </Card>
    </div>
  );
}