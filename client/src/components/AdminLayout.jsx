import React, { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  Phone, 
  MessageSquare, 
  BarChart3, 
  Settings, 
  LogOut,
  Menu,
  X,
  Shield,
  Building2
} from 'lucide-react';
import axios from 'axios';

const AdminLayout = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [userInfo, setUserInfo] = useState({ name: 'מנהל', role: 'admin' });
  const [systemStats, setSystemStats] = useState(null);

  const menuItems = [
    {
      icon: LayoutDashboard,
      label: 'דשבורד ראשי',
      path: '/admin/dashboard',
      color: 'text-blue-600'
    },
    {
      icon: Users,
      label: 'CRM מתקדם',
      path: '/admin/crm/advanced',
      color: 'text-purple-600'
    },
    {
      icon: Phone,
      label: 'מערכת שיחות',
      path: '/admin/phone-analysis',
      color: 'text-green-600'
    },
    {
      icon: MessageSquare,
      label: 'WhatsApp עסקי',
      path: '/admin/whatsapp',
      color: 'text-emerald-600'
    },
    {
      icon: BarChart3,
      label: 'ניתוח שיחות',
      path: '/admin/call-analysis',
      color: 'text-orange-600'
    }
  ];

  useEffect(() => {
    loadUserInfo();
    loadSystemStats();
  }, []);

  const loadUserInfo = () => {
    const userName = localStorage.getItem('user_name') || 'מנהל';
    const userRole = localStorage.getItem('user_role') || 'admin';
    setUserInfo({ name: userName, role: userRole });
  };

  const loadSystemStats = async () => {
    try {
      const response = await axios.get('/api/admin/summary');
      setSystemStats(response.data);
    } catch (error) {
      console.error('Error loading system stats:', error);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    localStorage.removeItem('user_name');
    localStorage.removeItem('business_id');
    localStorage.removeItem('admin_takeover_mode');
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100" dir="rtl" style={{ fontFamily: 'Assistant, system-ui, sans-serif' }}>
      <div className="flex">
        {/* Sidebar */}
        <div className={`${sidebarOpen ? 'w-72' : 'w-20'} bg-white shadow-xl border-l border-gray-200 min-h-screen transition-all duration-300 flex flex-col`}>
          {/* Header */}
          <div className="p-6 border-b border-gray-200">
            <div className="flex items-center justify-between">
              {sidebarOpen && (
                <div>
                  <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                    🎯 AI Call Center CRM
                  </h1>
                  <div className="flex items-center gap-2 mt-1">
                    <Shield className="w-4 h-4 text-blue-600" />
                    <span className="text-sm text-blue-600 font-medium">{userInfo.name}</span>
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">מנהל מערכת</span>
                  </div>
                </div>
              )}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="p-2 rounded-xl bg-gray-100 hover:bg-gray-200 transition-colors"
              >
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
            
            {/* Quick Stats */}
            {sidebarOpen && systemStats && (
              <div className="mt-4 grid grid-cols-2 gap-2">
                <div className="bg-gradient-to-r from-blue-50 to-purple-50 p-3 rounded-lg">
                  <div className="text-xs text-gray-600">עסקים פעילים</div>
                  <div className="text-lg font-bold text-blue-600">{systemStats.businesses?.total || 0}</div>
                </div>
                <div className="bg-gradient-to-r from-green-50 to-emerald-50 p-3 rounded-lg">
                  <div className="text-xs text-gray-600">שיחות היום</div>
                  <div className="text-lg font-bold text-green-600">{systemStats.today?.calls || 0}</div>
                </div>
              </div>
            )}
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-4">
            <div className="space-y-1">
              {menuItems.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path;
                
                return (
                  <button
                    key={item.path}
                    onClick={() => navigate(item.path)}
                    className={`w-full group flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all duration-200 ${
                      isActive 
                        ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg shadow-blue-200/50 scale-[1.02]' 
                        : 'text-gray-700 hover:bg-gradient-to-r hover:from-gray-50 hover:to-gray-100 hover:text-gray-900 hover:shadow-sm'
                    }`}
                  >
                    <Icon className={`w-5 h-5 transition-transform duration-200 ${
                      isActive 
                        ? 'text-white' 
                        : `${item.color} group-hover:scale-110`
                    }`} />
                    {sidebarOpen && (
                      <span className={`font-medium transition-all duration-200 ${
                        isActive ? 'text-white' : 'group-hover:font-semibold'
                      }`}>
                        {item.label}
                      </span>
                    )}
                    {isActive && sidebarOpen && (
                      <div className="mr-auto">
                        <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
                      </div>
                    )}
                  </button>
                );
              })}
            </div>
            
            {/* Navigation Help */}
            {sidebarOpen && (
              <div className="mt-6 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-xl border border-blue-100">
                <div className="text-xs text-blue-600 font-medium mb-2">💡 ניווט מהיר</div>
                <div className="space-y-1 text-xs text-gray-600">
                  <div>• דשבורד - סקירה כללית</div>
                  <div>• CRM - ניהול לקוחות</div>
                  <div>• שיחות - ניתוח קולי</div>
                  <div>• WhatsApp - הודעות</div>
                </div>
              </div>
            )}
          </nav>

          {/* Footer */}
          <div className="p-4 border-t border-gray-200">
            {/* System Status */}
            {sidebarOpen && (
              <div className="mb-4 p-3 bg-green-50 rounded-lg border border-green-200">
                <div className="flex items-center gap-2">
                  <div className="w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
                  <span className="text-sm text-green-700 font-medium">מערכת פעילה</span>
                </div>
                <div className="text-xs text-green-600 mt-1">כל השירותים זמינים</div>
              </div>
            )}
            
            <button
              onClick={handleLogout}
              className="w-full group flex items-center gap-3 px-4 py-3 text-red-600 hover:bg-red-50 rounded-xl transition-all duration-200 hover:shadow-sm"
            >
              <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform" />
              {sidebarOpen && <span className="font-medium group-hover:font-semibold">התנתק</span>}
            </button>
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </div>
    </div>
  );
};

export default AdminLayout;