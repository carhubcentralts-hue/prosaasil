import React, { useState, useEffect } from 'react';
import { 
  Calendar as CalendarIcon, 
  Plus, 
  Filter, 
  Search,
  MapPin,
  Clock,
  Phone,
  MessageCircle,
  User,
  ChevronLeft,
  ChevronRight,
  Eye,
  Edit,
  Trash2
} from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';

// Calendar components and types
interface Appointment {
  id: number;
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  location?: string;
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show';
  appointment_type: 'viewing' | 'meeting' | 'signing' | 'call_followup';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  contact_name?: string;
  contact_phone?: string;
  customer_id?: number;
  source: 'manual' | 'phone_call' | 'whatsapp' | 'ai_suggested';
  auto_generated: boolean;
}

const APPOINTMENT_TYPES = {
  viewing: { label: 'צפייה', color: 'bg-blue-100 text-blue-800' },
  meeting: { label: 'פגישה', color: 'bg-green-100 text-green-800' },
  signing: { label: 'חתימה', color: 'bg-purple-100 text-purple-800' },
  call_followup: { label: 'מעקב שיחה', color: 'bg-orange-100 text-orange-800' }
};

const STATUS_TYPES = {
  scheduled: { label: 'מתוכנן', color: 'bg-gray-100 text-gray-800' },
  confirmed: { label: 'מאושר', color: 'bg-blue-100 text-blue-800' },
  completed: { label: 'הושלם', color: 'bg-green-100 text-green-800' },
  cancelled: { label: 'בוטל', color: 'bg-red-100 text-red-800' },
  no_show: { label: 'לא הגיע', color: 'bg-yellow-100 text-yellow-800' }
};

const PRIORITY_TYPES = {
  low: { label: 'נמוך', color: 'bg-slate-100 text-slate-600' },
  medium: { label: 'בינוני', color: 'bg-amber-100 text-amber-700' },
  high: { label: 'גבוה', color: 'bg-orange-100 text-orange-700' },
  urgent: { label: 'דחוף', color: 'bg-red-100 text-red-700' }
};

export function CalendarPage() {
  const { user } = useAuth();
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [currentView, setCurrentView] = useState<'month' | 'week' | 'day'>('month');
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterType, setFilterType] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [showNewAppointmentModal, setShowNewAppointmentModal] = useState(false);

  // Fetch appointments
  const fetchAppointments = async () => {
    try {
      setLoading(true);
      const response = await fetch('/api/calendar/appointments', {
        credentials: 'include'
      });
      
      if (response.ok) {
        const data = await response.json();
        setAppointments(data.appointments || []);
      } else {
        console.error('שגיאה בטעינת פגישות');
      }
    } catch (error) {
      console.error('שגיאה בטעינת פגישות:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  // Calendar navigation
  const navigateMonth = (direction: 'prev' | 'next') => {
    const newDate = new Date(currentDate);
    newDate.setMonth(currentDate.getMonth() + (direction === 'next' ? 1 : -1));
    setCurrentDate(newDate);
  };

  // Get days in month for calendar grid
  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear();
    const month = date.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    const daysInMonth = lastDay.getDate();
    const startingDayOfWeek = firstDay.getDay(); // 0 = Sunday

    const days = [];
    
    // Add previous month's trailing days
    for (let i = startingDayOfWeek - 1; i >= 0; i--) {
      const prevDate = new Date(year, month, -i);
      days.push({ date: prevDate, isCurrentMonth: false });
    }
    
    // Add current month's days
    for (let day = 1; day <= daysInMonth; day++) {
      days.push({ date: new Date(year, month, day), isCurrentMonth: true });
    }
    
    // Add next month's leading days to complete the grid
    const remainingCells = 42 - days.length; // 6 rows × 7 days
    for (let day = 1; day <= remainingCells; day++) {
      days.push({ date: new Date(year, month + 1, day), isCurrentMonth: false });
    }
    
    return days;
  };

  // Get appointments for a specific date
  const getAppointmentsForDate = (date: Date) => {
    const dateStr = date.toISOString().split('T')[0];
    return appointments.filter(apt => 
      apt.start_time.split('T')[0] === dateStr
    );
  };

  // Filter appointments
  const filteredAppointments = appointments.filter(apt => {
    const matchesStatus = filterStatus === 'all' || apt.status === filterStatus;
    const matchesType = filterType === 'all' || apt.appointment_type === filterType;
    const matchesSearch = searchTerm === '' || 
      apt.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      apt.contact_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
      apt.description?.toLowerCase().includes(searchTerm.toLowerCase());
    
    return matchesStatus && matchesType && matchesSearch;
  });

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex items-center gap-3 text-slate-600">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span>טוען פגישות...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6" dir="rtl">
      {/* Header */}
      <div className="flex justify-between items-center mb-8">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 mb-2">לוח שנה</h1>
          <p className="text-slate-600">
            ניהול פגישות ומעקב אחר כל הפעילות העסקית
          </p>
        </div>
        
        <button
          className="btn-primary flex items-center gap-2"
          onClick={() => setShowNewAppointmentModal(true)}
          data-testid="button-new-appointment"
        >
          <Plus className="h-5 w-5" />
          פגישה חדשה
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">פגישות היום</p>
              <p className="text-2xl font-bold text-slate-900">
                {getAppointmentsForDate(new Date()).length}
              </p>
            </div>
            <CalendarIcon className="h-8 w-8 text-blue-600" />
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">מתוכננות</p>
              <p className="text-2xl font-bold text-slate-900">
                {appointments.filter(a => a.status === 'scheduled').length}
              </p>
            </div>
            <Clock className="h-8 w-8 text-amber-600" />
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">מאושרות</p>
              <p className="text-2xl font-bold text-slate-900">
                {appointments.filter(a => a.status === 'confirmed').length}
              </p>
            </div>
            <Phone className="h-8 w-8 text-green-600" />
          </div>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">מקור AI</p>
              <p className="text-2xl font-bold text-slate-900">
                {appointments.filter(a => a.auto_generated).length}
              </p>
            </div>
            <MessageCircle className="h-8 w-8 text-purple-600" />
          </div>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-8">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              placeholder="חיפוש פגישות, לקוחות או מיקומים..."
              className="input-field pr-10"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              data-testid="input-search-appointments"
            />
          </div>

          {/* Filters */}
          <div className="flex gap-4">
            <select 
              className="input-field min-w-[150px]"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              data-testid="select-filter-status"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="scheduled">מתוכנן</option>
              <option value="confirmed">מאושר</option>
              <option value="completed">הושלם</option>
              <option value="cancelled">בוטל</option>
              <option value="no_show">לא הגיע</option>
            </select>

            <select 
              className="input-field min-w-[150px]"
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              data-testid="select-filter-type"
            >
              <option value="all">כל הסוגים</option>
              <option value="viewing">צפייה</option>
              <option value="meeting">פגישה</option>
              <option value="signing">חתימה</option>
              <option value="call_followup">מעקב שיחה</option>
            </select>

            {/* View Toggle */}
            <div className="flex bg-slate-100 rounded-lg p-1">
              {(['month', 'week', 'day'] as const).map((view) => (
                <button
                  key={view}
                  className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                    currentView === view 
                      ? 'bg-white text-slate-900 shadow-sm' 
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                  onClick={() => setCurrentView(view)}
                  data-testid={`button-view-${view}`}
                >
                  {view === 'month' ? 'חודש' : view === 'week' ? 'שבוע' : 'יום'}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Calendar Display */}
      {currentView === 'month' && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
          {/* Calendar Header */}
          <div className="flex items-center justify-between p-6 border-b border-slate-200">
            <h2 className="text-xl font-semibold text-slate-900">
              {currentDate.toLocaleDateString('he-IL', { 
                month: 'long', 
                year: 'numeric' 
              })}
            </h2>
            <div className="flex items-center gap-2">
              <button
                className="btn-ghost p-2"
                onClick={() => navigateMonth('prev')}
                data-testid="button-prev-month"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
              <button
                className="btn-ghost px-4 py-2"
                onClick={() => setCurrentDate(new Date())}
                data-testid="button-today"
              >
                היום
              </button>
              <button
                className="btn-ghost p-2"
                onClick={() => navigateMonth('next')}
                data-testid="button-next-month"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
            </div>
          </div>

          {/* Calendar Grid */}
          <div className="p-6">
            {/* Days of week header */}
            <div className="grid grid-cols-7 gap-1 mb-4">
              {['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ש'].map((day) => (
                <div key={day} className="text-center font-medium text-slate-500 py-2">
                  {day}
                </div>
              ))}
            </div>

            {/* Calendar days */}
            <div className="grid grid-cols-7 gap-1">
              {getDaysInMonth(currentDate).map((day, index) => {
                const dayAppointments = getAppointmentsForDate(day.date);
                const isToday = day.date.toDateString() === new Date().toDateString();
                
                return (
                  <div
                    key={index}
                    className={`
                      min-h-[120px] p-2 border rounded-lg cursor-pointer hover:bg-slate-50
                      ${day.isCurrentMonth ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-100'}
                      ${isToday ? 'border-blue-500 bg-blue-50' : ''}
                    `}
                    onClick={() => setSelectedDate(day.date)}
                    data-testid={`calendar-day-${day.date.getDate()}`}
                  >
                    <div className={`
                      text-sm font-medium mb-1
                      ${day.isCurrentMonth ? 'text-slate-900' : 'text-slate-400'}
                      ${isToday ? 'text-blue-600 font-bold' : ''}
                    `}>
                      {day.date.getDate()}
                    </div>
                    
                    {/* Appointments for this day */}
                    <div className="space-y-1">
                      {dayAppointments.slice(0, 3).map((apt) => (
                        <div
                          key={apt.id}
                          className={`
                            text-xs px-2 py-1 rounded text-right truncate
                            ${APPOINTMENT_TYPES[apt.appointment_type]?.color || 'bg-gray-100 text-gray-800'}
                          `}
                          title={`${apt.title} - ${apt.start_time.split('T')[1].substring(0, 5)}`}
                        >
                          {apt.title}
                        </div>
                      ))}
                      {dayAppointments.length > 3 && (
                        <div className="text-xs text-slate-500 px-2">
                          +{dayAppointments.length - 3} נוספות
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Appointments List */}
      <div className="mt-8 bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="p-6 border-b border-slate-200">
          <h3 className="text-lg font-semibold text-slate-900">
            פגישות ({filteredAppointments.length})
          </h3>
        </div>
        
        <div className="divide-y divide-slate-200">
          {filteredAppointments.length === 0 ? (
            <div className="p-12 text-center">
              <CalendarIcon className="h-16 w-16 text-slate-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 mb-2">
                אין פגישות
              </h3>
              <p className="text-slate-600 mb-6">
                טרם נוספו פגישות למערכת. צור פגישה חדשה כדי להתחיל
              </p>
              <button
                className="btn-primary"
                onClick={() => setShowNewAppointmentModal(true)}
              >
                <Plus className="h-5 w-5 mr-2" />
                פגישה חדשה
              </button>
            </div>
          ) : (
            filteredAppointments.map((appointment) => (
              <div key={appointment.id} className="p-6 hover:bg-slate-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h4 className="text-lg font-medium text-slate-900">
                        {appointment.title}
                      </h4>
                      <span className={`
                        inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                        ${STATUS_TYPES[appointment.status]?.color}
                      `}>
                        {STATUS_TYPES[appointment.status]?.label}
                      </span>
                      <span className={`
                        inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium
                        ${APPOINTMENT_TYPES[appointment.appointment_type]?.color}
                      `}>
                        {APPOINTMENT_TYPES[appointment.appointment_type]?.label}
                      </span>
                      {appointment.auto_generated && (
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                          AI
                        </span>
                      )}
                    </div>
                    
                    <div className="flex items-center gap-6 text-sm text-slate-600 mb-3">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4" />
                        {new Date(appointment.start_time).toLocaleDateString('he-IL')} • 
                        {new Date(appointment.start_time).toLocaleTimeString('he-IL', { 
                          hour: '2-digit', 
                          minute: '2-digit' 
                        })}
                      </div>
                      {appointment.location && (
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4" />
                          {appointment.location}
                        </div>
                      )}
                      {appointment.contact_name && (
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4" />
                          {appointment.contact_name}
                        </div>
                      )}
                      {appointment.contact_phone && (
                        <div className="flex items-center gap-2">
                          <Phone className="h-4 w-4" />
                          {appointment.contact_phone}
                        </div>
                      )}
                    </div>
                    
                    {appointment.description && (
                      <p className="text-slate-600 text-sm">
                        {appointment.description}
                      </p>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-2 mr-4">
                    <button
                      className="btn-ghost p-2"
                      title="צפה בפרטים"
                      data-testid={`button-view-appointment-${appointment.id}`}
                    >
                      <Eye className="h-5 w-5" />
                    </button>
                    <button
                      className="btn-ghost p-2"
                      title="ערוך פגישה"
                      data-testid={`button-edit-appointment-${appointment.id}`}
                    >
                      <Edit className="h-5 w-5" />
                    </button>
                    <button
                      className="btn-ghost p-2 text-red-600 hover:text-red-700"
                      title="מחק פגישה"
                      data-testid={`button-delete-appointment-${appointment.id}`}
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* New Appointment Modal - Placeholder */}
      {showNewAppointmentModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">
              פגישה חדשה
            </h3>
            <p className="text-slate-600 mb-6">
              טופס יצירת פגישה חדשה יפותח בשלב הבא
            </p>
            <div className="flex gap-3">
              <button
                className="btn-primary flex-1"
                onClick={() => setShowNewAppointmentModal(false)}
              >
                בקרוב
              </button>
              <button
                className="btn-ghost flex-1"
                onClick={() => setShowNewAppointmentModal(false)}
              >
                ביטול
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}