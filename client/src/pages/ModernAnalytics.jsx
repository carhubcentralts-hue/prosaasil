import React, { useState, useEffect } from 'react';
import ModernLayout from '../components/ModernLayout';
import { 
  BarChart3, TrendingUp, Users, Phone, MessageSquare,
  DollarSign, Calendar, Star, Activity, ArrowUpRight,
  ArrowDownRight, PieChart, LineChart, Target,
  Clock, CheckCircle, AlertCircle, Award
} from 'lucide-react';

export default function ModernAnalytics() {
  const [userRole, setUserRole] = useState('business');
  const [timeRange, setTimeRange] = useState('7d');
  const [analyticsData, setAnalyticsData] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const role = localStorage.getItem('user_role') || localStorage.getItem('userRole');
    setUserRole(role || 'business');
    loadAnalytics(role);
  }, [timeRange]);

  const loadAnalytics = async (role) => {
    try {
      // Demo analytics data based on role
      const demoData = role === 'admin' ? {
        overview: {
          totalBusinesses: 24,
          totalCalls: 1247,
          totalRevenue: '₪456,789',
          successRate: '94.2%'
        },
        trends: {
          callsGrowth: '+23%',
          revenueGrowth: '+18%',
          businessGrowth: '+12%',
          satisfactionGrowth: '+8%'
        },
        topBusinesses: [
          { name: 'עסק ABC', calls: 145, revenue: '₪45,600', growth: '+25%' },
          { name: 'חברת XYZ', calls: 89, revenue: '₪32,100', growth: '+15%' },
          { name: 'משרד DEF', calls: 67, revenue: '₪28,900', growth: '+31%' }
        ]
      } : {
        overview: {
          totalCalls: 156,
          totalLeads: 89,
          conversionRate: '78%',
          avgCallDuration: '2:34'
        },
        trends: {
          callsGrowth: '+15%',
          leadsGrowth: '+22%',
          conversionGrowth: '+8%',
          durationGrowth: '+12%'
        },
        topSources: [
          { source: 'Google Ads', leads: 34, conversion: '82%' },
          { source: 'Facebook', leads: 28, conversion: '75%' },
          { source: 'המלצות', leads: 27, conversion: '95%' }
        ]
      };
      
      setAnalyticsData(demoData);
      setLoading(false);
    } catch (error) {
      console.error('Error loading analytics:', error);
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <ModernLayout userRole={userRole}>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="text-center">
            <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-purple-600 mx-auto mb-4"></div>
            <p className="text-gray-600">טוען נתוני אנליטיקה...</p>
          </div>
        </div>
      </ModernLayout>
    );
  }

  const AdminAnalytics = () => (
    <div className="space-y-8">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">עסקים במערכת</p>
              <p className="text-3xl font-bold text-blue-600">{analyticsData.overview?.totalBusinesses}</p>
              <p className="text-blue-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                {analyticsData.trends?.businessGrowth} החודש
              </p>
            </div>
            <Users className="w-12 h-12 text-blue-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">סה"כ שיחות</p>
              <p className="text-3xl font-bold text-green-600">{analyticsData.overview?.totalCalls}</p>
              <p className="text-green-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                {analyticsData.trends?.callsGrowth} השבוע
              </p>
            </div>
            <Phone className="w-12 h-12 text-green-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">הכנסות כלליות</p>
              <p className="text-3xl font-bold text-purple-600">{analyticsData.overview?.totalRevenue}</p>
              <p className="text-purple-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                {analyticsData.trends?.revenueGrowth} החודש
              </p>
            </div>
            <DollarSign className="w-12 h-12 text-purple-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שיעור הצלחה</p>
              <p className="text-3xl font-bold text-orange-600">{analyticsData.overview?.successRate}</p>
              <p className="text-orange-500 text-sm flex items-center gap-1">
                <Star className="w-4 h-4" />
                מעולה
              </p>
            </div>
            <Award className="w-12 h-12 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Top Performing Businesses */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
        <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
              <TrendingUp className="w-4 h-4 text-white" />
            </div>
            העסקים המובילים
          </h2>
        </div>
        
        <div className="p-6">
          <div className="space-y-4">
            {analyticsData.topBusinesses?.map((business, index) => (
              <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                <div className="flex items-center gap-4">
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white ${
                    index === 0 ? 'bg-yellow-500' : index === 1 ? 'bg-gray-400' : 'bg-orange-500'
                  }`}>
                    {index + 1}
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{business.name}</h3>
                    <p className="text-sm text-gray-600">{business.calls} שיחות החודש</p>
                  </div>
                </div>
                <div className="text-left">
                  <div className="font-bold text-gray-900">{business.revenue}</div>
                  <div className="text-sm text-green-600 flex items-center gap-1">
                    <ArrowUpRight className="w-3 h-3" />
                    {business.growth}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  const BusinessAnalytics = () => (
    <div className="space-y-8">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שיחות החודש</p>
              <p className="text-3xl font-bold text-blue-600">{analyticsData.overview?.totalCalls}</p>
              <p className="text-blue-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                {analyticsData.trends?.callsGrowth} מהחודש שעבר
              </p>
            </div>
            <Phone className="w-12 h-12 text-blue-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">לידים חדשים</p>
              <p className="text-3xl font-bold text-green-600">{analyticsData.overview?.totalLeads}</p>
              <p className="text-green-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                {analyticsData.trends?.leadsGrowth} השבוע
              </p>
            </div>
            <Target className="w-12 h-12 text-green-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">שיעור המרה</p>
              <p className="text-3xl font-bold text-purple-600">{analyticsData.overview?.conversionRate}</p>
              <p className="text-purple-500 text-sm flex items-center gap-1">
                <ArrowUpRight className="w-4 h-4" />
                {analyticsData.trends?.conversionGrowth} החודש
              </p>
            </div>
            <CheckCircle className="w-12 h-12 text-purple-500" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-600 text-sm">זמן שיחה ממוצע</p>
              <p className="text-3xl font-bold text-orange-600">{analyticsData.overview?.avgCallDuration}</p>
              <p className="text-orange-500 text-sm flex items-center gap-1">
                <Clock className="w-4 h-4" />
                דקות
              </p>
            </div>
            <Activity className="w-12 h-12 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Traffic Sources */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
        <div className="px-8 py-6 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-gray-100">
          <h2 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-br from-green-500 to-green-600 rounded-xl flex items-center justify-center">
              <PieChart className="w-4 h-4 text-white" />
            </div>
            מקורות לידים מובילים
          </h2>
        </div>
        
        <div className="p-6">
          <div className="space-y-4">
            {analyticsData.topSources?.map((source, index) => (
              <div key={index} className="flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                <div className="flex items-center gap-4">
                  <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                  <div>
                    <h3 className="font-semibold text-gray-900">{source.source}</h3>
                    <p className="text-sm text-gray-600">{source.leads} לידים</p>
                  </div>
                </div>
                <div className="text-left">
                  <div className="font-bold text-green-600">{source.conversion}</div>
                  <div className="text-sm text-gray-500">המרה</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <ModernLayout userRole={userRole}>
      <div className="space-y-8">
        {/* Header Section */}
        <div className="bg-gradient-to-r from-purple-600 to-pink-700 rounded-3xl p-8 text-white">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-2 flex items-center gap-3">
                <BarChart3 className="w-10 h-10" />
                📊 דוחות ואנליטיקה
              </h1>
              <p className="text-purple-100 text-lg">
                {userRole === 'admin' 
                  ? 'תובנות עסקיות על כל המערכת'
                  : 'נתונים מפורטים על הביצועים העסקיים שלך'
                }
              </p>
            </div>
            <div className="text-left">
              <select
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                className="bg-white/20 border border-white/30 rounded-xl px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-white/50"
              >
                <option value="7d" className="text-gray-900">7 ימים אחרונים</option>
                <option value="30d" className="text-gray-900">30 ימים אחרונים</option>
                <option value="90d" className="text-gray-900">3 חודשים אחרונים</option>
                <option value="1y" className="text-gray-900">שנה אחרונה</option>
              </select>
            </div>
          </div>
        </div>

        {/* Analytics Content */}
        {userRole === 'admin' ? <AdminAnalytics /> : <BusinessAnalytics />}

        {/* Quick Insights */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <LineChart className="w-6 h-6 text-blue-600" />
              תובנות מרכזיות
            </h3>
            <div className="space-y-3">
              <div className="flex items-center gap-3 p-3 bg-green-50 rounded-lg">
                <CheckCircle className="w-5 h-5 text-green-600" />
                <span className="text-sm text-green-800">
                  {userRole === 'admin' 
                    ? 'המערכת צומחת ב-23% השבוע'
                    : 'שיעור ההמרה שלך גבוה ב-15% מהממוצע'
                  }
                </span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-blue-50 rounded-lg">
                <Activity className="w-5 h-5 text-blue-600" />
                <span className="text-sm text-blue-800">
                  {userRole === 'admin'
                    ? 'זמן תגובה ממוצע: 1.2 שניות'
                    : 'זמן השיחות הממוצע עלה ב-12%'
                  }
                </span>
              </div>
              <div className="flex items-center gap-3 p-3 bg-purple-50 rounded-lg">
                <Star className="w-5 h-5 text-purple-600" />
                <span className="text-sm text-purple-800">
                  {userRole === 'admin'
                    ? 'שביעות רצון לקוחות: 4.8/5'
                    : 'המקור הטוב ביותר: המלצות (95% המרה)'
                  }
                </span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
            <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center gap-2">
              <Calendar className="w-6 h-6 text-orange-600" />
              יעדים השבוע
            </h3>
            <div className="space-y-4">
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {userRole === 'admin' ? 'עסקים חדשים' : 'שיחות חדשות'}
                  </span>
                  <span className="text-sm text-gray-500">85%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full" style={{width: '85%'}}></div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {userRole === 'admin' ? 'הכנסות יעד' : 'לידים יעד'}
                  </span>
                  <span className="text-sm text-gray-500">72%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-green-600 h-2 rounded-full" style={{width: '72%'}}></div>
                </div>
              </div>
              
              <div>
                <div className="flex justify-between items-center mb-2">
                  <span className="text-sm font-medium text-gray-700">שביעות רצון</span>
                  <span className="text-sm text-gray-500">94%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div className="bg-purple-600 h-2 rounded-full" style={{width: '94%'}}></div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </ModernLayout>
  );
}