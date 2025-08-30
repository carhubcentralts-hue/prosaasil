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
  }, [])

  const fetchOverviewData = async () => {
    try {
      // Mock data - replace with real API calls
      setTimeout(() => {
        setKpis({
          activeCalls: 12,
          whatsappPerHour: 45,
          avgResponseTime: '2.3 דק',
          activeBusinesses: 8
        })
        
        setRecentEvents([
          {
            id: 1,
            type: 'error',
            message: 'Webhook שגיאה בעסק "שי דירות"',
            time: '10:30',
            business: 'שי דירות ומשרדים'
          },
          {
            id: 2,
            type: 'success',
            message: 'עסק חדש נוצר בהצלחה',
            time: '09:15',
            business: 'דוד נכסים'
          },
          {
            id: 3,
            type: 'warning',
            message: 'PayPal לא מוגדר לעסק',
            time: '08:45',
            business: 'רון השקעות'
          }
        ])
        
        setLoading(false)
      }, 1000)
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
            bg: 'bg-green-100'
          },
          { 
            icon: MessageSquare, 
            label: 'WA/שעה', 
            value: kpis?.whatsappPerHour, 
            color: 'text-blue-600',
            bg: 'bg-blue-100'
          },
          { 
            icon: TrendingUp, 
            label: 'זמן תגובה', 
            value: kpis?.avgResponseTime, 
            color: 'text-purple-600',
            bg: 'bg-purple-100'
          },
          { 
            icon: Building2, 
            label: 'עסקים פעילים', 
            value: kpis?.activeBusinesses, 
            color: 'text-orange-600',
            bg: 'bg-orange-100'
          }
        ].map((kpi, index) => {
          const Icon = kpi.icon
          return (
            <motion.div
              key={index}
              className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.1 }}
              whileHover={{ scale: 1.02 }}
            >
              <div className={`w-12 h-12 ${kpi.bg} rounded-xl flex items-center justify-center mb-4`}>
                <Icon className={`w-6 h-6 ${kpi.color}`} />
              </div>
              <p className="text-sm text-slate-600 mb-1">{kpi.label}</p>
              <p className="text-2xl font-bold text-slate-800">{kpi.value}</p>
            </motion.div>
          )
        })}
      </div>

      {/* Quick Actions */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          פעולות מהירות
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
          
          <motion.button
            className="flex items-center gap-3 p-4 bg-slate-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Search className="w-5 h-5" />
            חיפוש גלובלי
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
          {recentEvents.map((event, index) => (
            <motion.div
              key={event.id}
              className="flex items-start gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.5 + index * 0.1 }}
            >
              <div className={`w-2 h-2 rounded-full mt-2 ${
                event.type === 'error' ? 'bg-red-500' :
                event.type === 'warning' ? 'bg-orange-500' : 'bg-green-500'
              }`} />
              <div className="flex-1">
                <p className="text-sm text-slate-800 font-medium">{event.message}</p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-xs text-slate-500">{event.time}</span>
                  <span className="text-xs text-slate-400">•</span>
                  <span className="text-xs text-slate-600">{event.business}</span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>
    </div>
  )
}

export default AdminOverview