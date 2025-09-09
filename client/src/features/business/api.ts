// business dashboard API functions
import { http } from '../../services/http';

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
  getDashboardStats: async (): Promise<BusinessDashboardStats> => {
    return await http.get<BusinessDashboardStats>('/api/dashboard/stats');
  },
  
  getDashboardActivity: async (): Promise<BusinessActivity[]> => {
    const response = await http.get<BusinessActivityResponse>('/api/dashboard/activity');
    return response.items || [];
  }
};