import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { 
  Building2, 
  ArrowRight, 
  ArrowLeft,
  Check,
  X,
  Settings,
  MessageSquare,
  Phone,
  CreditCard,
  Users,
  Eye,
  Globe,
  MapPin,
  Clock,
  Tag,
  FileText,
  Zap,
  TestTube,
  Save,
  AlertCircle
} from 'lucide-react'
import { useAuth } from '@/contexts/AuthContext'
import { useNavigate } from 'react-router-dom'

const BusinessNew = () => {
  const { hasPermission } = useAuth()
  const navigate = useNavigate()
  
  // Check permissions - Admin only
  if (!hasPermission('manage_businesses')) {
    navigate('/unauthorized')
    return null
  }

  // Wizard state
  const [currentStep, setCurrentStep] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [validationErrors, setValidationErrors] = useState({})

  // Form data for all steps
  const [formData, setFormData] = useState({
    // Step 1: Basic Info
    name: '',
    legalName: '',
    domain: '',
    logo: null,
    timezone: 'Asia/Jerusalem',
    language: 'he',
    category: '',
    
    // Step 2: Channel Permissions
    enableWhatsApp: false,
    enableCalls: false,
    
    // Step 3: Numbers and Providers
    callsProvider: 'twilio',
    callsAccountSid: '',
    callsAuthToken: '',
    incomingNumbers: [''],
    defaultNumber: '',
    whatsappProvider: 'baileys', // baileys or twilio
    whatsappSender: '',
    whatsappStatus: 'not_configured',
    
    // Step 4: Prompts
    systemPrompt: '',
    whatsappPrompt: '',
    callsPrompt: '',
    minSilenceMs: 1500,
    bargeIn: true,
    ttsVoice: 'he-IL-Standard-A',
    sttLanguage: 'he-IL',
    maxCallDuration: 300,
    
    // Step 5: Limits
    userLimit: 10,
    maxConcurrentCalls: 5,
    messagesPerMinute: 30,
    dataRetentionDays: 90,
    
    // Step 6: Review
    connectivityTests: {}
  })

  const steps = [
    { id: 1, title: 'פרטים בסיסיים', icon: Building2 },
    { id: 2, title: 'הרשאות ערוצים', icon: Settings },
    { id: 3, title: 'מספרים וספקים', icon: Phone },
    { id: 4, title: 'פרומפטים והתנהגות', icon: MessageSquare },
    { id: 5, title: 'מגבלות והיקפים', icon: Users },
    { id: 6, title: 'סיכום ויצירה', icon: Check }
  ]

  const categories = [
    { value: 'real-estate', label: 'נדל״ן' },
    { value: 'legal', label: 'משפטי' },
    { value: 'finance', label: 'פיננסי' },
    { value: 'healthcare', label: 'בריאות' },
    { value: 'education', label: 'חינוך' },
    { value: 'technology', label: 'טכנולוגיה' },
    { value: 'other', label: 'אחר' }
  ]

  const timezones = [
    { value: 'Asia/Jerusalem', label: 'ישראל (GMT+2/+3)' },
    { value: 'Europe/London', label: 'לונדון (GMT+0/+1)' },
    { value: 'America/New_York', label: 'ניו יורק (GMT-5/-4)' },
    { value: 'America/Los_Angeles', label: 'לוס אנג׳לס (GMT-8/-7)' }
  ]

  const updateFormData = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }))
    // Clear validation error for this field
    if (validationErrors[field]) {
      setValidationErrors(prev => ({ ...prev, [field]: null }))
    }
  }

  const validateStep = (step) => {
    const errors = {}
    
    switch (step) {
      case 1:
        if (!formData.name.trim()) errors.name = 'שם העסק נדרש'
        if (!formData.legalName.trim()) errors.legalName = 'השם המשפטי נדרש'
        if (!formData.category) errors.category = 'קטגוריה נדרשת'
        break
        
      case 2:
        // No validation needed - permissions are boolean
        break
        
      case 3:
        if (formData.enableCalls) {
          if (!formData.callsAccountSid.trim()) errors.callsAccountSid = 'Account SID נדרש'
          if (!formData.callsAuthToken.trim()) errors.callsAuthToken = 'Auth Token נדרש'
          if (!formData.defaultNumber.trim()) errors.defaultNumber = 'מספר ברירת מחדל נדרש'
        }
        if (formData.enableWhatsApp) {
          if (!formData.whatsappSender.trim()) errors.whatsappSender = 'מספר WhatsApp נדרש'
        }
        break
        
      case 4:
        if (!formData.systemPrompt.trim()) errors.systemPrompt = 'פרומפט מערכת נדרש'
        if (formData.enableWhatsApp && !formData.whatsappPrompt.trim()) {
          errors.whatsappPrompt = 'פרומפט WhatsApp נדרש'
        }
        if (formData.enableCalls && !formData.callsPrompt.trim()) {
          errors.callsPrompt = 'פרומפט שיחות נדרש'
        }
        break
        
      case 5:
        if (formData.userLimit <= 0) errors.userLimit = 'מגבלת משתמשים חייבת להיות חיובית'
        if (formData.maxConcurrentCalls <= 0) errors.maxConcurrentCalls = 'מגבלת שיחות חייבת להיות חיובית'
        break
        
      default:
        break
    }
    
    setValidationErrors(errors)
    return Object.keys(errors).length === 0
  }

  const nextStep = () => {
    if (validateStep(currentStep)) {
      setCurrentStep(prev => Math.min(prev + 1, 6))
    }
  }

  const prevStep = () => {
    setCurrentStep(prev => Math.max(prev - 1, 1))
  }

  const testConnectivity = async (channel) => {
    setFormData(prev => ({
      ...prev,
      connectivityTests: {
        ...prev.connectivityTests,
        [channel]: { status: 'testing', message: 'בודק חיבוריות...' }
      }
    }))

    // Simulate connectivity test
    setTimeout(() => {
      const success = Math.random() > 0.3 // 70% success rate
      setFormData(prev => ({
        ...prev,
        connectivityTests: {
          ...prev.connectivityTests,
          [channel]: {
            status: success ? 'success' : 'error',
            message: success 
              ? 'החיבור תקין ✅' 
              : 'שגיאה בחיבור - בדוק הגדרות ❌'
          }
        }
      }))
    }, 2000)
  }

  const handleSubmit = async () => {
    if (!validateStep(6)) return
    
    setIsSubmitting(true)
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000))
      
      // Mock business creation
      console.log('Creating business with data:', formData)
      
      // Navigate to business list with success message
      navigate('/app/admin/businesses', { 
        state: { message: `עסק "${formData.name}" נוצר בהצלחה!` }
      })
    } catch (error) {
      console.error('Error creating business:', error)
      setValidationErrors({ submit: 'שגיאה ביצירת העסק. אנא נסה שוב.' })
    } finally {
      setIsSubmitting(false)
    }
  }

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-6">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שם העסק *
                </label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => updateFormData('name', e.target.value)}
                  className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    validationErrors.name ? 'border-red-300' : 'border-slate-200'
                  }`}
                  placeholder="לדוגמה: שי דירות ומשרדים"
                />
                {validationErrors.name && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.name}</p>
                )}
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שם משפטי *
                </label>
                <input
                  type="text"
                  value={formData.legalName}
                  onChange={(e) => updateFormData('legalName', e.target.value)}
                  className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    validationErrors.legalName ? 'border-red-300' : 'border-slate-200'
                  }`}
                  placeholder="לדוגמה: שי דירות ומשרדים בע״מ"
                />
                {validationErrors.legalName && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.legalName}</p>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  דומיין/מותג (אופציונלי)
                </label>
                <input
                  type="text"
                  value={formData.domain}
                  onChange={(e) => updateFormData('domain', e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="לדוגמה: shai-realestate.co.il"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  קטגוריה *
                </label>
                <select
                  value={formData.category}
                  onChange={(e) => updateFormData('category', e.target.value)}
                  className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    validationErrors.category ? 'border-red-300' : 'border-slate-200'
                  }`}
                >
                  <option value="">בחר קטגוריה</option>
                  {categories.map(cat => (
                    <option key={cat.value} value={cat.value}>{cat.label}</option>
                  ))}
                </select>
                {validationErrors.category && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.category}</p>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  אזור זמן
                </label>
                <select
                  value={formData.timezone}
                  onChange={(e) => updateFormData('timezone', e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {timezones.map(tz => (
                    <option key={tz.value} value={tz.value}>{tz.label}</option>
                  ))}
                </select>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שפת ברירת מחדל
                </label>
                <select
                  value={formData.language}
                  onChange={(e) => updateFormData('language', e.target.value)}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  <option value="he">עברית</option>
                  <option value="en">אנגלית</option>
                  <option value="ar">ערבית</option>
                </select>
              </div>
            </div>
          </div>
        )

      case 2:
        return (
          <div className="space-y-6">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-800 mb-1">הבהרה חשובה</h4>
                  <p className="text-sm text-blue-700">
                    CRM תמיד פעיל לכל עסק. הערוצים (WhatsApp ושיחות) פותחים/סוגרים יכולות ותפריטים נוספים.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <motion.div
                className={`p-6 border-2 rounded-2xl cursor-pointer transition-all ${
                  formData.enableWhatsApp 
                    ? 'border-green-300 bg-green-50' 
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
                onClick={() => updateFormData('enableWhatsApp', !formData.enableWhatsApp)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      formData.enableWhatsApp ? 'bg-green-500' : 'bg-slate-400'
                    }`}>
                      <MessageSquare className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-800">WhatsApp</h3>
                      <p className="text-sm text-slate-600">הודעות ותמיכה</p>
                    </div>
                  </div>
                  <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                    formData.enableWhatsApp 
                      ? 'border-green-500 bg-green-500' 
                      : 'border-slate-300'
                  }`}>
                    {formData.enableWhatsApp && <Check className="w-4 h-4 text-white" />}
                  </div>
                </div>
                <p className="text-sm text-slate-600">
                  {formData.enableWhatsApp ? 'WhatsApp מופעל - יידרשו הגדרות ספק ומספרים' : 'לחץ להפעלת WhatsApp'}
                </p>
              </motion.div>

              <motion.div
                className={`p-6 border-2 rounded-2xl cursor-pointer transition-all ${
                  formData.enableCalls 
                    ? 'border-blue-300 bg-blue-50' 
                    : 'border-slate-200 bg-white hover:border-slate-300'
                }`}
                onClick={() => updateFormData('enableCalls', !formData.enableCalls)}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
              >
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${
                      formData.enableCalls ? 'bg-blue-500' : 'bg-slate-400'
                    }`}>
                      <Phone className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <h3 className="font-semibold text-slate-800">שיחות קוליות</h3>
                      <p className="text-sm text-slate-600">AI שיחות אוטומטיות</p>
                    </div>
                  </div>
                  <div className={`w-6 h-6 rounded-full border-2 flex items-center justify-center ${
                    formData.enableCalls 
                      ? 'border-blue-500 bg-blue-500' 
                      : 'border-slate-300'
                  }`}>
                    {formData.enableCalls && <Check className="w-4 h-4 text-white" />}
                  </div>
                </div>
                <p className="text-sm text-slate-600">
                  {formData.enableCalls ? 'שיחות מופעלות - יידרשו הגדרות Twilio' : 'לחץ להפעלת שיחות קוליות'}
                </p>
              </motion.div>
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <h4 className="font-medium text-slate-800 mb-2">סיכום הרשאות:</h4>
              <div className="space-y-1 text-sm">
                <div className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-600" />
                  <span>CRM - תמיד פעיל</span>
                </div>
                <div className="flex items-center gap-2">
                  {formData.enableWhatsApp ? 
                    <Check className="w-4 h-4 text-green-600" /> : 
                    <X className="w-4 h-4 text-slate-400" />
                  }
                  <span className={formData.enableWhatsApp ? 'text-slate-800' : 'text-slate-400'}>
                    WhatsApp
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {formData.enableCalls ? 
                    <Check className="w-4 h-4 text-green-600" /> : 
                    <X className="w-4 h-4 text-slate-400" />
                  }
                  <span className={formData.enableCalls ? 'text-slate-800' : 'text-slate-400'}>
                    שיחות קוליות
                  </span>
                </div>
              </div>
            </div>
          </div>
        )

      case 3:
        return (
          <div className="space-y-6">
            {/* Calls Configuration */}
            {formData.enableCalls && (
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-blue-800 mb-4 flex items-center gap-2">
                  <Phone className="w-5 h-5" />
                  הגדרות שיחות (Twilio)
                </h3>
                
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Account SID *
                    </label>
                    <input
                      type="text"
                      value={formData.callsAccountSid}
                      onChange={(e) => updateFormData('callsAccountSid', e.target.value)}
                      className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        validationErrors.callsAccountSid ? 'border-red-300' : 'border-slate-200'
                      }`}
                      placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
                    />
                    {validationErrors.callsAccountSid && (
                      <p className="mt-1 text-sm text-red-600">{validationErrors.callsAccountSid}</p>
                    )}
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-2">
                      Auth Token *
                    </label>
                    <input
                      type="password"
                      value={formData.callsAuthToken}
                      onChange={(e) => updateFormData('callsAuthToken', e.target.value)}
                      className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                        validationErrors.callsAuthToken ? 'border-red-300' : 'border-slate-200'
                      }`}
                      placeholder="••••••••••••••••••••••••••••••••"
                    />
                    {validationErrors.callsAuthToken && (
                      <p className="mt-1 text-sm text-red-600">{validationErrors.callsAuthToken}</p>
                    )}
                  </div>
                </div>

                <div className="mt-4">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    מספר נכנס ברירת מחדל *
                  </label>
                  <input
                    type="tel"
                    value={formData.defaultNumber}
                    onChange={(e) => updateFormData('defaultNumber', e.target.value)}
                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      validationErrors.defaultNumber ? 'border-red-300' : 'border-slate-200'
                    }`}
                    placeholder="+972501234567"
                  />
                  {validationErrors.defaultNumber && (
                    <p className="mt-1 text-sm text-red-600">{validationErrors.defaultNumber}</p>
                  )}
                </div>

                <motion.button
                  onClick={() => testConnectivity('calls')}
                  className="mt-4 flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <TestTube className="w-4 h-4" />
                  בדוק חיבוריות
                </motion.button>
                
                {formData.connectivityTests.calls && (
                  <div className={`mt-2 text-sm ${
                    formData.connectivityTests.calls.status === 'success' ? 'text-green-600' :
                    formData.connectivityTests.calls.status === 'error' ? 'text-red-600' :
                    'text-blue-600'
                  }`}>
                    {formData.connectivityTests.calls.message}
                  </div>
                )}
              </div>
            )}

            {/* WhatsApp Configuration */}
            {formData.enableWhatsApp && (
              <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                <h3 className="text-lg font-semibold text-green-800 mb-4 flex items-center gap-2">
                  <MessageSquare className="w-5 h-5" />
                  הגדרות WhatsApp
                </h3>
                
                <div className="mb-4">
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    ספק WhatsApp
                  </label>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <motion.div
                      className={`p-4 border-2 rounded-xl cursor-pointer transition-all ${
                        formData.whatsappProvider === 'baileys' 
                          ? 'border-green-500 bg-green-100' 
                          : 'border-slate-200 bg-white'
                      }`}
                      onClick={() => updateFormData('whatsappProvider', 'baileys')}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${
                          formData.whatsappProvider === 'baileys' ? 'bg-green-500' : 'bg-slate-300'
                        }`} />
                        <div>
                          <h4 className="font-medium">Baileys</h4>
                          <p className="text-sm text-slate-600">חיבור ישיר לWhatsApp Web</p>
                        </div>
                      </div>
                    </motion.div>
                    
                    <motion.div
                      className={`p-4 border-2 rounded-xl cursor-pointer transition-all ${
                        formData.whatsappProvider === 'twilio' 
                          ? 'border-green-500 bg-green-100' 
                          : 'border-slate-200 bg-white'
                      }`}
                      onClick={() => updateFormData('whatsappProvider', 'twilio')}
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-3 h-3 rounded-full ${
                          formData.whatsappProvider === 'twilio' ? 'bg-green-500' : 'bg-slate-300'
                        }`} />
                        <div>
                          <h4 className="font-medium">Twilio</h4>
                          <p className="text-sm text-slate-600">WhatsApp Business API</p>
                        </div>
                      </div>
                    </motion.div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    מספר WhatsApp *
                  </label>
                  <input
                    type="tel"
                    value={formData.whatsappSender}
                    onChange={(e) => updateFormData('whatsappSender', e.target.value)}
                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 ${
                      validationErrors.whatsappSender ? 'border-red-300' : 'border-slate-200'
                    }`}
                    placeholder="+972501234567"
                  />
                  {validationErrors.whatsappSender && (
                    <p className="mt-1 text-sm text-red-600">{validationErrors.whatsappSender}</p>
                  )}
                </div>

                <motion.button
                  onClick={() => testConnectivity('whatsapp')}
                  className="mt-4 flex items-center gap-2 px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 transition-colors"
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                >
                  <TestTube className="w-4 h-4" />
                  בדוק חיבוריות
                </motion.button>
                
                {formData.connectivityTests.whatsapp && (
                  <div className={`mt-2 text-sm ${
                    formData.connectivityTests.whatsapp.status === 'success' ? 'text-green-600' :
                    formData.connectivityTests.whatsapp.status === 'error' ? 'text-red-600' :
                    'text-green-600'
                  }`}>
                    {formData.connectivityTests.whatsapp.message}
                  </div>
                )}
              </div>
            )}

            {!formData.enableCalls && !formData.enableWhatsApp && (
              <div className="text-center py-12 text-slate-500">
                <Settings className="w-16 h-16 mx-auto mb-4 text-slate-300" />
                <p>לא נבחרו ערוצים להגדרה</p>
                <p className="text-sm">CRM יהיה זמין ללא הגדרות נוספות</p>
              </div>
            )}
          </div>
        )

      case 4:
        return (
          <div className="space-y-6">
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-blue-800 mb-1">הנחיות פרומפטים</h4>
                  <p className="text-sm text-blue-700">
                    פרומפטים מגדירים את התנהגות ה-AI. ניתן להגדיר פרומפט כללי ופרומפטים ייעודיים לכל ערוץ.
                  </p>
                </div>
              </div>
            </div>

            {/* System Prompt */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                פרומפט מערכת כללי *
              </label>
              <textarea
                value={formData.systemPrompt}
                onChange={(e) => updateFormData('systemPrompt', e.target.value)}
                rows={4}
                className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  validationErrors.systemPrompt ? 'border-red-300' : 'border-slate-200'
                }`}
                placeholder="אתה AI מתקדם המתמחה בנדל״ן. תמיד תהיה אדיב, מקצועי ומועיל. תענה בעברית בלבד..."
              />
              {validationErrors.systemPrompt && (
                <p className="mt-1 text-sm text-red-600">{validationErrors.systemPrompt}</p>
              )}
              <p className="mt-1 text-xs text-slate-500">זהות, תחום, מדיניות, שפה וטון</p>
            </div>

            {/* WhatsApp Prompt */}
            {formData.enableWhatsApp && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  פרומפט WhatsApp *
                </label>
                <textarea
                  value={formData.whatsappPrompt}
                  onChange={(e) => updateFormData('whatsappPrompt', e.target.value)}
                  rows={3}
                  className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 ${
                    validationErrors.whatsappPrompt ? 'border-red-300' : 'border-slate-200'
                  }`}
                  placeholder="בהודעות WhatsApp, תכתב הודעות קצרות וברורות. תמיד תסיים עם שאלה או הזמנה לפעולה..."
                />
                {validationErrors.whatsappPrompt && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.whatsappPrompt}</p>
                )}
                <p className="mt-1 text-xs text-slate-500">ניסוחי WA, follow-up, זמן תגובה, שעות פעילות</p>
              </div>
            )}

            {/* Calls Prompt */}
            {formData.enableCalls && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  פרומפט שיחות קוליות *
                </label>
                <textarea
                  value={formData.callsPrompt}
                  onChange={(e) => updateFormData('callsPrompt', e.target.value)}
                  rows={3}
                  className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    validationErrors.callsPrompt ? 'border-red-300' : 'border-slate-200'
                  }`}
                  placeholder="בשיחות קוליות, תדבר בצורה טבעית וחברותית. תהיה קצר ותמציתי. אל תחזור על עצמך..."
                />
                {validationErrors.callsPrompt && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.callsPrompt}</p>
                )}
                <p className="mt-1 text-xs text-slate-500">פתיח קולי, ניהול תורות, גבולות זמן, קול TTS</p>
              </div>
            )}

            {/* Technical Settings */}
            {formData.enableCalls && (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    זמן שתיקה מינימלי (ms)
                  </label>
                  <input
                    type="number"
                    value={formData.minSilenceMs}
                    onChange={(e) => updateFormData('minSilenceMs', parseInt(e.target.value))}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="500"
                    max="5000"
                    step="100"
                  />
                  <p className="mt-1 text-xs text-slate-500">מתי להפסיק להקליט (500-5000)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    משך שיחה מקסימלי (שניות)
                  </label>
                  <input
                    type="number"
                    value={formData.maxCallDuration}
                    onChange={(e) => updateFormData('maxCallDuration', parseInt(e.target.value))}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="60"
                    max="1800"
                    step="30"
                  />
                  <p className="mt-1 text-xs text-slate-500">הגבלת זמן שיחה (60-1800)</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    קול TTS
                  </label>
                  <select
                    value={formData.ttsVoice}
                    onChange={(e) => updateFormData('ttsVoice', e.target.value)}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="he-IL-Standard-A">עברית - קול A (נשי)</option>
                    <option value="he-IL-Standard-B">עברית - קול B (גברי)</option>
                    <option value="he-IL-Standard-C">עברית - קול C (נשי)</option>
                    <option value="he-IL-Standard-D">עברית - קול D (גברי)</option>
                  </select>
                </div>

                <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                  <div>
                    <h4 className="font-medium text-slate-800">קטיעת דיבור</h4>
                    <p className="text-sm text-slate-600">אפשר למשתמש לקטוע את ה-AI</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => updateFormData('bargeIn', !formData.bargeIn)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                      formData.bargeIn ? 'bg-blue-600' : 'bg-slate-300'
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                        formData.bargeIn ? 'translate-x-6' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              </div>
            )}
          </div>
        )

      case 5:
        return (
          <div className="space-y-6">
            <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-yellow-800 mb-1">מגבלות משאבים</h4>
                  <p className="text-sm text-yellow-700">
                    הגדר מגבלות לשימוש במשאבי המערכת ושמירת נתונים.
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  מגבלת משתמשים *
                </label>
                <input
                  type="number"
                  value={formData.userLimit}
                  onChange={(e) => updateFormData('userLimit', parseInt(e.target.value))}
                  className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                    validationErrors.userLimit ? 'border-red-300' : 'border-slate-200'
                  }`}
                  min="1"
                  max="1000"
                  step="1"
                />
                {validationErrors.userLimit && (
                  <p className="mt-1 text-sm text-red-600">{validationErrors.userLimit}</p>
                )}
                <p className="mt-1 text-xs text-slate-500">מקסימום משתמשים לעסק (1-1000)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-2">
                  שמירת נתונים (ימים)
                </label>
                <input
                  type="number"
                  value={formData.dataRetentionDays}
                  onChange={(e) => updateFormData('dataRetentionDays', parseInt(e.target.value))}
                  className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                  min="30"
                  max="365"
                  step="30"
                />
                <p className="mt-1 text-xs text-slate-500">זמן שמירה להקלטות ותמלולים (30-365)</p>
              </div>

              {formData.enableCalls && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    שיחות במקביל
                  </label>
                  <input
                    type="number"
                    value={formData.maxConcurrentCalls}
                    onChange={(e) => updateFormData('maxConcurrentCalls', parseInt(e.target.value))}
                    className={`w-full px-4 py-3 border rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                      validationErrors.maxConcurrentCalls ? 'border-red-300' : 'border-slate-200'
                    }`}
                    min="1"
                    max="50"
                    step="1"
                  />
                  {validationErrors.maxConcurrentCalls && (
                    <p className="mt-1 text-sm text-red-600">{validationErrors.maxConcurrentCalls}</p>
                  )}
                  <p className="mt-1 text-xs text-slate-500">מקסימום שיחות בו-זמנית (1-50)</p>
                </div>
              )}

              {formData.enableWhatsApp && (
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-2">
                    הודעות לדקה
                  </label>
                  <input
                    type="number"
                    value={formData.messagesPerMinute}
                    onChange={(e) => updateFormData('messagesPerMinute', parseInt(e.target.value))}
                    className="w-full px-4 py-3 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500"
                    min="10"
                    max="100"
                    step="5"
                  />
                  <p className="mt-1 text-xs text-slate-500">קצב שליחת הודעות מקסימלי (10-100)</p>
                </div>
              )}
            </div>

            <div className="bg-slate-50 border border-slate-200 rounded-xl p-4">
              <h4 className="font-medium text-slate-800 mb-3">סיכום מגבלות:</h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-slate-600">משתמשים:</span>
                  <span className="font-medium">{formData.userLimit}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-600">שמירת נתונים:</span>
                  <span className="font-medium">{formData.dataRetentionDays} ימים</span>
                </div>
                {formData.enableCalls && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">שיחות במקביל:</span>
                    <span className="font-medium">{formData.maxConcurrentCalls}</span>
                  </div>
                )}
                {formData.enableWhatsApp && (
                  <div className="flex justify-between">
                    <span className="text-slate-600">הודעות/דקה:</span>
                    <span className="font-medium">{formData.messagesPerMinute}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )

      case 6:
        return (
          <div className="space-y-6">
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 mb-6">
              <div className="flex items-start gap-3">
                <Check className="w-5 h-5 text-green-600 mt-0.5" />
                <div>
                  <h4 className="font-medium text-green-800 mb-1">סיכום העסק החדש</h4>
                  <p className="text-sm text-green-700">
                    סקור את כל ההגדרות לפני יצירת העסק. לאחר היצירה, תתבצע בדיקת חיבוריות אוטומטית.
                  </p>
                </div>
              </div>
            </div>

            {/* Business Summary */}
            <div className="space-y-4">
              <div className="space-y-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <h4 className="font-medium text-slate-800 mb-3 flex items-center gap-2">
                    <Building2 className="w-4 h-4" />
                    פרטי עסק
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-600">שם:</span>
                      <span className="font-medium">{formData.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">שם משפטי:</span>
                      <span className="font-medium">{formData.legalName}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">קטגוריה:</span>
                      <span className="font-medium">
                        {categories.find(c => c.value === formData.category)?.label || 'לא נבחר'}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">אזור זמן:</span>
                      <span className="font-medium">
                        {timezones.find(t => t.value === formData.timezone)?.label}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <h4 className="font-medium text-slate-800 mb-3 flex items-center gap-2">
                    <Settings className="w-4 h-4" />
                    הרשאות ערוצים
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-600">CRM:</span>
                      <span className="text-green-600 font-medium">✅ פעיל</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-600">WhatsApp:</span>
                      <span className={formData.enableWhatsApp ? 'text-green-600 font-medium' : 'text-slate-400'}>
                        {formData.enableWhatsApp ? '✅ מופעל' : '❌ כבוי'}
                      </span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-slate-600">שיחות:</span>
                      <span className={formData.enableCalls ? 'text-green-600 font-medium' : 'text-slate-400'}>
                        {formData.enableCalls ? '✅ מופעל' : '❌ כבוי'}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <h4 className="font-medium text-slate-800 mb-3 flex items-center gap-2">
                    <Users className="w-4 h-4" />
                    מגבלות
                  </h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-slate-600">משתמשים:</span>
                      <span className="font-medium">{formData.userLimit}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-600">שמירת נתונים:</span>
                      <span className="font-medium">{formData.dataRetentionDays} ימים</span>
                    </div>
                    {formData.enableCalls && (
                      <div className="flex justify-between">
                        <span className="text-slate-600">שיחות במקביל:</span>
                        <span className="font-medium">{formData.maxConcurrentCalls}</span>
                      </div>
                    )}
                    {formData.enableWhatsApp && (
                      <div className="flex justify-between">
                        <span className="text-slate-600">הודעות/דקה:</span>
                        <span className="font-medium">{formData.messagesPerMinute}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Connectivity Tests */}
                <div className="bg-white border border-slate-200 rounded-xl p-4">
                  <h4 className="font-medium text-slate-800 mb-3 flex items-center gap-2">
                    <TestTube className="w-4 h-4" />
                    מצב חיבוריות
                  </h4>
                  <div className="space-y-2 text-sm">
                    {formData.enableWhatsApp && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">WhatsApp:</span>
                        <span className={`font-medium ${
                          formData.connectivityTests.whatsapp?.status === 'success' ? 'text-green-600' :
                          formData.connectivityTests.whatsapp?.status === 'error' ? 'text-red-600' :
                          'text-slate-400'
                        }`}>
                          {formData.connectivityTests.whatsapp?.status === 'success' ? '✅ תקין' :
                           formData.connectivityTests.whatsapp?.status === 'error' ? '❌ שגיאה' :
                           '⚪ לא נבדק'}
                        </span>
                      </div>
                    )}
                    {formData.enableCalls && (
                      <div className="flex items-center justify-between">
                        <span className="text-slate-600">שיחות:</span>
                        <span className={`font-medium ${
                          formData.connectivityTests.calls?.status === 'success' ? 'text-green-600' :
                          formData.connectivityTests.calls?.status === 'error' ? 'text-red-600' :
                          'text-slate-400'
                        }`}>
                          {formData.connectivityTests.calls?.status === 'success' ? '✅ תקין' :
                           formData.connectivityTests.calls?.status === 'error' ? '❌ שגיאה' :
                           '⚪ לא נבדק'}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>

            {/* Warnings */}
            {(!formData.connectivityTests.whatsapp?.status || !formData.connectivityTests.calls?.status) && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4">
                <div className="flex items-start gap-3">
                  <AlertCircle className="w-5 h-5 text-yellow-600 mt-0.5" />
                  <div>
                    <h4 className="font-medium text-yellow-800 mb-1">אזהרות</h4>
                    <ul className="text-sm text-yellow-700 space-y-1">
                      {formData.enableWhatsApp && !formData.connectivityTests.whatsapp?.status && (
                        <li>• WhatsApp לא נבדק - יומלץ לבדוק חיבוריות בשלב 3</li>
                      )}
                      {formData.enableCalls && !formData.connectivityTests.calls?.status && (
                        <li>• שיחות לא נבדקו - יומלץ לבדוק חיבוריות בשלב 3</li>
                      )}
                    </ul>
                  </div>
                </div>
              </div>
            )}

            {validationErrors.submit && (
              <div className="bg-red-50 border border-red-200 rounded-xl p-4">
                <div className="flex items-center gap-3">
                  <XCircle className="w-5 h-5 text-red-600" />
                  <p className="text-sm text-red-700">{validationErrors.submit}</p>
                </div>
              </div>
            )}
          </div>
        )

      default:
        return (
          <div className="text-center py-12">
            <FileText className="w-16 h-16 mx-auto mb-4 text-slate-300" />
            <p className="text-slate-600">שלב {currentStep} בפיתוח...</p>
          </div>
        )
    }
  }

  return (
    <div className="max-w-2xl mx-auto p-4">
      {/* Header */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 border border-slate-200/60 shadow-lg mb-4"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
              <Building2 className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-800">יצירת עסק חדש</h1>
              <p className="text-sm text-slate-600">אשף הגדרה מושלם</p>
            </div>
          </div>
          
          <motion.button
            onClick={() => navigate('/app/admin/businesses')}
            className="flex items-center gap-2 px-3 py-2 text-slate-600 hover:text-slate-800 transition-colors text-sm"
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <X className="w-4 h-4" />
            ביטול
          </motion.button>
        </div>

        {/* Progress Steps */}
        <div className="overflow-x-auto">
          <div className="flex items-center justify-between min-w-max px-2">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <div className={`flex items-center gap-2 ${
                  step.id === currentStep ? 'text-blue-600' :
                  step.id < currentStep ? 'text-green-600' : 'text-slate-400'
                }`}>
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-medium ${
                    step.id === currentStep ? 'bg-blue-100 text-blue-600' :
                    step.id < currentStep ? 'bg-green-100 text-green-600' : 'bg-slate-100 text-slate-400'
                  }`}>
                    {step.id < currentStep ? <Check className="w-3 h-3" /> : step.id}
                  </div>
                  <span className="hidden sm:block text-xs font-medium truncate max-w-20">{step.title}</span>
                </div>
                {index < steps.length - 1 && (
                  <div className={`w-8 h-px mx-2 ${
                    step.id < currentStep ? 'bg-green-300' : 'bg-slate-200'
                  }`} />
                )}
              </div>
            ))}
          </div>
        </div>
      </motion.div>

      {/* Step Content */}
      <motion.div
        className="bg-white/80 backdrop-blur-sm rounded-2xl p-4 border border-slate-200/60 shadow-lg mb-4"
        key={currentStep}
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.3 }}
      >
        <div className="mb-4">
          <h2 className="text-lg font-bold text-slate-800 mb-2">
            {steps.find(s => s.id === currentStep)?.title}
          </h2>
          <div className="w-8 h-1 bg-gradient-to-r from-blue-500 to-purple-600 rounded-full" />
        </div>

        {renderStepContent()}
      </motion.div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <motion.button
          onClick={prevStep}
          disabled={currentStep === 1}
          className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
            currentStep === 1 
              ? 'bg-slate-100 text-slate-400 cursor-not-allowed' 
              : 'bg-slate-200 text-slate-700 hover:bg-slate-300'
          }`}
          whileHover={currentStep > 1 ? { scale: 1.02 } : {}}
          whileTap={currentStep > 1 ? { scale: 0.98 } : {}}
        >
          <ArrowLeft className="w-5 h-5" />
          הקודם
        </motion.button>

        <div className="flex-1 mx-4">
          <div className="w-full bg-slate-200 rounded-full h-2">
            <div 
              className="bg-gradient-to-r from-blue-500 to-purple-600 h-2 rounded-full transition-all duration-500"
              style={{ width: `${(currentStep / 6) * 100}%` }}
            />
          </div>
          <p className="text-center text-sm text-slate-600 mt-2">
            שלב {currentStep} מתוך 6
          </p>
        </div>

        {currentStep === 6 ? (
          <motion.button
            onClick={handleSubmit}
            disabled={isSubmitting}
            className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
              isSubmitting 
                ? 'bg-slate-400 text-white cursor-not-allowed' 
                : 'bg-gradient-to-r from-green-500 to-emerald-600 text-white hover:shadow-lg'
            }`}
            whileHover={!isSubmitting ? { scale: 1.02 } : {}}
            whileTap={!isSubmitting ? { scale: 0.98 } : {}}
          >
            {isSubmitting ? (
              <>
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                יוצר...
              </>
            ) : (
              <>
                <Save className="w-5 h-5" />
                צור עסק
              </>
            )}
          </motion.button>
        ) : (
          <motion.button
            onClick={nextStep}
            className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-500 to-purple-600 text-white rounded-xl font-medium hover:shadow-lg transition-all"
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
          >
            הבא
            <ArrowRight className="w-5 h-5" />
          </motion.button>
        )}
      </div>
    </div>
  )
}

export default BusinessNew