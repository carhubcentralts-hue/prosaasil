import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Settings, User, Bell, Shield, Palette, Globe,
  Phone, MessageSquare, Key, Database, Cloud,
  Save, Reset, Eye, EyeOff, Upload, Download,
  Smartphone, Monitor, Volume2, Mic, Camera,
  Lock, Unlock, AlertTriangle, CheckCircle
} from 'lucide-react';

export default function ModernSettings() {
  const [userRole, setUserRole] = useState('business');
  const [activeTab, setActiveTab] = useState('profile');
  const [settings, setSettings] = useState({
    profile: {
      name: 'עסק דמיון',
      email: 'business@demo.com',
      phone: '050-1234567',
      address: 'תל אביב, ישראל',
      website: 'www.demo-business.co.il',
      description: 'עסק מוביל בתחום השירותים'
    },
    notifications: {
      emailNotifications: true,
      smsNotifications: true,
      whatsappNotifications: true,
      callNotifications: true,
      soundEnabled: true,
      pushNotifications: true
    },
    security: {
      twoFactorEnabled: false,
      passwordExpiry: '90',
      loginAlerts: true,
      sessionTimeout: '30',
      ipWhitelist: ''
    },
    integrations: {
      whatsappConnected: true,
      twilioConnected: true,
      openaiEnabled: true,
      googleTTSEnabled: true,
      autoRecording: true,
      aiResponses: true
    },
    display: {
      theme: 'light',
      language: 'he',
      dateFormat: 'DD/MM/YYYY',
      timeFormat: '24h',
      currency: 'ILS'
    }
  });
  const [showApiKey, setShowApiKey] = useState(false);
  const [saveStatus, setSaveStatus] = useState('');

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
  }, []);

  const tabs = [
    { id: 'profile', label: 'פרופיל עסקי', icon: User, color: 'text-blue-600' },
    { id: 'notifications', label: 'התראות', icon: Bell, color: 'text-yellow-600' },
    { id: 'security', label: 'אבטחה', icon: Shield, color: 'text-red-600' },
    { id: 'integrations', label: 'אינטגרציות', icon: Cloud, color: 'text-green-600' },
    { id: 'display', label: 'תצוגה', icon: Monitor, color: 'text-purple-600' }
  ];

  const handleSettingChange = (section, key, value) => {
    setSettings(prev => ({
      ...prev,
      [section]: {
        ...prev[section],
        [key]: value
      }
    }));
  };

  const handleSave = async () => {
    setSaveStatus('saving');
    // Simulate API call
    setTimeout(() => {
      setSaveStatus('saved');
      setTimeout(() => setSaveStatus(''), 2000);
    }, 1000);
  };

  const ProfileSettings = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <User className="w-6 h-6 text-blue-600" />
          פרטי העסק
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">שם העסק</label>
            <input
              type="text"
              value={settings.profile.name}
              onChange={(e) => handleSettingChange('profile', 'name', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">אימייל</label>
            <input
              type="email"
              value={settings.profile.email}
              onChange={(e) => handleSettingChange('profile', 'email', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">טלפון</label>
            <input
              type="tel"
              value={settings.profile.phone}
              onChange={(e) => handleSettingChange('profile', 'phone', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">אתר אינטרנט</label>
            <input
              type="url"
              value={settings.profile.website}
              onChange={(e) => handleSettingChange('profile', 'website', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">כתובת</label>
          <input
            type="text"
            value={settings.profile.address}
            onChange={(e) => handleSettingChange('profile', 'address', e.target.value)}
            className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
        
        <div className="mt-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">תיאור העסק</label>
          <textarea
            value={settings.profile.description}
            onChange={(e) => handleSettingChange('profile', 'description', e.target.value)}
            rows={4}
            className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>
    </div>
  );

  const NotificationSettings = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Bell className="w-6 h-6 text-yellow-600" />
          התראות וביטרצות
        </h3>
        
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center gap-3">
              <Bell className="w-5 h-5 text-blue-600" />
              <div>
                <span className="font-medium text-gray-900">התראות במייל</span>
                <p className="text-sm text-gray-600">קבל עדכונים על פעילות במייל</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications.emailNotifications}
                onChange={(e) => handleSettingChange('notifications', 'emailNotifications', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
            </label>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center gap-3">
              <Smartphone className="w-5 h-5 text-green-600" />
              <div>
                <span className="font-medium text-gray-900">הודעות SMS</span>
                <p className="text-sm text-gray-600">התראות טקסט על שיחות ולידים</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications.smsNotifications}
                onChange={(e) => handleSettingChange('notifications', 'smsNotifications', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-green-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-green-600"></div>
            </label>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center gap-3">
              <MessageSquare className="w-5 h-5 text-emerald-600" />
              <div>
                <span className="font-medium text-gray-900">התראות WhatsApp</span>
                <p className="text-sm text-gray-600">עדכונים על הודעות חדשות</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications.whatsappNotifications}
                onChange={(e) => handleSettingChange('notifications', 'whatsappNotifications', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-emerald-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center gap-3">
              <Volume2 className="w-5 h-5 text-purple-600" />
              <div>
                <span className="font-medium text-gray-900">צלילי התראה</span>
                <p className="text-sm text-gray-600">השמע צלילים לאירועים חשובים</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.notifications.soundEnabled}
                onChange={(e) => handleSettingChange('notifications', 'soundEnabled', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
            </label>
          </div>
        </div>
      </div>
    </div>
  );

  const SecuritySettings = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Shield className="w-6 h-6 text-red-600" />
          הגדרות אבטחה
        </h3>
        
        <div className="space-y-6">
          <div className="p-4 bg-red-50 rounded-xl border border-red-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Key className="w-5 h-5 text-red-600" />
                <div>
                  <span className="font-medium text-red-900">אימות דו-שלבי</span>
                  <p className="text-sm text-red-700">הגנה נוספת על החשבון שלך</p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.security.twoFactorEnabled}
                  onChange={(e) => handleSettingChange('security', 'twoFactorEnabled', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-red-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-red-600"></div>
              </label>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">תקופת תפוגת סיסמה (ימים)</label>
              <select
                value={settings.security.passwordExpiry}
                onChange={(e) => handleSettingChange('security', 'passwordExpiry', e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="30">30 ימים</option>
                <option value="60">60 ימים</option>
                <option value="90">90 ימים</option>
                <option value="365">שנה</option>
                <option value="never">ללא תפוגה</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">זמן קצוב לסשן (דקות)</label>
              <select
                value={settings.security.sessionTimeout}
                onChange={(e) => handleSettingChange('security', 'sessionTimeout', e.target.value)}
                className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-red-500"
              >
                <option value="15">15 דקות</option>
                <option value="30">30 דקות</option>
                <option value="60">שעה</option>
                <option value="120">שעתיים</option>
                <option value="480">8 שעות</option>
              </select>
            </div>
          </div>

          <div className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center gap-3">
              <AlertTriangle className="w-5 h-5 text-orange-600" />
              <div>
                <span className="font-medium text-gray-900">התראות התחברות</span>
                <p className="text-sm text-gray-600">קבל התראה על כניסות חשודות</p>
              </div>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={settings.security.loginAlerts}
                onChange={(e) => handleSettingChange('security', 'loginAlerts', e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-orange-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600"></div>
            </label>
          </div>
        </div>
      </div>
    </div>
  );

  const IntegrationSettings = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Cloud className="w-6 h-6 text-green-600" />
          אינטגרציות וחיבורים
        </h3>
        
        <div className="space-y-4">
          <div className="p-4 bg-green-50 rounded-xl border border-green-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <MessageSquare className="w-5 h-5 text-green-600" />
                <div>
                  <span className="font-medium text-green-900">WhatsApp Business</span>
                  <p className="text-sm text-green-700">מחובר ופעיל</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="text-sm text-green-600 font-medium">מחובר</span>
              </div>
            </div>
          </div>

          <div className="p-4 bg-blue-50 rounded-xl border border-blue-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Phone className="w-5 h-5 text-blue-600" />
                <div>
                  <span className="font-medium text-blue-900">Twilio (שיחות קוליות)</span>
                  <p className="text-sm text-blue-700">מחובר ופעיל</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-blue-600" />
                <span className="text-sm text-blue-600 font-medium">מחובר</span>
              </div>
            </div>
          </div>

          <div className="p-4 bg-purple-50 rounded-xl border border-purple-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Database className="w-5 h-5 text-purple-600" />
                <div>
                  <span className="font-medium text-purple-900">OpenAI GPT</span>
                  <p className="text-sm text-purple-700">בינה מלאכותית לתגובות</p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.integrations.openaiEnabled}
                  onChange={(e) => handleSettingChange('integrations', 'openaiEnabled', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-purple-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-purple-600"></div>
              </label>
            </div>
          </div>

          <div className="p-4 bg-orange-50 rounded-xl border border-orange-200">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Mic className="w-5 h-5 text-orange-600" />
                <div>
                  <span className="font-medium text-orange-900">Google TTS (דיבור)</span>
                  <p className="text-sm text-orange-700">המרת טקסט לקול בעברית</p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.integrations.googleTTSEnabled}
                  onChange={(e) => handleSettingChange('integrations', 'googleTTSEnabled', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-orange-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-orange-600"></div>
              </label>
            </div>
          </div>

          <div className="p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Camera className="w-5 h-5 text-gray-600" />
                <div>
                  <span className="font-medium text-gray-900">הקלטה אוטומטית</span>
                  <p className="text-sm text-gray-600">הקלט שיחות אוטומטית לתמלול</p>
                </div>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={settings.integrations.autoRecording}
                  onChange={(e) => handleSettingChange('integrations', 'autoRecording', e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-gray-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gray-600"></div>
              </label>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const DisplaySettings = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Monitor className="w-6 h-6 text-purple-600" />
          הגדרות תצוגה
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">ערכת נושא</label>
            <select
              value={settings.display.theme}
              onChange={(e) => handleSettingChange('display', 'theme', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="light">בהיר</option>
              <option value="dark">כהה</option>
              <option value="auto">אוטומטי</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">שפה</label>
            <select
              value={settings.display.language}
              onChange={(e) => handleSettingChange('display', 'language', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="he">עברית</option>
              <option value="en">English</option>
              <option value="ar">العربية</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">פורמט תאריך</label>
            <select
              value={settings.display.dateFormat}
              onChange={(e) => handleSettingChange('display', 'dateFormat', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="DD/MM/YYYY">DD/MM/YYYY</option>
              <option value="MM/DD/YYYY">MM/DD/YYYY</option>
              <option value="YYYY-MM-DD">YYYY-MM-DD</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">פורמט שעה</label>
            <select
              value={settings.display.timeFormat}
              onChange={(e) => handleSettingChange('display', 'timeFormat', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="24h">24 שעות</option>
              <option value="12h">12 שעות</option>
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">מטבע</label>
            <select
              value={settings.display.currency}
              onChange={(e) => handleSettingChange('display', 'currency', e.target.value)}
              className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
            >
              <option value="ILS">שקל (₪)</option>
              <option value="USD">דולר ($)</option>
              <option value="EUR">יורו (€)</option>
            </select>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'profile': return <ProfileSettings />;
      case 'notifications': return <NotificationSettings />;
      case 'security': return <SecuritySettings />;
      case 'integrations': return <IntegrationSettings />;
      case 'display': return <DisplaySettings />;
      default: return <ProfileSettings />;
    }
  };

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-gray-700 to-gray-900 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Settings className="w-10 h-10" />
                ⚙️ הגדרות מערכת
              </h1>
              <p className="text-gray-200 text-lg">
                התאמה אישית והגדרות מתקדמות של המערכת
              </p>
            </div>
            <div className="text-left">
              <button
                onClick={handleSave}
                disabled={saveStatus === 'saving'}
                className={`flex items-center gap-2 px-6 py-3 rounded-xl font-medium transition-all duration-200 ${
                  saveStatus === 'saving'
                    ? 'bg-gray-600 text-gray-300 cursor-not-allowed'
                    : saveStatus === 'saved'
                    ? 'bg-green-600 text-white'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {saveStatus === 'saving' ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    שומר...
                  </>
                ) : saveStatus === 'saved' ? (
                  <>
                    <CheckCircle className="w-5 h-5" />
                    נשמר!
                  </>
                ) : (
                  <>
                    <Save className="w-5 h-5" />
                    שמור
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Settings Interface */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-lg font-bold text-gray-900">קטגוריות</h2>
              </div>
              <nav className="p-2">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id)}
                      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-right transition-all duration-200 ${
                        activeTab === tab.id
                          ? 'bg-blue-50 text-blue-600 border-l-4 border-l-blue-600'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <Icon className={`w-5 h-5 ${
                        activeTab === tab.id ? 'text-blue-600' : tab.color
                      }`} />
                      <span className="font-medium">{tab.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>

          {/* Content */}
          <div className="lg:col-span-3">
            {renderTabContent()}
          </div>
        </div>
      </div>
    </ModernLayout>
  );
}