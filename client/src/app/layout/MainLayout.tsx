import React, { useState, useEffect, useRef } from 'react';
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
  User
} from 'lucide-react';
import { useAuth } from '../../features/auth/hooks';
import { NotificationPanel } from '../../shared/components/ui/NotificationPanel';
import { ImpersonationBanner } from '../../features/businesses/components/ImpersonationBanner';
import { SearchModal } from '../../shared/components/ui/SearchModal';
import { cn } from '../../shared/utils/cn';

const menuItems = [
  { 
    icon: LayoutDashboard, 
    label: 'סקירה כללית', 
    to: '/app/admin/overview', 
    roles: ['admin', 'manager'] 
  },
  { 
    icon: LayoutDashboard, 
    label: 'סקירה כללית', 
    to: '/app/business/overview', 
    roles: ['business'] 
  },
  { 
    icon: Users, 
    label: 'לידים',
    comingSoon: true
  },
  { 
    icon: MessageCircle, 
    label: 'WhatsApp',
    comingSoon: true
  },
  { 
    icon: Phone, 
    label: 'שיחות',
    comingSoon: true
  },
  { 
    icon: Building2, 
    label: 'CRM',
    comingSoon: true
  },
  { 
    icon: CreditCard, 
    label: 'תשלומים וחוזים',
    comingSoon: true
  },
  { 
    icon: UserCog, 
    label: 'ניהול עסקים', 
    to: '/app/admin/businesses',
    roles: ['admin', 'manager']
  },
  { 
    icon: Users, 
    label: 'ניהול משתמשים', 
    roles: ['admin', 'manager'],
    comingSoon: true
  },
  { 
    icon: Settings, 
    label: 'הגדרות מערכת',
    comingSoon: true
  },
  { 
    icon: Calendar, 
    label: 'לוח שנה',
    to: '/app/calendar',
    roles: ['admin', 'manager', 'business']
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

  if (to && !comingSoon) {
    return (
      <button onClick={() => navigate(to)} className={baseStyles}>
        {content}
      </button>
    );
  }

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
  
  const handleUnreadCountChange = (count: number) => {
    console.log('📮 MainLayout מקבל עדכון מונה:', count);
    setUnreadNotifications(count);
  };
  // Impersonation state
  const [impersonationState, setImpersonationState] = useState({
    isImpersonating: false,
    originalUser: null as any,
    impersonatedBusiness: null as any
  });
  const { user, tenant, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const sidebarRef = useRef<HTMLDivElement>(null);
  const toggleButtonRef = useRef<HTMLButtonElement>(null);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Filter menu items based on user role
  const filteredMenuItems = menuItems.filter(item => 
    !item.roles || (user && item.roles.includes(user.role))
  );

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

  // Check for impersonation state on mount and auth changes
  useEffect(() => {
    const checkImpersonationState = () => {
      const isImpersonating = localStorage.getItem('is_impersonating') === 'true';
      const originalUserData = localStorage.getItem('impersonation_original_user');
      const businessName = localStorage.getItem('impersonating_business_name');
      const businessDomain = localStorage.getItem('impersonating_business_domain');

      if (isImpersonating && originalUserData && businessName) {
        try {
          const originalUser = JSON.parse(originalUserData);
          setImpersonationState({
            isImpersonating: true,
            originalUser,
            impersonatedBusiness: {
              name: businessName,
              domain: businessDomain || ''
            }
          });
        } catch (error) {
          console.error('שגיאה בטעינת מצב התחזות:', error);
        }
      } else {
        setImpersonationState({
          isImpersonating: false,
          originalUser: null,
          impersonatedBusiness: null
        });
      }
    };

    checkImpersonationState();
  }, [user]);

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

  const handleExitImpersonation = () => {
    // Clear impersonation state
    localStorage.removeItem('impersonation_original_user');
    localStorage.removeItem('is_impersonating');
    localStorage.removeItem('impersonating_business_id');
    localStorage.removeItem('impersonating_business_name');
    localStorage.removeItem('impersonating_business_domain');
    
    setImpersonationState({
      isImpersonating: false,
      originalUser: null,
      impersonatedBusiness: null
    });
  };

  return (
    <div className="h-screen flex flex-col bg-slate-50" dir="rtl">
      {/* Impersonation Banner */}
      {impersonationState.isImpersonating && impersonationState.originalUser && impersonationState.impersonatedBusiness && (
        <ImpersonationBanner
          originalUser={impersonationState.originalUser}
          impersonatedBusiness={impersonationState.impersonatedBusiness}
          onExit={handleExitImpersonation}
        />
      )}
      
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
          'fixed inset-y-0 right-0 z-50 w-80 bg-white shadow-xl transform transition-transform duration-300 ease-in-out',
          'md:relative md:translate-x-0 md:w-72 md:shadow-sm md:border-l md:border-slate-200',
          sidebarOpen ? 'translate-x-0' : 'translate-x-full'
        )}
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
        <div className="p-6 border-b border-slate-200">
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
                  user?.role === 'admin' ? 'bg-violet-100 text-violet-800' :
                  user?.role === 'manager' ? 'bg-blue-100 text-blue-800' :
                  'bg-slate-100 text-slate-800'
                )}>
                  {user?.role === 'admin' ? 'מנהל מערכת' : 
                   user?.role === 'manager' ? 'מנהל' : 'עסק'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-6 overflow-y-auto">
          {filteredMenuItems.map((item, index) => {
            const isActive = !!(item.to && location.pathname === item.to);
            return (
              <SidebarItem
                key={index}
                icon={<item.icon className="h-5 w-5" />}
                label={item.label}
                to={item.to}
                active={isActive}
                onClick={item.comingSoon ? handleComingSoon : undefined}
                comingSoon={item.comingSoon}
                navigate={navigate}
              />
            );
          })}
        </nav>

        {/* Logout button */}
        <div className="p-6 border-t border-slate-200">
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
                  {user?.role === 'admin' || user?.role === 'manager' 
                    ? 'מנהל המערכת' 
                    : tenant?.name || 'שי דירות'}
                </h1>
              </div>

              {/* Right side - Action buttons + User */}
              <div className="flex items-center space-x-reverse space-x-2">
                {/* Quick Search */}
                <button
                  className="p-2.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-xl transition-colors relative"
                  onClick={() => setSearchModalOpen(true)}
                  data-testid="button-search"
                  title="חיפוש מהיר"
                >
                  <Search className="h-5 w-5" />
                </button>

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
                                user?.role === 'admin' ? 'bg-violet-100 text-violet-800' :
                                user?.role === 'manager' ? 'bg-blue-100 text-blue-800' :
                                'bg-slate-100 text-slate-800'
                              )}>
                                {user?.role === 'admin' ? 'מנהל מערכת' : 
                                 user?.role === 'manager' ? 'מנהל' : 'עסק'}
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
        <div className="flex-1 overflow-y-auto">
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
                  if (item.to && !item.comingSoon) {
                    navigate(item.to);
                  } else if (item.comingSoon) {
                    handleComingSoon();
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

      {/* Notification Panel */}
      <NotificationPanel
        isOpen={notificationsPanelOpen}
        onClose={() => setNotificationsPanelOpen(false)}
        onUnreadCountChange={handleUnreadCountChange}
      />

      {/* Search Modal */}
      <SearchModal
        isOpen={searchModalOpen}
        onClose={() => setSearchModalOpen(false)}
      />
      </div>
    </div>
  );
}