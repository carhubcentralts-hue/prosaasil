import React, { useState, useEffect } from 'react';
import { Plus, Users, Bell, Calendar, CheckCircle, Circle, Clock, X, Edit2, AlertCircle } from 'lucide-react';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: any) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses: Record<string, string> = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    danger: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses: Record<string, string> = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant] || variantClasses.default} ${sizeClasses[size] || sizeClasses.default} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: any) => {
  const variantClasses: Record<string, string> = {
    default: "bg-gray-100 text-gray-800",
    low: "bg-green-100 text-green-800",
    medium: "bg-yellow-100 text-yellow-800",
    high: "bg-red-100 text-red-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant] || variantClasses.default} ${className}`}>
      {children}
    </span>
  );
};

// Reminder and Contact interfaces
interface CRMReminder {
  id: string | number;
  note: string;
  description?: string;
  due_at: string;
  completed_at?: string | null;
  priority?: 'low' | 'medium' | 'high';
  lead_id?: number;
  lead_name?: string;
  reminder_type?: string;
  created_at?: string;
}

interface CRMContact {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  tags: string[];
  lastContact?: string;
}

interface Lead {
  id: number;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  phone_e164?: string;
}

export function CrmPage() {
  const [reminders, setReminders] = useState<CRMReminder[]>([]);
  const [contacts, setContacts] = useState<CRMContact[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'reminders' | 'contacts'>('reminders');
  const [showReminderModal, setShowReminderModal] = useState(false);
  const [showContactModal, setShowContactModal] = useState(false);
  const [editingReminder, setEditingReminder] = useState<CRMReminder | null>(null);
  const [reminderForm, setReminderForm] = useState({
    note: '',
    description: '',
    due_date: '',
    due_time: '',
    priority: 'medium' as 'low' | 'medium' | 'high',
    reminder_type: 'general',
    lead_id: ''
  });

  useEffect(() => {
    loadData();
    loadLeads();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Fetch reminders from API
      const response = await fetch('/api/reminders', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setReminders(data.reminders || []);
      } else {
        console.error('Failed to load reminders');
        setReminders([]);
      }
      
      setContacts([]);
      
    } catch (error) {
      console.error('Error loading CRM data:', error);
      setReminders([]);
      setContacts([]);
    } finally {
      setLoading(false);
    }
  };

  const loadLeads = async () => {
    try {
      const response = await fetch('/api/leads', { credentials: 'include' });
      if (response.ok) {
        const data = await response.json();
        setLeads(data.leads || []);
      }
    } catch (error) {
      console.error('Error loading leads:', error);
    }
  };

  const handleCreateOrUpdateReminder = async () => {
    try {
      if (!reminderForm.note.trim() || !reminderForm.due_date) {
        alert('נא למלא את כל השדות הנדרשים');
        return;
      }

      const payload = {
        note: reminderForm.note,
        description: reminderForm.description,
        due_at: `${reminderForm.due_date}T${reminderForm.due_time || '09:00'}:00Z`,
        priority: reminderForm.priority,
        reminder_type: reminderForm.reminder_type,
        lead_id: reminderForm.lead_id ? parseInt(reminderForm.lead_id) : undefined,
        channel: 'ui'
      };

      // Use new general reminders endpoints
      const url = editingReminder 
        ? `/api/reminders/${editingReminder.id}` 
        : `/api/reminders`;
      
      const method = editingReminder ? 'PATCH' : 'POST';

      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload)
      });

      if (response.ok) {
        alert(editingReminder ? 'תזכורת עודכנה בהצלחה!' : 'תזכורת נוצרה בהצלחה!');
        closeReminderModal();
        loadData();
      } else {
        const error = await response.json();
        alert(`שגיאה בשמירת תזכורת: ${error.error || 'שגיאה לא ידועה'}`);
      }
    } catch (error) {
      console.error('Error saving reminder:', error);
      alert('שגיאה בשמירת תזכורת');
    }
  };

  const handleEditReminder = (reminder: CRMReminder) => {
    setEditingReminder(reminder);
    const dueDate = new Date(reminder.due_at);
    setReminderForm({
      note: reminder.note,
      description: reminder.description || '',
      due_date: dueDate.toISOString().split('T')[0],
      due_time: dueDate.toTimeString().slice(0, 5),
      priority: reminder.priority || 'medium',
      reminder_type: reminder.reminder_type || 'general',
      lead_id: reminder.lead_id?.toString() || ''
    });
    setShowReminderModal(true);
  };

  const closeReminderModal = () => {
    setShowReminderModal(false);
    setEditingReminder(null);
    setReminderForm({
      note: '',
      description: '',
      due_date: '',
      due_time: '',
      priority: 'medium',
      reminder_type: 'general',
      lead_id: ''
    });
  };

  const getPendingReminders = () => {
    return reminders.filter(r => !r.completed_at && new Date(r.due_at) > new Date());
  };

  const getOverdueReminders = () => {
    return reminders.filter(r => !r.completed_at && new Date(r.due_at) <= new Date());
  };

  const getCompletedReminders = () => {
    return reminders.filter(r => !!r.completed_at);
  };

  const getPriorityColor = (priority?: string) => {
    switch (priority) {
      case 'high': return 'high';
      case 'medium': return 'medium';
      case 'low': return 'low';
      default: return 'default';
    }
  };

  const getPriorityLabel = (priority?: string) => {
    switch (priority) {
      case 'high': return 'גבוה';
      case 'medium': return 'בינוני';
      case 'low': return 'נמוך';
      default: return 'רגיל';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען נתוני CRM...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="w-6 h-6 text-purple-600" />
            <h1 className="text-2xl font-bold text-gray-900">תזכורות ואנשי קשר</h1>
          </div>
          
          <div className="flex items-center gap-3">
            <Button 
              onClick={() => activeTab === 'reminders' ? setShowReminderModal(true) : setShowContactModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              {activeTab === 'reminders' ? 'תזכורת חדשה' : 'איש קשר חדש'}
            </Button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b border-gray-200 px-6">
        <nav className="flex space-x-8" dir="ltr">
          <button
            onClick={() => setActiveTab('reminders')}
            className={`${
              activeTab === 'reminders'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Bell className="w-4 h-4 mr-2" />
            תזכורות ({reminders.length})
          </button>
          <button
            onClick={() => setActiveTab('contacts')}
            className={`${
              activeTab === 'contacts'
                ? 'border-purple-500 text-purple-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            } whitespace-nowrap py-4 px-1 border-b-2 font-medium text-sm flex items-center`}
          >
            <Users className="w-4 h-4 mr-2" />
            אנשי קשר ({contacts.length})
          </button>
        </nav>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'reminders' ? (
          // Reminders Board
          <div className="h-full p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-full">
              {/* Pending Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="w-5 h-5 text-blue-500" />
                  <h3 className="font-semibold text-gray-900">ממתין</h3>
                  <Badge>{getPendingReminders().length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getPendingReminders().map((reminder) => (
                    <Card key={reminder.id} className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{reminder.note}</h4>
                        {reminder.priority && (
                          <Badge variant={getPriorityColor(reminder.priority)}>
                            {getPriorityLabel(reminder.priority)}
                          </Badge>
                        )}
                      </div>
                      
                      {reminder.description && (
                        <p className="text-sm text-gray-600 mb-3">{reminder.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                        <span>{reminder.lead_name || 'כללי'}</span>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {new Date(reminder.due_at).toLocaleString('he-IL')}
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleEditReminder(reminder)}
                          className="flex-1"
                        >
                          <Edit2 className="w-3 h-3 ml-1" />
                          ערוך
                        </Button>
                      </div>
                    </Card>
                  ))}
                  
                  {getPendingReminders().length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין תזכורות ממתינות</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Overdue Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <AlertCircle className="w-5 h-5 text-red-500" />
                  <h3 className="font-semibold text-gray-900">באיחור</h3>
                  <Badge variant="high">{getOverdueReminders().length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getOverdueReminders().map((reminder) => (
                    <Card key={reminder.id} className="p-4 border-red-200 bg-red-50">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{reminder.note}</h4>
                        {reminder.priority && (
                          <Badge variant={getPriorityColor(reminder.priority)}>
                            {getPriorityLabel(reminder.priority)}
                          </Badge>
                        )}
                      </div>
                      
                      {reminder.description && (
                        <p className="text-sm text-gray-600 mb-3">{reminder.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                        <span>{reminder.lead_name || 'כללי'}</span>
                        <div className="flex items-center gap-1 text-red-600">
                          <AlertCircle className="w-3 h-3" />
                          {new Date(reminder.due_at).toLocaleString('he-IL')}
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleEditReminder(reminder)}
                          className="flex-1"
                        >
                          <Edit2 className="w-3 h-3 ml-1" />
                          ערוך
                        </Button>
                      </div>
                    </Card>
                  ))}
                  
                  {getOverdueReminders().length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <AlertCircle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין תזכורות באיחור</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Completed Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <CheckCircle className="w-5 h-5 text-green-500" />
                  <h3 className="font-semibold text-gray-900">הושלם</h3>
                  <Badge>{getCompletedReminders().length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getCompletedReminders().map((reminder) => (
                    <Card key={reminder.id} className="p-4 border-green-200 bg-green-50">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1 line-through opacity-75">{reminder.note}</h4>
                      </div>
                      
                      {reminder.description && (
                        <p className="text-sm text-gray-600 mb-3 opacity-75">{reminder.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>{reminder.lead_name || 'כללי'}</span>
                        <div className="flex items-center gap-1 text-green-600">
                          <CheckCircle className="w-3 h-3" />
                          הושלם
                        </div>
                      </div>
                    </Card>
                  ))}
                  
                  {getCompletedReminders().length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <CheckCircle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין תזכורות שהושלמו</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ) : (
          // Contacts List
          <div className="h-full p-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {contacts.map((contact) => (
                <Card key={contact.id} className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="font-semibold text-gray-900 mb-1">{contact.name}</h3>
                      {contact.company && (
                        <p className="text-sm text-gray-600">{contact.company}</p>
                      )}
                    </div>
                    <Users className="w-5 h-5 text-gray-400" />
                  </div>
                  
                  <div className="space-y-2 mb-4">
                    {contact.email && (
                      <p className="text-sm text-gray-600" dir="ltr">{contact.email}</p>
                    )}
                    {contact.phone && (
                      <p className="text-sm text-gray-600" dir="ltr">{contact.phone}</p>
                    )}
                  </div>
                  
                  {contact.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-4">
                      {contact.tags.map((tag, index) => (
                        <Badge key={index} variant="default">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                  
                  {contact.lastContact && (
                    <p className="text-xs text-gray-500">
                      קשר אחרון: {new Date(contact.lastContact).toLocaleDateString('he-IL')}
                    </p>
                  )}
                </Card>
              ))}
              
              {contacts.length === 0 && (
                <div className="col-span-full text-center py-12">
                  <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
                  <h3 className="text-lg font-medium text-gray-900 mb-2">אין אנשי קשר</h3>
                  <p className="text-gray-500">התחל בהוספת אנשי הקשר שלך</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Reminder Modal */}
      {showReminderModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-semibold text-gray-900">
                  {editingReminder ? 'ערוך תזכורת' : 'תזכורת חדשה'}
                </h3>
                <button
                  onClick={closeReminderModal}
                  className="p-2 hover:bg-gray-100 rounded-full"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* Note */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    תוכן התזכורת <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={reminderForm.note}
                    onChange={(e) => setReminderForm({...reminderForm, note: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    placeholder="לדוגמה: להתקשר לדוד כהן..."
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    פרטים נוספים
                  </label>
                  <textarea
                    value={reminderForm.description}
                    onChange={(e) => setReminderForm({...reminderForm, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500 resize-none"
                    rows={3}
                    placeholder="הוסף פרטים נוספים..."
                  />
                </div>

                {/* Date and Time */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      תאריך <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="date"
                      value={reminderForm.due_date}
                      onChange={(e) => setReminderForm({...reminderForm, due_date: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      שעה
                    </label>
                    <input
                      type="time"
                      value={reminderForm.due_time}
                      onChange={(e) => setReminderForm({...reminderForm, due_time: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                </div>

                {/* Priority */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    עדיפות
                  </label>
                  <select
                    value={reminderForm.priority}
                    onChange={(e) => setReminderForm({...reminderForm, priority: e.target.value as any})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="low">נמוך</option>
                    <option value="medium">בינוני</option>
                    <option value="high">גבוה</option>
                  </select>
                </div>

                {/* Reminder Type */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    סוג תזכורת
                  </label>
                  <select
                    value={reminderForm.reminder_type}
                    onChange={(e) => setReminderForm({...reminderForm, reminder_type: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="general">כללי</option>
                    <option value="call">שיחה</option>
                    <option value="meeting">פגישה</option>
                    <option value="email">דוא"ל</option>
                    <option value="task">משימה</option>
                  </select>
                </div>

                {/* Lead Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    קשור לליד
                  </label>
                  <select
                    value={reminderForm.lead_id}
                    onChange={(e) => setReminderForm({...reminderForm, lead_id: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="">-- לא משויך לליד --</option>
                    {leads.map(lead => (
                      <option key={lead.id} value={lead.id}>
                        {lead.full_name || `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'ללא שם'} {lead.phone_e164 ? `(${lead.phone_e164})` : ''}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Actions */}
                <div className="flex justify-end gap-3 pt-4 border-t">
                  <Button
                    variant="outline"
                    onClick={closeReminderModal}
                  >
                    ביטול
                  </Button>
                  <Button
                    onClick={handleCreateOrUpdateReminder}
                  >
                    {editingReminder ? 'עדכן תזכורת' : 'צור תזכורת'}
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
