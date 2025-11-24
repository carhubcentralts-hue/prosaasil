import React, { useState, useEffect, useRef, useCallback } from 'react'; // ✅ CRITICAL: Default React import for classic JSX
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
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
  LogOut,
  Search,
  Bell,
  User,
  Bot,
  Brain
} from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import { useImpersonation } from '../../features/businesses/hooks/useImpersonation';
import { NotificationPanel } from '../../shared/components/ui/NotificationPanel';
import { ImpersonationBanner } from '../../features/businesses/components/ImpersonationBanner';
import { SearchModal } from '../../shared/components/ui/SearchModal';
import { cn } from '../../shared/utils/cn';

const menuItems = [
  { 
    icon: LayoutDashboard, 
    label: 'סקירה כללית', 
    to: '/app/admin/overview', 
    roles: ['system_admin', 'owner', 'admin'] 
  },
  { 
    icon: Users, 
    label: 'לידים',
    to: '/app/leads',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: MessageCircle, 
    label: 'WhatsApp',
    to: '/app/whatsapp',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: Phone, 
    label: 'שיחות',
    to: '/app/calls',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: Building2, 
    label: 'CRM',
    to: '/app/crm',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: Brain, 
    label: 'אינטליגנציה לקוחות',
    to: '/app/intelligence',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: CreditCard, 
    label: 'תשלומים וחוזים',
    to: '/app/billing',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: UserCog, 
    label: 'ניהול עסקים', 
    to: '/app/admin/businesses',
    roles: ['system_admin', 'owner', 'admin']
  },
  { 
    icon: Bot, 
    label: 'AI Prompts', 
    to: '/app/admin/prompts',
    roles: ['system_admin', 'owner', 'admin']
  },
  { 
    icon: UserCog, 
    label: 'ניהול משתמשים', 
    to: '/app/users',
    roles: ['system_admin', 'owner', 'admin']
  },
  { 
    icon: Settings, 
    label: 'הגדרות מערכת',
    to: '/app/settings',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
  { 
    icon: Calendar, 
    label: 'לוח שנה',
    to: '/app/calendar'
  },
  { 
    icon: Bell, 
    label: 'תזכורות',
    to: '/app/notifications',
    roles: ['system_admin', 'owner', 'admin', 'agent']
  },
];

interface SidebarItemProps {
  icon: React.ReactNode;
  label: string;
  to?: string;
  active?: boolean;
  onClick?: () => void;
  comingSoon?: boolean;
  navigate?: (path: string) => void;
}

function SidebarItem({ icon, label, to, active, onClick, comingSoon, navigate }: SidebarItemProps) {
  const content = (
    <div className="flex items-center">
      <div className="ml-3 text-slate-500">
        {icon}
      </div>
      <span className="flex-1">{label}</span>
      {comingSoon && (
        <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded-full">
          בקרוב
        </span>
      )}
    </div>
  );

  const baseStyles = cn(
    'flex items-center px-4 py-3 text-sm font-medium transition-all duration-200 rounded-xl mx-2',
    'hover:bg-slate-100 hover:text-slate-900',
    'focus:outline-none focus:ring-2 focus:ring-blue-300 focus:ring-offset-1',
    active && 'bg-slate-100 text-slate-900 border border-slate-200',
    comingSoon && 'cursor-pointer'
  );

  // Always use onClick to ensure sidebar closes
  return (
    <button className={baseStyles} onClick={onClick}>
      {content}
    </button>
  );
}

export function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [notificationsPanelOpen, setNotificationsPanelOpen] = useState(false);
  const [searchModalOpen, setSearchModalOpen] = useState(false);
  const [unreadNotifications, setUnreadNotifications] = useState(0); // Will be set from notifications
  
  // FIXED: Wrap in useCallback to prevent infinite loop
  const handleUnreadCountChange = useCallback((count: number) => {
    console.log('📮 MainLayout מקבל עדכון מונה:', count);
    setUnreadNotifications(count);
  }, []); // Empty dependency array - function doesn't depend on any values
  
  const { user, tenant, logout } = useAuth();
  const { isImpersonating } = useImpersonation(); // Use server-side impersonation state
  const location = useLocation();
  const navigate = useNavigate();
  const sidebarRef = useRef<HTMLDivElement>(null);
  const toggleButtonRef = useRef<HTMLButtonElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Filter menu items based on user role and impersonation state
  const filteredMenuItems = menuItems.filter(item => {
    // Check role permissions first
    if (item.roles && (!user || !item.roles.includes(user.role))) {
      return false;
    }
    
    // Hide "Business Management" during impersonation - only show business-specific items
    if (isImpersonating && item.label === 'ניהול עסקים') {
      return false;
    }
    
    return true;
  });

  // Handle coming soon click
  const handleComingSoon = () => {
    alert('בקרוב! תכונה זו תהיה זמינה בגרסה הבאה.');
    setSidebarOpen(false);
  };

  // Handle logout
  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Focus trap for mobile drawer
  useEffect(() => {
    if (!sidebarOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSidebarOpen(false);
        toggleButtonRef.current?.focus();
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (sidebarRef.current && !sidebarRef.current.contains(e.target as Node)) {
        setSidebarOpen(false);
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.addEventListener('mousedown', handleClickOutside);
    
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [sidebarOpen]);

  // Removed localStorage-based impersonation state management
  // Now using server-side session state from useImpersonation hook

  // User menu click outside handler
  useEffect(() => {
    if (!userMenuOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (userMenuRef.current && !userMenuRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false);
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setUserMenuOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('keydown', handleKeyDown);
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [userMenuOpen]);

  // Removed handleExitImpersonation - now handled by ImpersonationBanner component

  return (
    <div className="h-screen flex flex-col bg-slate-50" dir="rtl">
      {/* Impersonation Banner - now self-contained */}
      {isImpersonating && <ImpersonationBanner />}
      
      <div className="flex-1 flex flex-row-reverse overflow-hidden">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black bg-opacity-50 md:hidden"
          onClick={() => setSidebarOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar - Desktop fixed, Mobile drawer */}
      <aside 
        ref={sidebarRef}
        className={cn(
          'fixed inset-y-0 right-0 z-50 w-80 bg-white shadow-xl transform transition-transform duration-300 ease-in-out flex flex-col',
          'md:relative md:translate-x-0 md:w-72 md:shadow-sm md:border-l md:border-slate-200',
          sidebarOpen ? 'translate-x-0' : 'translate-x-full'
        )}
        style={{ height: '100vh' }}
        role="navigation"
        aria-label="תפריט ראשי"
        aria-expanded={sidebarOpen ? 'true' : 'false'}
        id="sidebar"
      >
        {/* Sidebar header */}
        <div className="flex items-center justify-between h-20 px-6 border-b border-slate-200">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <div className="w-12 h-12 gradient-brand rounded-xl flex items-center justify-center">
                <span className="text-white font-bold text-xl">ש</span>
              </div>
            </div>
            <div className="mr-4">
              <h1 className="text-lg font-semibold text-slate-900">שי דירות</h1>
              <p className="text-sm text-slate-500">{tenant?.name || 'ומשרדים בע״מ'}</p>
            </div>
          </div>
          <button
            className="md:hidden p-2 rounded-xl hover:bg-slate-100 transition-colors"
            onClick={() => setSidebarOpen(false)}
            aria-label="סגור תפריט"
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* User info */}
        <div className="p-6 border-b border-slate-200 flex-shrink-0">
          <div className="flex items-center">
            <div className="w-12 h-12 gradient-brand rounded-xl flex items-center justify-center">
              <span className="text-white font-bold text-lg">
                {user?.email.charAt(0).toUpperCase()}
              </span>
            </div>
            <div className="mr-4 flex-1">
              <p className="text-base font-medium text-slate-900 truncate">
                {user?.name || user?.email}
              </p>
              <div className="mt-1">
                <span className={cn(
                  'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                  user?.role === 'system_admin' ? 'bg-purple-100 text-purple-800' :
                  user?.role === 'owner' ? 'bg-blue-100 text-blue-800' :
                  user?.role === 'admin' ? 'bg-violet-100 text-violet-800' :
                  'bg-slate-100 text-slate-800'
                )}>
                  {user?.role === 'system_admin' ? 'מנהל מערכת' : 
                   user?.role === 'owner' ? 'בעלים' : 
                   user?.role === 'admin' ? 'מנהל' : 
                   user?.role === 'agent' ? 'סוכן' : 'משתמש'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-6 overflow-y-auto min-h-0">
          {filteredMenuItems.map((item, index) => {
            const isActive = !!(item.to && location.pathname === item.to);
            return (
              <SidebarItem
                key={index}
                icon={<item.icon className="h-5 w-5" />}
                label={item.label}
                to={item.to}
                active={isActive}
                onClick={() => {
                  if (item.to) {
                    navigate(item.to);
                    // Always close sidebar after navigation (mobile AND desktop)
                    setTimeout(() => setSidebarOpen(false), 100);
                  }
                }}
                navigate={navigate}
              />
            );
          })}
        </nav>

        {/* Logout button */}
        <div className="p-6 border-t border-slate-200 flex-shrink-0">
          <button
            className="w-full flex items-center px-4 py-3 text-slate-700 rounded-xl hover:bg-slate-100 transition-colors btn-ghost"
            onClick={handleLogout}
            data-testid="button-logout"
          >
            <LogOut className="h-5 w-5 ml-3" />
            יציאה מהמערכת
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Desktop & Mobile Header */}
        <header className="bg-white shadow-sm border-b border-slate-200">
          <div className="px-4 md:px-6">
            <div className="flex justify-between items-center h-16">
              {/* Left side - Mobile menu + Title */}
              <div className="flex items-center">
                <button
                  ref={toggleButtonRef}
                  className="md:hidden p-2 rounded-xl hover:bg-slate-100 transition-colors"
                  onClick={() => setSidebarOpen(true)}
                  aria-expanded={sidebarOpen ? 'true' : 'false'}
                  aria-controls="sidebar"
                  aria-label="פתח תפריט"
                  data-testid="button-menu"
                >
                  <Menu className="h-6 w-6" />
                </button>
                <h1 className="mr-3 md:mr-0 text-lg font-semibold text-slate-900">
                  {user?.role === 'system_admin' || user?.role === 'owner' || user?.role === 'admin'
                    ? 'מנהל המערכת' 
                    : tenant?.name || 'שי דירות'}
                </h1>
              </div>

              {/* Right side - Action buttons + User */}
              <div className="flex items-center space-x-reverse space-x-2">
                {/* Quick Search - Temporarily hidden - Search API needs to be implemented
                <button
                  className="p-2.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors relative"
                  onClick={() => setSearchModalOpen(true)}
                  data-testid="button-search"
                  title="חיפוש מהיר"
                >
                  <Search className="h-5 w-5" />
                </button>
                */}

                {/* Notifications */}
                <button
                  className="p-2.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors relative"
                  onClick={() => setNotificationsPanelOpen(!notificationsPanelOpen)}
                  data-testid="button-notifications"
                  title="התראות"
                >
                  <Bell className="h-5 w-5" />
                  {/* Notification badge */}
                  {unreadNotifications > 0 && (
                    <span 
                      className="absolute -top-1 -right-1 h-5 w-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center"
                      data-testid="unread-count-badge"
                    >
                      {unreadNotifications}
                    </span>
                  )}
                </button>

                {/* User Avatar with Dropdown */}
                <div className="relative mr-2" ref={userMenuRef}>
                  <button
                    className="w-10 h-10 gradient-brand rounded-full flex items-center justify-center hover:ring-4 hover:ring-blue-100 transition-all duration-200 focus:outline-none focus:ring-4 focus:ring-blue-200"
                    onClick={() => setUserMenuOpen(!userMenuOpen)}
                    data-testid="button-user-menu"
                    title="תפריט משתמש"
                  >
                    <span className="text-white font-bold text-sm">
                      {user?.email.charAt(0).toUpperCase()}
                    </span>
                  </button>

                  {/* User Dropdown Menu */}
                  {userMenuOpen && (
                    <div className="absolute left-0 mt-2 w-64 bg-white rounded-xl shadow-xl border border-slate-200 py-2 z-50">
                      {/* User Info Header */}
                      <div className="px-4 py-3 border-b border-slate-100">
                        <div className="flex items-center">
                          <div className="w-12 h-12 gradient-brand rounded-xl flex items-center justify-center">
                            <span className="text-white font-bold text-lg">
                              {user?.email.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div className="mr-3 flex-1">
                            <p className="text-base font-medium text-slate-900 truncate">
                              {user?.name || user?.email}
                            </p>
                            <div className="mt-1">
                              <span className={cn(
                                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                                user?.role === 'system_admin' ? 'bg-purple-100 text-purple-800' :
                                user?.role === 'owner' ? 'bg-blue-100 text-blue-800' :
                                user?.role === 'admin' ? 'bg-violet-100 text-violet-800' :
                                'bg-slate-100 text-slate-800'
                              )}>
                                {user?.role === 'system_admin' ? 'מנהל מערכת' : 
                                 user?.role === 'owner' ? 'בעלים' : 
                                 user?.role === 'admin' ? 'מנהל' : 
                                 user?.role === 'agent' ? 'סוכן' : 'משתמש'}
                              </span>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Menu Items */}
                      <div className="py-2">
                        <button
                          className="w-full flex items-center px-4 py-2 text-slate-700 hover:bg-slate-50 transition-colors text-right"
                          onClick={() => {
                            setUserMenuOpen(false);
                            alert('הגדרות פרופיל בפיתוח!');
                          }}
                          data-testid="button-profile"
                        >
                          <User className="h-4 w-4 ml-3" />
                          הגדרות פרופיל
                        </button>
                        
                        <button
                          className="w-full flex items-center px-4 py-2 text-red-700 hover:bg-red-50 transition-colors text-right border-t border-slate-100 mt-2 pt-3"
                          onClick={() => {
                            setUserMenuOpen(false);
                            handleLogout();
                          }}
                          data-testid="button-logout-dropdown"
                        >
                          <LogOut className="h-4 w-4 ml-3" />
                          יציאה מהמערכת
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto pb-20 md:pb-0">
          <Outlet />
        </div>
      </main>

      {/* Bottom Navigation for mobile (optional - top 4 items) */}
      <div className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-slate-200 px-2 py-2 shadow-xl">
        <div className="flex justify-around items-center">
          {filteredMenuItems.slice(0, 4).map((item, index) => {
            const isActive = item.to && location.pathname === item.to;
            return (
              <button
                key={index}
                className={cn(
                  'flex flex-col items-center p-2 min-h-[60px] transition-all duration-200 rounded-xl',
                  isActive 
                    ? 'text-[var(--brand)] bg-blue-50 scale-105' 
                    : 'text-slate-500 hover:text-[var(--brand)] active:scale-95'
                )}
                onClick={() => {
                  if (item.to) {
                    navigate(item.to);
                    // Always close sidebar after navigation (mobile AND desktop)  
                    setTimeout(() => setSidebarOpen(false), 100);
                  }
                }}
              >
                <item.icon className="h-5 w-5 mb-1" />
                <span className="text-[11px] font-medium leading-tight text-center">
                  {item.label.length > 7 ? item.label.substring(0, 6) + '...' : item.label}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* BUILD Indicator */}
      <div className="fixed bottom-1 left-1 text-xs text-gray-400 font-mono z-10 pointer-events-none">
        BUILD: 108
      </div>

      {/* Notification Panel */}
      <NotificationPanel
        isOpen={notificationsPanelOpen}
        onClose={() => setNotificationsPanelOpen(false)}
        onUnreadCountChange={handleUnreadCountChange}
      />

      {/* Search Modal - Temporarily disabled until API is implemented */}
      {/* <SearchModal
        isOpen={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
      /> */}
      </div>
    </div>
  );
}