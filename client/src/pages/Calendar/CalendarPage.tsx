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
  Trash2,
  X,
  Save,
  Calendar
} from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import { http } from '../../services/http';

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

interface AppointmentForm {
  title: string;
  description: string;
  start_time: string;
  end_time: string;
  location: string;
  status: 'scheduled' | 'confirmed' | 'completed' | 'cancelled' | 'no_show';
  appointment_type: 'viewing' | 'meeting' | 'signing' | 'call_followup';
  priority: 'low' | 'medium' | 'high' | 'urgent';
  contact_name: string;
  contact_phone: string;
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
  const [showFilters, setShowFilters] = useState(false);
  
  // Modal states
  const [showAppointmentModal, setShowAppointmentModal] = useState(false);
  const [editingAppointment, setEditingAppointment] = useState<Appointment | null>(null);
  const [formData, setFormData] = useState<AppointmentForm>({
    title: '',
    description: '',
    start_time: '',
    end_time: '',
    location: '',
    status: 'scheduled',
    appointment_type: 'meeting',
    priority: 'medium',
    contact_name: '',
    contact_phone: ''
  });

  // Fetch appointments using the proper HTTP client
  const fetchAppointments = async () => {
    try {
      setLoading(true);
      // ✅ משתמש בhttp service שמכיל את כל ההגדרות הנכונות
      const data = await http.get<{appointments: Appointment[]}>('/api/calendar/appointments');
      setAppointments(data.appointments || []);
    } catch (error) {
      console.error('שגיאה בטעינת פגישות:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAppointments();
  }, []);

  // Filter appointments based on search and filters
  const filteredAppointments = appointments.filter(appointment => {
    const matchesSearch = !searchTerm || 
      appointment.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      appointment.contact_name?.toLowerCase().includes(searchTerm.toLowerCase());
    
    const matchesStatus = filterStatus === 'all' || appointment.status === filterStatus;
    const matchesType = filterType === 'all' || appointment.appointment_type === filterType;
    
    return matchesSearch && matchesStatus && matchesType;
  });

  // Get appointments for a specific date
  const getAppointmentsForDate = (date: Date) => {
    return filteredAppointments.filter(appointment => {
      const appointmentDate = new Date(appointment.start_time);
      return appointmentDate.toDateString() === date.toDateString();
    });
  };

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
    
    return days;
  };

  // Handle form submit
  const handleSubmitAppointment = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const url = editingAppointment 
        ? `/api/calendar/appointments/${editingAppointment.id}` 
        : '/api/calendar/appointments';
      
      const method = editingAppointment ? 'PUT' : 'POST';
      
      // Convert datetime-local values to ISO format with timezone
      const dataToSend = {
        ...formData,
        start_time: formData.start_time ? new Date(formData.start_time).toISOString() : formData.start_time,
        end_time: formData.end_time ? new Date(formData.end_time).toISOString() : formData.end_time
      };
      
      const response = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(dataToSend)
      });

      if (response.ok) {
        await fetchAppointments(); // Refresh appointments
        closeModal();
        alert(editingAppointment ? 'הפגישה עודכנה בהצלחה!' : 'הפגישה נוצרה בהצלחה!');
      } else {
        const errorData = await response.json().catch(() => ({}));
        alert(`שגיאה בשמירת הפגישה: ${errorData.error || 'שגיאה לא ידועה'}`);
        console.error('שגיאה בשמירת הפגישה', errorData);
      }
    } catch (error) {
      alert('שגיאה בשמירת הפגישה. אנא נסה שוב.');
      console.error('שגיאה בשמירת הפגישה:', error);
    }
  };

  // Handle delete appointment
  const handleDeleteAppointment = async (id: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק פגישה זו?')) return;
    
    try {
      const response = await fetch(`/api/calendar/appointments/${id}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (response.ok) {
        await fetchAppointments();
      } else {
        console.error('שגיאה במחיקת הפגישה');
      }
    } catch (error) {
      console.error('שגיאה במחיקת הפגישה:', error);
    }
  };

  // Open modal for new appointment
  const openNewAppointmentModal = () => {
    setEditingAppointment(null);
    setFormData({
      title: '',
      description: '',
      start_time: '',
      end_time: '',
      location: '',
      status: 'scheduled',
      appointment_type: 'meeting',
      priority: 'medium',
      contact_name: '',
      contact_phone: ''
    });
    setShowAppointmentModal(true);
  };

  // Open modal for editing appointment
  const openEditAppointmentModal = (appointment: Appointment) => {
    setEditingAppointment(appointment);
    
    // Convert ISO datetime to local datetime-local format (handling timezone properly)
    const formatDatetimeLocal = (isoString: string) => {
      if (!isoString) return '';
      const date = new Date(isoString);
      // Get local datetime in YYYY-MM-DDTHH:MM format
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      const hours = String(date.getHours()).padStart(2, '0');
      const minutes = String(date.getMinutes()).padStart(2, '0');
      return `${year}-${month}-${day}T${hours}:${minutes}`;
    };
    
    setFormData({
      title: appointment.title,
      description: appointment.description || '',
      start_time: formatDatetimeLocal(appointment.start_time),
      end_time: formatDatetimeLocal(appointment.end_time),
      location: appointment.location || '',
      status: appointment.status,
      appointment_type: appointment.appointment_type,
      priority: appointment.priority,
      contact_name: appointment.contact_name || '',
      contact_phone: appointment.contact_phone || ''
    });
    setShowAppointmentModal(true);
  };

  // Close modal
  const closeModal = () => {
    setShowAppointmentModal(false);
    setEditingAppointment(null);
  };

  return (
    <div className="mx-auto max-w-7xl w-full p-4 md:p-6 flex flex-col gap-6 min-h-[calc(100svh-64px)] pb-24">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-slate-900 mb-2">
            לוח שנה
          </h1>
          <p className="text-slate-600">
            ניהול פגישות ומעקב פעילות יומית
          </p>
        </div>
        <div className="flex gap-3 w-full sm:w-auto">
          <button
            className="btn-ghost flex-1 sm:flex-none md:hidden"
            onClick={() => setShowFilters(!showFilters)}
            data-testid="button-toggle-filters"
          >
            <Filter className="h-5 w-5 mr-2" />
            סינון
          </button>
          <button
            className="btn-primary flex-1 sm:flex-none sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2 min-w-fit whitespace-nowrap"
            onClick={openNewAppointmentModal}
            data-testid="button-new-appointment"
          >
            <Plus className="h-5 w-5 flex-shrink-0" />
            <span className="hidden sm:inline font-medium">פגישה חדשה</span>
            <span className="sm:hidden font-medium">פגישה</span>
          </button>
        </div>
      </div>

      {/* Mobile Filters */}
      {showFilters && (
        <div className="md:hidden bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-6 space-y-4">
          <div className="grid grid-cols-1 gap-4">
            <div className="relative overflow-hidden">
              <input
                type="text"
                placeholder="חיפוש פגישות..."
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                data-testid="input-search"
              />
              <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
            </div>
            
            <select
              className="border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
              className="border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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

            <div className="flex bg-slate-100 rounded-lg p-1 w-full">
              {(['month', 'week', 'day'] as const).map((view) => (
                <button
                  key={view}
                  className={`flex-1 px-2 py-2 text-xs font-medium rounded-md transition-colors ${
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
      )}

      {/* Desktop Filters */}
      <div className="hidden md:block bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex flex-wrap items-center gap-4 overflow-x-auto">
          {/* Search */}
          <div className="relative flex-1 min-w-[300px]">
            <input
              type="text"
              placeholder="חיפוש פגישות..."
              className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              data-testid="input-search"
            />
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
          </div>

          <div className="flex items-center gap-4 flex-shrink-0">
            {/* Status Filter */}
            <select
              className="border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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

            {/* Type Filter */}
            <select
              className="border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
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
            <div className="flex bg-slate-100 rounded-lg p-1 flex-shrink-0">
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
          <div className="flex items-center justify-between p-3 md:p-6 border-b border-slate-200 overflow-hidden">
            <h2 className="text-base md:text-xl font-semibold text-slate-900 truncate flex-1">
              {currentDate.toLocaleDateString('he-IL', { 
                month: 'long', 
                year: 'numeric' 
              })}
            </h2>
            <div className="flex items-center gap-1 md:gap-2 flex-shrink-0">
              <button
                className="btn-ghost p-2"
                onClick={() => navigateMonth('prev')}
                data-testid="button-prev-month"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
              <button
                className="btn-ghost px-2 md:px-4 py-1 md:py-2 text-xs md:text-base"
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
          <div className="p-2 md:p-6">
            {/* Days of week header */}
            <div className="grid grid-cols-7 gap-1 mb-2 md:mb-4">
              {['א', 'ב', 'ג', 'ד', 'ה', 'ו', 'ש'].map((day) => (
                <div key={day} className="text-center font-medium text-slate-500 py-2 text-xs md:text-sm">
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
                      min-h-[60px] md:min-h-[120px] p-1 md:p-2 border rounded-lg cursor-pointer hover:bg-slate-50
                      ${day.isCurrentMonth ? 'bg-white border-slate-200' : 'bg-slate-50 border-slate-100'}
                      ${isToday ? 'border-blue-500 bg-blue-50' : ''}
                    `}
                    onClick={() => setSelectedDate(day.date)}
                    data-testid={`calendar-day-${day.date.getDate()}`}
                  >
                    <div className={`
                      text-xs md:text-sm font-medium mb-1
                      ${day.isCurrentMonth ? 'text-slate-900' : 'text-slate-400'}
                      ${isToday ? 'text-blue-600 font-bold' : ''}
                    `}>
                      {day.date.getDate()}
                    </div>
                    
                    {/* Appointments for this day */}
                    <div className="space-y-1">
                      {dayAppointments.slice(0, currentView === 'month' ? 2 : 3).map((apt) => (
                        <div
                          key={apt.id}
                          className={`
                            text-[10px] md:text-xs px-1 md:px-2 py-0.5 md:py-1 rounded text-right truncate
                            ${APPOINTMENT_TYPES[apt.appointment_type]?.color || 'bg-gray-100 text-gray-800'}
                          `}
                          title={`${apt.title} - ${apt.start_time.split('T')[1]?.substring(0, 5) || ''}`}
                        >
                          <span className="hidden md:inline">{apt.title}</span>
                          <span className="md:hidden">•</span>
                        </div>
                      ))}
                      {dayAppointments.length > 2 && (
                        <div className="text-[10px] md:text-xs text-slate-500 px-1 md:px-2">
                          +{dayAppointments.length - 2}
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
      <div className="mt-6 md:mt-8 bg-white rounded-xl shadow-sm border border-slate-200">
        <div className="p-4 md:p-6 border-b border-slate-200">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
            <h3 className="text-lg font-semibold text-slate-900">
              פגישות ({filteredAppointments.length})
            </h3>
            <button
              className="btn-primary inline-flex items-center justify-center gap-2 px-4 py-2 min-w-fit whitespace-nowrap"
              onClick={openNewAppointmentModal}
              data-testid="button-new-appointment-header"
            >
              <Plus className="h-5 w-5 flex-shrink-0" />
              <span className="font-medium">פגישה חדשה</span>
            </button>
          </div>
        </div>
        
        {/* Meetings list content with internal scroll */}
        <div className="max-h-[60vh] overflow-y-auto overscroll-contain pr-1">
          <div className="divide-y divide-slate-200">
            {filteredAppointments.length === 0 ? (
              <div className="p-6 md:p-12 text-center">
                <CalendarIcon className="h-12 md:h-16 w-12 md:w-16 text-slate-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-slate-900 mb-2">
                  אין פגישות
                </h3>
                <p className="text-slate-600">
                  טרם נוספו פגישות למערכת. השתמש בכפתור למעלה כדי ליצור פגישה חדשה
                </p>
              </div>
            ) : (
              filteredAppointments.map((appointment) => (
                <div key={appointment.id} className="p-4 md:p-6 hover:bg-slate-50">
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2 md:gap-3 mb-2">
                      <h4 className="text-base md:text-lg font-medium text-slate-900 truncate">
                        {appointment.title}
                      </h4>
                      <span className={`
                        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
                        ${STATUS_TYPES[appointment.status]?.color}
                      `}>
                        {STATUS_TYPES[appointment.status]?.label}
                      </span>
                      <span className={`
                        inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium
                        ${APPOINTMENT_TYPES[appointment.appointment_type]?.color}
                      `}>
                        {APPOINTMENT_TYPES[appointment.appointment_type]?.label}
                      </span>
                      {appointment.auto_generated && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
                          AI
                        </span>
                      )}
                    </div>
                    
                    <div className="flex flex-wrap items-center gap-3 md:gap-6 text-xs md:text-sm text-slate-600 mb-3">
                      <div className="flex items-center gap-2">
                        <Clock className="h-4 w-4 flex-shrink-0" />
                        <span className="truncate">
                          {new Date(appointment.start_time).toLocaleDateString('he-IL')} • 
                          {new Date(appointment.start_time).toLocaleTimeString('he-IL', { 
                            hour: '2-digit', 
                            minute: '2-digit' 
                          })}
                        </span>
                      </div>
                      {appointment.location && (
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4 flex-shrink-0" />
                          <span className="truncate">{appointment.location}</span>
                        </div>
                      )}
                      {appointment.contact_name && (
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 flex-shrink-0" />
                          <span className="truncate">{appointment.contact_name}</span>
                        </div>
                      )}
                      {appointment.contact_phone && (
                        <div className="flex items-center gap-2">
                          <Phone className="h-4 w-4 flex-shrink-0" />
                          <span className="truncate">{appointment.contact_phone}</span>
                        </div>
                      )}
                    </div>
                    
                    {appointment.description && (
                      <p className="text-slate-600 text-sm line-clamp-2">
                        {appointment.description}
                      </p>
                    )}
                  </div>
                  
                  <div className="flex items-center gap-1 md:gap-2 mr-2 md:mr-4 flex-shrink-0">
                    <button
                      className="btn-ghost p-2"
                      title="צפה בפרטים"
                      onClick={() => openEditAppointmentModal(appointment)}
                      data-testid={`button-view-appointment-${appointment.id}`}
                    >
                      <Eye className="h-4 w-4 md:h-5 md:w-5" />
                    </button>
                    <button
                      className="btn-ghost p-2"
                      title="ערוך פגישה"
                      onClick={() => openEditAppointmentModal(appointment)}
                      data-testid={`button-edit-appointment-${appointment.id}`}
                    >
                      <Edit className="h-4 w-4 md:h-5 md:w-5" />
                    </button>
                    <button
                      className="btn-ghost p-2 text-red-600 hover:text-red-700"
                      title="מחק פגישה"
                      onClick={() => handleDeleteAppointment(appointment.id)}
                      data-testid={`button-delete-appointment-${appointment.id}`}
                    >
                      <Trash2 className="h-4 w-4 md:h-5 md:w-5" />
                    </button>
                  </div>
                </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Appointment Modal */}
      {showAppointmentModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 md:p-6 border-b border-slate-200 flex items-center justify-between">
              <h3 className="text-lg md:text-xl font-semibold text-slate-900">
                {editingAppointment ? 'עריכת פגישה' : 'פגישה חדשה'}
              </h3>
              <button
                className="btn-ghost p-2"
                onClick={closeModal}
                data-testid="button-close-modal"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleSubmitAppointment} className="p-4 md:p-6 space-y-4 md:space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    כותרת הפגישה *
                  </label>
                  <input
                    type="text"
                    required
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.title}
                    onChange={(e) => setFormData({...formData, title: e.target.value})}
                    data-testid="input-appointment-title"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    תאריך ושעת התחלה *
                  </label>
                  <input
                    type="datetime-local"
                    required
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.start_time}
                    onChange={(e) => setFormData({...formData, start_time: e.target.value})}
                    data-testid="input-start-time"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    תאריך ושעת סיום *
                  </label>
                  <input
                    type="datetime-local"
                    required
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.end_time}
                    onChange={(e) => setFormData({...formData, end_time: e.target.value})}
                    data-testid="input-end-time"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    סוג פגישה
                  </label>
                  <select
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.appointment_type}
                    onChange={(e) => setFormData({...formData, appointment_type: e.target.value as any})}
                    data-testid="select-appointment-type"
                  >
                    <option value="meeting">פגישה</option>
                    <option value="viewing">צפייה</option>
                    <option value="signing">חתימה</option>
                    <option value="call_followup">מעקב שיחה</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    סטטוס
                  </label>
                  <select
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.status}
                    onChange={(e) => setFormData({...formData, status: e.target.value as any})}
                    data-testid="select-appointment-status"
                  >
                    <option value="scheduled">מתוכנן</option>
                    <option value="confirmed">מאושר</option>
                    <option value="completed">הושלם</option>
                    <option value="cancelled">בוטל</option>
                    <option value="no_show">לא הגיע</option>
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    מיקום
                  </label>
                  <input
                    type="text"
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.location}
                    onChange={(e) => setFormData({...formData, location: e.target.value})}
                    data-testid="input-location"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    שם איש קשר
                  </label>
                  <input
                    type="text"
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.contact_name}
                    onChange={(e) => setFormData({...formData, contact_name: e.target.value})}
                    data-testid="input-contact-name"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    טלפון איש קשר
                  </label>
                  <input
                    type="tel"
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.contact_phone}
                    onChange={(e) => setFormData({...formData, contact_phone: e.target.value})}
                    data-testid="input-contact-phone"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    עדיפות
                  </label>
                  <select
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.priority}
                    onChange={(e) => setFormData({...formData, priority: e.target.value as any})}
                    data-testid="select-priority"
                  >
                    <option value="low">נמוך</option>
                    <option value="medium">בינוני</option>
                    <option value="high">גבוה</option>
                    <option value="urgent">דחוף</option>
                  </select>
                </div>

                <div className="md:col-span-2">
                  <label className="block text-sm font-medium text-slate-900 mb-2">
                    תיאור
                  </label>
                  <textarea
                    rows={3}
                    className="w-full border border-slate-300 rounded-xl px-3 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    value={formData.description}
                    onChange={(e) => setFormData({...formData, description: e.target.value})}
                    data-testid="textarea-description"
                  />
                </div>
              </div>

              <div className="flex flex-col-reverse sm:flex-row gap-3 pt-4 border-t border-slate-200">
                <button
                  type="button"
                  className="btn-ghost flex-1 sm:flex-none"
                  onClick={closeModal}
                  data-testid="button-cancel-appointment"
                >
                  ביטול
                </button>
                <button
                  type="submit"
                  className="btn-primary flex-1 sm:flex-none"
                  data-testid="button-save-appointment"
                >
                  <Save className="h-5 w-5 mr-2" />
                  {editingAppointment ? 'עדכן פגישה' : 'צור פגישה'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}