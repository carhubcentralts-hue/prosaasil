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
  }, [])

  const fetchOverviewData = async () => {
    try {
      const businessId = getBusinessId()
      
      // Mock API call - replace with real endpoint
      setTimeout(() => {
        setOverview({
          kpis: {
            active_calls: 3,
            whatsapp_threads: 15,
            new_leads: 8,
            pending_documents: 2
          },
          integrations: {
            whatsapp: 'connected',
            twilio: 'connected',
            paypal: 'not_configured',
            tranzila: 'not_configured'
          },
          recent_activity: [
            {
              id: 1,
              type: 'call',
              time: '10:30',
              description: 'שיחה נכנסת מלקוח חדש',
              status: 'active'
            },
            {
              id: 2,
              type: 'whatsapp',
              time: '09:15',
              description: 'הודעה חדשה בוואטסאפ',
              status: 'unread'
            },
            {
              id: 3,
              type: 'crm',
              time: '08:45',
              description: 'ליד חדש נוצר',
              status: 'new'
            }
          ]
        })
        setLoading(false)
      }, 800)
      
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
            bg: 'bg-green-100'
          },
          { 
            icon: Phone, 
            label: 'שיחות חיות', 
            value: overview?.kpis?.active_calls,
            color: 'text-blue-600',
            bg: 'bg-blue-100'
          },
          { 
            icon: UserCheck, 
            label: 'לידים חדשים', 
            value: overview?.kpis?.new_leads,
            color: 'text-purple-600',
            bg: 'bg-purple-100'
          },
          { 
            icon: FileText, 
            label: 'מסמכים ממתינים', 
            value: overview?.kpis?.pending_documents,
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

      {/* Quick Actions */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Plus className="w-5 h-5" />
          פעולות מהירות
        </h3>
        
        <div className="grid grid-cols-1 gap-3">
          <motion.button
            className="flex items-center gap-3 p-4 bg-gradient-primary text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <MessageSquare className="w-5 h-5" />
            פתח ת׳רד WhatsApp חדש
          </motion.button>
          
          <motion.button
            className="flex items-center gap-3 p-4 bg-green-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <PhoneCall className="w-5 h-5" />
            התקשרות יזומה
          </motion.button>
          
          <motion.button
            className="flex items-center gap-3 p-4 bg-purple-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Users className="w-5 h-5" />
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
            const getActivityIcon = (type) => {
              switch (type) {
                case 'call': return Phone
                case 'whatsapp': return MessageSquare
                case 'crm': return UserCheck
                default: return BarChart3
              }
            }
            
            const Icon = getActivityIcon(activity.type)
            
            return (
              <motion.div
                key={activity.id}
                className="flex items-start gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.6 + index * 0.1 }}
              >
                <div className="w-8 h-8 bg-purple-100 rounded-lg flex items-center justify-center">
                  <Icon className="w-4 h-4 text-purple-600" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-800 font-medium">{activity.description}</p>
                  <span className="text-xs text-slate-500">{activity.time}</span>
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