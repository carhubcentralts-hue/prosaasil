import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { 
  Building2, 
  Plus, 
  Search, 
  Filter,
  Edit,
  Trash2,
  Eye,
  Power,
  PowerOff,
  MessageSquare,
  Phone,
  CreditCard,
  CheckCircle,
  XCircle,
  AlertCircle,
  Users,
  Calendar,
  MapPin,
  Crown,
  Settings
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

const Businesses = () => {
  const { user, hasPermission } = useAuth()
  const navigate = useNavigate()
  
  // State management
  const [businesses, setBusinesses] = useState([])
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [channelFilter, setChannelFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)

  // Check permissions - Admin only
  if (!hasPermission('manage_businesses')) {
    navigate('/unauthorized')
    return null
  }

  useEffect(() => {
    fetchBusinesses()
  }, [searchQuery, statusFilter, channelFilter, currentPage])

  const fetchBusinesses = async () => {
    setLoading(true)
    try {
      // Simulate API call with realistic business data
      setTimeout(() => {
        const mockBusinesses = [
          {
            id: 'shai_001',
            name: 'שי דירות ומשרדים בע״מ',
            legalName: 'שי דירות ומשרדים בע״מ',
            logo: null,
            domain: 'shai-realestate.co.il',
            businessId: 'IL-516789123',
            timezone: 'Asia/Jerusalem',
            category: 'Real Estate',
            status: 'active',
            createdAt: '2024-08-15',
            integrations: {
              whatsapp: { status: 'connected', provider: 'baileys' },
              calls: { status: 'connected', provider: 'twilio' },
              paypal: { status: 'ready' },
              tranzila: { status: 'ready' }
            },
            permissions: {
              crm: true,
              whatsapp: true,
              calls: true
            },
            users: { current: 8, limit: 15 },
            numbers: {
              incoming: ['+972501234567'],
              whatsapp: '+972501234567'
            }
          },
          {
            id: 'david_002',
            name: 'דוד נכסים',
            legalName: 'דוד נכסים ושותפים בע״מ',
            logo: null,
            domain: 'david-properties.com',
            businessId: 'IL-516234567',
            timezone: 'Asia/Jerusalem',
            category: 'Real Estate',
            status: 'active',
            createdAt: '2024-07-20',
            integrations: {
              whatsapp: { status: 'error', provider: 'twilio' },
              calls: { status: 'not_configured', provider: null },
              paypal: { status: 'not_configured' },
              tranzila: { status: 'ready' }
            },
            permissions: {
              crm: true,
              whatsapp: true,
              calls: false
            },
            users: { current: 3, limit: 10 },
            numbers: {
              incoming: [],
              whatsapp: '+972502345678'
            }
          },
          {
            id: 'ron_003',
            name: 'רון השקעות',
            legalName: 'רון השקעות ויעוץ פיננסי בע״מ',
            logo: null,
            domain: null,
            businessId: 'IL-516345678',
            timezone: 'Asia/Jerusalem',
            category: 'Finance',
            status: 'frozen',
            createdAt: '2024-06-10',
            integrations: {
              whatsapp: { status: 'not_configured', provider: null },
              calls: { status: 'not_configured', provider: null },
              paypal: { status: 'not_configured' },
              tranzila: { status: 'not_configured' }
            },
            permissions: {
              crm: true,
              whatsapp: false,
              calls: false
            },
            users: { current: 1, limit: 5 },
            numbers: {
              incoming: [],
              whatsapp: null
            }
          }
        ]

        // Apply filters
        let filtered = mockBusinesses
        
        if (searchQuery) {
          filtered = filtered.filter(b => 
            b.name.includes(searchQuery) || 
            b.businessId.includes(searchQuery) ||
            b.domain?.includes(searchQuery)
          )
        }
        
        if (statusFilter !== 'all') {
          filtered = filtered.filter(b => b.status === statusFilter)
        }
        
        if (channelFilter !== 'all') {
          filtered = filtered.filter(b => {
            switch (channelFilter) {
              case 'whatsapp':
                return b.permissions.whatsapp
              case 'calls':
                return b.permissions.calls
              default:
                return true
            }
          })
        }

        setBusinesses(filtered)
        setTotalPages(Math.ceil(filtered.length / 10))
        setLoading(false)
      }, 300)
    } catch (error) {
      console.error('Error fetching businesses:', error)
      setLoading(false)
    }
  }

  const getIntegrationIcon = (status) => {
    switch (status) {
      case 'connected':
      case 'ready':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'error':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'not_configured':
      default:
        return <AlertCircle className="w-4 h-4 text-gray-400" />
    }
  }

  const getIntegrationText = (status) => {
    switch (status) {
      case 'connected':
        return 'מחובר'
      case 'ready':
        return 'מוכן'
      case 'error':
        return 'שגיאה'
      case 'not_configured':
      default:
        return 'לא הוגדר'
    }
  }

  const getStatusBadge = (status) => {
    const configs = {
      active: { text: 'פעיל', color: 'bg-green-100 text-green-800' },
      frozen: { text: 'מוקפא', color: 'bg-yellow-100 text-yellow-800' },
      testing: { text: 'נבדק', color: 'bg-blue-100 text-blue-800' }
    }
    
    const config = configs[status] || configs.active
    return (
      <span className={`px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
        {config.text}
      </span>
    )
  }

  const handleImpersonate = (businessId) => {
    // Implement impersonate logic
    console.log('Impersonating business:', businessId)
    navigate(`/app/biz/overview?business_id=${businessId}`)
  }

  const handleEdit = (businessId) => {
    navigate(`/app/admin/businesses/${businessId}/edit`)
  }

  const handleFreeze = (businessId) => {
    // Implement freeze/unfreeze logic
    console.log('Toggling freeze status for:', businessId)
  }

  const handleDelete = (businessId) => {
    // Implement soft delete logic
    if (confirm('האם אתה בטוח שברצונך למחוק עסק זה? הפעולה ניתנת לשחזור.')) {
      console.log('Deleting business:', businessId)
    }
  }

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto p-6 space-y-6">
        {/* Header Skeleton */}
        <div className="h-16 bg-white/60 rounded-2xl animate-pulse" />
        
        {/* Filters Skeleton */}
        <div className="h-12 bg-white/60 rounded-xl animate-pulse" />
        
        {/* Business Cards Skeleton */}
        {[...Array(3)].map((_, i) => (
          <div key={i} className="h-48 bg-white/60 rounded-2xl animate-pulse" />
        ))}
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      {/* Header */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl flex items-center justify-center">
              <Building2 className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-800">ניהול עסקים</h1>
              <p className="text-slate-600">ניהול מלא של עסקים, ערוצים ואינטגרציות</p>
            </div>
          </div>
          
          <motion.button
            onClick={() => navigate('/app/admin/businesses/new')}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            <Plus className="w-5 h-5" />
            עסק חדש
          </motion.button>
        </div>

        {/* Search and Filters */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Search */}
          <div className="relative col-span-2">
            <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="חיפוש עסקים..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pr-10 pl-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          
          {/* Status Filter */}
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">כל הסטטוסים</option>
            <option value="active">פעיל</option>
            <option value="frozen">מוקפא</option>
            <option value="testing">נבדק</option>
          </select>
          
          {/* Channel Filter */}
          <select
            value={channelFilter}
            onChange={(e) => setChannelFilter(e.target.value)}
            className="px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">כל הערוצים</option>
            <option value="whatsapp">WhatsApp</option>
            <option value="calls">שיחות</option>
          </select>
        </div>
      </motion.div>

      {/* Business List */}
      <div className="space-y-4">
        {businesses.length === 0 ? (
          <motion.div
            className="bg-white/80 backdrop-blur-sm rounded-2xl p-12 border border-slate-200/60 text-center"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Building2 className="w-16 h-16 mx-auto text-slate-300 mb-4" />
            <h3 className="text-xl font-semibold text-slate-800 mb-2">אין עסקים</h3>
            <p className="text-slate-600 mb-6">התחל ביצירת העסק הראשון שלך</p>
            <motion.button
              onClick={() => navigate('/app/admin/businesses/new')}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-green-500 to-emerald-600 text-white rounded-xl font-medium shadow-lg hover:shadow-xl transition-all"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
            >
              <Plus className="w-5 h-5" />
              צור עסק חדש
            </motion.button>
          </motion.div>
        ) : (
          businesses.map((business, index) => (
            <motion.div
              key={business.id}
              className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-200/60 shadow-lg hover:shadow-xl transition-all"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.1 }}
            >
              {/* Business Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-4">
                  <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                    <span className="text-white font-bold text-lg">
                      {business.name.charAt(0)}
                    </span>
                  </div>
                  <div>
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-xl font-bold text-slate-800">{business.name}</h3>
                      {getStatusBadge(business.status)}
                    </div>
                    <div className="flex items-center gap-4 text-sm text-slate-600">
                      <span className="flex items-center gap-1">
                        <Building2 className="w-4 h-4" />
                        {business.businessId}
                      </span>
                      {business.domain && (
                        <span className="flex items-center gap-1">
                          <MapPin className="w-4 h-4" />
                          {business.domain}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Calendar className="w-4 h-4" />
                        {new Date(business.createdAt).toLocaleDateString('he-IL')}
                      </span>
                    </div>
                  </div>
                </div>
                
                {/* Action Buttons */}
                <div className="flex items-center gap-2">
                  <motion.button
                    onClick={() => handleImpersonate(business.id)}
                    className="p-2 bg-orange-100 text-orange-600 rounded-lg hover:bg-orange-200 transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title="השלטה"
                  >
                    <Crown className="w-4 h-4" />
                  </motion.button>
                  
                  <motion.button
                    onClick={() => navigate(`/app/admin/businesses/${business.id}`)}
                    className="p-2 bg-blue-100 text-blue-600 rounded-lg hover:bg-blue-200 transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title="צפייה"
                  >
                    <Eye className="w-4 h-4" />
                  </motion.button>
                  
                  <motion.button
                    onClick={() => handleEdit(business.id)}
                    className="p-2 bg-slate-100 text-slate-600 rounded-lg hover:bg-slate-200 transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title="עריכה"
                  >
                    <Edit className="w-4 h-4" />
                  </motion.button>
                  
                  <motion.button
                    onClick={() => handleFreeze(business.id)}
                    className={`p-2 rounded-lg transition-colors ${
                      business.status === 'active' 
                        ? 'bg-yellow-100 text-yellow-600 hover:bg-yellow-200' 
                        : 'bg-green-100 text-green-600 hover:bg-green-200'
                    }`}
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title={business.status === 'active' ? 'הקפאה' : 'הפעלה'}
                  >
                    {business.status === 'active' ? <PowerOff className="w-4 h-4" /> : <Power className="w-4 h-4" />}
                  </motion.button>
                  
                  <motion.button
                    onClick={() => handleDelete(business.id)}
                    className="p-2 bg-red-100 text-red-600 rounded-lg hover:bg-red-200 transition-colors"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    title="מחיקה"
                  >
                    <Trash2 className="w-4 h-4" />
                  </motion.button>
                </div>
              </div>

              {/* Integrations Status */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                  <MessageSquare className="w-4 h-4 text-slate-600" />
                  <div className="flex-1">
                    <p className="text-xs text-slate-500">WhatsApp</p>
                    <div className="flex items-center gap-1">
                      {getIntegrationIcon(business.integrations.whatsapp.status)}
                      <span className="text-xs font-medium">
                        {getIntegrationText(business.integrations.whatsapp.status)}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                  <Phone className="w-4 h-4 text-slate-600" />
                  <div className="flex-1">
                    <p className="text-xs text-slate-500">שיחות</p>
                    <div className="flex items-center gap-1">
                      {getIntegrationIcon(business.integrations.calls.status)}
                      <span className="text-xs font-medium">
                        {getIntegrationText(business.integrations.calls.status)}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                  <CreditCard className="w-4 h-4 text-slate-600" />
                  <div className="flex-1">
                    <p className="text-xs text-slate-500">PayPal</p>
                    <div className="flex items-center gap-1">
                      {getIntegrationIcon(business.integrations.paypal.status)}
                      <span className="text-xs font-medium">
                        {getIntegrationText(business.integrations.paypal.status)}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 p-3 bg-slate-50 rounded-lg">
                  <CreditCard className="w-4 h-4 text-slate-600" />
                  <div className="flex-1">
                    <p className="text-xs text-slate-500">Tranzila</p>
                    <div className="flex items-center gap-1">
                      {getIntegrationIcon(business.integrations.tranzila.status)}
                      <span className="text-xs font-medium">
                        {getIntegrationText(business.integrations.tranzila.status)}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Permissions and Users */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="text-slate-600">הרשאות:</span>
                    <span className="text-green-600 font-medium">CRM ✅</span>
                    <span className={business.permissions.whatsapp ? 'text-green-600 font-medium' : 'text-slate-400'}>
                      WhatsApp {business.permissions.whatsapp ? '✅' : '❌'}
                    </span>
                    <span className={business.permissions.calls ? 'text-green-600 font-medium' : 'text-slate-400'}>
                      שיחות {business.permissions.calls ? '✅' : '❌'}
                    </span>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <Users className="w-4 h-4" />
                  <span>{business.users.current}/{business.users.limit} משתמשים</span>
                  <motion.button
                    onClick={() => navigate(`/app/admin/businesses/${business.id}/users`)}
                    className="text-blue-600 hover:text-blue-700 underline"
                    whileHover={{ scale: 1.05 }}
                  >
                    ניהול
                  </motion.button>
                </div>
              </div>
            </motion.div>
          ))
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          {[...Array(totalPages)].map((_, i) => (
            <motion.button
              key={i}
              onClick={() => setCurrentPage(i + 1)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                currentPage === i + 1
                  ? 'bg-blue-500 text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-100'
              }`}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
            >
              {i + 1}
            </motion.button>
          ))}
        </div>
      )}
    </div>
  )
}

export default Businesses