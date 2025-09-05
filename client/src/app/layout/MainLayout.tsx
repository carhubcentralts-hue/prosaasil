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
import { Button } from '../../shared/components/Button';
import { Badge } from '../../shared/components/Badge';

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
          className="fixed inset-0 z-40 bg-black bg-opacity-50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 right-0 z-50 w-64 bg-white shadow-lg transform transition-transform duration-300 ease-in-out
        md:relative md:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : 'translate-x-full'}
      `}>
        {/* Sidebar header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-gray-200">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold text-sm">ש</span>
              </div>
            </div>
            <div className="mr-3">
              <h1 className="text-sm font-medium text-gray-900">שי דירות ומשרדים</h1>
              <p className="text-xs text-gray-500">{tenant?.name}</p>
            </div>
          </div>
          <button
            className="md:hidden p-1 rounded-md hover:bg-gray-100"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* User info */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center">
            <div className="w-10 h-10 bg-gray-300 rounded-full flex items-center justify-center">
              <span className="text-gray-600 font-medium text-sm">
                {user?.email.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="mr-3 flex-1">
              <p className="text-sm font-medium text-gray-900">{user?.email}</p>
              <div className="flex items-center mt-1">
                <Badge 
                  variant={user?.role === 'admin' ? 'info' : 'neutral'} 
                  size="sm"
                >
                  {user?.role === 'admin' ? 'מנהל מערכת' : 
                   user?.role === 'manager' ? 'מנהל' : 'עסק'}
                </Badge>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-2 py-4 space-y-1 overflow-y-auto">
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
        <div className="p-4 border-t border-gray-200">
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={handleLogout}
            data-testid="button-logout"
          >
            <LogOut className="h-5 w-5 ml-3" />
            יציאה מהמערכת
          </Button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-white shadow-sm border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center">
                <button
                  className="md:hidden p-2 rounded-md hover:bg-gray-100"
                  onClick={() => setSidebarOpen(true)}
                  data-testid="button-menu"
                >
                  <Menu className="h-6 w-6" />
                </button>
                <h1 className="mr-4 text-xl font-semibold text-gray-900">
                  מערכת ניהול לידים
                </h1>
              </div>
              <div className="hidden md:flex items-center space-x-4">
                <span className="text-sm text-gray-500">
                  {user?.email}
                </span>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom navigation */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 px-4 py-2">
        <div className="flex justify-around">
          {filteredMenuItems.slice(0, 4).map((item, index) => (
            <button
              key={index}
              className="flex flex-col items-center p-2 text-gray-600 hover:text-blue-600"
              onClick={item.disabled ? handleComingSoon : undefined}
            >
              <item.icon className="h-5 w-5" />
              <span className="text-xs mt-1">{item.label}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}