import React, { useState } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, 
  Users, 
  MessageCircle, 
  Phone, 
  Building2, 
  CreditCard, 
  Settings, 
  Calendar,
  UserCog,
  Menu,
  X,
  LogOut
} from 'lucide-react';
import { useAuthState } from '../../features/auth/hooks';
import { SidebarItem } from '../../shared/components/SidebarItem';

const menuItems = [
  { icon: LayoutDashboard, label: 'סקירה כללית', to: '/app/admin/overview', roles: ['admin', 'manager'] },
  { icon: LayoutDashboard, label: 'סקירה כללית', to: '/app/business/overview', roles: ['business'] },
  { icon: Users, label: 'לידים' },
  { icon: MessageCircle, label: 'WhatsApp' },
  { icon: Phone, label: 'שיחות' },
  { icon: Building2, label: 'CRM' },
  { icon: CreditCard, label: 'תשלומים' },
  { icon: UserCog, label: 'ניהול עסקים', roles: ['admin', 'manager'] },
  { icon: Users, label: 'משתמשים', roles: ['admin', 'manager'] },
  { icon: Settings, label: 'הגדרות' },
  { icon: Calendar, label: 'לוח שנה' },
];

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, tenant, logout } = useAuthState();
  const location = useLocation();

  const handleComingSoon = () => {
    alert('בקרוב! תכונה זו תהיה זמינה בגרסה הבאה.');
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const filteredMenuItems = menuItems.filter(item => 
    !item.roles || (user && item.roles.includes(user.role))
  );

  return (
    <div className="h-screen flex bg-gray-50" dir="rtl">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black bg-opacity-50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar - Always visible on tablet+ */}
      <div className={`
        fixed inset-y-0 right-0 z-50 w-80 bg-white shadow-xl transform transition-transform duration-200 ease-in-out
        md:relative md:translate-x-0 md:w-72
        ${sidebarOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>
        {/* Sidebar header */}
        <div className="flex items-center justify-between h-20 px-6 border-b border-gray-200">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-12 h-12 bg-blue-600 rounded-xl flex items-center justify-center">
                <span className="text-white font-bold text-xl">ש</span>
              </div>
            </div>
            <div className="mr-4">
              <h1 className="text-lg font-bold text-gray-900">שי דירות</h1>
              <p className="text-sm text-gray-500">{tenant?.name}</p>
            </div>
          </div>
          <button
            className="md:hidden p-2 rounded-lg hover:bg-gray-100"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* User info */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center">
            <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">
                {user?.email.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="mr-4 flex-1">
              <p className="text-base font-medium text-gray-900 truncate">{user?.email}</p>
              <div className="mt-1">
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                  user?.role === 'admin' ? 'bg-blue-100 text-blue-800' : 'bg-gray-100 text-gray-800'
                }`}>
                  {user?.role === 'admin' ? 'מנהל מערכת' : 
                   user?.role === 'manager' ? 'מנהל' : 'עסק'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          {filteredMenuItems.map((item, index) => (
            <SidebarItem
              key={index}
              to={item.to}
              icon={<item.icon className="h-5 w-5" />}
              label={item.label}
              onClick={!item.to ? handleComingSoon : undefined}
            />
          ))}
        </nav>

        {/* Logout button */}
        <div className="p-6 border-t border-gray-200">
          <button
            className="w-full flex items-center px-4 py-3 text-gray-700 rounded-xl hover:bg-gray-100 transition-colors"
            onClick={handleLogout}
            data-testid="button-logout"
          >
            <LogOut className="h-5 w-5 ml-3" />
            יציאה מהמערכת
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar - Mobile App Style */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-4 md:px-6">
            <div className="flex justify-between items-center h-16 md:h-20">
              <div className="flex items-center">
                <button
                  className="md:hidden p-2 rounded-xl hover:bg-gray-100 transition-colors"
                  onClick={() => setSidebarOpen(true)}
                  data-testid="button-menu"
                >
                  <Menu className="h-6 w-6" />
                </button>
                <h1 className="mr-3 text-lg md:text-2xl font-bold text-gray-900">
                  שי דירות
                </h1>
              </div>
              <div className="flex items-center">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-full flex items-center justify-center">
                  <span className="text-white font-bold text-sm">
                    {user?.email.charAt(0).toUpperCase()}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto pb-20 md:pb-0">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom navigation - App Style */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-2 py-2 shadow-xl">
        <div className="flex justify-around items-center">
          {filteredMenuItems.slice(0, 5).map((item, index) => {
            const isActive = item.to && location.pathname === item.to;
            return (
              <button
                key={index}
                className={`flex flex-col items-center p-2 min-h-[56px] transition-colors rounded-lg ${
                  isActive 
                    ? 'text-blue-600 bg-blue-50' 
                    : 'text-gray-600 hover:text-blue-600 hover:bg-gray-50'
                }`}
                onClick={item.to ? () => window.location.href = item.to : handleComingSoon}
              >
                <item.icon className="h-5 w-5 mb-1" />
                <span className="text-[10px] font-medium leading-tight text-center">
                  {item.label.length > 6 ? item.label.substring(0, 6) + '...' : item.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}