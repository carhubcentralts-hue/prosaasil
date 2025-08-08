import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  TrendingUp, Users, Phone, MessageSquare, Calendar, 
  Star, ArrowUpRight, ArrowDownRight, Activity, 
  BarChart3, PieChart, DollarSign, Clock, Building2,
  Shield, Zap, Database, Globe, Smartphone
} from 'lucide-react';

export default function ModernDashboard() {
  const [userRole, setUserRole] = useState('business');
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Determine user role
    const token = localStorage.getItem('authToken');
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    
    ;
    setUserRole(role || 'business');
    
    // Load dashboard data based on role
    loadDashboardData(role);
  }, []);

  const loadDashboardData = async (role) => {
    try {
      ;
      
      if (role === 'admin') {
        // Admin dashboard data
        setDashboardData({
          totalBusinesses: 24,
          activeBusinesses: 18,
          totalCustomers: 1247,
          totalCalls: 156,
          totalWhatsApp: 89,
          systemUptime: '99.9%',
          revenue: '₪45,230',
          growth: '+12.5%'
        });
      } else {
        // Business dashboard data
        setDashboardData({
          customers: 156,
          callsToday: 23,
          whatsappToday: 12,
          appointmentsToday: 5,
          revenue: '₪12,480',
          growth: '+8.3%',
          satisfaction: '4.8/5',
          responseTime: '2.3 דק'
        });
      }
      
      setLoading(false);
    } catch (error) {
      console.error('Error loading dashboard:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-600"></div>
        </div>
      </ModernLayout>
    );
  }

  const AdminDashboard = () => (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-700 rounded-3xl p-8 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">🏢 דשבורד מנהל מערכת</h1>
            <p className="text-blue-100 text-lg">ניהול וניטור כלל המערכת</p>
          </div>
          <div className="text-left">
            <div className="text-3xl font-bold">{dashboardData.totalBusinesses}</div>
            <div className="text-blue-100">עסקים במערכת</div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">עסקים פעילים</p>
              <p className="text-3xl font-bold text-green-600">{dashboardData.activeBusinesses}</p>
              <p className="text-green-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                +5.2% השבוע
              </p>
            </div>
            <Building2 className="w-12 h-12 text-green-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">סה"כ לקוחות</p>
              <p className="text-3xl font-bold text-blue-600">{dashboardData.totalCustomers}</p>
              <p className="text-blue-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                +12.3% החודש
              </p>
            </div>
            <Users className="w-12 h-12 text-blue-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שיחות היום</p>
              <p className="text-3xl font-bold text-purple-600">{dashboardData.totalCalls}</p>
              <p className="text-purple-500 text-sm flex items-center gap-1">
                <Activity className="w-4 h-4" />
                זמן אמת
              </p>
            </div>
            <Phone className="w-12 h-12 text-purple-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">זמינות מערכת</p>
              <p className="text-3xl font-bold text-emerald-600">{dashboardData.systemUptime}</p>
              <p className="text-emerald-500 text-sm flex items-center gap-1">
                <Shield className="w-4 h-4" />
                יציב
              </p>
            </div>
            <Database className="w-12 h-12 text-emerald-500" />
          </div>
        </div>
      </div>

      {/* System Overview */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-blue-600" />
            סטטיסטיקות כלליות
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">הודעות WhatsApp היום</span>
              <span className="font-bold text-green-600">{dashboardData.totalWhatsApp}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">הכנסות החודש</span>
              <span className="font-bold text-purple-600">{dashboardData.revenue}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">צמיחה</span>
              <span className="font-bold text-blue-600">{dashboardData.growth}</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Activity className="w-6 h-6 text-purple-600" />
            פעילות אחרונה
          </h3>
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span className="text-sm">עסק חדש הצטרף למערכת</span>
              <span className="text-xs text-gray-500 mr-auto">לפני 5 דקות</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-sm">העדכן מערכת הושלם בהצלחה</span>
              <span className="text-xs text-gray-500 mr-auto">לפני 12 דקות</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
              <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
              <span className="text-sm">סיכרון נתונים הושלם</span>
              <span className="text-xs text-gray-500 mr-auto">לפני 23 דקות</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const BusinessDashboard = () => (
    <div className="space-y-8">
      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-blue-700 rounded-3xl p-8 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-4xl font-bold mb-2">💼 דשבורד עסקי</h1>
            <p className="text-purple-100 text-lg">ניהול החברה שלך בצורה חכמה</p>
          </div>
          <div className="text-left">
            <div className="text-3xl font-bold">{dashboardData.customers}</div>
            <div className="text-purple-100">לקוחות פעילים</div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שיחות היום</p>
              <p className="text-3xl font-bold text-green-600">{dashboardData.callsToday}</p>
              <p className="text-green-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                +15% מאתמול
              </p>
            </div>
            <Phone className="w-12 h-12 text-green-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">WhatsApp היום</p>
              <p className="text-3xl font-bold text-blue-600">{dashboardData.whatsappToday}</p>
              <p className="text-blue-500 text-sm flex items-center gap-1">
                <MessageSquare className="w-4 h-4" />
                +8 חדשות
              </p>
            </div>
            <Smartphone className="w-12 h-12 text-blue-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">פגישות היום</p>
              <p className="text-3xl font-bold text-purple-600">{dashboardData.appointmentsToday}</p>
              <p className="text-purple-500 text-sm flex items-center gap-1">
                <Calendar className="w-4 h-4" />
                2 בהמתנה
              </p>
            </div>
            <Calendar className="w-12 h-12 text-purple-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100 hover:shadow-xl transition-all">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שביעות רצון</p>
              <p className="text-3xl font-bold text-orange-600">{dashboardData.satisfaction}</p>
              <p className="text-orange-500 text-sm flex items-center gap-1">
                <Star className="w-4 h-4" />
                מעולה
              </p>
            </div>
            <Star className="w-12 h-12 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Business Analytics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-green-600" />
            ביצועים עסקיים
          </h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-600">הכנסות החודש</span>
              <span className="font-bold text-green-600">{dashboardData.revenue}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">צמיחה</span>
              <span className="font-bold text-blue-600">{dashboardData.growth}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-600">זמן תגובה ממוצע</span>
              <span className="font-bold text-purple-600">{dashboardData.responseTime}</span>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
            <Clock className="w-6 h-6 text-blue-600" />
            פעילות אחרונה
          </h3>
          <div className="space-y-3">
            <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full"></div>
              <span className="text-sm">לקוח חדש הצטרף</span>
              <span className="text-xs text-gray-500 mr-auto">לפני 3 דקות</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
              <div className="w-2 h-2 bg-blue-500 rounded-full"></div>
              <span className="text-sm">שיחה הסתיימה בהצלחה</span>
              <span className="text-xs text-gray-500 mr-auto">לפני 7 דקות</span>
            </div>
            <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
              <div className="w-2 h-2 bg-purple-500 rounded-full"></div>
              <span className="text-sm">הודעת WhatsApp נשלחה</span>
              <span className="text-xs text-gray-500 mr-auto">לפני 12 דקות</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <ModernLayout userRole={userRole}>
      {userRole === 'admin' ? <AdminDashboard /> : <BusinessDashboard />}
    </ModernLayout>
  );
}