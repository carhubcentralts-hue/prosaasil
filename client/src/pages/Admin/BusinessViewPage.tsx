import React from 'react';
import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { 
  ArrowRight, 
  Building2, 
  Phone, 
  MessageSquare, 
  Users, 
  Calendar,
  Activity,
  Eye,
  UserCheck
} from 'lucide-react';
import { businessAPI } from '../../features/businesses/api';

interface BusinessOverview {
  id: number;
  name: string;
  business_type: string;
  phone_e164: string;
  whatsapp_number: string;
  status: string;
  whatsapp_status: string;
  call_status: string;
  created_at: string;
  stats: {
    total_calls: number;
    total_whatsapp: number;
    total_customers: number;
    users_count: number;
  };
  recent_calls: Array<{
    id: number;
    from_number: string;
    status: string;
    created_at: string;
  }>;
  recent_whatsapp: Array<{
    id: number;
    from_number: string;
    direction: string;
    created_at: string;
  }>;
}

export function BusinessViewPage() {
  const { businessId } = useParams<{ businessId: string }>();
  const navigate = useNavigate();
  const [business, setBusiness] = useState<BusinessOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!businessId) {
      navigate('/app/admin/businesses');
      return;
    }

    const loadBusinessOverview = async () => {
      try {
        setLoading(true);
        console.log(`🔍 Loading business overview for ID: ${businessId}`);
        const data = await businessAPI.getBusinessOverview(parseInt(businessId));
        setBusiness(data);
      } catch (err) {
        console.error('❌ Failed to load business overview:', err);
        setError(err instanceof Error ? err.message : 'שגיאה בטעינת נתוני העסק');
      } finally {
        setLoading(false);
      }
    };

    loadBusinessOverview();
  }, [businessId, navigate]);

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 ml-3"></div>
          <span className="text-slate-600">טוען נתוני עסק...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <div className="text-red-700 mb-4">
            <Building2 className="h-12 w-12 mx-auto mb-4 text-red-300" />
            <h3 className="text-lg font-medium">שגיאה בטעינת העסק</h3>
            <p className="text-sm mt-2">{error}</p>
          </div>
          <button
            onClick={() => navigate('/app/admin/businesses')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            חזרה לרשימת עסקים
          </button>
        </div>
      </div>
    );
  }

  if (!business) {
    return (
      <div className="p-6">
        <div className="text-center">
          <Building2 className="h-12 w-12 mx-auto mb-4 text-slate-300" />
          <h3 className="text-lg font-medium text-slate-900">עסק לא נמצא</h3>
          <button
            onClick={() => navigate('/app/admin/businesses')}
            className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            חזרה לרשימת עסקים
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => navigate('/app/admin/businesses')}
            className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ArrowRight className="h-5 w-5" />
          </button>
          <Eye className="h-6 w-6 text-blue-600" />
          <h1 className="text-2xl font-bold text-slate-900">צפייה בעסק (מצב אדמין)</h1>
        </div>
        
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-center gap-2 text-blue-800">
            <Eye className="h-4 w-4" />
            <span className="text-sm font-medium">
              מצב צפייה בלבד - אין שינוי סשן
            </span>
          </div>
        </div>
      </div>

      {/* Business Info */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-6">
        <div className="flex items-start justify-between mb-4">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
              <Building2 className="h-8 w-8 text-white" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-slate-900">{business.name}</h2>
              <p className="text-slate-600">{business.business_type}</p>
              <p className="text-sm text-slate-500">ID: {business.id}</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${
              business.status === 'active' 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            }`}>
              {business.status === 'active' ? 'פעיל' : 'מושעה'}
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
            <Phone className="h-5 w-5 text-slate-400" />
            <div>
              <p className="text-xs text-slate-500">טלפון</p>
              <p className="font-medium direction-ltr">{business.phone_e164 || 'לא הוגדר'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
            <MessageSquare className="h-5 w-5 text-slate-400" />
            <div>
              <p className="text-xs text-slate-500">WhatsApp</p>
              <p className="font-medium direction-ltr">{business.whatsapp_number || 'לא הוגדר'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-slate-50 rounded-lg">
            <Calendar className="h-5 w-5 text-slate-400" />
            <div>
              <p className="text-xs text-slate-500">נוצר</p>
              <p className="font-medium">{formatDate(business.created_at)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-6">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">שיחות</p>
              <p className="text-2xl font-bold text-slate-900">{business.stats.total_calls}</p>
            </div>
            <Phone className="h-8 w-8 text-blue-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">WhatsApp</p>
              <p className="text-2xl font-bold text-slate-900">{business.stats.total_whatsapp}</p>
            </div>
            <MessageSquare className="h-8 w-8 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">לקוחות</p>
              <p className="text-2xl font-bold text-slate-900">{business.stats.total_customers}</p>
            </div>
            <UserCheck className="h-8 w-8 text-purple-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-600">משתמשים</p>
              <p className="text-2xl font-bold text-slate-900">{business.stats.users_count}</p>
            </div>
            <Users className="h-8 w-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Calls */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <Phone className="h-5 w-5 text-blue-500" />
            שיחות אחרונות
          </h3>
          {business.recent_calls.length > 0 ? (
            <div className="space-y-3">
              {business.recent_calls.map((call) => (
                <div key={call.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div>
                    <p className="font-medium direction-ltr">{call.from_number}</p>
                    <p className="text-sm text-slate-500">{call.status}</p>
                  </div>
                  <div className="text-left">
                    <p className="text-sm text-slate-500">{formatDate(call.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">אין שיחות אחרונות</p>
          )}
        </div>

        {/* Recent WhatsApp */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
          <h3 className="text-lg font-semibold text-slate-900 mb-4 flex items-center gap-2">
            <MessageSquare className="h-5 w-5 text-green-500" />
            הודעות WhatsApp אחרונות
          </h3>
          {business.recent_whatsapp.length > 0 ? (
            <div className="space-y-3">
              {business.recent_whatsapp.map((msg) => (
                <div key={msg.id} className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
                  <div>
                    <p className="font-medium direction-ltr">{msg.from_number}</p>
                    <p className="text-sm text-slate-500">
                      {msg.direction === 'incoming' ? 'נכנסת' : 'יוצאת'}
                    </p>
                  </div>
                  <div className="text-left">
                    <p className="text-sm text-slate-500">{formatDate(msg.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-center py-8">אין הודעות אחרונות</p>
          )}
        </div>
      </div>
    </div>
  );
}