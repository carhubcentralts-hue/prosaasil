import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  Settings, Database, Server, Shield, Globe, 
  Activity, Monitor, HardDrive, Cpu, Memory,
  Network, Clock, AlertTriangle, CheckCircle,
  RefreshCw, Power, Download, Upload, Terminal,
  Key, Lock, Users, FileText, Bell, Mail,
  Phone, MessageSquare, Mic, Volume2, Cloud
} from 'lucide-react';

export default function AdminSystem() {
  const [activeTab, setActiveTab] = useState('overview');
  const [systemStatus, setSystemStatus] = useState({});
  const [services, setServices] = useState([]);
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSystemData();
  }, []);

  const loadSystemData = async () => {
    try {
      // Demo system data
      const demoStatus = {
        server: {
          uptime: '15 ימים, 8 שעות',
          cpu: 23,
          memory: 67,
          disk: 34,
          network: 'פעיל'
        },
        database: {
          status: 'פעיל',
          connections: 45,
          size: '2.4 GB',
          lastBackup: '2025-08-07 02:00'
        },
        integrations: {
          openai: true,
          twilio: true,
          google_tts: true,
          whatsapp: true
        }
      };

      const demoServices = [
        { name: 'Flask API Server', status: 'פעיל', port: 5000, uptime: '15d 8h' },
        { name: 'PostgreSQL Database', status: 'פעיל', port: 5432, uptime: '15d 8h' },
        { name: 'Redis Cache', status: 'פעיל', port: 6379, uptime: '15d 8h' },
        { name: 'WhatsApp Client', status: 'פעיל', port: 8080, uptime: '12h 30m' },
        { name: 'Background Tasks', status: 'פעיל', port: null, uptime: '15d 8h' }
      ];

      const demoLogs = [
        { time: '14:30:25', level: 'INFO', service: 'API', message: 'User authenticated successfully' },
        { time: '14:29:18', level: 'SUCCESS', service: 'WhatsApp', message: 'Message sent successfully to 050-1234567' },
        { time: '14:28:45', level: 'INFO', service: 'TTS', message: 'Generated Hebrew audio response' },
        { time: '14:27:32', level: 'WARNING', service: 'Database', message: 'Connection pool reaching 80% capacity' },
        { time: '14:26:01', level: 'INFO', service: 'Twilio', message: 'Incoming call processed successfully' }
      ];

      setSystemStatus(demoStatus);
      setServices(demoServices);
      setLogs(demoLogs);
      setLoading(false);
    } catch (error) {
      console.error('Error loading system data:', error);
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'overview', label: 'סקירה כללית', icon: Monitor },
    { id: 'services', label: 'שירותים', icon: Server },
    { id: 'database', label: 'מסד נתונים', icon: Database },
    { id: 'integrations', label: 'אינטגרציות', icon: Cloud },
    { id: 'logs', label: 'לוגים', icon: FileText },
    { id: 'security', label: 'אבטחה', icon: Shield }
  ];

  const SystemOverview = () => (
    <div className="space-y-6">
      {/* Server Status */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Monitor className="w-6 h-6 text-blue-600" />
          סטטוס שרת
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="bg-blue-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-blue-700 font-medium">זמן פעילות</span>
              <Clock className="w-5 h-5 text-blue-600" />
            </div>
            <div className="text-2xl font-bold text-blue-900">{systemStatus.server?.uptime}</div>
          </div>

          <div className="bg-green-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-green-700 font-medium">מעבד (CPU)</span>
              <Cpu className="w-5 h-5 text-green-600" />
            </div>
            <div className="text-2xl font-bold text-green-900">{systemStatus.server?.cpu}%</div>
            <div className="w-full bg-green-200 rounded-full h-2 mt-2">
              <div className="bg-green-600 h-2 rounded-full" style={{width: `${systemStatus.server?.cpu}%`}}></div>
            </div>
          </div>

          <div className="bg-purple-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-purple-700 font-medium">זיכרון (RAM)</span>
              <Memory className="w-5 h-5 text-purple-600" />
            </div>
            <div className="text-2xl font-bold text-purple-900">{systemStatus.server?.memory}%</div>
            <div className="w-full bg-purple-200 rounded-full h-2 mt-2">
              <div className="bg-purple-600 h-2 rounded-full" style={{width: `${systemStatus.server?.memory}%`}}></div>
            </div>
          </div>

          <div className="bg-orange-50 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-orange-700 font-medium">דיסק</span>
              <HardDrive className="w-5 h-5 text-orange-600" />
            </div>
            <div className="text-2xl font-bold text-orange-900">{systemStatus.server?.disk}%</div>
            <div className="w-full bg-orange-200 rounded-full h-2 mt-2">
              <div className="bg-orange-600 h-2 rounded-full" style={{width: `${systemStatus.server?.disk}%`}}></div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Settings className="w-6 h-6 text-purple-600" />
          פעולות מהירות
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="flex items-center gap-3 p-4 bg-blue-50 rounded-xl hover:bg-blue-100 transition-all">
            <RefreshCw className="w-5 h-5 text-blue-600" />
            <span className="font-medium text-blue-700">אתחל שירותים</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-green-50 rounded-xl hover:bg-green-100 transition-all">
            <Download className="w-5 h-5 text-green-600" />
            <span className="font-medium text-green-700">גבה מסד נתונים</span>
          </button>
          
          <button className="flex items-center gap-3 p-4 bg-orange-50 rounded-xl hover:bg-orange-100 transition-all">
            <Terminal className="w-5 h-5 text-orange-600" />
            <span className="font-medium text-orange-700">פתח Terminal</span>
          </button>
        </div>
      </div>
    </div>
  );

  const ServicesTab = () => (
    <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
      <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <Server className="w-6 h-6 text-green-600" />
        שירותי מערכת
      </h3>
      
      <div className="space-y-4">
        {services.map((service, index) => (
          <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
            <div className="flex items-center gap-4">
              <div className={`w-3 h-3 rounded-full ${
                service.status === 'פעיל' ? 'bg-green-500 animate-pulse' : 'bg-red-500'
              }`}></div>
              <div>
                <h4 className="font-semibold text-gray-900">{service.name}</h4>
                <p className="text-sm text-gray-600">
                  {service.port ? `Port: ${service.port}` : 'Background Service'}
                </p>
              </div>
            </div>
            <div className="text-left">
              <div className={`font-medium ${
                service.status === 'פעיל' ? 'text-green-600' : 'text-red-600'
              }`}>
                {service.status}
              </div>
              <div className="text-sm text-gray-500">{service.uptime}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const DatabaseTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Database className="w-6 h-6 text-blue-600" />
          סטטוס מסד נתונים
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-600">סטטוס</span>
              <span className="font-bold text-green-600 flex items-center gap-2">
                <CheckCircle className="w-4 h-4" />
                {systemStatus.database?.status}
              </span>
            </div>
            
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-600">חיבורים פעילים</span>
              <span className="font-bold text-blue-600">{systemStatus.database?.connections}</span>
            </div>
            
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-600">גודל מסד נתונים</span>
              <span className="font-bold text-purple-600">{systemStatus.database?.size}</span>
            </div>
            
            <div className="flex justify-between items-center p-3 bg-gray-50 rounded-lg">
              <span className="text-gray-600">גיבוי אחרון</span>
              <span className="font-bold text-orange-600">{systemStatus.database?.lastBackup}</span>
            </div>
          </div>
          
          <div className="space-y-4">
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-all">
              <Download className="w-4 h-4" />
              גבה עכשיו
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-all">
              <Upload className="w-4 h-4" />
              שחזר גיבוי
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-all">
              <RefreshCw className="w-4 h-4" />
              אתחל חיבורים
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 transition-all">
              <Activity className="w-4 h-4" />
              צפה בשאילתות
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const IntegrationsTab = () => (
    <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
      <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <Cloud className="w-6 h-6 text-purple-600" />
        אינטגרציות חיצוניות
      </h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className={`p-4 rounded-xl border-2 ${
          systemStatus.integrations?.openai ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Database className="w-6 h-6 text-purple-600" />
              <span className="font-semibold text-gray-900">OpenAI GPT</span>
            </div>
            <div className={`w-3 h-3 rounded-full ${
              systemStatus.integrations?.openai ? 'bg-green-500' : 'bg-red-500'
            }`}></div>
          </div>
          <p className="text-sm text-gray-600 mb-3">בינה מלאכותית לתגובות אוטומטיות</p>
          <div className={`text-sm font-medium ${
            systemStatus.integrations?.openai ? 'text-green-600' : 'text-red-600'
          }`}>
            {systemStatus.integrations?.openai ? 'מחובר ופעיל' : 'לא מחובר'}
          </div>
        </div>

        <div className={`p-4 rounded-xl border-2 ${
          systemStatus.integrations?.twilio ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Phone className="w-6 h-6 text-blue-600" />
              <span className="font-semibold text-gray-900">Twilio</span>
            </div>
            <div className={`w-3 h-3 rounded-full ${
              systemStatus.integrations?.twilio ? 'bg-green-500' : 'bg-red-500'
            }`}></div>
          </div>
          <p className="text-sm text-gray-600 mb-3">שירותי שיחות קוליות ו-SMS</p>
          <div className={`text-sm font-medium ${
            systemStatus.integrations?.twilio ? 'text-green-600' : 'text-red-600'
          }`}>
            {systemStatus.integrations?.twilio ? 'מחובר ופעיל' : 'לא מחובר'}
          </div>
        </div>

        <div className={`p-4 rounded-xl border-2 ${
          systemStatus.integrations?.google_tts ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <Volume2 className="w-6 h-6 text-orange-600" />
              <span className="font-semibold text-gray-900">Google TTS</span>
            </div>
            <div className={`w-3 h-3 rounded-full ${
              systemStatus.integrations?.google_tts ? 'bg-green-500' : 'bg-red-500'
            }`}></div>
          </div>
          <p className="text-sm text-gray-600 mb-3">המרת טקסט לקול בעברית</p>
          <div className={`text-sm font-medium ${
            systemStatus.integrations?.google_tts ? 'text-green-600' : 'text-red-600'
          }`}>
            {systemStatus.integrations?.google_tts ? 'מחובר ופעיל' : 'לא מחובר'}
          </div>
        </div>

        <div className={`p-4 rounded-xl border-2 ${
          systemStatus.integrations?.whatsapp ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'
        }`}>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-3">
              <MessageSquare className="w-6 h-6 text-green-600" />
              <span className="font-semibold text-gray-900">WhatsApp</span>
            </div>
            <div className={`w-3 h-3 rounded-full ${
              systemStatus.integrations?.whatsapp ? 'bg-green-500' : 'bg-red-500'
            }`}></div>
          </div>
          <p className="text-sm text-gray-600 mb-3">הודעות עסקיות WhatsApp</p>
          <div className={`text-sm font-medium ${
            systemStatus.integrations?.whatsapp ? 'text-green-600' : 'text-red-600'
          }`}>
            {systemStatus.integrations?.whatsapp ? 'מחובר ופעיל' : 'לא מחובר'}
          </div>
        </div>
      </div>
    </div>
  );

  const LogsTab = () => (
    <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
      <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
        <FileText className="w-6 h-6 text-gray-600" />
        לוגי מערכת
      </h3>
      
      <div className="space-y-3 max-h-96 overflow-y-auto">
        {logs.map((log, index) => (
          <div key={index} className={`p-3 rounded-lg border-l-4 ${
            log.level === 'SUCCESS' ? 'bg-green-50 border-green-500' :
            log.level === 'WARNING' ? 'bg-yellow-50 border-yellow-500' :
            log.level === 'ERROR' ? 'bg-red-50 border-red-500' :
            'bg-blue-50 border-blue-500'
          }`}>
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2">
                <span className={`text-xs px-2 py-1 rounded font-medium ${
                  log.level === 'SUCCESS' ? 'bg-green-200 text-green-800' :
                  log.level === 'WARNING' ? 'bg-yellow-200 text-yellow-800' :
                  log.level === 'ERROR' ? 'bg-red-200 text-red-800' :
                  'bg-blue-200 text-blue-800'
                }`}>
                  {log.level}
                </span>
                <span className="text-sm font-medium text-gray-700">{log.service}</span>
              </div>
              <span className="text-xs text-gray-500">{log.time}</span>
            </div>
            <p className="text-sm text-gray-600">{log.message}</p>
          </div>
        ))}
      </div>
    </div>
  );

  const SecurityTab = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
        <h3 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
          <Shield className="w-6 h-6 text-red-600" />
          הגדרות אבטחה
        </h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-4">
            <div className="p-4 bg-green-50 rounded-xl border border-green-200">
              <div className="flex items-center gap-3 mb-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">SSL/TLS פעיל</span>
              </div>
              <p className="text-sm text-green-700">תעבורה מוצפנת בין הלקוח לשרת</p>
            </div>
            
            <div className="p-4 bg-green-50 rounded-xl border border-green-200">
              <div className="flex items-center gap-3 mb-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">חומת אש פעילה</span>
              </div>
              <p className="text-sm text-green-700">הגנה מפני התקפות חיצוניות</p>
            </div>
            
            <div className="p-4 bg-green-50 rounded-xl border border-green-200">
              <div className="flex items-center gap-3 mb-2">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">גיבויים אוטומטיים</span>
              </div>
              <p className="text-sm text-green-700">גיבוי יומי של כל הנתונים</p>
            </div>
          </div>
          
          <div className="space-y-4">
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-all">
              <Key className="w-4 h-4" />
              חדש מפתחות API
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-all">
              <Shield className="w-4 h-4" />
              עדכן חומת אש
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-purple-50 text-purple-700 rounded-lg hover:bg-purple-100 transition-all">
              <Lock className="w-4 h-4" />
              ביקורת אבטחה
            </button>
            
            <button className="w-full flex items-center justify-center gap-2 p-3 bg-orange-50 text-orange-700 rounded-lg hover:bg-orange-100 transition-all">
              <Users className="w-4 h-4" />
              ניהול הרשאות
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'overview': return <SystemOverview />;
      case 'services': return <ServicesTab />;
      case 'database': return <DatabaseTab />;
      case 'integrations': return <IntegrationsTab />;
      case 'logs': return <LogsTab />;
      case 'security': return <SecurityTab />;
      default: return <SystemOverview />;
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole="admin">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען נתוני מערכת...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  return (
    <ModernLayout userRole="admin">
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-gray-800 to-black rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <Settings className="w-10 h-10" />
                ⚙️ הגדרות מערכת
              </h1>
              <p className="text-gray-200 text-lg">
                ניהול ובקרה מתקדמת של כל רכיבי המערכת
              </p>
            </div>
            <div className="text-left">
              <div className="flex items-center gap-2 bg-green-500/20 px-4 py-2 rounded-xl">
                <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                <span className="text-green-300 font-medium">המערכת פעילה</span>
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
                <h2 className="text-lg font-bold text-gray-900">קטגוריות מערכת</h2>
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
                        activeTab === tab.id ? 'text-blue-600' : 'text-gray-500'
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