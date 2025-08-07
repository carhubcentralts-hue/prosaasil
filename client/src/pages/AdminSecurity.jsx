import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Shield, Lock, Key, Eye, EyeOff, AlertTriangle,
  CheckCircle, Users, Activity, Globe, Clock,
  Fingerprint, Smartphone, Mail, Bell, Ban,
  RefreshCw, Download, Upload, Terminal, Database,
  Server, Network, Zap, FileText, Search
} from 'lucide-react';

export default function AdminSecurity() {
  const [activeTab, setActiveTab] = useState('overview');
  const [securityData, setSecurityData] = useState({});
  const [alerts, setAlerts] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSecurityData();
  }, []);

  const loadSecurityData = async () => {
    try {
      // Demo security data
      const demoData = {
        overview: {
          threatLevel: 'low',
          activeUsers: 24,
          failedLogins: 3,
          blockedIPs: 12,
          lastScan: '2025-08-07 02:00'
        },
        permissions: {
          admins: 2,
          businesses: 22,
          suspended: 3
        },
        firewall: {
          status: 'active',
          rules: 156,
          blocked: 1247,
          allowed: 98567
        }
      };

      const demoAlerts = [
        {
          id: 1,
          type: 'warning',
          title: 'ניסיון התחברות חשוד',
          description: 'מספר ניסיונות כושלים מ-IP זהה',
          time: '14:25',
          ip: '192.168.1.100',
          action: 'חסום זמנית'
        },
        {
          id: 2,
          type: 'info',
          title: 'עדכון אבטחה הושלם',
          description: 'כל הרכיבים עודכנו לגרסה אחרונה',
          time: '02:00',
          ip: null,
          action: 'הושלם'
        },
        {
          id: 3,
          type: 'success',
          title: 'גיבוי אוטומטי בוצע',
          description: 'כל הנתונים גובו בהצלחה לענן',
          time: '01:30',
          ip: null,
          action: 'הושלם'
        }
      ];

      const demoAuditLogs = [
        {
          time: '14:30:15',
          user: 'admin',
          action: 'התחבר למערכת',
          ip: '192.168.1.50',
          success: true
        },
        {
          time: '14:25:42',
          user: 'business_user_1',
          action: 'עדכן הגדרות עסק',
          ip: '192.168.1.75',
          success: true
        },
        {
          time: '14:23:18',
          user: 'unknown',
          action: 'ניסיון התחברות כושל',
          ip: '192.168.1.100',
          success: false
        },
        {
          time: '14:20:05',
          user: 'business_user_2',
          action: 'צפה ברשימת לקוחות',
          ip: '192.168.1.80',
          success: true
        }
      ];

      setSecurityData(demoData);
      setAlerts(demoAlerts);
      setAuditLogs(demoAuditLogs);
      setLoading(false);
    } catch (error) {
      console.error('Error loading security data:', error);
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'overview', label: 'סקירה כללית', icon: Shield },
    { id: 'users', label: 'ניהול משתמשים', icon: Users },
    { id: 'firewall', label: 'חומת אש', icon: Globe },
    { id: 'audit', label: 'רישום פעילות', icon: FileText },
    { id: 'alerts', label: 'התראות אבטחה', icon: Bell },
    { id: 'backup', label: 'גיבוי ושחזור', icon: Database }
  ];

  const SecurityOverview = () => (
    <div className="space-y-6">
      {/* Threat Level */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Shield className="w-6 h-6 text-green-600" />
          רמת איום נוכחית
        </h3>
        
        <div className="flex items-center justify-center">
          <div className="relative">
            <div className="w-32 h-32 bg-green-100 rounded-full flex items-center justify-center">
              <div className="w-24 h-24 bg-green-500 rounded-full flex items-center justify-center">
                <Shield className="w-12 h-12 text-white" />
              </div>
            </div>
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center mt-20">
                <div className="text-2xl font-bold text-green-600">נמוכה</div>
                <div className="text-sm text-gray-600">המערכת מאובטחת</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Security Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-blue-50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-blue-700 font-medium">משתמשים פעילים</span>
            <Users className="w-5 h-5 text-blue-600" />
          </div>
          <div className="text-2xl font-bold text-blue-900">{securityData.overview?.activeUsers}</div>
        </div>

        <div className="bg-red-50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-red-700 font-medium">התחברויות כושלות</span>
            <Ban className="w-5 h-5 text-red-600" />
          </div>
          <div className="text-2xl font-bold text-red-900">{securityData.overview?.failedLogins}</div>
        </div>

        <div className="bg-orange-50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-orange-700 font-medium">IP כתובות חסומות</span>
            <Globe className="w-5 h-5 text-orange-600" />
          </div>
          <div className="text-2xl font-bold text-orange-900">{securityData.overview?.blockedIPs}</div>
        </div>

        <div className="bg-green-50 rounded-xl p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-green-700 font-medium">סריקה אחרונה</span>
            <Clock className="w-5 h-5 text-green-600" />
          </div>
          <div className="text-sm font-bold text-green-900">{securityData.overview?.lastScan}</div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6">פעולות מהירות</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="flex items-center gap-3 p-4 bg-red-50 rounded-xl hover:bg-red-100 transition-all">
            <RefreshCw className="w-5 h-5 text-red-600" />
            <span className="font-medium text-red-700">סריקת אבטחה מלאה</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-blue-50 rounded-xl hover:bg-blue-100 transition-all">
            <Key className="w-5 h-5 text-blue-600" />
            <span className="font-medium text-blue-700">חדש מפתחות API</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-green-50 rounded-xl hover:bg-green-100 transition-all">
            <Download className="w-5 h-5 text-green-600" />
            <span className="font-medium text-green-700">ייצא רישומי ביקורת</span>
          </button>
        </div>
      </div>
    </div>
  );

  const UsersTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Users className="w-6 h-6 text-blue-600" />
          ניהול הרשאות משתמשים
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center p-4 bg-blue-50 rounded-xl">
            <div className="text-3xl font-bold text-blue-600 mb-2">{securityData.permissions?.admins}</div>
            <div className="text-blue-700 font-medium">מנהלי מערכת</div>
            <div className="text-sm text-blue-600 mt-2">גישה מלאה</div>
          </div>
          
          <div className="text-center p-4 bg-green-50 rounded-xl">
            <div className="text-3xl font-bold text-green-600 mb-2">{securityData.permissions?.businesses}</div>
            <div className="text-green-700 font-medium">עסקים פעילים</div>
            <div className="text-sm text-green-600 mt-2">גישה מוגבלת</div>
          </div>
          
          <div className="text-center p-4 bg-red-50 rounded-xl">
            <div className="text-3xl font-bold text-red-600 mb-2">{securityData.permissions?.suspended}</div>
            <div className="text-red-700 font-medium">משתמשים מושעים</div>
            <div className="text-sm text-red-600 mt-2">גישה חסומה</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-lg font-bold text-gray-900 mb-4">פעולות משתמשים</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button className="flex items-center gap-3 p-4 bg-blue-50 rounded-xl hover:bg-blue-100 transition-all">
            <Users className="w-5 h-5 text-blue-600" />
            <span className="font-medium text-blue-700">הוסף מנהל חדש</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-green-50 rounded-xl hover:bg-green-100 transition-all">
            <Eye className="w-5 h-5 text-green-600" />
            <span className="font-medium text-green-700">צפה בפעילות משתמשים</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-orange-50 rounded-xl hover:bg-orange-100 transition-all">
            <Lock className="w-5 h-5 text-orange-600" />
            <span className="font-medium text-orange-700">עדכן הרשאות</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-red-50 rounded-xl hover:bg-red-100 transition-all">
            <Ban className="w-5 h-5 text-red-600" />
            <span className="font-medium text-red-700">השעה משתמש</span>
          </button>
        </div>
      </div>
    </div>
  );

  const FirewallTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Globe className="w-6 h-6 text-green-600" />
          סטטוס חומת אש
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-green-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-green-700 font-medium">סטטוס</span>
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div className="text-lg font-bold text-green-900">{securityData.firewall?.status === 'active' ? 'פעיל' : 'לא פעיל'}</div>
          </div>

          <div className="bg-blue-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-blue-700 font-medium">כללים</span>
              <FileText className="w-5 h-5 text-blue-600" />
            </div>
            <div className="text-lg font-bold text-blue-900">{securityData.firewall?.rules}</div>
          </div>

          <div className="bg-red-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-red-700 font-medium">חסומים</span>
              <Ban className="w-5 h-5 text-red-600" />
            </div>
            <div className="text-lg font-bold text-red-900">{securityData.firewall?.blocked?.toLocaleString()}</div>
          </div>

          <div className="bg-green-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-green-700 font-medium">מורשים</span>
              <CheckCircle className="w-5 h-5 text-green-600" />
            </div>
            <div className="text-lg font-bold text-green-900">{securityData.firewall?.allowed?.toLocaleString()}</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-lg font-bold text-gray-900 mb-4">ניהול חומת אש</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <button className="flex items-center gap-3 p-4 bg-blue-50 rounded-xl hover:bg-blue-100 transition-all">
            <FileText className="w-5 h-5 text-blue-600" />
            <span className="font-medium text-blue-700">עדכן כללים</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-red-50 rounded-xl hover:bg-red-100 transition-all">
            <Ban className="w-5 h-5 text-red-600" />
            <span className="font-medium text-red-700">חסום IP</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-green-50 rounded-xl hover:bg-green-100 transition-all">
            <CheckCircle className="w-5 h-5 text-green-600" />
            <span className="font-medium text-green-700">הוסף לרשימה לבנה</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-purple-50 rounded-xl hover:bg-purple-100 transition-all">
            <Activity className="w-5 h-5 text-purple-600" />
            <span className="font-medium text-purple-700">צפה בלוגי תעבורה</span>
          </button>
        </div>
      </div>
    </div>
  );

  const AuditTab = () => (
    <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
      <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <FileText className="w-6 h-6 text-purple-600" />
        רישומי ביקורת
      </h3>
      
      <div className="mb-4">
        <div className="relative">
          <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
          <input
            type="text"
            placeholder="חיפוש בלוגים..."
            className="w-full bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-3 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />
        </div>
      </div>
      
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {auditLogs.map((log, index) => (
          <div key={index} className={`p-4 rounded-lg border-l-4 ${
            log.success ? 'bg-green-50 border-green-500' : 'bg-red-50 border-red-500'
          }`}>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                <span className="font-medium text-gray-900">{log.user}</span>
                <span className={`text-xs px-2 py-1 rounded font-medium ${
                  log.success ? 'bg-green-200 text-green-800' : 'bg-red-200 text-red-800'
                }`}>
                  {log.success ? 'הצליח' : 'נכשל'}
                </span>
              </div>
              <span className="text-sm text-gray-600">{log.time}</span>
            </div>
            <p className="text-sm text-gray-700 mb-1">{log.action}</p>
            <p className="text-xs text-gray-500">IP: {log.ip}</p>
          </div>
        ))}
      </div>
    </div>
  );

  const AlertsTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Bell className="w-6 h-6 text-orange-600" />
          התראות אבטחה פעילות
        </h3>
        
        <div className="space-y-4">
          {alerts.map((alert) => (
            <div key={alert.id} className={`p-4 rounded-xl border-l-4 ${
              alert.type === 'warning' ? 'bg-yellow-50 border-yellow-500' :
              alert.type === 'info' ? 'bg-blue-50 border-blue-500' :
              'bg-green-50 border-green-500'
            }`}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-2">
                    {alert.type === 'warning' ? <AlertTriangle className="w-5 h-5 text-yellow-600" /> :
                     alert.type === 'info' ? <Bell className="w-5 h-5 text-blue-600" /> :
                     <CheckCircle className="w-5 h-5 text-green-600" />}
                    <h4 className="font-semibold text-gray-900">{alert.title}</h4>
                  </div>
                  <p className="text-sm text-gray-700 mb-2">{alert.description}</p>
                  {alert.ip && (
                    <p className="text-xs text-gray-500">IP: {alert.ip}</p>
                  )}
                </div>
                <div className="text-left">
                  <div className="text-sm text-gray-600">{alert.time}</div>
                  <div className={`text-xs font-medium ${
                    alert.type === 'warning' ? 'text-yellow-700' :
                    alert.type === 'info' ? 'text-blue-700' :
                    'text-green-700'
                  }`}>
                    {alert.action}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );

  const BackupTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Database className="w-6 h-6 text-blue-600" />
          גיבוי ושחזור
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="p-4 bg-green-50 rounded-xl">
              <div className="flex items-center gap-3 mb-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">גיבוי אוטומטי פעיל</span>
              </div>
              <p className="text-sm text-green-700">גיבוי יומי בשעה 02:00</p>
            </div>
            
            <div className="p-4 bg-blue-50 rounded-xl">
              <div className="flex items-center gap-3 mb-2">
                <Clock className="w-5 h-5 text-blue-600" />
                <span className="font-semibold text-blue-800">גיבוי אחרון</span>
              </div>
              <p className="text-sm text-blue-700">{securityData.overview?.lastScan}</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <button className="w-full flex items-center justify-center gap-2 p-4 bg-blue-50 text-blue-700 rounded-xl hover:bg-blue-100 transition-all">
              <Download className="w-5 h-5" />
              גבה עכשיו
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-4 bg-green-50 text-green-700 rounded-xl hover:bg-green-100 transition-all">
              <Upload className="w-5 h-5" />
              שחזר מגיבוי
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-4 bg-purple-50 text-purple-700 rounded-xl hover:bg-purple-100 transition-all">
              <FileText className="w-5 h-5" />
              היסטוריית גיבויים
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <SecurityOverview />;
      case 'users': return <UsersTab />;
      case 'firewall': return <FirewallTab />;
      case 'audit': return <AuditTab />;
      case 'alerts': return <AlertsTab />;
      case 'backup': return <BackupTab />;
      default: return <SecurityOverview />;
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole="admin">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-red-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען נתוני אבטחה...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole="admin">
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-red-600 to-red-800 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Shield className="w-10 h-10" />
                🛡️ אבטחת מערכת
              </h1>
              <p className="text-red-100 text-lg">
                ניטור והגנה על המערכת מפני איומי אבטחה
              </p>
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2 bg-green-500/20 px-4 py-2 rounded-xl">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-green-300 font-medium">מאובטח</span>
              </div>
            </div>
          </div>
        </div>

        {/* Tabs and Content */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
              <div className="p-6 border-b border-gray-200">
                <h2 className="text-lg font-bold text-gray-900">אבטחה ובקרה</h2>
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
                          ? 'bg-red-50 text-red-600 border-l-4 border-l-red-600'
                          : 'text-gray-700 hover:bg-gray-50'
                      }`}
                    >
                      <Icon className={`w-5 h-5 ${
                        activeTab === tab.id ? 'text-red-600' : 'text-gray-500'
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