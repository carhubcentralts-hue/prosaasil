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
  Users,
  DollarSign,
  TrendingUp,
  Calendar,
  Bell,
  Clock,
  Target,
  Settings,
  Wifi,
  WifiOff,
  Activity,
  ArrowUpRight,
  Zap,
  Eye,
  Edit,
  ExternalLink,
  PlayCircle,
  Headphones
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const BusinessOverview = () => {
  const { user, getBusinessId, hasPermission } = useAuth()
  const [timeRange, setTimeRange] = useState('7d')
  const [kpis, setKpis] = useState(null)
  const [integrations, setIntegrations] = useState(null)
  const [recentActivity, setRecentActivity] = useState([])
  const [quickLists, setQuickLists] = useState(null)
  const [loading, setLoading] = useState(true)

  const timeRanges = [
    { value: 'today', label: 'היום' },
    { value: '7d', label: '7 ימים' },
    { value: '30d', label: '30 ימים' },
    { value: 'custom', label: 'מותאם' }
  ]

  useEffect(() => {
    fetchOverviewData()
    
    // Update data every 10 seconds for business view
    const interval = setInterval(fetchOverviewData, 10000)
    return () => clearInterval(interval)
  }, [timeRange])

  const fetchOverviewData = async () => {
    try {
      const businessId = getBusinessId()
      
      // Simulate business-specific API call
      setTimeout(() => {
        const hour = new Date().getHours()
        const isBusinessHours = hour >= 8 && hour <= 22
        
        // Business KPIs
        setKpis({
          activeCallsNow: isBusinessHours ? Math.floor(Math.random() * 3) + 1 : 0,
          whatsappThreads: Math.floor(Math.random() * 15) + 8,
          newLeadsToday: Math.floor(Math.random() * 8) + 3,
          pendingDocuments: Math.floor(Math.random() * 4) + 1,
          revenueToday: `₪${(Math.random() * 15000 + 5000).toLocaleString()}`,
          conversionRate: `${(Math.random() * 8 + 18).toFixed(1)}%`,
          avgFirstResponseSec: `${(Math.random() * 2 + 1.5).toFixed(1)} דק`,
          wsConnectionsOk: isBusinessHours
        })

        // Business Integration Status
        setIntegrations({
          whatsapp: Math.random() > 0.05 ? 'connected' : 'error',
          voice: isBusinessHours ? 'ws_ok' : 'fallback',
          paypal: Math.random() > 0.4 ? 'ready' : 'not_configured',
          tranzila: 'ready'
        })

        // Business Activity Feed
        setRecentActivity([
          {
            id: 1,
            type: 'call',
            time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            description: 'שיחה נכנסת מלקוח חדש - מחפש דירת 4 חדרים בחדרה',
            status: 'active',
            priority: 'high',
            icon: Phone,
            customer: 'דוד כהן'
          },
          {
            id: 2,
            type: 'whatsapp',
            time: new Date(Date.now() - 3 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            description: 'הודעה חדשה: "מתי אפשר לקבוע סיור בדירה?"',
            status: 'unread',
            priority: 'medium',
            icon: MessageSquare,
            customer: 'שרה לוי'
          },
          {
            id: 3,
            type: 'contract',
            time: new Date(Date.now() - 8 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            description: 'חוזה חדש נחתם דיגיטלית - דירה בחדרה ₪890K',
            status: 'signed',
            priority: 'high',
            icon: FileText,
            customer: 'יוסי משה'
          },
          {
            id: 4,
            type: 'lead',
            time: new Date(Date.now() - 12 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            description: 'ליד חדש מהאתר - מעוניין בפנטהאוס בתל אביב',
            status: 'new',
            priority: 'medium',
            icon: UserCheck,
            customer: 'רחל אברהם'
          },
          {
            id: 5,
            type: 'payment',
            time: new Date(Date.now() - 20 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            description: 'תשלום התקבל - ₪25,000 עמלת מכירה',
            status: 'completed',
            priority: 'high',
            icon: DollarSign,
            customer: 'מיכל דוד'
          }
        ])

        // Business Quick Lists
        setQuickLists({
          whatsappThreads: [
            { id: 1, name: 'אלון פרץ', phone: '054-1234567', unread: 2, status: 'delivered', lastMessage: 'מתי נוכל להיפגש לסיור?', business: 'shai_001' },
            { id: 2, name: 'יעל רוזן', phone: '052-9876543', unread: 0, status: 'read', lastMessage: 'תודה על הפרטים', business: 'shai_001' },
            { id: 3, name: 'עמית גולן', phone: '050-5555555', unread: 1, status: 'sent', lastMessage: 'אשלח לך עוד אפשרויות מחר', business: 'shai_001' },
            { id: 4, name: 'דנה שחר', phone: '053-7777777', unread: 3, status: 'delivered', lastMessage: 'מה התנאים לרכישה?', business: 'shai_001' },
            { id: 5, name: 'לילך בן דוד', phone: '054-3333333', unread: 0, status: 'read', lastMessage: 'נקבע לראשון בחודש', business: 'shai_001' }
          ],
          recentCalls: [
            { id: 1, name: 'דוד כהן', duration: '4:32', status: 'completed', transcribed: true, date: 'היום 15:20', sentiment: 'positive' },
            { id: 2, name: 'שרה לוי', duration: '2:45', status: 'completed', transcribed: true, date: 'היום 14:15', sentiment: 'neutral' },
            { id: 3, name: 'יוסי משה', duration: '7:18', status: 'completed', transcribed: false, date: 'היום 13:30', sentiment: 'positive' },
            { id: 4, name: 'רחל אברהם', duration: '3:20', status: 'missed', transcribed: false, date: 'אתמול 17:45', sentiment: null },
            { id: 5, name: 'מיכל דוד', duration: '5:55', status: 'completed', transcribed: true, date: 'אתמול 16:10', sentiment: 'very_positive' }
          ],
          openLeads: [
            { id: 1, name: 'אלון פרץ', status: 'hot', lastUpdate: 'לפני שעה', value: '₪890K', type: 'דירת 3 חדרים בחדרה', stage: 'viewing' },
            { id: 2, name: 'יעל רוזן', status: 'hot', lastUpdate: 'לפני 2 שעות', value: '₪2.3M', type: 'דירת גן בהרצליה', stage: 'negotiation' },
            { id: 3, name: 'דנה שחר', status: 'warm', lastUpdate: 'אתמול', value: '₪1.5M', type: 'פנטהאוס בתל אביב', stage: 'interest' },
            { id: 4, name: 'עמית גולן', status: 'hot', lastUpdate: 'לפני 3 שעות', value: '₪750K', type: 'דירת 4 חדרים בפתח תקוה', stage: 'offer' },
            { id: 5, name: 'לילך בן דוד', status: 'warm', lastUpdate: 'לפני 5 שעות', value: '₪1.2M', type: 'דירה בראשון לציון', stage: 'viewing' }
          ]
        })
        
        setLoading(false)
      }, 200)
      
    } catch (error) {
      console.error('Error fetching overview:', error)
      setLoading(false)
    }
  }

  const getIntegrationConfig = (integration, status) => {
    const configs = {
      connected: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100', text: 'מחובר' },
      ws_ok: { icon: Wifi, color: 'text-green-600', bg: 'bg-green-100', text: 'WS מחובר' },
      fallback: { icon: WifiOff, color: 'text-orange-600', bg: 'bg-orange-100', text: 'Fallback' },
      ready: { icon: CheckCircle, color: 'text-green-600', bg: 'bg-green-100', text: 'מוכן' },
      not_configured: { icon: XCircle, color: 'text-gray-600', bg: 'bg-gray-100', text: 'לא הוגדר' },
      error: { icon: AlertCircle, color: 'text-red-600', bg: 'bg-red-100', text: 'שגיאה' }
    }
    
    return configs[status] || configs.error
  }

  const getLeadStatusColor = (status) => {
    switch (status) {
      case 'hot': return 'bg-red-100 text-red-700'
      case 'warm': return 'bg-orange-100 text-orange-700'
      case 'cold': return 'bg-blue-100 text-blue-700'
      default: return 'bg-gray-100 text-gray-700'
    }
  }

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'very_positive': return 'bg-green-500'
      case 'positive': return 'bg-green-400'
      case 'neutral': return 'bg-yellow-400'
      case 'negative': return 'bg-red-400'
      default: return 'bg-gray-400'
    }
  }

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto space-y-6 p-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="h-32 bg-white/60 rounded-2xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6 p-4">
      {/* Hero Bar */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-slate-800">סקירה כללית</h1>
          <div className="flex items-center gap-2">
            <Bell className="w-5 h-5 text-slate-600" />
            <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          </div>
        </div>
        
        <p className="text-slate-600 mb-4">
          {user?.business?.name || 'העסק שלי'} • {new Date().toLocaleDateString('he-IL')}
        </p>
        
        {/* Time Range Selector */}
        <div className="flex gap-2">
          {timeRanges.map((range) => (
            <motion.button
              key={range.value}
              onClick={() => setTimeRange(range.value)}
              className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                timeRange === range.value
                  ? 'bg-gradient-primary text-white shadow-lg'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
              }`}
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              {range.label}
            </motion.button>
          ))}
        </div>
      </motion.div>

      {/* KPIs Grid - 4 tiles vertical */}
      <div className="space-y-3">
        {[
          { 
            icon: Phone, 
            label: 'שיחות פעילות כרגע', 
            value: kpis?.activeCallsNow,
            detail: kpis?.wsConnectionsOk ? 'WS מחובר' : 'Fallback',
            color: 'text-blue-600',
            bg: 'bg-blue-100'
          },
          { 
            icon: MessageSquare, 
            label: 'הודעות WA ב-24ש׳', 
            value: kpis?.whatsappThreads,
            detail: `${Math.floor(Math.random() * 20 + 15)} הודעות`,
            color: 'text-green-600',
            bg: 'bg-green-100'
          },
          { 
            icon: Clock, 
            label: 'זמן תגובה ראשון ממוצע', 
            value: kpis?.avgFirstResponseSec,
            detail: 'p95 זמן תגובה',
            color: 'text-purple-600',
            bg: 'bg-purple-100'
          },
          { 
            icon: Target, 
            label: 'לידים חדשים / הזדמנויות', 
            value: `${kpis?.newLeadsToday}/${Math.floor(kpis?.newLeadsToday * 0.6)}`,
            detail: 'טווח נבחר',
            color: 'text-orange-600',
            bg: 'bg-orange-100'
          }
        ].map((kpi, index) => {
          const Icon = kpi.icon
          return (
            <motion.div
              key={index}
              className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 border border-slate-200/60 shadow-lg"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.1 }}
            >
              <div className="flex items-center gap-3">
                <div className={`w-12 h-12 ${kpi.bg} rounded-xl flex items-center justify-center`}>
                  <Icon className={`w-6 h-6 ${kpi.color}`} />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-600">{kpi.label}</p>
                  <p className="text-xl font-bold text-slate-800">{kpi.value}</p>
                  <p className="text-xs text-slate-500">{kpi.detail}</p>
                </div>
              </div>
            </motion.div>
          )
        })}
      </div>

      {/* Quick Actions */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.5 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Zap className="w-5 h-5" />
          פעולות מהירות
        </h3>
        
        <div className="space-y-3">
          <motion.button
            onClick={() => window.location.href = '/app/biz/whatsapp/new'}
            className="w-full flex items-center gap-3 p-4 bg-green-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <MessageSquare className="w-5 h-5" />
            פתח ת׳רד WhatsApp חדש
          </motion.button>
          
          <motion.button
            onClick={() => window.location.href = '/app/biz/calls/new'}
            className="w-full flex items-center gap-3 p-4 bg-blue-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Phone className="w-5 h-5" />
            שיחה יוצאת
          </motion.button>
          
          <motion.button
            onClick={() => window.location.href = '/app/biz/crm/new'}
            className="w-full flex items-center gap-3 p-4 bg-purple-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <UserCheck className="w-5 h-5" />
            צור ליד חדש
          </motion.button>
        </div>
      </motion.div>

      {/* Integration Status */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.6 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Settings className="w-5 h-5" />
          מצב אינטגרציות
        </h3>
        
        <div className="space-y-3">
          {Object.entries(integrations || {}).map(([integration, status]) => {
            const config = getIntegrationConfig(integration, status)
            const Icon = config.icon
            
            const integrationNames = {
              whatsapp: 'WhatsApp',
              voice: 'Voice (WebSocket)',
              paypal: 'PayPal',
              tranzila: 'Tranzila'
            }
            
            return (
              <div
                key={integration}
                className={`flex items-center gap-3 p-3 rounded-xl ${config.bg} border`}
              >
                <Icon className={`w-5 h-5 ${config.color}`} />
                <div className="flex-1">
                  <p className="font-medium text-slate-800">
                    {integrationNames[integration]}
                  </p>
                  <p className={`text-sm ${config.color}`}>{config.text}</p>
                </div>
                {status === 'not_configured' && (
                  <button className="text-xs bg-slate-200 px-2 py-1 rounded-lg hover:bg-slate-300 transition-colors">
                    הגדר
                  </button>
                )}
              </div>
            )
          })}
        </div>
      </motion.div>

      {/* Revenue & Performance */}
      <div className="grid grid-cols-2 gap-4">
        <motion.div
          className="bg-gradient-to-r from-emerald-500 to-green-600 rounded-2xl p-6 text-white"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.7 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-emerald-100 text-sm">הכנסות היום</p>
              <p className="text-2xl font-bold">{kpis?.revenueToday}</p>
            </div>
            <DollarSign className="w-8 h-8 text-emerald-200" />
          </div>
        </motion.div>
        
        <motion.div
          className="bg-gradient-to-r from-purple-500 to-indigo-600 rounded-2xl p-6 text-white"
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.8 }}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-purple-100 text-sm">שיעור המרה</p>
              <p className="text-2xl font-bold">{kpis?.conversionRate}</p>
            </div>
            <TrendingUp className="w-8 h-8 text-purple-200" />
          </div>
        </motion.div>
      </div>

      {/* Business User Management Cube - Only for Owners */}
      {hasPermission('manage_business_users') && (
        <motion.div
          className="bg-gradient-to-br from-indigo-500 via-purple-600 to-pink-600 rounded-2xl p-6 text-white cursor-pointer"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.9 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => window.location.href = '/app/biz/users'}
        >
          <div className="flex items-center justify-between mb-4">
            <Users className="w-8 h-8 text-purple-200" />
            <span className="text-2xl font-bold">5</span>
          </div>
          <h3 className="text-lg font-semibold mb-2">ניהול משתמשי העסק</h3>
          <p className="text-purple-200 text-sm mb-3">הזמנה, שינוי תפקיד ומחיקה</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
              <span className="text-xs text-purple-200">2 הזמנות ממתינות</span>
            </div>
            <ArrowUpRight className="w-4 h-4 text-purple-200" />
          </div>
        </motion.div>
      )}

      {/* Quick Lists - WhatsApp Threads */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <MessageSquare className="w-5 h-5 text-green-600" />
          ת׳רדי WA אחרונים (5)
        </h3>
        
        <div className="space-y-3">
          {quickLists?.whatsappThreads?.slice(0, 5).map((thread) => (
            <motion.div
              key={thread.id}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100 cursor-pointer"
              whileHover={{ scale: 1.01 }}
              onClick={() => window.location.href = `/app/biz/whatsapp/thread/${thread.id}`}
            >
              <div className="w-10 h-10 bg-green-100 rounded-xl flex items-center justify-center">
                <MessageSquare className="w-5 h-5 text-green-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-slate-800">{thread.name}</p>
                  {thread.unread > 0 && (
                    <span className="px-2 py-1 bg-red-500 text-white text-xs rounded-full">
                      {thread.unread}
                    </span>
                  )}
                </div>
                <p className="text-sm text-slate-500">{thread.phone}</p>
                <p className="text-xs text-slate-600">{thread.lastMessage}</p>
              </div>
              <div className="flex flex-col items-end">
                <div className={`w-2 h-2 rounded-full ${
                  thread.status === 'read' ? 'bg-blue-500' :
                  thread.status === 'delivered' ? 'bg-green-500' : 'bg-gray-400'
                }`}></div>
                <span className="text-xs text-slate-500 mt-1">פתח</span>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Quick Lists - Recent Calls */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.1 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Phone className="w-5 h-5 text-blue-600" />
          שיחות אחרונות (5)
        </h3>
        
        <div className="space-y-3">
          {quickLists?.recentCalls?.slice(0, 5).map((call) => (
            <motion.div
              key={call.id}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100 cursor-pointer"
              whileHover={{ scale: 1.01 }}
              onClick={() => window.location.href = `/app/biz/calls/${call.id}`}
            >
              <div className="w-10 h-10 bg-blue-100 rounded-xl flex items-center justify-center">
                <Phone className="w-5 h-5 text-blue-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-slate-800">{call.name}</p>
                  <span className={`px-2 py-1 text-xs rounded-full ${
                    call.status === 'completed' ? 'bg-green-100 text-green-700' :
                    call.status === 'missed' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-700'
                  }`}>
                    {call.status === 'completed' ? 'הושלמה' :
                     call.status === 'missed' ? 'לא נענתה' : 'פעילה'}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <p className="text-sm text-slate-500">{call.duration}</p>
                  <span className="text-xs text-slate-400">•</span>
                  <p className="text-sm text-slate-500">{call.date}</p>
                  {call.sentiment && (
                    <>
                      <span className="text-xs text-slate-400">•</span>
                      <div className={`w-2 h-2 rounded-full ${getSentimentColor(call.sentiment)}`}></div>
                    </>
                  )}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                {call.transcribed && (
                  <Headphones className="w-4 h-4 text-green-600" />
                )}
                <span className="text-xs text-slate-500">נגן+תמלול</span>
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Quick Lists - Open Leads */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.2 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <UserCheck className="w-5 h-5 text-purple-600" />
          לידים פתוחים (5)
        </h3>
        
        <div className="space-y-3">
          {quickLists?.openLeads?.slice(0, 5).map((lead) => (
            <motion.div
              key={lead.id}
              className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100 cursor-pointer"
              whileHover={{ scale: 1.01 }}
              onClick={() => window.location.href = `/app/biz/crm/leads/${lead.id}`}
            >
              <div className="w-10 h-10 bg-purple-100 rounded-xl flex items-center justify-center">
                <UserCheck className="w-5 h-5 text-purple-600" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-slate-800">{lead.name}</p>
                  <span className={`px-2 py-1 text-xs rounded-full font-medium ${getLeadStatusColor(lead.status)}`}>
                    {lead.status === 'hot' ? 'חם' :
                     lead.status === 'warm' ? 'פושר' : 'קר'}
                  </span>
                </div>
                <p className="text-sm text-slate-500">{lead.type}</p>
                <div className="flex items-center gap-2">
                  <p className="text-xs font-medium text-emerald-600">{lead.value}</p>
                  <span className="text-xs text-slate-400">•</span>
                  <p className="text-xs text-slate-500">{lead.lastUpdate}</p>
                </div>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-xs text-slate-500">{lead.stage}</span>
                <ExternalLink className="w-4 h-4 text-slate-400 mt-1" />
              </div>
            </motion.div>
          ))}
        </div>
      </motion.div>

      {/* Recent Activity Feed */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.3 }}
      >
        <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center gap-2">
          <Activity className="w-5 h-5" />
          פעילות אחרונה
        </h3>
        
        <div className="space-y-3">
          {recentActivity.map((activity, index) => {
            const Icon = activity.icon
            return (
              <motion.div
                key={activity.id}
                className="flex items-start gap-3 p-4 rounded-xl hover:bg-slate-50 transition-colors border border-slate-100"
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 1.4 + index * 0.1 }}
              >
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                  activity.type === 'whatsapp' ? 'bg-green-100' :
                  activity.type === 'call' ? 'bg-blue-100' :
                  activity.type === 'payment' ? 'bg-emerald-100' :
                  activity.type === 'contract' ? 'bg-purple-100' : 'bg-orange-100'
                }`}>
                  <Icon className={`w-5 h-5 ${
                    activity.type === 'whatsapp' ? 'text-green-600' :
                    activity.type === 'call' ? 'text-blue-600' :
                    activity.type === 'payment' ? 'text-emerald-600' :
                    activity.type === 'contract' ? 'text-purple-600' : 'text-orange-600'
                  }`} />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-slate-800 font-medium">{activity.description}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-500">{activity.time}</span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs text-slate-600">{activity.customer}</span>
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