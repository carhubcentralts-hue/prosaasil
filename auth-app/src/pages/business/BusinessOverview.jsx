import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  BarChart3, 
  MessageSquare, 
  Phone, 
  UserCheck, 
  FileText,
  CheckCircle,
  AlertCircle,
  XCircle,
  Plus,
  PhoneCall,
  Users
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const BusinessOverview = () => {
  const { user, getBusinessId } = useAuth()
  const [overview, setOverview] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchOverviewData()
    
    // Update data every 15 seconds for business view
    const interval = setInterval(fetchOverviewData, 15000)
    return () => clearInterval(interval)
  }, [])

  const fetchOverviewData = async () => {
    try {
      const businessId = getBusinessId()
      
      // Real-time business data simulation
      setTimeout(() => {
        const hour = new Date().getHours()
        const isBusinessHours = hour >= 8 && hour <= 22
        
        setOverview({
          kpis: {
            active_calls: isBusinessHours ? Math.floor(Math.random() * 5) + 1 : 0,
            whatsapp_threads: Math.floor(Math.random() * 20) + 10,
            new_leads: Math.floor(Math.random() * 10) + 5,
            pending_documents: Math.floor(Math.random() * 5) + 1,
            revenue_today: `₪${(Math.random() * 10000 + 5000).toLocaleString()}`,
            conversion_rate: `${(Math.random() * 10 + 20).toFixed(1)}%`
          },
          integrations: {
            whatsapp: 'connected',
            twilio: 'connected',
            paypal: Math.random() > 0.5 ? 'connected' : 'not_configured',
            tranzila: 'connected'
          },
          recent_activity: [
            {
              id: 1,
              type: 'call',
              time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
              description: 'שיחה נכנסת מלקוח עפולה - מחפש דירת 3 חדרים',
              status: 'active',
              icon: Phone,
              priority: 'high'
            },
            {
              id: 2,
              type: 'whatsapp',
              time: new Date(Date.now() - 3 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
              description: 'הודעה חדשה: "מתי אפשר לקבוע פגישה?"',
              status: 'unread',
              icon: MessageSquare,
              priority: 'medium'
            },
            {
              id: 3,
              type: 'contract',
              time: new Date(Date.now() - 8 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
              description: 'חוזה חדש נחתם - דירה בחדרה 890K',
              status: 'completed',
              icon: FileText,
              priority: 'high'
            },
            {
              id: 4,
              type: 'lead',
              time: new Date(Date.now() - 12 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
              description: 'ליד חדש מהאתר - מעוניין בדירה בתל אביב',
              status: 'new',
              icon: UserCheck,
              priority: 'medium'
            }
          ]
        })
        setLoading(false)
      }, 400)
      
    } catch (error) {
      console.error('Error fetching overview:', error)
      setLoading(false)
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

  const getIntegrationStatus = (integration, status) => {
    const configs = {
      connected: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100', text: 'מחובר' },
      not_configured: { icon: XCircle, color: 'text-red-600', bg: 'bg-red-100', text: 'לא הוגדר' },
      error: { icon: AlertCircle, color: 'text-orange-600', bg: 'bg-orange-100', text: 'שגיאה' }
    }
    
    return configs[status] || configs.error
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
          לוח הבקרה שלי
        </h1>
        <p className="text-slate-600">
          {user?.business?.name || 'העסק שלי'} • {new Date().toLocaleDateString('he-IL')}
        </p>
      </motion.div>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4">
        {[
          { 
            icon: MessageSquare, 
            label: 'ת׳רדים פעילים', 
            value: overview?.kpis?.whatsapp_threads,
            color: 'text-green-600',
            bg: 'bg-green-100',
            clickable: true,
            route: '/app/biz/whatsapp'
          },
          { 
            icon: Phone, 
            label: 'שיחות חיות', 
            value: overview?.kpis?.active_calls,
            color: 'text-blue-600',
            bg: 'bg-blue-100',
            clickable: true,
            route: '/app/biz/calls'
          },
          { 
            icon: UserCheck, 
            label: 'לידים חדשים', 
            value: overview?.kpis?.new_leads,
            color: 'text-purple-600',
            bg: 'bg-purple-100',
            clickable: true,
            route: '/app/biz/crm'
          },
          { 
            icon: FileText, 
            label: 'מסמכים ממתינים', 
            value: overview?.kpis?.pending_documents,
            color: 'text-orange-600',
            bg: 'bg-orange-100',
            clickable: true,
            route: '/app/biz/finance'
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
              <div className={`w-12 h-12 ${kpi.bg} rounded-xl flex items-center justify-center mb-4`}>
                <Icon className={`w-6 h-6 ${kpi.color}`} />
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

      {/* Revenue & Performance */}
      <div className="grid grid-cols-2 gap-4">
        <motion.div
          className="bg-gradient-to-r from-emerald-500 to-green-600 rounded-2xl p-6 text-white"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.5 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-emerald-100 text-sm">הכנסות היום</p>
              <p className="text-3xl font-bold">{overview?.kpis?.revenue_today}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-emerald-200" />
          </div>
        </motion.div>
        
        <motion.div
          className="bg-gradient-to-r from-purple-500 to-indigo-600 rounded-2xl p-6 text-white"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.6 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">שיעור המרה</p>
              <p className="text-3xl font-bold">{overview?.kpis?.conversion_rate}</p>
            </div>
            <BarChart3 className="w-8 h-8 text-purple-200" />
          </div>
        </motion.div>
      </div>

      {/* Integration Status */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.4 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          מצב אינטגרציות
        </h3>
        
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(overview?.integrations || {}).map(([integration, status]) => {
            const config = getIntegrationStatus(integration, status)
            const Icon = config.icon
            
            return (
              <div
                key={integration}
                className={`flex items-center gap-3 p-3 rounded-xl ${config.bg} border`}
              >
                <Icon className={`w-5 h-5 ${config.color}`} />
                <div>
                  <p className="font-medium text-slate-800 capitalize">
                    {integration === 'whatsapp' ? 'WhatsApp' :
                     integration === 'twilio' ? 'שיחות' :
                     integration === 'paypal' ? 'PayPal' : 'Tranzila'}
                  </p>
                  <p className={`text-sm ${config.color}`}>{config.text}</p>
                </div>
              </div>
            )
          })}
        </div>
      </motion.div>

      {/* System Access Cards */}
      <div className="grid grid-cols-2 gap-4">
        {/* WhatsApp Access */}
        <motion.div
          className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg cursor-pointer"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.7 }}
          whileHover={{ scale: 1.02 }}
          onClick={() => window.location.href = '/app/biz/whatsapp'}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-green-100 rounded-xl flex items-center justify-center">
                <MessageSquare className="w-6 h-6 text-green-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-800">WhatsApp</h3>
                <p className="text-sm text-slate-600">{overview?.kpis?.whatsapp_threads} ת׳רדים</p>
              </div>
            </div>
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
          </div>
          <p className="text-xs text-slate-500">לחץ לפתיחת מערכת WhatsApp →</p>
        </motion.div>

        {/* Calls Access */}
        <motion.div
          className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg cursor-pointer"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.8 }}
          whileHover={{ scale: 1.02 }}
          onClick={() => window.location.href = '/app/biz/calls'}
        >
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center">
                <Phone className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                <h3 className="font-semibold text-slate-800">שיחות</h3>
                <p className="text-sm text-slate-600">{overview?.kpis?.active_calls} פעילות</p>
              </div>
            </div>
            <div className={`w-3 h-3 rounded-full ${overview?.kpis?.active_calls > 0 ? 'bg-green-500' : 'bg-gray-400'}`}></div>
          </div>
          <p className="text-xs text-slate-500">לחץ לפתיחת מערכת שיחות →</p>
        </motion.div>
      </div>

      {/* Quick Business Actions */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.9 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Plus className="w-5 h-5" />
          פעולות מהירות
        </h3>
        
        <div className="grid grid-cols-1 gap-3">
          <motion.button
            onClick={() => window.location.href = '/app/biz/whatsapp'}
            className="flex items-center gap-3 p-4 bg-green-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <MessageSquare className="w-5 h-5" />
            פתח ת׳רד WhatsApp חדש
          </motion.button>
          
          <motion.button
            onClick={() => window.location.href = '/app/biz/calls'}
            className="flex items-center gap-3 p-4 bg-blue-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Phone className="w-5 h-5" />
            התקשרות יזומה
          </motion.button>
          
          <motion.button
            onClick={() => window.location.href = '/app/biz/crm'}
            className="flex items-center gap-3 p-4 bg-purple-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <UserCheck className="w-5 h-5" />
            יצירת ליד חדש
          </motion.button>
        </div>
      </motion.div>

      {/* Recent Activity */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5" />
          פעילות אחרונה
        </h3>
        
        <div className="space-y-3">
          {overview?.recent_activity?.map((activity, index) => {
            const Icon = activity.icon
            
            return (
              <motion.div
                key={activity.id}
                className="flex items-start gap-3 p-4 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 1.0 + index * 0.1 }}
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  activity.type === 'call' ? 'bg-blue-100' :
                  activity.type === 'whatsapp' ? 'bg-green-100' :
                  activity.type === 'contract' ? 'bg-emerald-100' : 'bg-purple-100'
                }`}>
                  <Icon className={`w-5 h-5 ${
                    activity.type === 'call' ? 'text-blue-600' :
                    activity.type === 'whatsapp' ? 'text-green-600' :
                    activity.type === 'contract' ? 'text-emerald-600' : 'text-purple-600'
                  }`} />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-800 font-medium">{activity.description}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-500">{activity.time}</span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className={`text-xs px-2 py-1 rounded-full font-medium ${
                      activity.status === 'active' ? 'bg-green-100 text-green-700' :
                      activity.status === 'unread' ? 'bg-orange-100 text-orange-700' :
                      activity.status === 'completed' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'
                    }`}>
                      {activity.status === 'active' ? 'פעיל' :
                       activity.status === 'unread' ? 'לא נקרא' :
                       activity.status === 'completed' ? 'הושלם' : 'חדש'}
                    </span>
                  </div>
                </div>
                <div className={`px-2 py-1 rounded-full text-xs font-medium ${
                  activity.priority === 'high' ? 'bg-red-100 text-red-700' :
                  activity.priority === 'medium' ? 'bg-orange-100 text-orange-700' : 'bg-slate-100 text-slate-700'
                }`}>
                  {activity.priority === 'high' ? 'דחוף' :
                   activity.priority === 'medium' ? 'בינוני' : 'רגיל'}
                </div>
              </motion.div>
            )
          })}
        </div>
      </motion.div>
    </div>
  )
}

export default BusinessOverview