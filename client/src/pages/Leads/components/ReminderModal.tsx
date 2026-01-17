import React, { useState, useEffect } from 'react';
import { Button } from "../../../shared/components/ui/Button";
import { Lead, LeadReminder } from '../types';
import { Clock, X, Save } from 'lucide-react';
import { http } from '../../../services/http';

interface ReminderModalProps {
  isOpen: boolean;
  onClose: () => void;
  lead: Lead;
  reminder?: LeadReminder | null;
  onSuccess?: () => void;
}

export function ReminderModal({ isOpen, onClose, lead, reminder = null, onSuccess }: ReminderModalProps) {
  const [note, setNote] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [dueTime, setDueTime] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Pre-populate form when reminder is provided or reset when creating new
  useEffect(() => {
    if (isOpen) {
      if (reminder) {
        setNote(reminder.note || '');
        
        // 🔥 FIX: Parse due_at correctly as local Israel time
        // The due_at from server is in local Israel time (naive datetime)
        // Parse it directly without timezone conversion
        const dueDateStr = reminder.due_at;
        if (dueDateStr.includes('T')) {
          const [date, timeWithSeconds] = dueDateStr.split('T');
          const time = timeWithSeconds.split('.')[0].substring(0, 5); // Extract HH:MM
          setDueDate(date);
          setDueTime(time);
        } else {
          // Fallback for unexpected format: manually format as local time
          // Note: Date object treats input as local time when no timezone specified
          // This ensures consistency with the primary parsing path above
          const dueDate = new Date(reminder.due_at);
          const year = dueDate.getFullYear();
          const month = String(dueDate.getMonth() + 1).padStart(2, '0');
          const day = String(dueDate.getDate()).padStart(2, '0');
          const hours = String(dueDate.getHours()).padStart(2, '0');
          const minutes = String(dueDate.getMinutes()).padStart(2, '0');
          setDueDate(`${year}-${month}-${day}`);
          setDueTime(`${hours}:${minutes}`);
        }
      } else {
        // Reset form when creating new reminder
        setNote('');
        setDueDate('');
        setDueTime('');
      }
    }
  }, [reminder, isOpen]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!note.trim() || !dueDate || !dueTime) {
      alert('אנא מלא את כל השדות הנדרשים');
      return;
    }

    setIsSubmitting(true);
    
    try {
      // 🔥 FIX: Send local time without timezone suffix (no .000Z)
      // This matches the CalendarPage approach - send local Israel time as-is
      // The server will treat it as local time (naive datetime)
      const dueAt = `${dueDate}T${dueTime}:00`;
      
      if (reminder) {
        // Update existing reminder
        await http.patch(`/api/leads/${lead.id}/reminders/${reminder.id}`, {
          due_at: dueAt,
          note: note.trim(),
        });
        alert(`תזכורת עודכנה בהצלחה`);
      } else {
        // Create new reminder
        await http.post(`/api/leads/${lead.id}/reminders`, {
          due_at: dueAt,
          note: note.trim(),
        });
        alert(`תזכורת לחזרה ללקוח ${lead.full_name} נוצרה בהצלחה`);
      }

      onSuccess?.();
      handleClose();
    } catch (error: any) {
      console.error('Failed to save reminder:', error);
      alert(error.message || 'שגיאה בשמירת התזכורת');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleClose = () => {
    setNote('');
    setDueDate('');
    setDueTime('');
    onClose();
  };

  // Get tomorrow's date as default
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  const defaultDate = tomorrow.toISOString().split('T')[0];

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" dir="rtl">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={handleClose} />
      
      <div className="relative min-h-screen flex items-center justify-center p-4">
        <div className="relative bg-white rounded-xl shadow-xl max-w-md w-full">
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-200">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Clock className="h-5 w-5 text-white" />
              </div>
              <h2 className="text-lg font-semibold text-slate-900">
                {reminder ? 'ערוך תזכורת' : `חזור אלי - ${lead.full_name}`}
              </h2>
            </div>
            <button
              onClick={handleClose}
              className="p-2 hover:bg-slate-100 rounded-lg transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Content */}
          <form onSubmit={handleSubmit} className="p-6 space-y-6">
            {/* Date and Time */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label htmlFor="due-date" className="block text-sm font-medium text-slate-700 mb-2">
                  תאריך
                </label>
                <input
                  id="due-date"
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  data-testid="input-reminder-date"
                  lang="en"
                />
              </div>
              <div>
                <label htmlFor="due-time" className="block text-sm font-medium text-slate-700 mb-2">
                  שעה
                </label>
                <input
                  id="due-time"
                  type="time"
                  value={dueTime}
                  onChange={(e) => setDueTime(e.target.value)}
                  required
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  data-testid="input-reminder-time"
                />
              </div>
            </div>

            {/* Note */}
            <div>
              <label htmlFor="reminder-note" className="block text-sm font-medium text-slate-700 mb-2">
                הודעת תזכורת
              </label>
              <textarea
                id="reminder-note"
                placeholder="למשל: להתקשר ללקוח ולבדוק אם יש התקדמות..."
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent min-h-[80px]"
                required
                data-testid="textarea-reminder-note"
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-200">
              <button
                type="button"
                onClick={handleClose}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 hover:bg-slate-100 rounded-lg transition-colors"
                data-testid="button-cancel-reminder"
              >
                ביטול
              </button>
              <Button
                type="submit"
                disabled={isSubmitting}
                className="flex items-center gap-2"
                data-testid="button-create-reminder"
              >
                <Save className="h-4 w-4" />
                {isSubmitting ? (reminder ? 'שומר...' : 'יוצר...') : (reminder ? 'שמור שינויים' : 'צור תזכורת')}
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}