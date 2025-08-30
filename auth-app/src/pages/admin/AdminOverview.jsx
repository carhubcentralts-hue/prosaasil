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
  Eye,
  Calendar,
  Bell,
  CheckCircle,
  XCircle,
  UserPlus,
  Zap,
  Activity,
  DollarSign,
  Clock,
  Target,
  Filter,
  ArrowUpRight,
  Settings,
  Shield,
  Database,
  Wifi,
  WifiOff
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'

const AdminOverview = () => {
  console.log('🚀 AdminOverview component loaded!')
  const { user, impersonate } = useAuth()
  const [timeRange, setTimeRange] = useState('7d')
  const [selectedBusiness, setSelectedBusiness] = useState(null)
  const [kpis, setKpis] = useState(null)
  const [integrations, setIntegrations] = useState(null)
  const [recentActivity, setRecentActivity] = useState([])
  const [quickLists, setQuickLists] = useState(null)
  const [loading, setLoading] = useState(false) // Changed to false for testing

  const timeRanges = [
    { value: 'today', label: 'היום' },
    { value: '7d', label: '7 ימים' },
    { value: '30d', label: '30 ימים' },
    { value: 'custom', label: 'מותאם' }
  ]

  const businesses = [
    { id: 'all', name: 'כל העסקים', type: 'system' },
    { id: 'shai_001', name: 'שי דירות ומשרדים בע״מ', type: 'realestate', active: true },
    { id: 'david_002', name: 'דוד נכסים', type: 'realestate', active: true },
    { id: 'ron_003', name: 'רון השקעות', type: 'finance', active: false }
  ]

  useEffect(() => {
    fetchOverviewData()
    
    // Update data every 15 seconds for real-time feeling
    const interval = setInterval(fetchOverviewData, 15000)
    return () => clearInterval(interval)
  }, [timeRange, selectedBusiness])

  const fetchOverviewData = async () => {
    try {
      // Simulate API call with realistic data
      setTimeout(() => {
        const hour = new Date().getHours()
        const isBusinessHours = hour >= 8 && hour <= 22
        const businessId = selectedBusiness?.id || 'all'
        
        // KPIs with real-time variation
        setKpis({
          activeCalls: isBusinessHours ? Math.floor(Math.random() * 12) + 3 : Math.floor(Math.random() * 2),
          whatsappMessages24h: Math.floor(Math.random() * 150) + 200,
          deliveryRate: `${(Math.random() * 5 + 92).toFixed(1)}%`,
          avgResponseTime: `${(Math.random() * 3 + 1.2).toFixed(1)} דק`,
          newLeads: Math.floor(Math.random() * 15) + 25,
          opportunities: Math.floor(Math.random() * 8) + 12,
          streamStatus204Rate: `${(Math.random() * 5 + 95).toFixed(1)}%`,
          fallbackCount: Math.floor(Math.random() * 3)
        })

        // Integration Status
        setIntegrations({
          whatsapp: Math.random() > 0.1 ? 'connected' : 'error',
          voice: isBusinessHours ? 'ws_ok' : 'fallback',
          paypal: Math.random() > 0.3 ? 'ready' : 'not_configured',
          tranzila: 'ready',
          stripe: Math.random() > 0.7 ? 'ready' : 'not_configured'
        })

        // Recent Activity Feed
        setRecentActivity([
          {
            id: 1,
            type: 'whatsapp',
            business: 'שי דירות ומשרדים',
            message: 'לקוח חדש הצטרף ל-WhatsApp - מעוניין בדירת 4 חדרים',
            time: new Date().toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            status: 'unread',
            priority: 'medium',
            icon: MessageSquare
          },
          {
            id: 2,
            type: 'call',
            business: 'דוד נכסים',
            message: 'שיחה נענתה בהצלחה - תמלול מוכן',
            time: new Date(Date.now() - 2 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            status: 'completed',
            priority: 'high',
            icon: Phone
          },
          {
            id: 3,
            type: 'payment',
            business: 'רון השקעות',
            message: 'תשלום התקבל - ₪15,000 עמלת מכירה',
            time: new Date(Date.now() - 5 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            status: 'success',
            priority: 'high',
            icon: DollarSign
          },
          {
            id: 4,
            type: 'contract',
            business: 'שי דירות ומשרדים',
            message: 'חוזה חדש נחתם דיגיטלית - דירה בחדרה',
            time: new Date(Date.now() - 8 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            status: 'signed',
            priority: 'high',
            icon: TrendingUp
          },
          {
            id: 5,
            type: 'user',
            business: 'דוד נכסים',
            message: 'משתמש חדש הוזמן - סוכן מכירות',
            time: new Date(Date.now() - 12 * 60000).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' }),
            status: 'pending',
            priority: 'low',
            icon: UserPlus
          }
        ])

        // Quick Lists
        setQuickLists({
          whatsappThreads: [
            { id: 1, name: 'דוד כהן', phone: '054-1234567', unread: 3, status: 'delivered', lastMessage: 'אשמח לקבוע פגישה' },
            { id: 2, name: 'שרה לוי', phone: '052-9876543', unread: 1, status: 'read', lastMessage: 'תודה על הפרטים' },
            { id: 3, name: 'יוסי משה', phone: '050-5555555', unread: 0, status: 'sent', lastMessage: 'אני אחזור אליך מחר' },
            { id: 4, name: 'רחל אברהם', phone: '053-7777777', unread: 2, status: 'delivered', lastMessage: 'מה המחיר של הדירה?' },
            { id: 5, name: 'מיכל דוד', phone: '054-3333333', unread: 1, status: 'read', lastMessage: 'מתי נוכל להיפגש?' }
          ],
          recentCalls: [
            { id: 1, name: 'אבי שמש', duration: '5:23', status: 'completed', transcribed: true, date: 'היום 14:30' },
            { id: 2, name: 'ליאת גל', duration: '2:15', status: 'completed', transcribed: true, date: 'היום 13:15' },
            { id: 3, name: 'רון ברק', duration: '8:42', status: 'completed', transcribed: false, date: 'היום 11:20' },
            { id: 4, name: 'נועה כץ', duration: '3:30', status: 'missed', transcribed: false, date: 'אתמול 16:45' },
            { id: 5, name: 'תומר לב', duration: '6:12', status: 'completed', transcribed: true, date: 'אתמול 15:30' }
          ],
          openLeads: [
            { id: 1, name: 'יעל רוזן', status: 'hot', lastUpdate: 'לפני שעה', value: '₪2.3M', type: 'דירת גן בהרצליה' },
            { id: 2, name: 'אלון פרץ', status: 'warm', lastUpdate: 'לפני 3 שעות', value: '₪890K', type: 'דירת 3 חדרים בחדרה' },
            { id: 3, name: 'דנה שחר', status: 'cold', lastUpdate: 'אתמול', value: '₪1.5M', type: 'פנטהאוס בתל אביב' },
            { id: 4, name: 'עמית גולן', status: 'hot', lastUpdate: 'לפני 2 שעות', value: '₪750K', type: 'דירת 4 חדרים בפתח תקוה' },
            { id: 5, name: 'לילך בן דוד', status: 'warm', lastUpdate: 'לפני 4 שעות', value: '₪1.2M', type: 'דירה בראשון לציון' }
          ]
        })
        
        setLoading(false)
      }, 300)
    } catch (error) {
      console.error('Error fetching overview:', error)
      setLoading(false)
    }
  }

  const handleImpersonate = async (businessId) => {
    const success = await impersonate(businessId)
    if (success) {
      window.location.href = '/app/biz/overview'
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
            <div className="w-2 h-2 bg-red-500 rounded-full"></div>
          </div>
        </div>
        
        {/* Time Range Selector */}
        <div className="flex gap-2 mb-4">
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

        {/* Business Selector */}
        <div className="relative">
          <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-xl">
            <Building2 className="w-4 h-4 text-slate-600" />
            <select 
              value={selectedBusiness?.id || 'all'}
              onChange={(e) => setSelectedBusiness(businesses.find(b => b.id === e.target.value))}
              className="flex-1 bg-transparent text-sm font-medium text-slate-800 focus:outline-none"
            >
              {businesses.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name} {!business.active && business.id !== 'all' ? '(מוקפא)' : ''}
                </option>
              ))}
            </select>
          </div>
        </div>
      </motion.div>

      {/* KPIs Grid - 4 tiles vertical */}
      <div className="space-y-3">
        {[
          { 
            icon: Phone, 
            label: 'שיחות פעילות כרגע', 
            value: kpis?.activeCalls,
            detail: `${kpis?.streamStatus204Rate} stream תקין`,
            color: 'text-green-600',
            bg: 'bg-green-100'
          },
          { 
            icon: MessageSquare, 
            label: 'הודעות WA ב-24ש׳', 
            value: kpis?.whatsappMessages24h,
            detail: `${kpis?.deliveryRate} מסירה`,
            color: 'text-blue-600',
            bg: 'bg-blue-100'
          },
          { 
            icon: Clock, 
            label: 'זמן תגובה ראשון (p95)', 
            value: kpis?.avgResponseTime,
            detail: `${kpis?.fallbackCount} fallbacks`,
            color: 'text-purple-600',
            bg: 'bg-purple-100'
          },
          { 
            icon: Target, 
            label: 'לידים חדשים / הזדמנויות', 
            value: `${kpis?.newLeads}/${kpis?.opportunities}`,
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
            onClick={() => window.location.href = '/app/admin/businesses/new'}
            className="w-full flex items-center gap-3 p-4 bg-gradient-primary text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Plus className="w-5 h-5" />
            יצירת עסק חדש
          </motion.button>
          
          <motion.button
            onClick={() => handleImpersonate('shai_001')}
            className="w-full flex items-center gap-3 p-4 bg-orange-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Eye className="w-5 h-5" />
            Impersonate עסק
          </motion.button>
          
          <motion.button
            onClick={() => window.location.href = '/app/admin/users/invite'}
            className="w-full flex items-center gap-3 p-4 bg-purple-500 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <UserPlus className="w-5 h-5" />
            הזמנת משתמש מערכת
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
              tranzila: 'Tranzila',
              stripe: 'Stripe'
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
                  <p className="text-xs text-slate-500">הגדרה נדרשת</p>
                )}
              </div>
            )
          })}
        </div>
      </motion.div>

      {/* Management Cubes */}
      <div className="grid grid-cols-2 gap-4">
        {/* Business Management */}
        <motion.div
          className="bg-gradient-to-br from-purple-500 via-purple-600 to-indigo-600 rounded-2xl p-6 text-white cursor-pointer"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.7 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => window.location.href = '/app/admin/businesses'}
        >
          <div className="flex items-center justify-between mb-4">
            <Building2 className="w-8 h-8 text-purple-200" />
            <span className="text-2xl font-bold">12</span>
          </div>
          <h3 className="text-lg font-semibold mb-2">ניהול עסקים</h3>
          <p className="text-purple-200 text-sm mb-3">יצירה, הקפאה ו-Impersonate</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-green-400 rounded-full"></div>
              <span className="text-xs text-purple-200">9 פעילים</span>
            </div>
            <ArrowUpRight className="w-4 h-4 text-purple-200" />
          </div>
        </motion.div>

        {/* System Users Management */}
        <motion.div
          className="bg-gradient-to-br from-orange-500 via-red-500 to-pink-600 rounded-2xl p-6 text-white cursor-pointer"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.8 }}
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => window.location.href = '/app/admin/users'}
        >
          <div className="flex items-center justify-between mb-4">
            <Users className="w-8 h-8 text-orange-200" />
            <span className="text-2xl font-bold">47</span>
          </div>
          <h3 className="text-lg font-semibold mb-2">ניהול משתמשים (מערכת)</h3>
          <p className="text-orange-200 text-sm mb-3">Roles והזמנות ממתינות</p>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 bg-yellow-400 rounded-full"></div>
              <span className="text-xs text-orange-200">3 ממתינים</span>
            </div>
            <ArrowUpRight className="w-4 h-4 text-orange-200" />
          </div>
        </motion.div>
      </div>

      {/* Quick Lists - WhatsApp Threads */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.9 }}
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
              onClick={() => window.location.href = `/app/admin/whatsapp/thread/${thread.id}`}
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

      {/* Recent Activity Feed */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.0 }}
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
                transition={{ delay: 1.1 + index * 0.1 }}
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
                  <p className="text-sm text-slate-800 font-medium">{activity.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-500">{activity.time}</span>
                    <span className="text-xs text-slate-400">•</span>
                    <span className="text-xs text-slate-600">{activity.business}</span>
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

      {/* System Alerts */}
      <motion.div
        className="bg-gradient-to-r from-red-500 to-orange-500 rounded-2xl p-6 text-white"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1.2 }}
      >
        <div className="flex items-center gap-3 mb-4">
          <AlertCircle className="w-6 h-6" />
          <h3 className="text-lg font-semibold">התראות מערכתיות</h3>
        </div>
        
        <div className="space-y-2">
          <div className="flex items-center justify-between p-3 bg-white/20 rounded-xl">
            <div className="flex items-center gap-2">
              <WifiOff className="w-4 h-4" />
              <span className="text-sm">2 עסקים במצב Fallback</span>
            </div>
            <button className="text-xs bg-white/30 px-2 py-1 rounded-lg hover:bg-white/40 transition-colors">
              תקן
            </button>
          </div>
          
          <div className="flex items-center justify-between p-3 bg-white/20 rounded-xl">
            <div className="flex items-center gap-2">
              <XCircle className="w-4 h-4" />
              <span className="text-sm">PayPal לא מוגדר - 3 עסקים</span>
            </div>
            <button className="text-xs bg-white/30 px-2 py-1 rounded-lg hover:bg-white/40 transition-colors">
              הגדר
            </button>
          </div>
        </div>
      </motion.div>
    </div>
  )
}

export default AdminOverview