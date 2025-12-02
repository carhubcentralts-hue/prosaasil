// business dashboard API functions
import { http } from '../../services/http';

export type TimeFilter = 'today' | '7days' | '30days' | 'custom';

export interface DateRange {
  from: Date;
  to: Date;
}

export interface BusinessDashboardStats {
  calls: {
    today: number;
    last7d: number;
    avgHandleSec: number;
  };
  whatsapp: {
    today: number;
    last7d: number;
    unread: number;
  };
  revenue: {
    thisMonth: number;
    ytd: number;
  };
  filter?: {
    type: string;
    start: string;
    end: string;
  };
}

export interface BusinessActivity {
  ts: string;
  type: 'call' | 'whatsapp';
  leadId?: number;
  preview: string;
  provider: string;
}

export interface BusinessActivityResponse {
  items: BusinessActivity[];
}

export const businessApi = {
  getDashboardStats: async (timeFilter: TimeFilter = 'today', dateRange?: DateRange): Promise<BusinessDashboardStats> => {
    const params = new URLSearchParams();
    params.append('time_filter', timeFilter);
    
    if (timeFilter === 'custom' && dateRange) {
      params.append('start_date', dateRange.from.toISOString().split('T')[0]);
      params.append('end_date', dateRange.to.toISOString().split('T')[0]);
    }
    
    return await http.get<BusinessDashboardStats>(`/api/dashboard/stats?${params.toString()}`);
  },
  
  getDashboardActivity: async (timeFilter: TimeFilter = 'today', dateRange?: DateRange): Promise<BusinessActivity[]> => {
    const params = new URLSearchParams();
    params.append('time_filter', timeFilter);
    
    if (timeFilter === 'custom' && dateRange) {
      params.append('start_date', dateRange.from.toISOString().split('T')[0]);
      params.append('end_date', dateRange.to.toISOString().split('T')[0]);
    }
    
    const response = await http.get<BusinessActivityResponse>(`/api/dashboard/activity?${params.toString()}`);
    return response.items || [];
  }
};