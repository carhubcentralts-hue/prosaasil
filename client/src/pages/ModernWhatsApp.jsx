import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  MessageSquare, Phone, Send, Search, Filter, Settings, Wifi,
  WifiOff, Users, Clock, CheckCircle, AlertCircle, Star,
  Eye, MoreVertical, Copy, Share2, Download, Upload,
  Smartphone, Globe, Shield, Zap, Activity, TrendingUp,
  User, Calendar, Building2, RefreshCw, Power, Link, X
} from 'lucide-react';

export default function ModernWhatsApp() {
  const [userRole, setUserRole] = useState('business');
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [connectionMethod, setConnectionMethod] = useState('baileys'); // baileys or twilio
  const [conversations, setConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [newMessage, setNewMessage] = useState('');
  const [hasWhatsAppPermissions, setHasWhatsAppPermissions] = useState(true);
  const [qrCodeUrl, setQrCodeUrl] = useState(null);
  const [showSettings, setShowSettings] = useState(false);
  const [businessInfo, setBusinessInfo] = useState(null);
  const [hasTwilioNumber, setHasTwilioNumber] = useState(false);
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectionError, setConnectionError] = useState(null);

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadConversations(role);
    checkConnectionStatus();
  }, []);

  // Re-check connection when method changes
  useEffect(() => {
    checkConnectionStatus();
  }, [connectionMethod]);

  const connectWhatsApp = async () => {
    setIsConnecting(true);
    setConnectionError(null);
    
    try {
      if (connectionMethod === 'baileys') {
        // Generate QR code and wait for manual scan
        generateQRCode();
        setIsConnecting(false);
        // QR code will be displayed and user must scan it manually
        // No automatic connection simulation
        
      } else if (connectionMethod === 'twilio') {
        if (!hasTwilioNumber) {
          setConnectionError('לא נמצא מספר Twilio מאומת לעסק זה');
          setIsConnecting(false);
          return;
        }
        
        // Simulate Twilio connection
        setTimeout(() => {
          setConnectionStatus('connected');
          setIsConnecting(false);
        }, 2000);
      }
      
    } catch (error) {
      setConnectionError(`שגיאה בחיבור: ${error.message}`);
      setIsConnecting(false);
    }
  };

  const disconnectWhatsApp = async () => {
    setConnectionStatus('disconnected');
    setQrCodeUrl(null);
    setConnectionError(null);
  };

  const checkConnectionStatus = async () => {
    try {
      // Check business info and Twilio verification
      await loadBusinessInfo();
      
      // Simulate connection check - start disconnected for demo
      setConnectionStatus('disconnected');
    } catch (error) {
      console.error('Connection check failed:', error);
      setConnectionError('שגיאה בבדיקת סטטוס החיבור');
    }
  };

  const loadBusinessInfo = async () => {
    // Demo business info with Twilio verification status
    const demoBusiness = {
      id: 1,
      name: 'עסק דמו',
      phone: '+972501234567',
      twilioPhoneVerified: Math.random() > 0.5, // Random for demo
      twilioAccountSid: Math.random() > 0.5 ? 'AC123456789' : null,
      whatsappEnabled: true
    };
    
    setBusinessInfo(demoBusiness);
    setHasTwilioNumber(demoBusiness.twilioPhoneVerified && demoBusiness.twilioAccountSid);
  };

  const generateQRCode = () => {
    // Generate a more realistic QR code
    const qrData = `whatsapp-connect-${Date.now()}-${Math.random().toString(36).substring(7)}`;
    
    // Create SVG QR code pattern (simplified for demo)
    const qrSvg = `
      <svg width="200" height="200" xmlns="http://www.w3.org/2000/svg">
        <rect width="100%" height="100%" fill="white"/>
        <rect x="20" y="20" width="20" height="20" fill="black"/>
        <rect x="60" y="20" width="20" height="20" fill="black"/>
        <rect x="100" y="20" width="20" height="20" fill="black"/>
        <rect x="140" y="20" width="20" height="20" fill="black"/>
        <rect x="20" y="60" width="20" height="20" fill="black"/>
        <rect x="140" y="60" width="20" height="20" fill="black"/>
        <rect x="20" y="100" width="20" height="20" fill="black"/>
        <rect x="100" y="100" width="20" height="20" fill="black"/>
        <rect x="20" y="140" width="20" height="20" fill="black"/>
        <rect x="60" y="140" width="20" height="20" fill="black"/>
        <rect x="100" y="140" width="20" height="20" fill="black"/>
        <rect x="140" y="140" width="20" height="20" fill="black"/>
        <text x="100" y="185" text-anchor="middle" font-size="12px" font-family="Arial">${connectionMethod.toUpperCase()}</text>
      </svg>
    `;
    
    const base64QR = btoa(qrSvg);
    setQrCodeUrl(`data:image/svg+xml;base64,${base64QR}`);
  };

  // Manual connection function for when QR is scanned
  const handleManualConnection = () => {
    setConnectionStatus('connected');
    setQrCodeUrl(null);
    setConnectionError(null);
  };

  const loadConversations = async (role) => {
    try {
      await checkWhatsAppPermissions(role);
      
      // Enhanced demo conversations data
      const demoConversations = [
        {
          id: 1,
          customer_name: 'יוסי כהן',
          customer_phone: '972501234567',
          business_name: 'עסק ABC - ייעוץ',
          business_id: 1,
          last_message: 'תודה על המידע, אחזור אליכם בקרוב',
          last_message_time: '2025-08-07 16:30:00',
          unread_count: 0,
          status: 'active',
          lead_score: 85,
          sentiment: 'positive',
          messages: [
            {
              id: 1,
              sender: 'customer',
              content: 'שלום, אני מעוניין בשירותי ייעוץ עסקי',
              timestamp: '2025-08-07 16:20:00',
              type: 'text'
            },
            {
              id: 2,
              sender: 'business',
              content: 'שלום! נשמח לעזור. איזה סוג ייעוץ מעניין אותך?',
              timestamp: '2025-08-07 16:21:00',
              type: 'text'
            },
            {
              id: 3,
              sender: 'customer',
              content: 'אני צריך עזרה עם תכנון אסטרטגי',
              timestamp: '2025-08-07 16:22:00',
              type: 'text'
            },
            {
              id: 4,
              sender: 'business',
              content: 'מצוין! זה אחד מתחומי ההתמחות שלנו. אשלח לך חומר נוסף',
              timestamp: '2025-08-07 16:25:00',
              type: 'text'
            },
            {
              id: 5,
              sender: 'customer',
              content: 'תודה על המידע, אחזור אליכם בקרוב',
              timestamp: '2025-08-07 16:30:00',
              type: 'text'
            }
          ]
        },
        {
          id: 2,
          customer_name: 'שרה לוי',
          customer_phone: '972529876543',
          business_name: 'עסק XYZ - מכירות',
          business_id: 2,
          last_message: 'אני רוצה לדבר עם מנהל',
          last_message_time: '2025-08-07 18:15:00',
          unread_count: 2,
          status: 'pending',
          lead_score: 60,
          sentiment: 'neutral',
          messages: [
            {
              id: 1,
              sender: 'customer',
              content: 'יש לי בעיה עם המוצר שרכשתי',
              timestamp: '2025-08-07 18:10:00',
              type: 'text'
            },
            {
              id: 2,
              sender: 'business',
              content: 'אני מצטער לשמוע. איך אני יכול לעזור?',
              timestamp: '2025-08-07 18:12:00',
              type: 'text'
            },
            {
              id: 3,
              sender: 'customer',
              content: 'אני רוצה לדבר עם מנהל',
              timestamp: '2025-08-07 18:15:00',
              type: 'text'
            }
          ]
        },
        {
          id: 3,
          customer_name: 'דני אברהם',
          customer_phone: '972535555555',
          business_name: 'עסק 123 - טכנולוגיה',
          business_id: 3,
          last_message: 'מתי אפשר לקבוע פגישה?',
          last_message_time: '2025-08-07 19:45:00',
          unread_count: 1,
          status: 'hot_lead',
          lead_score: 90,
          sentiment: 'positive',
          messages: [
            {
              id: 1,
              sender: 'customer',
              content: 'ראיתי את המערכות שלכם, מרשים מאוד!',
              timestamp: '2025-08-07 19:40:00',
              type: 'text'
            },
            {
              id: 2,
              sender: 'business',
              content: 'תודה רבה! נשמח להציג לך עוד פתרונות',
              timestamp: '2025-08-07 19:42:00',
              type: 'text'
            },
            {
              id: 3,
              sender: 'customer',
              content: 'מתי אפשר לקבוע פגישה?',
              timestamp: '2025-08-07 19:45:00',
              type: 'text'
            }
          ]
        }
      ];

      setConversations(demoConversations);
      setLoading(false);
    } catch (error) {
      console.error('Error loading conversations:', error);
      setLoading(false);
    }
  };

  const checkWhatsAppPermissions = async (role) => {
    if (role === 'business') {
      const businessData = { whatsapp_enabled: true };
      setHasWhatsAppPermissions(businessData.whatsapp_enabled);
    } else {
      setHasWhatsAppPermissions(true);
    }
  };



  const sendMessage = () => {
    if (!newMessage.trim() || !selectedConversation) return;
    
    const message = {
      id: Date.now(),
      sender: 'business',
      content: newMessage,
      timestamp: new Date().toISOString(),
      type: 'text'
    };

    setConversations(prev => 
      prev.map(conv => 
        conv.id === selectedConversation.id
          ? {
              ...conv,
              messages: [...conv.messages, message],
              last_message: newMessage,
              last_message_time: new Date().toISOString()
            }
          : conv
      )
    );

    setNewMessage('');
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'hot_lead': return 'bg-red-100 text-red-800 border-red-200';
      case 'active': return 'bg-green-100 text-green-800 border-green-200';
      case 'pending': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'hot_lead': return 'ליד חם';
      case 'active': return 'פעיל';
      case 'pending': return 'ממתין';
      default: return 'לא ידוע';
    }
  };

  const getSentimentColor = (sentiment) => {
    switch (sentiment) {
      case 'positive': return 'text-green-600';
      case 'negative': return 'text-red-600';
      case 'neutral': return 'text-yellow-600';
      default: return 'text-gray-600';
    }
  };

  const filteredConversations = conversations.filter(conv => 
    conv.customer_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    conv.customer_phone.includes(searchTerm) ||
    conv.last_message.toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (!hasWhatsAppPermissions) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center bg-red-50 p-8 rounded-2xl border border-red-200 max-w-md">
            <AlertCircle className="w-16 h-16 text-red-500 mx-auto mb-4" />
            <h3 className="text-xl font-semibold text-red-800 mb-2">אין הרשאה ל-WhatsApp עסקי</h3>
            <p className="text-red-600">העסק שלך לא כולל תכונת WhatsApp עסקי. צור קשר לשדרוג החבילה.</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-green-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען WhatsApp עסקי...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header */}
        <div className="bg-gradient-to-r from-green-600 to-emerald-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <MessageSquare className="w-10 h-10" />
                💬 WhatsApp עסקי AI
              </h1>
              <p className="text-green-100 text-lg">
                ניהול שיחות WhatsApp עם בינה מלאכותית מתקדמת
              </p>
            </div>
            <div className="text-left">
              <div className={`inline-flex items-center px-4 py-2 rounded-full text-sm font-medium ${
                connectionStatus === 'connected' 
                  ? 'bg-green-500 text-white' 
                  : 'bg-red-500 text-white'
              }`}>
                {connectionStatus === 'connected' ? (
                  <><Wifi className="w-4 h-4 mr-2" />מחובר</>
                ) : (
                  <><WifiOff className="w-4 h-4 mr-2" />מנותק</>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Connection Settings */}
        {connectionStatus === 'disconnected' && (
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <h2 className="text-xl font-bold mb-4">הגדרות חיבור WhatsApp</h2>
            
            <div className="grid md:grid-cols-2 gap-6 mb-6">
              {/* Baileys Method */}
              <div className={`border-2 rounded-xl p-4 cursor-pointer transition-all ${
                connectionMethod === 'baileys' 
                  ? 'border-blue-500 bg-blue-50' 
                  : 'border-gray-200 hover:border-blue-300'
              }`} onClick={() => setConnectionMethod('baileys')}>
                <div className="flex items-center gap-3 mb-3">
                  <Smartphone className="w-8 h-8 text-blue-600" />
                  <div>
                    <h3 className="font-bold text-gray-900">Baileys (מומלץ)</h3>
                    <p className="text-sm text-gray-600">חיבור ישיר ל-WhatsApp Web</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    חינם ללא עלויות נוספות
                  </div>
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    תמיכה מלאה בכל תכונות WhatsApp
                  </div>
                  <div className="flex items-center gap-2 text-yellow-600">
                    <AlertCircle className="w-4 h-4" />
                    דורש סריקת QR כל 24 שעות
                  </div>
                </div>
              </div>

              {/* Twilio Method */}
              <div className={`border-2 rounded-xl p-4 cursor-pointer transition-all ${
                connectionMethod === 'twilio' 
                  ? 'border-purple-500 bg-purple-50' 
                  : 'border-gray-200 hover:border-purple-300'
              }`} onClick={() => setConnectionMethod('twilio')}>
                <div className="flex items-center gap-3 mb-3">
                  <Globe className="w-8 h-8 text-purple-600" />
                  <div>
                    <h3 className="font-bold text-gray-900">Twilio API</h3>
                    <p className="text-sm text-gray-600">חיבור עסקי מקצועי</p>
                  </div>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    יציבות מירבית
                  </div>
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    ללא צורך בסריקת QR
                  </div>
                  <div className="flex items-center gap-2 text-red-600">
                    <AlertCircle className="w-4 h-4" />
                    עלות נוספת עפ"י שימוש
                  </div>
                  {!hasTwilioNumber && (
                    <div className="flex items-center gap-2 text-red-600 mt-2">
                      <X className="w-4 h-4" />
                      לא זמין - אין מספר Twilio מאומת
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div className="flex gap-4 justify-center">
              <button
                onClick={connectWhatsApp}
                disabled={isConnecting || (connectionMethod === 'twilio' && !hasTwilioNumber)}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all ${
                  isConnecting || (connectionMethod === 'twilio' && !hasTwilioNumber)
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-green-500 text-white hover:bg-green-600'
                }`}
              >
                {isConnecting ? (
                  <RefreshCw className="w-5 h-5 animate-spin" />
                ) : (
                  <Power className="w-5 h-5" />
                )}
                {isConnecting ? 'מתחבר...' : 'התחבר ל-WhatsApp'}
              </button>
            </div>

            {connectionError && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-center">
                <AlertCircle className="w-5 h-5 inline mr-2" />
                {connectionError}
              </div>
            )}

            {businessInfo && (
              <div className="mt-6 bg-gray-50 rounded-xl p-4">
                <h3 className="font-bold text-gray-900 mb-2">מידע עסק</h3>
                <div className="text-sm text-gray-600 space-y-1">
                  <p><span className="font-medium">שם:</span> {businessInfo.name}</p>
                  <p><span className="font-medium">טלפון:</span> {businessInfo.phone}</p>
                  <p><span className="font-medium">Twilio מאומת:</span> {hasTwilioNumber ? '✅ כן' : '❌ לא'}</p>
                </div>
              </div>
            )}
          </div>
        )}

        {/* QR Code Display */}
        {qrCodeUrl && connectionMethod === 'baileys' && (
          <div className="bg-gradient-to-br from-white to-green-50 rounded-3xl shadow-2xl border border-green-100 p-10 text-center">
            <div className="flex items-center justify-center gap-4 mb-8">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center">
                <Smartphone className="w-7 h-7 text-white" />
              </div>
              <h3 className="text-3xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                📱 סרוק QR Code
              </h3>
            </div>
            
            <div className="max-w-lg mx-auto">
              <div className="bg-white rounded-3xl p-8 mb-8 shadow-lg border border-gray-200">
                <div className="w-72 h-72 mx-auto bg-white rounded-2xl border-4 border-green-200 flex items-center justify-center shadow-inner">
                  <img 
                    src={qrCodeUrl} 
                    alt="WhatsApp QR Code" 
                    className="w-full h-full rounded-xl object-contain"
                  />
                </div>
              </div>
              
              <div className="bg-green-50 rounded-2xl p-6 mb-6 border border-green-200">
                <h4 className="font-bold text-green-900 mb-4 text-lg">🔢 הוראות חיבור:</h4>
                <div className="space-y-4 text-gray-700">
                  <div className="flex items-start gap-4 p-3 bg-white rounded-xl shadow-sm">
                    <div className="w-8 h-8 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center text-white font-bold shrink-0">1</div>
                    <div>
                      <p className="font-semibold text-gray-900">פתח WhatsApp במכשיר הנייד</p>
                      <p className="text-sm text-gray-600">וודא שאתה מחובר לאינטרנט</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-4 p-3 bg-white rounded-xl shadow-sm">
                    <div className="w-8 h-8 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center text-white font-bold shrink-0">2</div>
                    <div>
                      <p className="font-semibold text-gray-900">עבור להגדרות ← מכשירים מקושרים</p>
                      <p className="text-sm text-gray-600">או לחץ על שלוש הנקודות ← WhatsApp Web</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-4 p-3 bg-white rounded-xl shadow-sm">
                    <div className="w-8 h-8 bg-gradient-to-r from-green-500 to-emerald-500 rounded-full flex items-center justify-center text-white font-bold shrink-0">3</div>
                    <div>
                      <p className="font-semibold text-gray-900">סרוק את הקוד</p>
                      <p className="text-sm text-gray-600">כוון את המצלמה לכיוון הQR</p>
                    </div>
                  </div>
                </div>
              </div>
              
              <div className="flex items-center justify-center gap-3 text-orange-600 mb-6 bg-orange-50 rounded-xl p-4 border border-orange-200">
                <div className="w-8 h-8 bg-orange-100 rounded-full flex items-center justify-center">
                  <div className="w-3 h-3 bg-orange-500 rounded-full animate-pulse"></div>
                </div>
                <div className="text-center">
                  <span className="text-lg font-bold block">👀 סרוק את הקוד עכשיו</span>
                  <span className="text-sm text-orange-700">אחרי שסרקת - לחץ על "סרקתי בהצלחה"</span>
                </div>
              </div>
              
              {connectionError && (
                <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 flex items-center justify-center gap-2">
                  <AlertCircle className="w-5 h-5" />
                  <span>{connectionError}</span>
                </div>
              )}
              
              <div className="flex gap-4 justify-center">
                <button
                  onClick={handleManualConnection}
                  className="px-8 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl hover:from-blue-700 hover:to-indigo-700 transition-all font-bold text-lg shadow-lg flex items-center gap-3"
                >
                  <CheckCircle className="w-5 h-5" />
                  ✅ סרקתי בהצלחה
                </button>
                
                <button
                  onClick={generateQRCode}
                  className="px-8 py-4 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-xl hover:from-green-700 hover:to-emerald-700 transition-all font-bold text-lg shadow-lg flex items-center gap-3"
                >
                  <RefreshCw className="w-5 h-5" />
                  חדש QR Code
                </button>
                
                <button
                  onClick={() => {
                    setQrCodeUrl(null);
                    setConnectionStatus('disconnected');
                  }}
                  className="px-8 py-4 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-all font-medium text-lg border border-gray-300 flex items-center gap-3"
                >
                  <X className="w-5 h-5" />
                  בטל
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Stats Cards */}
        {connectionStatus === 'connected' && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm">שיחות פעילות</p>
                  <p className="text-3xl font-bold text-green-600">
                    {conversations.filter(c => c.status === 'active').length}
                  </p>
                </div>
                <MessageSquare className="w-12 h-12 text-green-500" />
              </div>
            </div>
            
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm">ליידים חמים</p>
                  <p className="text-3xl font-bold text-red-600">
                    {conversations.filter(c => c.status === 'hot_lead').length}
                  </p>
                </div>
                <Star className="w-12 h-12 text-red-500" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm">הודעות שלא נקראו</p>
                  <p className="text-3xl font-bold text-orange-600">
                    {conversations.reduce((sum, c) => sum + c.unread_count, 0)}
                  </p>
                </div>
                <Eye className="w-12 h-12 text-orange-500" />
              </div>
            </div>

            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-gray-600 text-sm">ממוצע ליד</p>
                  <p className="text-3xl font-bold text-purple-600">
                    {Math.round(conversations.reduce((sum, c) => sum + c.lead_score, 0) / conversations.length)}%
                  </p>
                </div>
                <TrendingUp className="w-12 h-12 text-purple-500" />
              </div>
            </div>
          </div>
        )}

        {/* Main Chat Interface */}
        {connectionStatus === 'connected' && (
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden" style={{ height: '70vh' }}>
            <div className="flex h-full">
              {/* Conversations List */}
              <div className="w-1/3 border-l border-gray-200 flex flex-col">
                {/* Search */}
                <div className="p-4 border-b border-gray-200">
                  <div className="relative">
                    <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
                    <input
                      type="text"
                      placeholder="חיפוש שיחות..."
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                    />
                  </div>
                </div>

                {/* Conversations */}
                <div className="flex-1 overflow-y-auto">
                  {filteredConversations.map(conversation => (
                    <div
                      key={conversation.id}
                      onClick={() => setSelectedConversation(conversation)}
                      className={`p-4 border-b border-gray-100 cursor-pointer hover:bg-gray-50 transition-colors ${
                        selectedConversation?.id === conversation.id ? 'bg-green-50 border-l-4 border-l-green-500' : ''
                      }`}
                    >
                      <div className="flex items-start justify-between mb-2">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full flex items-center justify-center text-white font-bold text-sm">
                            {conversation.customer_name.charAt(0)}
                          </div>
                          <div>
                            <h4 className="font-medium text-gray-900">{conversation.customer_name}</h4>
                            <p className="text-xs text-gray-500">{conversation.customer_phone}</p>
                          </div>
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          {conversation.unread_count > 0 && (
                            <div className="bg-green-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                              {conversation.unread_count}
                            </div>
                          )}
                          <span className="text-xs text-gray-400">
                            {new Date(conversation.last_message_time).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                          </span>
                        </div>
                      </div>
                      
                      <div className="flex items-center justify-between mb-2">
                        <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium border ${getStatusColor(conversation.status)}`}>
                          {getStatusText(conversation.status)}
                        </span>
                        <div className="flex items-center gap-1">
                          <Star className="w-3 h-3 text-yellow-500" />
                          <span className="text-xs text-gray-600">{conversation.lead_score}%</span>
                        </div>
                      </div>

                      <p className="text-sm text-gray-600 truncate">{conversation.last_message}</p>
                      
                      {userRole === 'admin' && conversation.business_name && (
                        <p className="text-xs text-purple-600 mt-1">{conversation.business_name}</p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Chat Area */}
              <div className="flex-1 flex flex-col">
                {selectedConversation ? (
                  <>
                    {/* Chat Header */}
                    <div className="p-4 border-b border-gray-200 bg-gray-50">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 bg-gradient-to-br from-green-500 to-emerald-600 rounded-full flex items-center justify-center text-white font-bold">
                            {selectedConversation.customer_name.charAt(0)}
                          </div>
                          <div>
                            <h3 className="font-bold text-gray-900">{selectedConversation.customer_name}</h3>
                            <p className="text-sm text-gray-600">{selectedConversation.customer_phone}</p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`px-2 py-1 rounded-full text-xs font-medium ${getSentimentColor(selectedConversation.sentiment)}`}>
                            {selectedConversation.sentiment === 'positive' ? 'חיובי' : 
                             selectedConversation.sentiment === 'negative' ? 'שלילי' : 'נייטרלי'}
                          </span>
                          <button className="p-2 hover:bg-gray-200 rounded-full">
                            <MoreVertical className="w-5 h-5" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Messages */}
                    <div className="flex-1 overflow-y-auto p-4 space-y-4">
                      {selectedConversation.messages.map(message => (
                        <div key={message.id} className={`flex ${message.sender === 'business' ? 'justify-end' : 'justify-start'}`}>
                          <div className={`max-w-[70%] rounded-2xl p-3 ${
                            message.sender === 'business' 
                              ? 'bg-green-500 text-white' 
                              : 'bg-gray-100 text-gray-900'
                          }`}>
                            <p className="text-sm">{message.content}</p>
                            <p className={`text-xs mt-1 ${
                              message.sender === 'business' ? 'text-green-100' : 'text-gray-500'
                            }`}>
                              {new Date(message.timestamp).toLocaleTimeString('he-IL', { hour: '2-digit', minute: '2-digit' })}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Message Input */}
                    <div className="p-4 border-t border-gray-200">
                      <div className="flex gap-3">
                        <input
                          type="text"
                          value={newMessage}
                          onChange={(e) => setNewMessage(e.target.value)}
                          onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                          placeholder="כתוב הודעה..."
                          className="flex-1 border border-gray-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-green-500"
                        />
                        <button
                          onClick={sendMessage}
                          disabled={!newMessage.trim()}
                          className="px-6 py-3 bg-green-500 text-white rounded-xl hover:bg-green-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
                        >
                          <Send className="w-5 h-5" />
                        </button>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex-1 flex items-center justify-center">
                    <div className="text-center">
                      <MessageSquare className="w-24 h-24 text-gray-300 mx-auto mb-4" />
                      <h3 className="text-xl font-medium text-gray-900 mb-2">בחר שיחה</h3>
                      <p className="text-gray-500">בחר שיחה מהרשימה כדי להתחיל לצ'טט</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Connection Actions */}
        {connectionStatus === 'connected' && (
          <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2 text-green-600">
                  <CheckCircle className="w-5 h-5" />
                  <span className="font-medium">מחובר ב-{connectionMethod === 'baileys' ? 'Baileys' : 'Twilio'}</span>
                </div>
                <div className="text-sm text-gray-500">
                  זמן חיבור: {new Date().toLocaleTimeString('he-IL')}
                </div>
              </div>
              
              <div className="flex gap-3">
                <button
                  onClick={() => checkConnectionStatus()}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-500 text-white rounded-xl hover:bg-blue-600"
                >
                  <RefreshCw className="w-4 h-4" />
                  רענן
                </button>
                <button
                  onClick={disconnectWhatsApp}
                  className="flex items-center gap-2 px-4 py-2 bg-red-500 text-white rounded-xl hover:bg-red-600"
                >
                  <WifiOff className="w-4 h-4" />
                  התנתק
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ModernLayout>
  );
}