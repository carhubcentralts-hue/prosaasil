import React, { useState, useEffect } from 'react';
import { Routes, Route, Link, useLocation } from 'wouter';
import { 
  Phone, 
  MessageCircle, 
  Users, 
  Settings, 
  Home,
  Menu,
  X,
  Bell,
  Search,
  User
} from 'lucide-react';
import Dashboard from './pages/Dashboard';
import AdminDashboard from './pages/AdminDashboard';
import CallsPage from './pages/CallsPage';
import WhatsAppPage from './pages/WhatsAppPage';
import CRMPage from './pages/CRMPage';
import CustomerPage from './pages/CustomerPage';
import LoginPage from './pages/LoginPage';

function App() {
  const [user, setUser] = useState(null);
  const [business, setBusiness] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [permissions, setPermissions] = useState({});
  const [location] = useLocation();

  useEffect(() => {
    // טעינת נתוני משתמש ועסק
    fetchUserData();
  }, []);

  const fetchUserData = async () => {
    try {
      const response = await fetch('/api/user/current');
      if (response.ok) {
        const userData = await response.json();
        setUser(userData.user);
        setBusiness(userData.business);
        setPermissions(userData.permissions || {});
      }
    } catch (error) {
      console.error('Failed to fetch user data:', error);
    }
  };

  const handleLogout = async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
      setUser(null);
      setBusiness(null);
      setPermissions({});
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  if (!user) {
    return <LoginPage onLogin={fetchUserData} />;
  }

  const menuItems = [
    { 
      path: '/dashboard', 
      icon: Home, 
      label: 'דשבורד ראשי',
      show: true 
    },
    { 
      path: '/calls', 
      icon: Phone, 
      label: 'מוקד שיחות',
      show: permissions.calls_enabled 
    },
    { 
      path: '/whatsapp', 
      icon: MessageCircle, 
      label: 'וואטסאפ',
      show: permissions.whatsapp_enabled 
    },
    { 
      path: '/crm', 
      icon: Users, 
      label: 'ניהול לקוחות',
      show: permissions.crm_enabled 
    },
  ];

  // הוספת תפריט מנהל אם המשתמש הוא מנהל
  if (user.role === 'admin') {
    menuItems.push({
      path: '/admin/dashboard',
      icon: Settings,
      label: 'ניהול מערכת',
      show: true
    });
  }

  return (
    <div className="min-h-screen bg-gray-50 rtl" dir="rtl">
      {/* Sidebar */}
      <div className={`fixed inset-y-0 right-0 z-50 w-64 bg-white shadow-lg transform ${
        sidebarOpen ? 'translate-x-0' : 'translate-x-full'
      } transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0`}>
        
        {/* Sidebar Header */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-gray-200">
          <div className="flex items-center">
            <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center text-white font-bold">
              ח
            </div>
            <span className="mr-3 text-lg font-semibold text-gray-900">
              {business?.name || 'מערכת CRM'}
            </span>
          </div>
          <button
            onClick={() => setSidebarOpen(false)}
            className="p-2 rounded-md text-gray-400 hover:text-gray-600 lg:hidden"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="mt-5 px-2">
          {menuItems.filter(item => item.show).map((item) => {
            const Icon = item.icon;
            const isActive = location === item.path;
            
            return (
              <Link
                key={item.path}
                href={item.path}
                className={`group flex items-center px-2 py-3 text-sm font-medium rounded-md mb-1 ${
                  isActive
                    ? 'bg-blue-100 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}
                onClick={() => setSidebarOpen(false)}
              >
                <Icon className={`ml-3 w-5 h-5 ${
                  isActive ? 'text-blue-600' : 'text-gray-400 group-hover:text-gray-500'
                }`} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User Info */}
        <div className="absolute bottom-0 w-full p-4 border-t border-gray-200">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <User className="w-8 h-8 text-gray-400" />
            </div>
            <div className="mr-3">
              <p className="text-sm font-medium text-gray-700">{user.name}</p>
              <p className="text-xs text-gray-500">{user.email}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="mt-2 w-full bg-gray-100 hover:bg-gray-200 text-gray-700 py-2 px-3 rounded-md text-sm transition-colors"
          >
            התנתק
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="lg:pr-64">
        {/* Top Header */}
        <div className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="p-2 rounded-md text-gray-400 hover:text-gray-600 lg:hidden"
                >
                  <Menu className="w-6 h-6" />
                </button>
                
                {/* Search Bar */}
                <div className="hidden sm:block mr-4">
                  <div className="relative">
                    <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                      <Search className="h-5 w-5 text-gray-400" />
                    </div>
                    <input
                      type="text"
                      placeholder="חיפוש..."
                      className="block w-full pr-10 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-4 space-x-reverse">
                {/* Notifications */}
                <button className="p-2 text-gray-400 hover:text-gray-600 relative">
                  <Bell className="w-6 h-6" />
                  <span className="absolute top-0 left-0 block h-2 w-2 rounded-full bg-red-400 ring-2 ring-white"></span>
                </button>

                {/* Business Status */}
                <div className="hidden md:block">
                  <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                    פעיל
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Page Content */}
        <main className="py-6">
          <Routes>
            <Route path="/dashboard" component={() => 
              <Dashboard business={business} permissions={permissions} />
            } />
            <Route path="/admin/dashboard" component={() => 
              <AdminDashboard user={user} />
            } />
            <Route path="/calls" component={() => 
              <CallsPage business={business} />
            } />
            <Route path="/whatsapp" component={() => 
              <WhatsAppPage business={business} />
            } />
            <Route path="/crm" component={() => 
              <CRMPage business={business} />
            } />
            <Route path="/crm/customer/:id" component={CustomerPage} />
            <Route path="/" component={() => 
              <Dashboard business={business} permissions={permissions} />
            } />
          </Routes>
        </main>
      </div>

      {/* Mobile Sidebar Overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-gray-600 bg-opacity-75 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
    </div>
  );
}

export default App;