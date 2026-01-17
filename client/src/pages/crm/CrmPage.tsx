import React, { useState, useEffect } from 'react';
import { formatDate, formatDateOnly, formatTimeOnly, formatRelativeTime } from '../../shared/utils/format';
import { Plus, Users, Bell, Calendar, CheckCircle, Circle, Clock, X, Edit2, AlertCircle, Trash2, Loader2, Filter, ChevronDown, ChevronUp } from 'lucide-react';
import { useNotifications } from '../../shared/contexts/NotificationContext';
import { http } from '../../services/http';

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

// Task interface (previously Reminder)
interface CRMTask {
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

interface Lead {
  id: number;
  full_name?: string;
  first_name?: string;
  last_name?: string;
  phone_e164?: string;
}

export function CrmPage() {
  const { refreshNotifications } = useNotifications();
  const [tasks, setTasks] = useState<CRMTask[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [editingTask, setEditingTask] = useState<CRMTask | null>(null);
  const [deletingCompleted, setDeletingCompleted] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deletingTask, setDeletingTask] = useState<string | number | null>(null);
  // Date range filter state
  const [dateFilterFrom, setDateFilterFrom] = useState('');
  const [dateFilterTo, setDateFilterTo] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [taskForm, setTaskForm] = useState({
    note: '',
    description: '',
    due_date: '',
    due_time: '',
    priority: 'medium' as 'low' | 'medium' | 'high',
    reminder_type: 'general',
    lead_id: ''
  });

  useEffect(() => {
    // Fire both requests in parallel (each handles its own errors)
    loadData();
    loadLeads();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // Fetch tasks from API using http service (includes CSRF)
      const data = await http.get<{reminders: CRMTask[]}>('/api/reminders');
      setTasks(data.reminders || []);
    } catch (error) {
      console.error('Error loading tasks data:', error);
      setTasks([]);
    } finally {
      setLoading(false);
    }
  };

  const loadLeads = async () => {
    try {
      const data = await http.get<{items?: Lead[], leads?: Lead[]}>('/api/leads');
      setLeads(data.items || data.leads || []);
    } catch (error) {
      console.error('Error loading leads:', error);
    }
  };

  const handleCreateOrUpdateTask = async () => {
    try {
      if (!taskForm.note.trim() || !taskForm.due_date) {
        alert('נא למלא את כל השדות הנדרשים');
        return;
      }

      // 🔥 FIX: Send local Israel time without timezone conversion
      // The server expects naive datetime (local Israel time) without timezone suffix
      // Don't use toISOString() as it converts to UTC
      const localDateTime = `${taskForm.due_date}T${taskForm.due_time || '09:00'}:00`;
      const due_at = localDateTime; // Send as-is (YYYY-MM-DDTHH:MM:SS)

      const payload = {
        note: taskForm.note,
        description: taskForm.description,
        due_at,
        priority: taskForm.priority,
        reminder_type: taskForm.reminder_type,
        lead_id: taskForm.lead_id ? parseInt(taskForm.lead_id) : undefined,
        channel: 'ui'
      };

      // Use http service with CSRF token
      if (editingTask) {
        await http.patch(`/api/reminders/${editingTask.id}`, payload);
      } else {
        await http.post('/api/reminders', payload);
      }
      
      alert(editingTask ? 'משימה עודכנה בהצלחה!' : 'משימה נוצרה בהצלחה!');
      closeTaskModal();
      loadData();
      // Refresh notifications when task is created/updated
      refreshNotifications();
    } catch (error: any) {
      console.error('Error saving task:', error);
      alert(`שגיאה בשמירת משימה: ${error.message || 'שגיאה לא ידועה'}`);
    }
  };

  const handleEditTask = (task: CRMTask) => {
    setEditingTask(task);
    
    // 🔥 FIX: Parse datetime WITHOUT timezone conversion
    // The server sends Israel time with timezone info
    // Extract date/time parts directly without JavaScript timezone conversion
    const dateTimePart = task.due_at.split('+')[0].split('Z')[0].split('.')[0];
    
    let due_date = '';
    let due_time = '';
    
    if (dateTimePart.includes('T')) {
      const [datePart, timePart] = dateTimePart.split('T');
      due_date = datePart;
      const [hours, minutes] = timePart.split(':');
      due_time = `${hours}:${minutes}`;
    } else {
      // Fallback: use Date object (will convert to browser local time)
      const dueDate = new Date(task.due_at);
      const year = dueDate.getFullYear();
      const month = String(dueDate.getMonth() + 1).padStart(2, '0');
      const day = String(dueDate.getDate()).padStart(2, '0');
      const hours = String(dueDate.getHours()).padStart(2, '0');
      const minutes = String(dueDate.getMinutes()).padStart(2, '0');
      due_date = `${year}-${month}-${day}`;
      due_time = `${hours}:${minutes}`;
    }
    
    setTaskForm({
      note: task.note,
      description: task.description || '',
      due_date,
      due_time,
      priority: task.priority || 'medium',
      reminder_type: task.reminder_type || 'general',
      lead_id: task.lead_id?.toString() || ''
    });
    setShowTaskModal(true);
  };

  const handleCompleteTask = async (task: CRMTask) => {
    if (!task.lead_id) {
      alert('לא ניתן להשלים משימה ללא ליד מקושר');
      return;
    }
    
    try {
      // Use http.patch with CSRF token
      await http.patch(`/api/leads/${task.lead_id}/reminders/${task.id}`, { completed: true });
      loadData();
      // Refresh notifications when task is completed
      refreshNotifications();
    } catch (error: any) {
      console.error('Error completing task:', error);
      alert(`שגיאה בסימון משימה: ${error.message || 'שגיאה לא ידועה'}`);
    }
  };

  const closeTaskModal = () => {
    setShowTaskModal(false);
    setEditingTask(null);
    setTaskForm({
      note: '',
      description: '',
      due_date: '',
      due_time: '',
      priority: 'medium',
      reminder_type: 'general',
      lead_id: ''
    });
  };

  const handleDeleteCompletedTasks = async () => {
    const completedTasks = getCompletedTasks();
    if (completedTasks.length === 0) return;
    
    setDeletingCompleted(true);
    try {
      let deleted = 0;
      let failed = 0;
      
      for (const task of completedTasks) {
        try {
          await http.delete(`/api/reminders/${task.id}`);
          deleted++;
        } catch (err) {
          console.error(`Failed to delete task ${task.id}:`, err);
          failed++;
        }
      }
      
      if (failed > 0) {
        alert(`נמחקו ${deleted} משימות, ${failed} נכשלו`);
      }
      
      loadData();
      refreshNotifications();
    } catch (error: any) {
      console.error('Error deleting completed tasks:', error);
      alert(`שגיאה במחיקת משימות: ${error.message || 'שגיאה לא ידועה'}`);
    } finally {
      setDeletingCompleted(false);
      setShowDeleteConfirm(false);
    }
  };

  const handleDeleteSingleTask = async (taskId: string | number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק משימה זו?')) {
      return;
    }
    
    setDeletingTask(taskId);
    try {
      await http.delete(`/api/reminders/${taskId}`);
      loadData();
      refreshNotifications();
    } catch (error: any) {
      console.error('Error deleting task:', error);
      alert(`שגיאה במחיקת משימה: ${error.message || 'שגיאה לא ידועה'}`);
    } finally {
      setDeletingTask(null);
    }
  };

  // Date range filter helper
  const isInDateRange = (dueAt: string): boolean => {
    if (!dateFilterFrom && !dateFilterTo) return true;
    
    const taskDate = new Date(dueAt);
    const fromDate = dateFilterFrom ? new Date(dateFilterFrom + 'T00:00:00') : null;
    const toDate = dateFilterTo ? new Date(dateFilterTo + 'T23:59:59') : null;
    
    if (fromDate && taskDate < fromDate) return false;
    if (toDate && taskDate > toDate) return false;
    
    return true;
  };

  const clearDateFilters = () => {
    setDateFilterFrom('');
    setDateFilterTo('');
  };

  const getPendingTasks = () => {
    return tasks.filter(r => !r.completed_at && new Date(r.due_at) > new Date() && isInDateRange(r.due_at));
  };

  const getOverdueTasks = () => {
    return tasks.filter(r => !r.completed_at && new Date(r.due_at) <= new Date() && isInDateRange(r.due_at));
  };

  const getCompletedTasks = () => {
    return tasks.filter(r => !!r.completed_at && isInDateRange(r.due_at));
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
          <p>טוען משימות...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-gray-50 pb-20 md:pb-6">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 md:px-6 py-4 sticky top-0 z-10">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell className="w-6 h-6 text-purple-600" />
            <h1 className="text-xl md:text-2xl font-bold text-gray-900">משימות</h1>
          </div>
          
          <div className="flex items-center gap-2 md:gap-3">
            {/* Filter Toggle Button */}
            <Button 
              variant="outline"
              onClick={() => setShowFilters(!showFilters)}
              className={`${(dateFilterFrom || dateFilterTo) ? 'border-purple-500 text-purple-600' : ''}`}
            >
              <Filter className="w-4 h-4 mr-1" />
              <span className="hidden sm:inline">סינון</span>
              {showFilters ? <ChevronUp className="w-4 h-4 mr-1" /> : <ChevronDown className="w-4 h-4 mr-1" />}
            </Button>
            
            <Button 
              onClick={() => setShowTaskModal(true)}
            >
              <Plus className="w-4 h-4 mr-2" />
              <span className="hidden sm:inline">משימה חדשה</span>
              <span className="sm:hidden">חדש</span>
            </Button>
          </div>
        </div>
        
        {/* Date Range Filter - Collapsible */}
        {showFilters && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center">
              <div className="flex items-center gap-2 text-sm text-gray-600">
                <Calendar className="w-4 h-4" />
                <span>סינון לפי תאריך:</span>
              </div>
              <div className="flex flex-wrap gap-2 items-center">
                <div className="flex items-center gap-1">
                  <label className="text-sm text-gray-500">מתאריך:</label>
                  <input
                    type="date"
                    value={dateFilterFrom}
                    onChange={(e) => setDateFilterFrom(e.target.value)}
                    className="px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  />
                </div>
                <div className="flex items-center gap-1">
                  <label className="text-sm text-gray-500">עד תאריך:</label>
                  <input
                    type="date"
                    value={dateFilterTo}
                    onChange={(e) => setDateFilterTo(e.target.value)}
                    className="px-2 py-1.5 border border-gray-300 rounded-md text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  />
                </div>
                {(dateFilterFrom || dateFilterTo) && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={clearDateFilters}
                    className="text-red-600 hover:bg-red-50"
                  >
                    <X className="w-4 h-4 mr-1" />
                    נקה
                  </Button>
                )}
              </div>
            </div>
            {(dateFilterFrom || dateFilterTo) && (
              <div className="mt-2 text-sm text-purple-600">
                מציג משימות {dateFilterFrom ? `מ-${dateFilterFrom}` : ''} {dateFilterTo ? `עד ${dateFilterTo}` : ''}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Content - Scrollable on mobile */}
      <div className="flex-1 overflow-y-auto">
          {/* Tasks Board */}
          <div className="p-4 md:p-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
              {/* Pending Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <Clock className="w-5 h-5 text-blue-500" />
                  <h3 className="font-semibold text-gray-900">ממתין</h3>
                  <Badge>{getPendingTasks().length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getPendingTasks().map((task) => (
                    <Card key={task.id} className="p-4">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{task.note}</h4>
                        {task.priority && (
                          <Badge variant={getPriorityColor(task.priority)}>
                            {getPriorityLabel(task.priority)}
                          </Badge>
                        )}
                      </div>
                      
                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                        <span>{task.lead_name || 'כללי'}</span>
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {formatDate(task.due_at)}
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleCompleteTask(task)}
                          className="flex-1 text-green-600 hover:bg-green-50"
                          data-testid={`button-complete-task-${task.id}`}
                        >
                          <CheckCircle className="w-3 h-3 ml-1" />
                          השלם
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleEditTask(task)}
                          className="flex-1"
                          data-testid={`button-edit-task-${task.id}`}
                        >
                          <Edit2 className="w-3 h-3 ml-1" />
                          ערוך
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleDeleteSingleTask(task.id)}
                          className="text-red-600 hover:bg-red-50"
                          disabled={deletingTask === task.id}
                          data-testid={`button-delete-task-${task.id}`}
                        >
                          {deletingTask === task.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Trash2 className="w-3 h-3" />
                          )}
                        </Button>
                      </div>
                    </Card>
                  ))}
                  
                  {getPendingTasks().length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <Clock className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין משימות ממתינות</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Overdue Column */}
              <div className="flex flex-col">
                <div className="flex items-center gap-2 mb-4">
                  <AlertCircle className="w-5 h-5 text-red-500" />
                  <h3 className="font-semibold text-gray-900">באיחור</h3>
                  <Badge variant="high">{getOverdueTasks().length}</Badge>
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getOverdueTasks().map((task) => (
                    <Card key={task.id} className="p-4 border-red-200 bg-red-50">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1">{task.note}</h4>
                        {task.priority && (
                          <Badge variant={getPriorityColor(task.priority)}>
                            {getPriorityLabel(task.priority)}
                          </Badge>
                        )}
                      </div>
                      
                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3">{task.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500 mb-3">
                        <span>{task.lead_name || 'כללי'}</span>
                        <div className="flex items-center gap-1 text-red-600">
                          <AlertCircle className="w-3 h-3" />
                          {formatDate(task.due_at)}
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleCompleteTask(task)}
                          className="flex-1 text-green-600 hover:bg-green-50"
                          data-testid={`button-complete-overdue-task-${task.id}`}
                        >
                          <CheckCircle className="w-3 h-3 ml-1" />
                          השלם
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleEditTask(task)}
                          className="flex-1"
                          data-testid={`button-edit-overdue-task-${task.id}`}
                        >
                          <Edit2 className="w-3 h-3 ml-1" />
                          ערוך
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleDeleteSingleTask(task.id)}
                          className="text-red-600 hover:bg-red-50"
                          disabled={deletingTask === task.id}
                          data-testid={`button-delete-overdue-task-${task.id}`}
                        >
                          {deletingTask === task.id ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <Trash2 className="w-3 h-3" />
                          )}
                        </Button>
                      </div>
                    </Card>
                  ))}
                  
                  {getOverdueTasks().length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <AlertCircle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין משימות באיחור</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Completed Column */}
              <div className="flex flex-col">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="w-5 h-5 text-green-500" />
                    <h3 className="font-semibold text-gray-900">הושלם</h3>
                    <Badge>{getCompletedTasks().length}</Badge>
                  </div>
                  {getCompletedTasks().length > 0 && (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowDeleteConfirm(true)}
                      className="text-red-600 hover:bg-red-50 hover:text-red-700"
                      disabled={deletingCompleted}
                      data-testid="button-delete-completed"
                    >
                      {deletingCompleted ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Trash2 className="w-4 h-4 ml-1" />
                          מחק הכל
                        </>
                      )}
                    </Button>
                  )}
                </div>
                
                <div className="flex-1 space-y-3 overflow-y-auto">
                  {getCompletedTasks().map((task) => (
                    <Card key={task.id} className="p-4 border-green-200 bg-green-50">
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-medium text-gray-900 flex-1 line-through opacity-75">{task.note}</h4>
                      </div>
                      
                      {task.description && (
                        <p className="text-sm text-gray-600 mb-3 opacity-75">{task.description}</p>
                      )}
                      
                      <div className="flex items-center justify-between text-xs text-gray-500">
                        <span>{task.lead_name || 'כללי'}</span>
                        <div className="flex items-center gap-1 text-green-600">
                          <CheckCircle className="w-3 h-3" />
                          הושלם
                        </div>
                      </div>
                    </Card>
                  ))}
                  
                  {getCompletedTasks().length === 0 && (
                    <div className="text-center py-8 text-gray-500">
                      <CheckCircle className="w-8 h-8 mx-auto mb-2 text-gray-300" />
                      <p className="text-sm">אין משימות שהושלמו</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
      </div>

      {/* Reminder Modal */}
      {showTaskModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-semibold text-gray-900">
                  {editingTask ? 'ערוך משימה' : 'משימה חדשה'}
                </h3>
                <button
                  onClick={closeTaskModal}
                  className="p-2 hover:bg-gray-100 rounded-full"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="space-y-4">
                {/* Note */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    תוכן המשימה <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={taskForm.note}
                    onChange={(e) => setTaskForm({...taskForm, note: e.target.value})}
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
                    value={taskForm.description}
                    onChange={(e) => setTaskForm({...taskForm, description: e.target.value})}
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
                      value={taskForm.due_date}
                      onChange={(e) => setTaskForm({...taskForm, due_date: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      שעה
                    </label>
                    <input
                      type="time"
                      value={taskForm.due_time}
                      onChange={(e) => setTaskForm({...taskForm, due_time: e.target.value})}
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
                    value={taskForm.priority}
                    onChange={(e) => setTaskForm({...taskForm, priority: e.target.value as any})}
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
                    value={taskForm.reminder_type}
                    onChange={(e) => setTaskForm({...taskForm, reminder_type: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="general">כללי</option>
                    <option value="call">שיחה</option>
                    <option value="meeting">פגישה</option>
                    <option value="email">דוא"ל</option>
                    <option value="follow_up">מעקב</option>
                  </select>
                </div>

                {/* Lead Selection */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    קשור לליד
                  </label>
                  <select
                    value={taskForm.lead_id}
                    onChange={(e) => setTaskForm({...taskForm, lead_id: e.target.value})}
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
                    onClick={closeTaskModal}
                  >
                    ביטול
                  </Button>
                  <Button
                    onClick={handleCreateOrUpdateTask}
                  >
                    {editingTask ? 'עדכן משימה' : 'צור משימה'}
                  </Button>
                </div>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
          <Card className="w-full max-w-md">
            <div className="p-6">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center">
                  <Trash2 className="w-6 h-6 text-red-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">מחיקת משימות שהושלמו</h3>
                  <p className="text-sm text-gray-500">פעולה זו לא ניתנת לביטול</p>
                </div>
              </div>
              
              <p className="text-gray-700 mb-6">
                האם אתה בטוח שברצונך למחוק את כל {getCompletedTasks().length} המשימות שהושלמו?
              </p>
              
              <div className="flex justify-end gap-3">
                <Button
                  variant="outline"
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={deletingCompleted}
                  data-testid="button-cancel-delete"
                >
                  ביטול
                </Button>
                <Button
                  variant="danger"
                  onClick={handleDeleteCompletedTasks}
                  disabled={deletingCompleted}
                  data-testid="button-confirm-delete"
                >
                  {deletingCompleted ? (
                    <>
                      <Loader2 className="w-4 h-4 ml-1 animate-spin" />
                      מוחק...
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-4 h-4 ml-1" />
                      מחק הכל
                    </>
                  )}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
