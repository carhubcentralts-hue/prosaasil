import React, { useState, useEffect } from 'react';
import { useLocation } from 'wouter';
import { 
  Menu, X, Home, Users, Phone, MessageSquare, Settings, 
  BarChart3, LogOut, Bell, Search, UserCheck, Building2,
  Shield, Star, TrendingUp, Calendar, Mail, FileText,
  Zap, Globe, Activity, Database, Lock, Smartphone, Briefcase
} from 'lucide-react';

export default function ModernLayout({ children, userRole = 'business' }) {
  const [location] = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [notifications, setNotifications] = useState(3);
  const [systemStatus, setSystemStatus] = useState('active');

  // Admin vs Business menu items
  const adminMenuItems = [
    { 
      path: '/admin/dashboard', 
      label: 'דשבורד ראשי', 
      icon: Home, 
      color: 'text-blue-600',
      badge: null
    },
    { 
      path: '/admin/crm/advanced', 
      label: 'CRM כללי', 
      icon: Users, 
      color: 'text-purple-600',
      badge: 'חדש'
    },
    { 
      path: '/admin/calls', 
      label: 'שיחות קוליות', 
      icon: Phone, 
      color: 'text-blue-600',
      badge: null
    },
    { 
      path: '/admin/whatsapp', 
      label: 'WhatsApp עסקי', 
      icon: MessageSquare, 
      color: 'text-green-600',
      badge: null
    },
    { 
      path: '/admin/businesses', 
      label: 'ניהול עסקים', 
      icon: Building2, 
      color: 'text-emerald-600',
      badge: null
    },
    { 
      path: '/admin/system', 
      label: 'הגדרות מערכת', 
      icon: Settings, 
      color: 'text-gray-600',
      badge: null
    },
    { 
      path: '/admin/analytics', 
      label: 'אנליטיקה מתקדמת', 
      icon: BarChart3, 
      color: 'text-orange-600',
      badge: null
    },
    { 
      path: '/admin/security', 
      label: 'אבטחה', 
      icon: Shield, 
      color: 'text-red-600',
      badge: null
    }
  ];

  const businessMenuItems = [
    { 
      path: '/', 
      label: 'דשבורד עסקי', 
      icon: Home, 
      color: 'text-blue-600',
      badge: null
    },
    { 
      path: '/crm', 
      label: 'ניהול לקוחות', 
      icon: Users, 
      color: 'text-purple-600',
      badge: notifications > 0 ? notifications.toString() : null
    },
    { 
      path: '/advanced-crm', 
      label: '🚀 CRM מתקדם', 
      icon: Briefcase, 
      color: 'text-indigo-600',
      badge: 'חדש'
    },
    { 
      path: '/calls', 
      label: 'מערכת שיחות', 
      icon: Phone, 
      color: 'text-green-600',
      badge: null
    },
    { 
      path: '/whatsapp', 
      label: 'WhatsApp עסקי', 
      icon: MessageSquare, 
      color: 'text-emerald-600',
      badge: null
    },
    { 
      path: '/analytics', 
      label: 'דוחות ואנליטיקה', 
      icon: BarChart3, 
      color: 'text-orange-600',
      badge: null
    },
    { 
      path: '/settings', 
      label: 'הגדרות', 
      icon: Settings, 
      color: 'text-gray-600',
      badge: null
    }
  ];

  const menuItems = userRole === 'admin' ? adminMenuItems : businessMenuItems;

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('user_role');
    localStorage.removeItem('userRole');
    window.location.href = '/login';
  };

  const getUserInfo = () => {
    try {
      const token = localStorage.getItem('authToken');
      if (token) {
        const parts = token.split('.');
        if (parts.length === 3) {
          const base64Url = parts[1];
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const decoded = JSON.parse(atob(base64));
          return {
            name: decoded.name || 'משתמש',
            email: decoded.email || 'user@system.com',
            role: decoded.role || 'user',
            business_id: decoded.business_id
          };
        }
      }
    } catch (error) {
      console.error('Error decoding token:', error);
    }
    return { 
      name: userRole === 'admin' ? 'מנהל מערכת' : 'משתמש עסקי', 
      email: 'user@system.com',
      role: userRole,
      business_id: 1
    };
  };

  const userInfo = getUserInfo();

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 font-['Assistant']" dir="rtl">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setSidebarOpen(false)}
        ></div>
      )}
      
      {/* Sidebar */}
      <div className={`fixed right-0 top-0 h-full bg-white/95 backdrop-blur-xl border-l border-gray-200/50 shadow-2xl z-50 transition-all duration-300 ease-in-out ${
        sidebarOpen ? 'w-80 md:w-80' : 'w-20 md:w-20'
      } ${sidebarOpen ? 'max-sm:w-full max-sm:right-0' : 'max-sm:w-16'}`}>
        
        {/* Header */}
        <div className="p-6 border-b border-gray-100">
          <div className="flex items-center justify-between">
            <div className={`transition-all duration-300 ${sidebarOpen ? 'opacity-100' : 'opacity-0'}`}>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                {userRole === 'admin' ? '🏢 מנהל מערכת' : '💼 CRM עסקי'}
              </h1>
              <p className="text-sm text-gray-500 mt-1">
                {userRole === 'admin' ? 'ניהול כלל המערכת' : `עסק #${userInfo.business_id}`}
              </p>
            </div>
            <button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              className="p-3 rounded-xl bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg hover:shadow-xl transition-all duration-200 hover:scale-105 flex-shrink-0"
            >
              {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
          
          {/* User Info */}
          {sidebarOpen && (
            <div className="mt-6 p-4 bg-gradient-to-r from-blue-50 to-purple-50 rounded-2xl border border-blue-100">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center text-white font-bold text-lg">
                  {userInfo.name?.charAt(0) || 'U'}
                </div>
                <div className="flex-1">
                  <div className="font-semibold text-gray-900">{userInfo.name}</div>
                  <div className="text-sm text-gray-600">{userInfo.email}</div>
                  <div className="flex items-center gap-2 mt-1">
                    <div className={`w-2 h-2 rounded-full ${systemStatus === 'active' ? 'bg-green-500' : 'bg-red-500'} animate-pulse`}></div>
                    <span className="text-xs text-gray-500">
                      {systemStatus === 'active' ? 'מחובר' : 'לא מחובר'}
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {menuItems.map((item) => {
            const Icon = item.icon;
            const isActive = location === item.path;
            
            return (
              <button
                key={item.path}
                onClick={() => window.location.href = item.path}
                className={`w-full group flex items-center gap-4 px-4 py-4 rounded-xl transition-all duration-200 ${
                  isActive 
                    ? 'bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg shadow-blue-200/50 scale-[1.02]' 
                    : 'text-gray-700 hover:bg-gradient-to-r hover:from-gray-50 hover:to-blue-50 hover:text-blue-600 hover:shadow-md'
                }`}
              >
                <Icon className={`w-6 h-6 transition-all duration-200 ${
                  isActive 
                    ? 'text-white' 
                    : `${item.color} group-hover:scale-110`
                }`} />
                {sidebarOpen && (
                  <div className="flex-1 flex items-center justify-between">
                    <span className={`font-medium transition-all duration-200 ${
                      isActive ? 'text-white' : 'group-hover:font-semibold'
                    }`}>
                      {item.label}
                    </span>
                    {item.badge && (
                      <span className={`px-2 py-1 text-xs rounded-full font-bold ${
                        isActive 
                          ? 'bg-white/20 text-white' 
                          : 'bg-red-500 text-white'
                      }`}>
                        {item.badge}
                      </span>
                    )}
                  </div>
                )}
                {isActive && sidebarOpen && (
                  <div className="w-2 h-2 bg-white rounded-full animate-pulse"></div>
                )}
              </button>
            );
          })}
        </nav>

        {/* Quick Stats */}
        {sidebarOpen && (
          <div className="p-4">
            <div className="bg-gradient-to-r from-green-50 to-emerald-50 rounded-xl p-4 border border-green-100">
              <div className="flex items-center gap-3 mb-3">
                <Activity className="w-5 h-5 text-green-600" />
                <span className="font-semibold text-green-800">סטטוס מערכת</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {userRole === 'admin' ? '24' : '12'}
                  </div>
                  <div className="text-xs text-green-700">
                    {userRole === 'admin' ? 'עסקים פעילים' : 'לקוחות פעילים'}
                  </div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">
                    {userRole === 'admin' ? '156' : '8'}
                  </div>
                  <div className="text-xs text-green-700">
                    {userRole === 'admin' ? 'שיחות היום' : 'שיחות היום'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="w-full group flex items-center gap-3 px-4 py-3 text-red-600 hover:bg-red-50 rounded-xl transition-all duration-200 hover:shadow-md"
          >
            <LogOut className="w-5 h-5 group-hover:scale-110 transition-transform" />
            {sidebarOpen && <span className="font-medium group-hover:font-semibold">התנתק</span>}
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className={`transition-all duration-300 ${sidebarOpen ? 'mr-80 md:mr-80' : 'mr-20 md:mr-20'} ${sidebarOpen ? 'max-sm:mr-0 max-sm:opacity-30' : 'max-sm:mr-16'}`}>
        {/* Top Bar */}
        <div className="bg-white/80 backdrop-blur-xl border-b border-gray-200/50 p-4 sticky top-0 z-40">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Search className="w-5 h-5 text-gray-400 absolute right-3 top-1/2 transform -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="חיפוש..."
                  className="bg-gray-50 border border-gray-200 rounded-xl pr-10 pl-4 py-2 w-80 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>
            
            <div className="flex items-center gap-4">
              {/* Notifications */}
              <button className="relative p-2 text-gray-600 hover:bg-gray-100 rounded-xl transition-all">
                <Bell className="w-5 h-5" />
                {notifications > 0 && (
                  <span className="absolute -top-1 -left-1 bg-red-500 text-white text-xs rounded-full w-5 h-5 flex items-center justify-center">
                    {notifications}
                  </span>
                )}
              </button>
              
              {/* Status Indicator */}
              <div className="flex items-center gap-2 px-3 py-2 bg-green-50 rounded-xl border border-green-200">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-green-700">פעיל</span>
              </div>
            </div>
          </div>
        </div>

        {/* Page Content */}
        <div className="p-6">
          {children}
        </div>
      </div>
    </div>
  );
}