import React, { useState, useEffect } from 'react';
import { X, Phone, Mail, User, Tag, Clock, Activity, MessageSquare, Trash2, Edit3 } from 'lucide-react';
import { Button } from '../../../shared/components/ui/Button';
import { Input } from '../../../shared/components/ui/Input';
import { Card } from '../../../shared/components/ui/Card';
import { Badge } from '../../../shared/components/Badge';
import { Lead, LeadStatus, LeadSource, LeadReminder, LeadActivity, UpdateLeadRequest } from '../types';
import { http } from '../../../services/http';
import { formatDate } from '../../../shared/utils/format';

interface LeadDetailModalProps {
  lead: Lead;
  isOpen: boolean;
  onClose: () => void;
  onUpdate: (updatedLead: Lead) => Promise<void>;
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
  { key: 'Won', label: 'זכיה' },
  { key: 'Lost', label: 'אובדן' },
  { key: 'Unqualified', label: 'לא מוכשר' },
];

export default function LeadDetailModal({ lead, isOpen, onClose, onUpdate }: LeadDetailModalProps) {
  const [activeTab, setActiveTab] = useState<'overview' | 'activities' | 'reminders' | 'notes'>('overview');
  const [isEditing, setIsEditing] = useState(false);
  const [formData, setFormData] = useState<UpdateLeadRequest>({});
  const [activities, setActivities] = useState<LeadActivity[]>([]);
  const [reminders, setReminders] = useState<LeadReminder[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState('');
  const [newReminderNote, setNewReminderNote] = useState('');
  const [newReminderDate, setNewReminderDate] = useState('');

  // Initialize form data when lead changes
  useEffect(() => {
    if (lead) {
      setFormData({
        first_name: lead.first_name,
        last_name: lead.last_name,
        phone_e164: lead.phone_e164,
        email: lead.email,
        source: lead.source,
        notes: lead.notes,
        tags: lead.tags || [],
      });
    }
  }, [lead]);

  // Fetch additional data when modal opens
  useEffect(() => {
    if (isOpen && lead) {
      fetchLeadActivities();
      fetchLeadReminders();
    }
  }, [isOpen, lead]);

  const fetchLeadActivities = async () => {
    try {
      const response = await http.get<{ activities: LeadActivity[] }>(`/api/leads/${lead.id}/activities`);
      setActivities(response.activities || []);
    } catch (err) {
      console.error('Failed to fetch activities:', err);
    }
  };

  const fetchLeadReminders = async () => {
    try {
      const response = await http.get<{ reminders: LeadReminder[] }>(`/api/leads/${lead.id}/reminders`);
      setReminders(response.reminders || []);
    } catch (err) {
      console.error('Failed to fetch reminders:', err);
    }
  };

  const handleInputChange = (field: keyof UpdateLeadRequest, value: string) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleSave = async () => {
    try {
      setLoading(true);
      setError(null);

      // Format phone number if provided
      let phone_e164 = formData.phone_e164?.trim();
      if (phone_e164) {
        if (phone_e164.startsWith('0')) {
          phone_e164 = '+972' + phone_e164.substring(1);
        } else if (!phone_e164.startsWith('+')) {
          phone_e164 = '+972' + phone_e164;
        }
      }

      const updateData = {
        ...formData,
        phone_e164,
        first_name: formData.first_name?.trim(),
        last_name: formData.last_name?.trim(),
        email: formData.email?.trim() || undefined,
        notes: formData.notes?.trim() || undefined,
      };

      const updatedLead: Lead = { 
        ...lead, 
        ...updateData,
        first_name: updateData.first_name || lead.first_name,
        last_name: updateData.last_name || lead.last_name,
        phone_e164: updateData.phone_e164 || lead.phone_e164,
        email: updateData.email || lead.email,
        source: updateData.source || lead.source,
        notes: updateData.notes || lead.notes,
        tags: updateData.tags || lead.tags,
      };
      await onUpdate(updatedLead);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בעדכון הליד');
    } finally {
      setLoading(false);
    }
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

  const handleCreateReminder = async () => {
    if (!newReminderNote.trim() || !newReminderDate) return;

    try {
      setLoading(true);
      await http.post(`/api/leads/${lead.id}/reminders`, {
        due_at: new Date(newReminderDate).toISOString(),
        note: newReminderNote.trim(),
        channel: 'ui',
      });
      
      setNewReminderNote('');
      setNewReminderDate('');
      await fetchLeadReminders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה ביצירת תזכורת');
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteReminder = async (reminderId: number) => {
    try {
      await http.patch(`/api/leads/${lead.id}/reminders/${reminderId}`, {
        completed: true,
      });
      await fetchLeadReminders();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בהשלמת תזכורת');
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 md:p-4" dir="rtl">
      <Card className="w-full max-w-4xl max-h-[95vh] overflow-hidden bg-white flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b bg-gray-50">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-xl font-semibold" data-testid={`text-lead-detail-name-${lead.id}`}>
                {lead.full_name || 'ללא שם'}
              </h2>
              <div className="flex items-center gap-2 mt-1">
                <Badge className="text-xs">
                  {STATUSES.find(s => s.key === lead.status)?.label}
                </Badge>
                <Badge variant="neutral" className="text-xs">
                  {SOURCES.find(s => s.key === lead.source)?.label}
                </Badge>
              </div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsEditing(!isEditing)}
              data-testid="button-toggle-edit"
            >
              <Edit3 className="w-4 h-4 ml-1" />
              {isEditing ? 'ביטול' : 'עריכה'}
            </Button>
            <button
              onClick={onClose}
              className="p-2 hover:bg-gray-100 rounded-full"
              data-testid="button-close-detail-modal"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mx-6 mt-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-md">
            {error}
          </div>
        )}

        {/* Tabs */}
        <div className="border-b">
          <nav className="flex space-x-8 px-6">
            {[
              { key: 'overview', label: 'סקירה', icon: User },
              { key: 'activities', label: 'פעילות', icon: Activity },
              { key: 'reminders', label: 'תזכורות', icon: Clock },
              { key: 'notes', label: 'הערות', icon: MessageSquare },
            ].map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key as any)}
                className={`py-4 px-2 border-b-2 font-medium text-sm flex items-center gap-2 ${
                  activeTab === key
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
                data-testid={`tab-${key}`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="flex-1 p-4 md:p-6 overflow-y-auto overflow-x-hidden">
          {activeTab === 'overview' && (
            <div className="space-y-4 md:space-y-6">
              {/* Contact Info */}
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 md:gap-6">
                <div>
                  <label className="block text-sm font-medium mb-2">שם פרטי</label>
                  {isEditing ? (
                    <Input
                      value={formData.first_name || ''}
                      onChange={(e) => handleInputChange('first_name', e.target.value)}
                      data-testid="input-edit-first-name"
                    />
                  ) : (
                    <p className="text-gray-900" data-testid="text-first-name">{lead.first_name || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium mb-2">שם משפחה</label>
                  {isEditing ? (
                    <Input
                      value={formData.last_name || ''}
                      onChange={(e) => handleInputChange('last_name', e.target.value)}
                      data-testid="input-edit-last-name"
                    />
                  ) : (
                    <p className="text-gray-900" data-testid="text-last-name">{lead.last_name || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium mb-2">
                    <Phone className="w-4 h-4 inline ml-1" />
                    טלפון
                  </label>
                  {isEditing ? (
                    <Input
                      value={formData.phone_e164 || ''}
                      onChange={(e) => handleInputChange('phone_e164', e.target.value)}
                      type="tel"
                      data-testid="input-edit-phone"
                    />
                  ) : (
                    <p className="text-gray-900" data-testid="text-phone">{lead.display_phone || lead.phone_e164 || '-'}</p>
                  )}
                </div>
                
                <div>
                  <label className="block text-sm font-medium mb-2">
                    <Mail className="w-4 h-4 inline ml-1" />
                    מייל
                  </label>
                  {isEditing ? (
                    <Input
                      value={formData.email || ''}
                      onChange={(e) => handleInputChange('email', e.target.value)}
                      type="email"
                      data-testid="input-edit-email"
                    />
                  ) : (
                    <p className="text-gray-900" data-testid="text-email">{lead.email || '-'}</p>
                  )}
                </div>
              </div>

              {/* Source */}
              <div>
                <label className="block text-sm font-medium mb-2">מקור הליד</label>
                {isEditing ? (
                  <select
                    value={formData.source || lead.source}
                    onChange={(e) => handleInputChange('source', e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    data-testid="select-edit-source"
                  >
                    {SOURCES.map(source => (
                      <option key={source.key} value={source.key}>
                        {source.label}
                      </option>
                    ))}
                  </select>
                ) : (
                  <p className="text-gray-900" data-testid="text-source">
                    {SOURCES.find(s => s.key === lead.source)?.label}
                  </p>
                )}
              </div>

              {/* Tags */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  <Tag className="w-4 h-4 inline ml-1" />
                  תגיות
                </label>
                
                {/* Current tags */}
                <div className="flex flex-wrap gap-2 mb-2">
                  {(isEditing ? formData.tags : lead.tags)?.map((tag, index) => (
                    <span
                      key={index}
                      className="inline-flex items-center px-3 py-1 bg-blue-100 text-blue-800 text-sm rounded-full"
                      data-testid={`tag-${index}`}
                    >
                      {tag}
                      {isEditing && (
                        <button
                          type="button"
                          onClick={() => handleRemoveTag(tag)}
                          className="mr-2 hover:text-blue-600"
                        >
                          <X className="w-3 h-3" />
                        </button>
                      )}
                    </span>
                  )) || <span className="text-gray-500">אין תגיות</span>}
                </div>
                
                {/* Add new tag */}
                {isEditing && (
                  <div className="flex gap-2">
                    <Input
                      value={newTag}
                      onChange={(e) => setNewTag(e.target.value)}
                      placeholder="הוסף תגית"
                      onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), handleAddTag())}
                      data-testid="input-new-tag-detail"
                    />
                    <Button
                      type="button"
                      onClick={handleAddTag}
                      variant="secondary"
                      size="sm"
                      data-testid="button-add-tag-detail"
                    >
                      הוסף
                    </Button>
                  </div>
                )}
              </div>

              {/* Metadata */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">נוצר</label>
                  <p className="text-sm" data-testid="text-created-at">{formatDate(lead.created_at)}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">עודכן</label>
                  <p className="text-sm" data-testid="text-updated-at">{formatDate(lead.updated_at)}</p>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">קשר אחרון</label>
                  <p className="text-sm" data-testid="text-last-contact">
                    {lead.last_contact_at ? formatDate(lead.last_contact_at) : 'אין'}
                  </p>
                </div>
              </div>

              {/* Save button */}
              {isEditing && (
                <div className="flex justify-end gap-3 pt-4 border-t">
                  <Button
                    onClick={() => setIsEditing(false)}
                    variant="secondary"
                    disabled={loading}
                  >
                    ביטול
                  </Button>
                  <Button
                    onClick={handleSave}
                    disabled={loading}
                    data-testid="button-save-lead"
                  >
                    {loading ? 'שומר...' : 'שמור'}
                  </Button>
                </div>
              )}
            </div>
          )}

          {activeTab === 'activities' && (
            <div className="space-y-4">
              <h3 className="font-semibold">פעילות</h3>
              {activities.length === 0 ? (
                <p className="text-gray-500 text-center py-8">אין פעילות עדיין</p>
              ) : (
                activities.map((activity) => (
                  <div key={activity.id} className="border rounded-lg p-4" data-testid={`activity-${activity.id}`}>
                    <div className="flex justify-between items-start mb-2">
                      <span className="font-medium">{activity.type}</span>
                      <span className="text-sm text-gray-500">{formatDate(activity.at)}</span>
                    </div>
                    {activity.payload && (
                      <pre className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
                        {JSON.stringify(activity.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'reminders' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="font-semibold">תזכורות</h3>
              </div>

              {/* Add new reminder */}
              <div className="border rounded-lg p-4 bg-gray-50">
                <h4 className="font-medium mb-3">הוסף תזכורת חדשה</h4>
                <div className="space-y-3">
                  <Input
                    value={newReminderNote}
                    onChange={(e) => setNewReminderNote(e.target.value)}
                    placeholder="הערת תזכורת..."
                    data-testid="input-new-reminder-note"
                  />
                  <div className="flex gap-2">
                    <Input
                      type="datetime-local"
                      value={newReminderDate}
                      onChange={(e) => setNewReminderDate(e.target.value)}
                      data-testid="input-new-reminder-date"
                    />
                    <Button
                      onClick={handleCreateReminder}
                      disabled={!newReminderNote.trim() || !newReminderDate || loading}
                      data-testid="button-create-reminder"
                    >
                      הוסף
                    </Button>
                  </div>
                </div>
              </div>

              {/* Reminders list */}
              {reminders.length === 0 ? (
                <p className="text-gray-500 text-center py-8">אין תזכורות</p>
              ) : (
                reminders.map((reminder) => (
                  <div
                    key={reminder.id}
                    className={`border rounded-lg p-4 ${
                      reminder.completed_at ? 'bg-green-50 border-green-200' : 'bg-white'
                    }`}
                    data-testid={`reminder-${reminder.id}`}
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <p className="font-medium">{reminder.note}</p>
                        <p className="text-sm text-gray-500 mt-1">
                          יעד: {formatDate(reminder.due_at)}
                        </p>
                        {reminder.completed_at && (
                          <p className="text-sm text-green-600 mt-1">
                            הושלם: {formatDate(reminder.completed_at)}
                          </p>
                        )}
                      </div>
                      {!reminder.completed_at && (
                        <Button
                          onClick={() => handleCompleteReminder(reminder.id)}
                          variant="secondary"
                          size="sm"
                          data-testid={`button-complete-reminder-${reminder.id}`}
                        >
                          סמן כהושלם
                        </Button>
                      )}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'notes' && (
            <div className="space-y-4">
              <h3 className="font-semibold">הערות</h3>
              {isEditing ? (
                <textarea
                  value={formData.notes || ''}
                  onChange={(e) => handleInputChange('notes', e.target.value)}
                  placeholder="הערות על הליד..."
                  rows={8}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                  data-testid="textarea-edit-notes"
                />
              ) : (
                <div className="min-h-[200px] p-4 border rounded-lg bg-gray-50" data-testid="text-notes">
                  {lead.notes ? (
                    <pre className="whitespace-pre-wrap text-gray-900">{lead.notes}</pre>
                  ) : (
                    <p className="text-gray-500">אין הערות</p>
                  )}
                </div>
              )}
              
              {isEditing && (
                <div className="flex justify-end">
                  <Button
                    onClick={handleSave}
                    disabled={loading}
                    data-testid="button-save-notes"
                  >
                    {loading ? 'שומר...' : 'שמור הערות'}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}