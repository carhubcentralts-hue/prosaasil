import React, { useState, useEffect } from 'react';
import '../styles/advanced-crm.css';
import AdvancedNavigation from './AdvancedNavigation';
import CRMDashboard from './CRMDashboard';
import CallsManagement from './CallsManagement';
import WhatsAppManagement from './WhatsAppManagement';
import axios from 'axios';
import { 
  Users, 
  Phone, 
  MessageSquare, 
  Activity,
  TrendingUp,
  Calendar,
  CheckCircle,
  Clock,
  LogOut
} from 'lucide-react';

const AdvancedBusinessDashboard = () => {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [businessInfo, setBusinessInfo] = useState(null);
  const [dashboardStats, setDashboardStats] = useState({});
  const [loading, setLoading] = useState(true);

  const userName = localStorage.getItem('user_name') || 'משתמש עסק';
  const businessId = localStorage.getItem('business_id') || 1;

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      
      const [infoRes, crmStatsRes, callStatsRes, whatsappStatsRes] = await Promise.all([
        axios.get(`/api/business/info?business_id=${businessId}`),
        axios.get(`/api/crm/stats?business_id=${businessId}`),
        axios.get(`/api/calls/stats?business_id=${businessId}`),
        axios.get(`/api/whatsapp/stats?business_id=${businessId}`)
      ]);

      setBusinessInfo(infoRes.data);
      setDashboardStats({
        crm: crmStatsRes.data,
        calls: callStatsRes.data,
        whatsapp: whatsappStatsRes.data
      });
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    const adminTakeoverMode = localStorage.getItem('admin_takeover_mode');
    const originalAdminToken = localStorage.getItem('original_admin_token');
    
    if (adminTakeoverMode && originalAdminToken) {
      if (window.confirm('האם אתה רוצה לחזור לדשבורד המנהל?')) {
        localStorage.removeItem('admin_takeover_mode');
        localStorage.setItem('auth_token', originalAdminToken);
        localStorage.setItem('user_role', 'admin');
        localStorage.setItem('user_name', 'מנהל');
        localStorage.removeItem('original_admin_token');
        window.location.href = '/admin/dashboard';
      }
    } else {
      if (window.confirm('האם אתה בטוח שברצונך להתנתק?')) {
        localStorage.clear();
        window.location.href = '/login';
      }
    }
  };

  const StatCard = ({ title, value, subtitle, icon: Icon, color = "blue", trend = null }) => (
    <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-gray-600 font-hebrew">{title}</p>
          <p className={`text-3xl font-bold text-${color}-600 font-hebrew`}>{value}</p>
          {subtitle && <p className="text-sm text-gray-500 font-hebrew">{subtitle}</p>}
          {trend && (
            <div className={`flex items-center mt-2 text-sm ${trend > 0 ? 'text-green-600' : 'text-red-600'}`}>
              <TrendingUp className="w-4 h-4 ml-1" />
              <span className="font-hebrew">{trend > 0 ? '+' : ''}{trend}%</span>
            </div>
          )}
        </div>
        <div className={`w-12 h-12 bg-${color}-100 rounded-lg flex items-center justify-center`}>
          <Icon className={`w-6 h-6 text-${color}-600`} />
        </div>
      </div>
    </div>
  );

  const DashboardOverview = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
        </div>
      );
    }

    return (
      <div className="space-y-6">
        {/* Welcome Section */}
        <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-lg shadow-lg text-white p-8">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold font-hebrew">ברוך הבא, {userName}</h1>
              <p className="text-blue-100 font-hebrew mt-2">{businessInfo?.name || 'העסק שלך'}</p>
              <p className="text-blue-100 font-hebrew">מערכת CRM מתקדמת ברמת Monday.com</p>
            </div>
            <div className="text-left">
              <p className="text-blue-100 font-hebrew">היום</p>
              <p className="text-2xl font-bold font-hebrew">{new Date().toLocaleDateString('he-IL')}</p>
            </div>
          </div>
        </div>

        {/* Main Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard 
            title="סך הכל לקוחות" 
            value={dashboardStats.crm?.total_customers || 0}
            subtitle="בבסיס הנתונים"
            icon={Users} 
            color="blue"
            trend={12}
          />
          <StatCard 
            title="שיחות היום" 
            value={dashboardStats.calls?.today_calls || 0}
            subtitle="שיחות נכנסות ויוצאות"
            icon={Phone} 
            color="green"
            trend={8}
          />
          <StatCard 
            title="הודעות WhatsApp" 
            value={dashboardStats.whatsapp?.today_messages || 0}
            subtitle="הודעות היום"
            icon={MessageSquare} 
            color="green"
            trend={15}
          />
          <StatCard 
            title="משימות פתוחות" 
            value={dashboardStats.crm?.new_leads || 0}
            subtitle="מחכות לטיפול"
            icon={CheckCircle} 
            color="orange"
          />
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <StatCard 
            title="שיעור המרה" 
            value={`${dashboardStats.crm?.conversion_rate || 0}%`}
            subtitle="החודש האחרון"
            icon={TrendingUp} 
            color="purple"
            trend={5}
          />
          <StatCard 
            title="זמן מענה ממוצע" 
            value={`${dashboardStats.whatsapp?.avg_response_time || 0} דק'`}
            subtitle="WhatsApp ושיחות"
            icon={Clock} 
            color="yellow"
          />
          <StatCard 
            title="לקוחות פעילים" 
            value={dashboardStats.crm?.active_customers || 0}
            subtitle="החודש האחרון"
            icon={Activity} 
            color="indigo"
            trend={3}
          />
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 font-hebrew mb-4">פעולות מהירות</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <button 
              onClick={() => setActiveTab('crm')}
              className="flex flex-col items-center p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors"
            >
              <Users className="w-8 h-8 text-blue-600 mb-2" />
              <span className="text-sm font-medium text-blue-600 font-hebrew">לקוח חדש</span>
            </button>
            <button 
              onClick={() => setActiveTab('calls')}
              className="flex flex-col items-center p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors"
            >
              <Phone className="w-8 h-8 text-green-600 mb-2" />
              <span className="text-sm font-medium text-green-600 font-hebrew">בצע שיחה</span>
            </button>
            <button 
              onClick={() => setActiveTab('whatsapp')}
              className="flex flex-col items-center p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors"
            >
              <MessageSquare className="w-8 h-8 text-green-600 mb-2" />
              <span className="text-sm font-medium text-green-600 font-hebrew">שלח הודעה</span>
            </button>
            <button 
              onClick={() => setActiveTab('calendar')}
              className="flex flex-col items-center p-4 bg-orange-50 rounded-lg hover:bg-orange-100 transition-colors"
            >
              <Calendar className="w-8 h-8 text-orange-600 mb-2" />
              <span className="text-sm font-medium text-orange-600 font-hebrew">קבע פגישה</span>
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <DashboardOverview />;
      case 'crm':
        return <CRMDashboard businessId={businessId} />;
      case 'calls':
        return <CallsManagement businessId={businessId} />;
      case 'whatsapp':
        return <WhatsAppManagement businessId={businessId} />;
      case 'calendar':
        return (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
            <Calendar className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 font-hebrew">יומן ופגישות</h3>
            <p className="text-gray-500 font-hebrew">בקרוב - ניהול יומן מתקדם</p>
          </div>
        );
      case 'tasks':
        return (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
            <CheckCircle className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 font-hebrew">ניהול משימות</h3>
            <p className="text-gray-500 font-hebrew">בקרוב - מערכת משימות מתקדמת</p>
          </div>
        );
      case 'reports':
        return (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
            <Activity className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 font-hebrew">דוחות וניתוחים</h3>
            <p className="text-gray-500 font-hebrew">בקרוב - דוחות מתקדמים</p>
          </div>
        );
      case 'settings':
        return (
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
            <Settings className="w-16 h-16 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 font-hebrew">הגדרות מערכת</h3>
            <p className="text-gray-500 font-hebrew">בקרוב - הגדרות מתקדמות</p>
          </div>
        );
      default:
        return <DashboardOverview />;
    }
  };

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      {/* Header with Logout */}
      <div className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900 font-hebrew">
              {businessInfo?.name || 'מערכת CRM מתקדמת'}
            </h1>
            <button 
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-hebrew"
            >
              <LogOut className="w-4 h-4" />
              יציאה
            </button>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <AdvancedNavigation activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {renderContent()}
      </main>
    </div>
  );
};

export default AdvancedBusinessDashboard;