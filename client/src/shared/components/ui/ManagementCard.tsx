import React from 'react'; // ✅ Classic JSX runtime
import { useEffect, useState } from 'react';
import { LucideIcon, ChevronRight, Building2, UserCog, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { cn } from '../../utils/cn';
import { useAuth } from '../../../features/auth/hooks';
import { http } from '../../../services/http';

interface ManagementCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  onClick: () => void;
  requiredRoles: string[];
  stats?: {
    count: number;
    label: string;
  };
  className?: string;
}

export function ManagementCard({ 
  title, 
  description, 
  icon: Icon, 
  onClick, 
  requiredRoles, 
  stats,
  className 
}: ManagementCardProps) {
  const { user } = useAuth();

  // Security check - only show if user has required role
  if (!user || !requiredRoles.includes(user.role)) {
    return null;
  }

  return (
    <div 
      className={cn(
        'bg-white rounded-xl p-6 shadow-sm border border-slate-200',
        'hover:shadow-md hover:border-slate-300 transition-all duration-200',
        'cursor-pointer group',
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center mb-3">
            <div className="p-2.5 bg-blue-50 rounded-lg mr-3">
              <Icon className="h-6 w-6 text-blue-600" />
            </div>
            <h3 className="text-lg font-semibold text-slate-900">
              {title}
            </h3>
          </div>
          
          <p className="text-sm text-slate-600 mb-4 leading-relaxed">
            {description}
          </p>
          
          {stats && (
            <div className="flex items-center text-sm">
              <span className="font-semibold text-slate-900 text-xl tabular-nums">
                {stats.count}
              </span>
              <span className="text-slate-500 mr-2">
                {stats.label}
              </span>
            </div>
          )}
        </div>
        
        <div className="group-hover:translate-x-1 transition-transform duration-200">
          <ChevronRight className="h-5 w-5 text-slate-400" />
        </div>
      </div>
    </div>
  );
}

interface QuickManagementActionsProps {
  className?: string;
}

export function QuickManagementActions({ className }: QuickManagementActionsProps) {
  const { user, impersonating } = useAuth();
  const navigate = useNavigate();
  const [businessCount, setBusinessCount] = useState<number | null>(null);
  const [userCount, setUserCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchRealData = async () => {
      try {
        setLoading(true);
        
        // Fetch real business count from our new API
        const businessData = await http.get('/api/admin/businesses?pageSize=1') as any;
        setBusinessCount(businessData.total || 0);
        
        // For users - we'll use a simple estimate for now until we create users API
        // TODO: Create a proper users API endpoint
        setUserCount(user?.role === 'business' ? 5 : (businessData as any).total * 3);
        
      } catch (error) {
        console.error('Error fetching management stats:', error);
        // Fallback to 0 if API fails
        setBusinessCount(0);
        setUserCount(0);
      } finally {
        setLoading(false);
      }
    };

    if (user) {
      fetchRealData();
    }
  }, [user]);

  const handleBusinessManagement = () => {
    navigate('/app/admin/businesses');
  };

  const handleUserManagement = () => {
    alert('ניהול משתמשים בפיתוח! כאן תוכלו לנהל משתמשים ולהעניק הרשאות.');
  };

  if (!user) return null;

  return (
    <div className={cn('space-y-4', className)}>
      {/* Business Management - Admin/Manager only, hide during impersonation */}
      {(user.role === 'admin' || user.role === 'manager') && !impersonating && (
        <ManagementCard
          title="ניהול עסקים"
          description="נהלו את כל העסקים במערכת, הוסיפו עסקים חדשים ועדכנו הגדרות"
          icon={Building2}
          onClick={handleBusinessManagement}
          requiredRoles={['admin', 'manager']}
          stats={{
            count: loading ? 0 : (businessCount || 0),
            label: loading ? 'טוען...' : 'עסקים פעילים'
          }}
        />
      )}

      {/* User Management - All roles (with different permissions) */}
      <ManagementCard
        title="ניהול משתמשים"
        description={
          user.role === 'business' 
            ? 'נהלו את המשתמשים בעסק שלכם והעניקו הרשאות'
            : 'נהלו משתמשים בכל המערכת והעניקו הרשאות מתקדמות'
        }
        icon={UserCog}
        onClick={handleUserManagement}
        requiredRoles={['admin', 'manager', 'business']}
        stats={{
          count: loading ? 0 : (userCount || 0),
          label: loading ? 'טוען...' : (user.role === 'business' ? 'משתמשים בעסק' : 'משתמשים במערכת')
        }}
      />
    </div>
  );
}