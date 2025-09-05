import React, { useState } from 'react';
import { Outlet } from 'react-router-dom';
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
  { icon: Users, label: 'לידים', disabled: true },
  { icon: MessageCircle, label: 'WhatsApp', disabled: true },
  { icon: Phone, label: 'שיחות', disabled: true },
  { icon: Building2, label: 'CRM', disabled: true },
  { icon: CreditCard, label: 'תשלומים וחוזים', disabled: true },
  { icon: UserCog, label: 'ניהול עסקים', disabled: true, roles: ['admin', 'manager'] },
  { icon: Users, label: 'ניהול משתמשים', disabled: true, roles: ['admin', 'manager'] },
  { icon: Settings, label: 'הגדרות מערכת', disabled: true },
  { icon: Calendar, label: 'לוח שנה', disabled: true },
];

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, tenant, logout } = useAuthState();

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
          className="fixed inset-0 z-40 bg-black bg-opacity-50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 right-0 z-50 w-72 bg-white shadow-lg transform transition-transform duration-300 ease-in-out
        lg:relative lg:translate-x-0
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
            className="lg:hidden p-2 rounded-lg hover:bg-gray-100"
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
        <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
          {filteredMenuItems.map((item, index) => (
            <SidebarItem
              key={index}
              to={item.disabled ? undefined : item.to}
              icon={<item.icon className="h-5 w-5" />}
              label={item.label}
              onClick={item.disabled ? handleComingSoon : undefined}
              disabled={item.disabled}
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
        {/* Top bar */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="px-6 lg:px-8">
            <div className="flex justify-between items-center h-20">
              <div className="flex items-center">
                <button
                  className="lg:hidden p-3 rounded-xl hover:bg-gray-100 transition-colors"
                  onClick={() => setSidebarOpen(true)}
                  data-testid="button-menu"
                >
                  <Menu className="h-6 w-6" />
                </button>
                <h1 className="mr-4 text-2xl font-bold text-gray-900">
                  מערכת ניהול לידים
                </h1>
              </div>
              <div className="hidden lg:flex items-center">
                <span className="text-sm text-gray-600 px-3 py-1 bg-gray-100 rounded-lg">
                  {user?.email}
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto pb-20 lg:pb-0">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <div className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-2 py-3 shadow-lg">
        <div className="flex justify-around">
          {filteredMenuItems.slice(0, 4).map((item, index) => (
            <button
              key={index}
              className="flex flex-col items-center p-3 min-h-[60px] text-gray-600 hover:text-blue-600 transition-colors rounded-xl hover:bg-gray-50"
              onClick={item.disabled ? handleComingSoon : undefined}
            >
              <item.icon className="h-6 w-6 mb-1" />
              <span className="text-xs font-medium">{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}