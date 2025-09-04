import { useState } from 'react';
import { Outlet, Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../features/auth/hooks';
import { cn } from '../../shared/utils/cn';
import {
  Home,
  Users,
  MessageCircle,
  Phone,
  CreditCard,
  Building,
  UserCheck,
  Settings,
  Calendar,
  Menu,
  X,
  Search,
  Bell,
  User,
  LogOut,
} from 'lucide-react';

interface SidebarItem {
  path: string;
  icon: React.ComponentType<any>;
  label: string;
  roles?: string[];
  comingSoon?: boolean;
}

const sidebarItems: SidebarItem[] = [
  {
    path: '/app/admin/overview',
    icon: Home,
    label: 'סקירה כללית',
    roles: ['admin', 'manager'],
  },
  {
    path: '/app/business/overview',
    icon: Home,
    label: 'סקירה כללית',
    roles: ['business'],
  },
  {
    path: '/app/leads',
    icon: Users,
    label: 'לידים',
    comingSoon: true,
  },
  {
    path: '/app/whatsapp',
    icon: MessageCircle,
    label: 'וואטסאפ',
    comingSoon: true,
  },
  {
    path: '/app/calls',
    icon: Phone,
    label: 'שיחות',
    comingSoon: true,
  },
  {
    path: '/app/crm',
    icon: Users,
    label: 'ניהול לקוחות',
    comingSoon: true,
  },
  {
    path: '/app/payments',
    icon: CreditCard,
    label: 'תשלומים וחשבוניות',
    roles: ['admin', 'manager'],
    comingSoon: true,
  },
  {
    path: '/app/business-manager',
    icon: Building,
    label: 'ניהול עסקים',
    roles: ['admin', 'manager'],
    comingSoon: true,
  },
  {
    path: '/app/users',
    icon: UserCheck,
    label: 'משתמשים',
    roles: ['admin', 'manager'],
    comingSoon: true,
  },
  {
    path: '/app/settings',
    icon: Settings,
    label: 'הגדרות מערכת',
    roles: ['admin', 'manager'],
    comingSoon: true,
  },
  {
    path: '/app/calendar',
    icon: Calendar,
    label: 'יומן',
    comingSoon: true,
  },
];

// Mobile bottom navigation items (top 4 most used)
const mobileNavItems = [
  { path: '/app/leads', icon: Users, label: 'לידים' },
  { path: '/app/whatsapp', icon: MessageCircle, label: 'וואטסאפ' },
  { path: '/app/calls', icon: Phone, label: 'שיחות' },
  { path: '/app/calendar', icon: Calendar, label: 'יומן' },
];

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const { user, business, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();

  // Filter sidebar items based on user role
  const filteredSidebarItems = sidebarItems.filter(item => {
    if (!item.roles) return true;
    return user && item.roles.includes(user.role);
  });

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  const isItemActive = (path: string) => {
    return location.pathname === path;
  };

  return (
    <div className="min-h-screen bg-gray-50 rtl" dir="rtl">
      {/* Desktop Sidebar */}
      <div className="hidden lg:fixed lg:inset-y-0 lg:right-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex min-h-0 flex-1 flex-col bg-white shadow-lg">
          {/* Sidebar Header */}
          <div className="flex h-16 flex-shrink-0 items-center justify-between px-6 border-b border-gray-200">
            <div className="flex items-center">
              <div className="h-8 w-8 bg-primary rounded-full flex items-center justify-center text-primary-foreground font-bold">
                ח
              </div>
              <span className="mr-3 text-lg font-semibold text-gray-900 truncate">
                {business?.name || 'מערכת CRM'}
              </span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 px-2 py-4 overflow-y-auto">
            {filteredSidebarItems.map((item) => {
              const Icon = item.icon;
              const isActive = isItemActive(item.path);
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'group flex items-center px-2 py-3 text-sm font-medium rounded-md transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary border-r-2 border-primary'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                    item.comingSoon && 'opacity-60'
                  )}
                >
                  <Icon className={cn(
                    'ml-3 h-5 w-5 flex-shrink-0',
                    isActive ? 'text-primary' : 'text-gray-400 group-hover:text-gray-500'
                  )} />
                  <span className="flex-1">{item.label}</span>
                  {item.comingSoon && (
                    <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full">
                      בקרוב
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* User Info */}
          <div className="flex-shrink-0 border-t border-gray-200 p-4">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <User className="h-8 w-8 text-gray-400" />
              </div>
              <div className="mr-3 flex-1">
                <p className="text-sm font-medium text-gray-700 truncate">{user?.name}</p>
                <p className="text-xs text-gray-500 truncate">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="mt-2 w-full flex items-center justify-center px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
            >
              <LogOut className="h-4 w-4 ml-2" />
              התנתק
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Sidebar */}
      <div className={cn(
        'fixed inset-0 z-50 lg:hidden',
        sidebarOpen ? 'block' : 'hidden'
      )}>
        {/* Overlay */}
        <div 
          className="fixed inset-0 bg-gray-600 bg-opacity-75"
          onClick={() => setSidebarOpen(false)}
        />
        
        {/* Sidebar */}
        <div className="fixed inset-y-0 right-0 flex w-full max-w-xs flex-col bg-white shadow-xl">
          {/* Header */}
          <div className="flex h-16 items-center justify-between px-6 border-b border-gray-200">
            <div className="flex items-center">
              <div className="h-8 w-8 bg-primary rounded-full flex items-center justify-center text-primary-foreground font-bold">
                ח
              </div>
              <span className="mr-3 text-lg font-semibold text-gray-900">
                {business?.name || 'מערכת CRM'}
              </span>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="p-2 rounded-md text-gray-400 hover:text-gray-600"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 space-y-1 px-2 py-4 overflow-y-auto">
            {filteredSidebarItems.map((item) => {
              const Icon = item.icon;
              const isActive = isItemActive(item.path);
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    'group flex items-center px-2 py-3 text-sm font-medium rounded-md transition-colors',
                    isActive
                      ? 'bg-primary/10 text-primary'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900',
                    item.comingSoon && 'opacity-60'
                  )}
                >
                  <Icon className={cn(
                    'ml-3 h-5 w-5 flex-shrink-0',
                    isActive ? 'text-primary' : 'text-gray-400 group-hover:text-gray-500'
                  )} />
                  <span className="flex-1">{item.label}</span>
                  {item.comingSoon && (
                    <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded-full">
                      בקרוב
                    </span>
                  )}
                </Link>
              );
            })}
          </nav>

          {/* User Info */}
          <div className="border-t border-gray-200 p-4">
            <div className="flex items-center mb-3">
              <User className="h-8 w-8 text-gray-400 flex-shrink-0" />
              <div className="mr-3">
                <p className="text-sm font-medium text-gray-700">{user?.name}</p>
                <p className="text-xs text-gray-500">{user?.email}</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center px-3 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-md transition-colors"
            >
              <LogOut className="h-4 w-4 ml-2" />
              התנתק
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="lg:pr-64 flex flex-col min-h-screen">
        {/* Top Header */}
        <header className="bg-white shadow-sm border-b border-gray-200 lg:static lg:overflow-y-visible">
          <div className="px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between h-16">
              <div className="flex items-center">
                {/* Mobile menu button */}
                <button
                  onClick={() => setSidebarOpen(true)}
                  className="p-2 rounded-md text-gray-400 hover:text-gray-600 lg:hidden"
                >
                  <Menu className="h-6 w-6" />
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
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                      className="block w-full pr-10 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
                    />
                  </div>
                </div>
              </div>

              <div className="flex items-center space-x-4 space-x-reverse">
                {/* Notifications */}
                <button className="p-2 text-gray-400 hover:text-gray-600 relative">
                  <Bell className="h-6 w-6" />
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
        </header>

        {/* Page Content */}
        <main className="flex-1">
          <Outlet />
        </main>

        {/* Mobile Bottom Navigation */}
        <div className="lg:hidden bg-white border-t border-gray-200 px-4 py-2">
          <div className="flex justify-around">
            {mobileNavItems.map((item) => {
              const Icon = item.icon;
              const isActive = isItemActive(item.path);
              
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={cn(
                    'flex flex-col items-center px-3 py-2 text-xs transition-colors',
                    isActive
                      ? 'text-primary'
                      : 'text-gray-500 hover:text-gray-700'
                  )}
                >
                  <Icon className="h-5 w-5" />
                  <span className="mt-1">{item.label}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}