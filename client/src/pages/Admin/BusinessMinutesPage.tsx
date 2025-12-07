import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { 
  Clock, 
  Phone, 
  PhoneIncoming, 
  PhoneOutgoing, 
  Loader2,
  Calendar,
  Building2,
  AlertCircle,
  Download
} from 'lucide-react';
import { cn } from '../../shared/utils/cn';

interface DirectionBreakdown {
  inbound_seconds: number;
  inbound_minutes: number;
  inbound_calls: number;
  outbound_seconds: number;
  outbound_minutes: number;
  outbound_calls: number;
}

interface BusinessMinutesData {
  business_id: number;
  business_name: string;
  total_seconds: number;
  total_minutes: number;
  total_calls: number;
  direction_breakdown: DirectionBreakdown;
}

interface BusinessMinutesResponse {
  businesses: BusinessMinutesData[];
  summary: {
    total_businesses: number;
    total_seconds: number;
    total_minutes: number;
    total_calls: number;
  };
  date_range: {
    from: string;
    to: string;
  };
}

type DateRange = 'today' | 'this_week' | 'this_month' | 'last_30_days' | 'last_month' | 'last_3_months' | 'this_year' | 'custom';

export function BusinessMinutesPage() {
  const [dateRange, setDateRange] = useState<DateRange>('today');
  const [customFrom, setCustomFrom] = useState<string>('');
  const [customTo, setCustomTo] = useState<string>('');

  const { fromDate, toDate } = useMemo(() => {
    const today = new Date();
    let from: Date, to: Date;

    switch (dateRange) {
      case 'today':
        from = today;
        to = today;
        break;
      case 'this_week':
        from = new Date(today);
        from.setDate(from.getDate() - 7);
        to = today;
        break;
      case 'this_month':
        from = new Date(today.getFullYear(), today.getMonth(), 1);
        to = today;
        break;
      case 'last_30_days':
        from = new Date(today);
        from.setDate(from.getDate() - 30);
        to = today;
        break;
      case 'last_month':
        from = new Date(today.getFullYear(), today.getMonth() - 1, 1);
        to = new Date(today.getFullYear(), today.getMonth(), 0);
        break;
      case 'last_3_months':
        from = new Date(today);
        from.setMonth(from.getMonth() - 3);
        to = today;
        break;
      case 'this_year':
        from = new Date(today.getFullYear(), 0, 1);
        to = today;
        break;
      case 'custom':
        from = customFrom ? new Date(customFrom) : new Date(today.getFullYear(), today.getMonth(), 1);
        to = customTo ? new Date(customTo) : today;
        break;
      default:
        from = new Date(today.getFullYear(), today.getMonth(), 1);
        to = today;
    }

    return {
      fromDate: from.toISOString().split('T')[0],
      toDate: to.toISOString().split('T')[0]
    };
  }, [dateRange, customFrom, customTo]);

  const { data, isLoading, error, refetch } = useQuery<BusinessMinutesResponse>({
    queryKey: ['/api/admin/business-minutes', fromDate, toDate],
    queryFn: async () => {
      const params = new URLSearchParams({
        from: fromDate,
        to: toDate
      });
      const response = await fetch(`/api/admin/business-minutes?${params}`, {
        credentials: 'include'
      });
      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('אין לך הרשאות לצפות בדף זה');
        }
        throw new Error('אירעה שגיאה בטעינת הנתונים');
      }
      return response.json();
    }
  });

  const formatMinutes = (minutes: number): string => {
    if (minutes >= 60) {
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return `${hours}:${mins.toString().padStart(2, '0')} שעות`;
    }
    return `${minutes} דקות`;
  };

  const formatSeconds = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const handleExportCSV = () => {
    if (!data?.businesses) return;
    
    const headers = ['מספר עסק', 'שם עסק', 'סה"כ שניות', 'סה"כ דקות', 'שיחות נכנסות', 'דקות נכנסות', 'שיחות יוצאות', 'דקות יוצאות'];
    const rows = data.businesses.map(b => [
      b.business_id,
      b.business_name,
      b.total_seconds,
      b.total_minutes,
      b.direction_breakdown.inbound_calls || 0,
      b.direction_breakdown.inbound_minutes,
      b.direction_breakdown.outbound_calls || 0,
      b.direction_breakdown.outbound_minutes
    ]);
    
    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');
    
    const blob = new Blob(['\uFEFF' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `business-minutes-${fromDate}-${toDate}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  if (error) {
    return (
      <div className="p-6" data-testid="page-business-minutes">
        <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
          <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-lg font-semibold text-red-800 mb-2">שגיאה</h2>
          <p className="text-red-600">{error.message}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6" data-testid="page-business-minutes">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Clock className="h-8 w-8 text-blue-600" />
          <div>
            <h1 className="text-2xl font-bold text-slate-900">ניהול דקות שיחה</h1>
            <p className="text-slate-500 text-sm">צפייה בשימוש דקות שיחה לפי עסק</p>
          </div>
        </div>
        
        <button
          onClick={handleExportCSV}
          disabled={!data?.businesses?.length}
          className={cn(
            "flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors",
            data?.businesses?.length
              ? "bg-green-600 text-white hover:bg-green-700"
              : "bg-slate-200 text-slate-400 cursor-not-allowed"
          )}
          data-testid="button-export-csv"
        >
          <Download className="h-4 w-4" />
          ייצוא CSV
        </button>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4">
        <div className="flex flex-wrap items-center gap-4">
          <div className="flex items-center gap-2">
            <Calendar className="h-5 w-5 text-slate-400" />
            <label className="text-sm font-medium text-slate-700">טווח תאריכים:</label>
          </div>
          
          <select
            value={dateRange}
            onChange={(e) => setDateRange(e.target.value as DateRange)}
            className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            data-testid="select-date-range"
          >
            <option value="today">היום</option>
            <option value="this_week">7 ימים אחרונים</option>
            <option value="this_month">מתחילת החודש</option>
            <option value="last_30_days">30 ימים אחרונים</option>
            <option value="last_month">החודש הקודם</option>
            <option value="last_3_months">3 חודשים אחרונים</option>
            <option value="this_year">השנה הנוכחית</option>
            <option value="custom">טווח מותאם אישי</option>
          </select>

          {dateRange === 'custom' && (
            <>
              <input
                type="date"
                value={customFrom}
                onChange={(e) => setCustomFrom(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                data-testid="input-date-from"
              />
              <span className="text-slate-400">עד</span>
              <input
                type="date"
                value={customTo}
                onChange={(e) => setCustomTo(e.target.value)}
                className="px-3 py-2 border border-slate-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500"
                data-testid="input-date-to"
              />
            </>
          )}

          {data?.date_range && (
            <div className="flex items-center gap-2">
              <div className="text-sm text-slate-500">
                מציג: {new Date(data.date_range.from).toLocaleDateString('he-IL')} - {new Date(data.date_range.to).toLocaleDateString('he-IL')}
              </div>
              <span className="text-xs text-slate-400">
                ({Math.ceil((new Date(data.date_range.to).getTime() - new Date(data.date_range.from).getTime()) / (1000 * 60 * 60 * 24)) + 1} ימים)
              </span>
            </div>
          )}
        </div>
      </div>

      {data?.summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-blue-100 text-sm">סה"כ דקות</p>
                <p className="text-3xl font-bold mt-1">{formatMinutes(data.summary.total_minutes)}</p>
                <p className="text-blue-200 text-xs mt-1">{data.summary.total_seconds.toLocaleString()} שניות</p>
              </div>
              <Phone className="h-12 w-12 text-blue-200" />
            </div>
          </div>

          <div className="bg-gradient-to-br from-emerald-500 to-emerald-600 rounded-xl p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-emerald-100 text-sm">עסקים פעילים</p>
                <p className="text-3xl font-bold mt-1">{data.summary.total_businesses}</p>
                <p className="text-emerald-200 text-xs mt-1">עסקים עם שיחות</p>
              </div>
              <Building2 className="h-12 w-12 text-emerald-200" />
            </div>
          </div>

          <div className="bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl p-6 text-white">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-purple-100 text-sm">ממוצע לעסק</p>
                <p className="text-3xl font-bold mt-1">
                  {data.summary.total_businesses > 0 
                    ? formatMinutes(Math.round(data.summary.total_minutes / data.summary.total_businesses))
                    : '0 דקות'
                  }
                </p>
                <p className="text-purple-200 text-xs mt-1">דקות ממוצע</p>
              </div>
              <Clock className="h-12 w-12 text-purple-200" />
            </div>
          </div>
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
            <span className="mr-3 text-slate-600">טוען נתוני דקות...</span>
          </div>
        ) : !data?.businesses?.length ? (
          <div className="text-center py-12">
            <Phone className="h-12 w-12 text-slate-300 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-slate-700">אין נתוני שיחות</h3>
            <p className="text-slate-500 mt-1">לא נמצאו שיחות בטווח התאריכים שנבחר</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
          <table className="w-full min-w-[700px]" data-testid="table-business-minutes">
            <thead className="bg-slate-50 border-b border-slate-200">
              <tr>
                <th className="px-6 py-4 text-right text-sm font-semibold text-slate-700">מספר עסק</th>
                <th className="px-6 py-4 text-right text-sm font-semibold text-slate-700">עסק</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-700">דקות שיחה</th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-700">
                  <div className="flex items-center gap-1">
                    <PhoneIncoming className="h-4 w-4 text-green-500" />
                    נכנסות
                  </div>
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-700">
                  <div className="flex items-center gap-1">
                    <PhoneOutgoing className="h-4 w-4 text-blue-500" />
                    יוצאות
                  </div>
                </th>
                <th className="px-6 py-4 text-left text-sm font-semibold text-slate-700">זמן גולמי</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.businesses.map((business, index) => (
                <tr 
                  key={business.business_id}
                  className={cn(
                    "hover:bg-slate-50 transition-colors",
                    index % 2 === 0 ? "bg-white" : "bg-slate-25"
                  )}
                  data-testid={`row-business-${business.business_id}`}
                >
                  <td className="px-6 py-4">
                    <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-slate-100 text-slate-600 text-sm font-medium">
                      {business.business_id}
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-blue-600 flex items-center justify-center text-white font-bold">
                        {business.business_name.charAt(0)}
                      </div>
                      <span className="font-medium text-slate-900">{business.business_name}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-lg font-bold text-slate-900">{business.total_minutes}</div>
                    <div className="text-xs text-slate-500">דקות</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <PhoneIncoming className="h-4 w-4 text-green-500" />
                      <span className="font-medium text-green-700">{business.direction_breakdown.inbound_calls}</span>
                      <span className="text-xs text-slate-400">({formatSeconds(business.direction_breakdown.inbound_seconds)})</span>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex items-center gap-2">
                      <PhoneOutgoing className="h-4 w-4 text-blue-500" />
                      <span className="font-medium text-blue-700">{business.direction_breakdown.outbound_calls}</span>
                      <span className="text-xs text-slate-400">({formatSeconds(business.direction_breakdown.outbound_seconds)})</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 text-left">
                    <code className="px-2 py-1 bg-slate-100 rounded text-sm text-slate-600 tabular-nums">
                      {formatSeconds(business.total_seconds)}
                    </code>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot className="bg-blue-50 border-t-2 border-blue-200">
              <tr>
                <td colSpan={2} className="px-6 py-4 font-bold text-slate-900">
                  סה"כ לכל העסקים
                </td>
                <td className="px-6 py-4">
                  <div className="text-xl font-bold text-blue-600">{data.summary.total_minutes}</div>
                  <div className="text-xs text-slate-500">דקות</div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <PhoneIncoming className="h-4 w-4 text-green-500" />
                    <span className="font-bold text-green-700">
                      {data.businesses.reduce((sum, b) => sum + (b.direction_breakdown.inbound_calls || 0), 0)}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4">
                  <div className="flex items-center gap-2">
                    <PhoneOutgoing className="h-4 w-4 text-blue-500" />
                    <span className="font-bold text-blue-700">
                      {data.businesses.reduce((sum, b) => sum + (b.direction_breakdown.outbound_calls || 0), 0)}
                    </span>
                  </div>
                </td>
                <td className="px-6 py-4 text-left">
                  <code className="px-2 py-1 bg-blue-100 rounded text-sm text-blue-700 font-bold tabular-nums">
                    {formatSeconds(data.summary.total_seconds)}
                  </code>
                </td>
              </tr>
            </tfoot>
          </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default BusinessMinutesPage;
