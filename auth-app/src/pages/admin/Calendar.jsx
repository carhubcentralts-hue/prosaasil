import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Calendar as CalendarIcon, 
  Plus, 
  Edit, 
  Trash2, 
  Clock, 
  User, 
  MapPin, 
  Phone, 
  MessageSquare,
  ChevronLeft, 
  ChevronRight,
  Filter,
  Search
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const Calendar = () => {
  console.log('🗓️ קומפוננט לוח השנה נטען!')
  const { user, hasPermission } = useAuth()
  
  // Calendar state
  const today = new Date()
  const [currentDate, setCurrentDate] = useState(today)
  const [selectedDate, setSelectedDate] = useState(today)
  const [viewMode, setViewMode] = useState('month') // month, week, day
  const [events, setEvents] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [eventTypeFilter, setEventTypeFilter] = useState('all')
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [editingEvent, setEditingEvent] = useState(null)
  
  // Event form state
  const [newEvent, setNewEvent] = useState({
    title: '',
    description: '',
    type: 'meeting',
    date: '',
    startTime: '',
    endTime: '',
    attendees: '',
    location: '',
    priority: 'medium'
  })

  useEffect(() => {
    loadEvents()
  }, [currentDate])

  const loadEvents = () => {
    // Mock events data - in production this would come from API
    const mockEvents = [
      {
        id: 1,
        title: 'פגישה עם לקוח - דוד כהן',
        description: 'צפייה בדירת 4 חדרים ברמת גן',
        type: 'meeting',
        date: '2025-08-31',
        startTime: '10:00',
        endTime: '11:00',
        attendees: 'דוד כהן, שי נתן',
        location: 'רמת גן, רחוב הרצל 25',
        priority: 'high',
        businessId: 'shai_001'
      },
      {
        id: 2,
        title: 'שיחת טלפון - רחל לוי',
        description: 'מעקב אחרי הצעת מחיר למשרד',
        type: 'call',
        date: '2025-08-31',
        startTime: '14:30',
        endTime: '15:00',
        attendees: 'רחל לוי',
        location: 'שיחת טלפון',
        priority: 'medium',
        businessId: 'shai_001'
      },
      {
        id: 3,
        title: 'ישיבת צוות שבועית',
        description: 'סקירת לידים חדשים והתקדמות פרויקטים',
        type: 'internal',
        date: '2025-09-01',
        startTime: '09:00',
        endTime: '10:00',
        attendees: 'כל הצוות',
        location: 'משרד ראשי',
        priority: 'medium',
        businessId: 'shai_001'
      }
    ]
    
    setEvents(mockEvents)
  }

  const handleCreateEvent = () => {
    if (!newEvent.title || !newEvent.date || !newEvent.startTime) {
      alert('אנא מלא את כל השדות הנדרשים')
      return
    }

    if (editingEvent) {
      // Update existing event
      const updatedEvents = events.map(e => 
        e.id === editingEvent.id 
          ? { ...e, ...newEvent, date: newEvent.date || selectedDate.toISOString().split('T')[0] }
          : e
      )
      setEvents(updatedEvents)
      alert('אירוע עודכן בהצלחה!')
    } else {
      // Create new event
      const eventToAdd = {
        id: Date.now(),
        ...newEvent,
        businessId: user.role === 'admin' ? 'admin_event' : user.businessId
      }

      setEvents([...events, eventToAdd])
      alert('אירוע נוסף בהצלחה!')
    }

    setNewEvent({
      title: '',
      description: '',
      type: 'meeting',
      date: '',
      startTime: '',
      endTime: '',
      attendees: '',
      location: '',
      priority: 'medium'
    })
    setEditingEvent(null)
    setShowCreateForm(false)
  }

  const handleDeleteEvent = (eventId) => {
    if (confirm('האם אתה בטוח שברצונך למחוק את האירוע?')) {
      setEvents(events.filter(e => e.id !== eventId))
      alert('אירוע נמחק בהצלחה!')
    }
  }

  const handleEditEvent = (eventData) => {
    console.log('🔄 פונקציית עריכה נקראת!', eventData)
    setEditingEvent(eventData)
    setNewEvent({
      title: eventData.title,
      description: eventData.description || '',
      type: eventData.type,
      date: eventData.date,
      startTime: eventData.startTime,
      endTime: eventData.endTime,
      attendees: eventData.attendees || '',
      location: eventData.location || '',
      priority: eventData.priority
    })
    setShowCreateForm(true)
    console.log('📝 טופס עריכה נפתח!')
  }

  const getEventTypeIcon = (type) => {
    switch (type) {
      case 'meeting': return <User className="w-4 h-4" />
      case 'call': return <Phone className="w-4 h-4" />
      case 'internal': return <MessageSquare className="w-4 h-4" />
      default: return <CalendarIcon className="w-4 h-4" />
    }
  }

  const getEventTypeText = (type) => {
    switch (type) {
      case 'meeting': return 'פגישה'
      case 'call': return 'שיחה'
      case 'internal': return 'פנימי'
      default: return 'אירוע'
    }
  }

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'bg-red-100 text-red-600 border-red-200'
      case 'medium': return 'bg-yellow-100 text-yellow-600 border-yellow-200'
      case 'low': return 'bg-green-100 text-green-600 border-green-200'
      default: return 'bg-slate-100 text-slate-600 border-slate-200'
    }
  }

  // Generate calendar grid
  const generateCalendarDays = () => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const startDate = new Date(firstDay)
    startDate.setDate(startDate.getDate() - firstDay.getDay())
    
    const days = []
    for (let i = 0; i < 42; i++) {
      const date = new Date(startDate)
      date.setDate(startDate.getDate() + i)
      days.push(date)
    }
    return days
  }

  const calendarDays = generateCalendarDays()
  const monthNames = ['ינואר', 'פברואר', 'מרץ', 'אפריל', 'מאי', 'יוני', 'יולי', 'אוגוסט', 'ספטמבר', 'אוקטובר', 'נובמבר', 'דצמבר']

  // Get events for specific date
  const getEventsForDate = (date) => {
    const dateStr = date.toISOString().split('T')[0]
    return events.filter(event => event.date === dateStr)
  }

  // Filter events based on search and type
  const filteredEvents = events.filter(event => {
    const matchesSearch = searchQuery === '' || 
      event.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      event.description.toLowerCase().includes(searchQuery.toLowerCase())
    
    const matchesType = eventTypeFilter === 'all' || event.type === eventTypeFilter
    
    return matchesSearch && matchesType
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800 mb-1">לוח שנה</h1>
          <p className="text-sm text-slate-600">ניהול פגישות ואירועים</p>
        </div>
        
        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowCreateForm(true)}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl text-sm font-medium shadow-lg hover:shadow-xl transition-all"
          >
            <Plus className="w-4 h-4" />
            אירוע חדש
          </button>
        </div>
      </div>

      {/* Calendar View Controls */}
      <div className="flex flex-col sm:flex-row gap-4">
        {/* View Mode Buttons */}
        <div className="flex items-center gap-2">
          {['month', 'week', 'day'].map((mode) => (
            <button
              key={mode}
              onClick={() => setViewMode(mode)}
              className={`px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                viewMode === mode
                  ? 'bg-purple-600 text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-100'
              }`}
            >
              {mode === 'month' ? 'חודש' : mode === 'week' ? 'שבוע' : 'יום'}
            </button>
          ))}
        </div>

        {/* Month Navigation */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              const newDate = new Date(currentDate)
              newDate.setMonth(currentDate.getMonth() - 1)
              setCurrentDate(newDate)
            }}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          
          <h2 className="text-lg font-semibold text-slate-800 min-w-[120px] text-center">
            {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
          </h2>
          
          <button
            onClick={() => {
              const newDate = new Date(currentDate)
              newDate.setMonth(currentDate.getMonth() + 1)
              setCurrentDate(newDate)
            }}
            className="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Filters and Search */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-4 h-4" />
            <input
              type="text"
              placeholder="חיפוש אירועים..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-4 pr-10 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
            />
          </div>
        </div>
        
        <select
          value={eventTypeFilter}
          onChange={(e) => setEventTypeFilter(e.target.value)}
          className="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
        >
          <option value="all">כל הסוגים</option>
          <option value="meeting">פגישות</option>
          <option value="call">שיחות</option>
          <option value="internal">פנימי</option>
        </select>
      </div>

      {/* Calendar Grid */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200">
        {/* Calendar Header */}
        <div className="grid grid-cols-7 gap-2 mb-4">
          {['ראשון', 'שני', 'שלישי', 'רביעי', 'חמישי', 'שישי', 'שבת'].map((day) => (
            <div key={day} className="text-center text-sm font-semibold text-slate-600 py-2">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Days */}
        <div className="grid grid-cols-7 gap-2">
          {calendarDays.map((date, index) => {
            const isToday = date.toDateString() === today.toDateString()
            const isCurrentMonth = date.getMonth() === currentDate.getMonth()
            const isSelected = date.toDateString() === selectedDate.toDateString()
            const dayEvents = getEventsForDate(date)
            
            return (
              <motion.div
                key={index}
                className={`min-h-[100px] p-2 border-2 rounded-lg cursor-pointer transition-all hover:shadow-md ${
                  isSelected 
                    ? 'border-purple-500 bg-purple-50' 
                    : isToday
                    ? 'border-blue-500 bg-blue-50'
                    : isCurrentMonth
                    ? 'border-slate-200 bg-white hover:bg-slate-50'
                    : 'border-slate-100 bg-slate-50 text-slate-400'
                }`}
                onClick={() => setSelectedDate(date)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                {/* Date Number */}
                <div className={`text-sm font-semibold mb-1 ${
                  isToday ? 'text-blue-600' : isSelected ? 'text-purple-600' : 'text-slate-700'
                }`}>
                  {date.getDate()}
                </div>

                {/* Events for this day */}
                <div className="space-y-1">
                  {dayEvents.slice(0, 2).map((event) => (
                    <div
                      key={event.id}
                      className={`px-2 py-1 rounded text-xs font-medium border ${getPriorityColor(event.priority)}`}
                    >
                      <div className="flex items-center gap-1">
                        {getEventTypeIcon(event.type)}
                        <span className="truncate">{event.title}</span>
                      </div>
                    </div>
                  ))}
                  {dayEvents.length > 2 && (
                    <div className="text-xs text-slate-500 text-center">
                      +{dayEvents.length - 2} נוספים
                    </div>
                  )}
                </div>
              </motion.div>
            )
          })}
        </div>
      </div>

      {/* Events List for Selected Date */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200">
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <CalendarIcon className="w-5 h-5" />
          אירועים ב-{selectedDate.toLocaleDateString('he-IL')}
        </h3>

        {getEventsForDate(selectedDate).length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <CalendarIcon className="w-12 h-12 mx-auto text-slate-300 mb-3" />
            <p>אין אירועים מתוכננים ליום זה</p>
          </div>
        ) : (
          <div className="space-y-3">
            {getEventsForDate(selectedDate).map((event) => (
              <motion.div
                key={event.id}
                className={`p-4 rounded-lg border-2 ${getPriorityColor(event.priority)}`}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {getEventTypeIcon(event.type)}
                    <h4 className="font-semibold">{event.title}</h4>
                    <span className="px-2 py-1 bg-slate-200 text-slate-600 text-xs rounded-full">
                      {getEventTypeText(event.type)}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => {
                        alert('עריכת אירוע: ' + event.title)
                        setEditingEvent(event)
                        setNewEvent({
                          title: event.title,
                          description: event.description || '',
                          type: event.type,
                          date: event.date,
                          startTime: event.startTime,
                          endTime: event.endTime,
                          attendees: event.attendees || '',
                          location: event.location || '',
                          priority: event.priority
                        })
                        setShowCreateForm(true)
                      }}
                      className="w-8 h-8 rounded-lg hover:bg-blue-100 text-blue-600 flex items-center justify-center transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => {
                        if (confirm('האם אתה בטוח שברצונך למחוק את האירוע?')) {
                          setEvents(events.filter(e => e.id !== event.id))
                          alert('אירוע נמחק בהצלחה!')
                        }
                      }}
                      className="w-8 h-8 rounded-lg hover:bg-red-100 text-red-600 flex items-center justify-center transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {event.description && (
                  <p className="text-sm text-slate-600 mb-2">{event.description}</p>
                )}

                <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {event.startTime} - {event.endTime}
                  </div>
                  {event.location && (
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {event.location}
                    </div>
                  )}
                  {event.attendees && (
                    <div className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {event.attendees}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Create Event Form */}
      {showCreateForm && (
        <motion.div
          className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
        >
          <motion.div
            className="bg-white rounded-2xl p-6 max-w-md w-full max-h-[90vh] overflow-y-auto"
            initial={{ scale: 0.95, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
          >
            <h3 className="text-lg font-semibold text-slate-800 mb-4">{editingEvent ? 'עריכת אירוע' : 'אירוע חדש'}</h3>
            
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">כותרת*</label>
                <input
                  type="text"
                  value={newEvent.title}
                  onChange={(event) => setNewEvent({...newEvent, title: event.target.value})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="שם האירוע"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">תיאור</label>
                <textarea
                  value={newEvent.description}
                  onChange={(event) => setNewEvent({...newEvent, description: event.target.value})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  rows={3}
                  placeholder="תיאור האירוע"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">תאריך*</label>
                  <input
                    type="date"
                    value={newEvent.date}
                    onChange={(event) => setNewEvent({...newEvent, date: event.target.value})}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">סוג</label>
                  <select
                    value={newEvent.type}
                    onChange={(event) => setNewEvent({...newEvent, type: event.target.value})}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="meeting">פגישה</option>
                    <option value="call">שיחה</option>
                    <option value="internal">פנימי</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">שעת התחלה*</label>
                  <input
                    type="time"
                    value={newEvent.startTime}
                    onChange={(event) => setNewEvent({...newEvent, startTime: event.target.value})}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">שעת סיום</label>
                  <input
                    type="time"
                    value={newEvent.endTime}
                    onChange={(event) => setNewEvent({...newEvent, endTime: event.target.value})}
                    className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">משתתפים</label>
                <input
                  type="text"
                  value={newEvent.attendees}
                  onChange={(event) => setNewEvent({...newEvent, attendees: event.target.value})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="שמות המשתתפים"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">מיקום</label>
                <input
                  type="text"
                  value={newEvent.location}
                  onChange={(event) => setNewEvent({...newEvent, location: event.target.value})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                  placeholder="כתובת או מיקום"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">עדיפות</label>
                <select
                  value={newEvent.priority}
                  onChange={(event) => setNewEvent({...newEvent, priority: event.target.value})}
                  className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500"
                >
                  <option value="low">נמוכה</option>
                  <option value="medium">בינונית</option>
                  <option value="high">גבוהה</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3 mt-6">
              <button
                onClick={handleCreateEvent}
                className="flex-1 px-4 py-2 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-lg font-medium hover:shadow-lg transition-all"
              >
                שמור אירוע
              </button>
              <button
                onClick={() => {
                  setShowCreateForm(false)
                  setEditingEvent(null)
                  setNewEvent({
                    title: '',
                    description: '',
                    type: 'meeting',
                    date: '',
                    startTime: '',
                    endTime: '',
                    attendees: '',
                    location: '',
                    priority: 'medium'
                  })
                }}
                className="px-4 py-2 bg-slate-200 text-slate-700 rounded-lg font-medium hover:bg-slate-300 transition-colors"
              >
                ביטול
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}

      {/* All Events List */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-slate-200">
        <h3 className="text-lg font-semibold text-slate-800 mb-4">כל האירועים ({filteredEvents.length})</h3>
        
        {filteredEvents.length === 0 ? (
          <div className="text-center py-8 text-slate-500">
            <CalendarIcon className="w-12 h-12 mx-auto text-slate-300 mb-3" />
            <p>אין אירועים המתאימים לחיפוש</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredEvents.map((event) => (
              <motion.div
                key={event.id}
                className={`p-4 rounded-lg border-2 ${getPriorityColor(event.priority)}`}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {getEventTypeIcon(event.type)}
                    <h4 className="font-semibold">{event.title}</h4>
                    <span className="px-2 py-1 bg-slate-200 text-slate-600 text-xs rounded-full">
                      {getEventTypeText(event.type)}
                    </span>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    <button 
                      onClick={() => {
                        alert('עריכת אירוע: ' + event.title)
                        setEditingEvent(event)
                        setNewEvent({
                          title: event.title,
                          description: event.description || '',
                          type: event.type,
                          date: event.date,
                          startTime: event.startTime,
                          endTime: event.endTime,
                          attendees: event.attendees || '',
                          location: event.location || '',
                          priority: event.priority
                        })
                        setShowCreateForm(true)
                      }}
                      className="w-8 h-8 rounded-lg hover:bg-blue-100 text-blue-600 flex items-center justify-center transition-colors"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button 
                      onClick={() => {
                        if (confirm('האם אתה בטוח שברצונך למחוק את האירוע?')) {
                          setEvents(events.filter(e => e.id !== event.id))
                          alert('אירוע נמחק בהצלחה!')
                        }
                      }}
                      className="w-8 h-8 rounded-lg hover:bg-red-100 text-red-600 flex items-center justify-center transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {event.description && (
                  <p className="text-sm text-slate-600 mb-2">{event.description}</p>
                )}

                <div className="flex flex-wrap gap-3 text-xs text-slate-500">
                  <div className="flex items-center gap-1">
                    <CalendarIcon className="w-3 h-3" />
                    {new Date(event.date).toLocaleDateString('he-IL')}
                  </div>
                  <div className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {event.startTime} - {event.endTime}
                  </div>
                  {event.location && (
                    <div className="flex items-center gap-1">
                      <MapPin className="w-3 h-3" />
                      {event.location}
                    </div>
                  )}
                  {event.attendees && (
                    <div className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {event.attendees}
                    </div>
                  )}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Calendar