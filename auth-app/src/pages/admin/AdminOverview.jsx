import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  BarChart3, 
  Users, 
  Building2, 
  MessageSquare, 
  Phone, 
  TrendingUp,
  AlertCircle,
  Plus,
  Search,
  Eye
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const AdminOverview = () => {
  const { user, impersonate } = useAuth()
  const [kpis, setKpis] = useState(null)
  const [recentEvents, setRecentEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchOverviewData()
    
    // Update data every 30 seconds
    const interval = setInterval(fetchOverviewData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchOverviewData = async () => {
    try {
      // Realistic real-time data
      setTimeout(() => {
        const hour = new Date().getHours()
        const isBusinessHours = hour >= 8 && hour <= 22
        
        setKpis({
          activeCalls: isBusinessHours ? Math.floor(Math.random() * 15) + 5 : Math.floor(Math.random() * 3),
          whatsappPerHour: isBusinessHours ? Math.floor(Math.random() * 30) + 40 : Math.floor(Math.random() * 10) + 5,
          avgResponseTime: `${(Math.random() * 2 + 1).toFixed(1)} דק`,
          activeBusinesses: 12,
          totalMessages: 1247,
          conversionRate: `${(Math.random() * 5 + 15).toFixed(1)}%`
        })
        
        setRecentEvents([
          {
            id: 1,
            type: 'success',
            message: 'שיחה חדשה נענתה בהצלחה - "שי דירות"',
            time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            business: 'שי דירות ומשרדים',
            icon: Phone
          },
          {
            id: 2,
            type: 'info',
            message: 'לקוח חדש הצטרף ל-WhatsApp',
            time: new Date(Date.now() - 5 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            business: 'דוד נכסים',
            icon: MessageSquare
          },
          {
            id: 3,
            type: 'warning',
            message: 'תור המתנה ארוך - 3 שיחות',
            time: new Date(Date.now() - 10 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            business: 'רון השקעות',
            icon: AlertCircle
          },
          {
            id: 4,
            type: 'success',
            message: 'חוזה חדש נחתם דיגיטלית',
            time: new Date(Date.now() - 15 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            business: 'שי דירות ומשרדים',
            icon: TrendingUp
          }
        ])
        
        setLoading(false)
      }, 500)
    } catch (error) {
      console.error('Error fetching overview:', error)
      setLoading(false)
    }
  }

  const handleImpersonate = async (businessId) => {
    const success = await impersonate(businessId)
    if (success) {
      // Redirect to business overview
      window.location.href = '/app/biz/overview'
    }
  }

  if (loading) {
    return (
      <div className="space-y-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 bg-white/60 rounded-2xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <motion.div
        className="text-center py-8"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <h1 className="text-3xl font-bold text-slate-800 mb-2">
          לוח בקרה מנהל מערכת
        </h1>
        <p className="text-slate-600">
          ברוך הבא, {user?.name} • {new Date().toLocaleDateString('he-IL')}
        </p>
      </motion.div>

      {/* KPIs Grid */}
      <div className="grid grid-cols-2 gap-4">
        {[
          { 
            icon: Phone, 
            label: 'שיחות חיות', 
            value: kpis?.activeCalls, 
            color: 'text-green-600',
            bg: 'bg-green-100',
            trend: '+12%',
            clickable: true,
            route: '/app/admin/calls'
          },
          { 
            icon: MessageSquare, 
            label: 'WA/שעה', 
            value: kpis?.whatsappPerHour, 
            color: 'text-blue-600',
            bg: 'bg-blue-100',
            trend: '+8%',
            clickable: true,
            route: '/app/admin/whatsapp'
          },
          { 
            icon: TrendingUp, 
            label: 'זמן תגובה', 
            value: kpis?.avgResponseTime, 
            color: 'text-purple-600',
            bg: 'bg-purple-100',
            trend: '-5%',
            clickable: false
          },
          { 
            icon: Building2, 
            label: 'עסקים פעילים', 
            value: kpis?.activeBusinesses, 
            color: 'text-orange-600',
            bg: 'bg-orange-100',
            trend: '+2',
            clickable: true,
            route: '/app/admin/businesses'
          }
        ].map((kpi, index) => {
          const Icon = kpi.icon
          return (
            <motion.div
              key={index}
              className={`bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg ${
                kpi.clickable ? 'cursor-pointer hover:shadow-xl' : ''
              }`}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.1 }}
              whileHover={{ scale: kpi.clickable ? 1.03 : 1.01 }}
              onClick={() => kpi.clickable && kpi.route && (window.location.href = kpi.route)}
            >
              <div className="flex items-center justify-between mb-4">
                <div className={`w-12 h-12 ${kpi.bg} rounded-xl flex items-center justify-center`}>
                  <Icon className={`w-6 h-6 ${kpi.color}`} />
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-full ${
                  kpi.trend.includes('+') 
                    ? 'bg-green-100 text-green-700' 
                    : kpi.trend.includes('-')
                    ? 'bg-red-100 text-red-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {kpi.trend}
                </span>
              </div>
              <p className="text-sm text-slate-600 mb-1">{kpi.label}</p>
              <p className="text-2xl font-bold text-slate-800">{kpi.value}</p>
              {kpi.clickable && (
                <p className="text-xs text-slate-500 mt-2">לחץ לפרטים →</p>
              )}
            </motion.div>
          )
        })}
      </div>

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 gap-4">
        <motion.div
          className="bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl p-6 text-white"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-blue-100 text-sm">הודעות היום</p>
              <p className="text-3xl font-bold">{kpis?.totalMessages}</p>
            </div>
            <MessageSquare className="w-8 h-8 text-blue-200" />
          </div>
        </motion.div>
        
        <motion.div
          className="bg-gradient-to-r from-green-500 to-emerald-600 rounded-2xl p-6 text-white"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-green-100 text-sm">שיעור המרה</p>
              <p className="text-3xl font-bold">{kpis?.conversionRate}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-green-200" />
          </div>
        </motion.div>
      </div>

      {/* System Access & Management */}
      <div className="grid grid-cols-2 gap-4">
        {/* WhatsApp Access */}
        <motion.div
          className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
        >
          <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <MessageSquare className="w-5 h-5 text-green-600" />
            WhatsApp Panorama
          </h3>
          
          <div className="space-y-3">
            <motion.button
              onClick={() => window.location.href = '/app/admin/whatsapp'}
              className="w-full flex items-center gap-3 p-3 bg-green-500 text-white rounded-xl font-medium hover:bg-green-600 transition-all"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <MessageSquare className="w-4 h-4" />
              פתח מערכת WhatsApp
            </motion.button>
            
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">עסקים מחוברים</span>
              <span className="font-bold text-green-600">8/12</span>
            </div>
            
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">הודעות פעילות</span>
              <span className="font-bold text-blue-600">{kpis?.whatsappPerHour}/שעה</span>
            </div>
          </div>
        </motion.div>

        {/* Calls Access */}
        <motion.div
          className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
        >
          <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
            <Phone className="w-5 h-5 text-blue-600" />
            מערכת שיחות
          </h3>
          
          <div className="space-y-3">
            <motion.button
              onClick={() => window.location.href = '/app/admin/calls'}
              className="w-full flex items-center gap-3 p-3 bg-blue-500 text-white rounded-xl font-medium hover:bg-blue-600 transition-all"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Phone className="w-4 h-4" />
              פתח מערכת שיחות
            </motion.button>
            
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">שיחות פעילות</span>
              <span className="font-bold text-green-600">{kpis?.activeCalls}</span>
            </div>
            
            <div className="flex items-center justify-between text-sm">
              <span className="text-slate-600">זמן המתנה ממוצע</span>
              <span className="font-bold text-purple-600">{kpis?.avgResponseTime}</span>
            </div>
          </div>
        </motion.div>
      </div>

      {/* Management Cubes */}
      <div className="grid grid-cols-2 gap-4">
        {/* Business Management */}
        <motion.div
          className="bg-gradient-to-br from-purple-500 via-purple-600 to-indigo-600 rounded-2xl p-6 text-white cursor-pointer"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.9 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => window.location.href = '/app/admin/businesses'}
        >
          <div className="flex items-center justify-between mb-4">
            <Building2 className="w-8 h-8 text-purple-200" />
            <span className="text-2xl font-bold">{kpis?.activeBusinesses}</span>
          </div>
          <h3 className="text-lg font-semibold mb-2">ניהול עסקים</h3>
          <p className="text-purple-200 text-sm">הוספה, עריכה וניהול עסקים במערכת</p>
          <div className="mt-4 flex items-center gap-2">
            <div className="w-2 h-2 bg-green-400 rounded-full"></div>
            <span className="text-xs text-purple-200">פעיל</span>
          </div>
        </motion.div>

        {/* User Management */}
        <motion.div
          className="bg-gradient-to-br from-orange-500 via-red-500 to-pink-600 rounded-2xl p-6 text-white cursor-pointer"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 1.0 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => window.location.href = '/app/admin/users'}
        >
          <div className="flex items-center justify-between mb-4">
            <Users className="w-8 h-8 text-orange-200" />
            <span className="text-2xl font-bold">47</span>
          </div>
          <h3 className="text-lg font-semibold mb-2">ניהול משתמשים</h3>
          <p className="text-orange-200 text-sm">הרשאות, יצירה ועדכון משתמשים</p>
          <div className="mt-4 flex items-center gap-2">
            <div className="w-2 h-2 bg-green-400 rounded-full"></div>
            <span className="text-xs text-orange-200">מעודכן</span>
          </div>
        </motion.div>
      </div>

      {/* Quick Admin Actions */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.1 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          פעולות מנהל מהירות
        </h3>
        
        <div className="grid grid-cols-1 gap-3">
          <motion.button
            className="flex items-center gap-3 p-4 bg-gradient-primary text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Plus className="w-5 h-5" />
            יצירת עסק חדש
          </motion.button>
          
          <motion.button
            onClick={() => handleImpersonate('biz_001')}
            className="flex items-center gap-3 p-4 bg-orange-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Eye className="w-5 h-5" />
            התחזה לעסק "שי דירות"
          </motion.button>
        </div>
      </motion.div>

      {/* Recent Events */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          אירועים אחרונים
        </h3>
        
        <div className="space-y-3">
          {recentEvents.map((event, index) => {
            const Icon = event.icon
            return (
              <motion.div
                key={event.id}
                className="flex items-start gap-3 p-4 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 1.2 + index * 0.1 }}
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  event.type === 'error' ? 'bg-red-100' :
                  event.type === 'warning' ? 'bg-orange-100' :
                  event.type === 'info' ? 'bg-blue-100' : 'bg-green-100'
                }`}>
                  <Icon className={`w-5 h-5 ${
                    event.type === 'error' ? 'text-red-600' :
                    event.type === 'warning' ? 'text-orange-600' :
                    event.type === 'info' ? 'text-blue-600' : 'text-green-600'
                  }`} />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-800 font-medium">{event.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-500">{event.time}</span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs text-slate-600">{event.business}</span>
                  </div>
                </div>
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                  event.type === 'error' ? 'bg-red-100 text-red-700' :
                  event.type === 'warning' ? 'bg-orange-100 text-orange-700' :
                  event.type === 'info' ? 'bg-blue-100 text-blue-700' : 'bg-green-100 text-green-700'
                }`}>
                  {event.type === 'error' ? 'שגיאה' :
                   event.type === 'warning' ? 'אזהרה' :
                   event.type === 'info' ? 'מידע' : 'הצלחה'}
                </div>
              </motion.div>
            )
          })}
        </div>
      </motion.div>
    </div>
  )
}

export default AdminOverview