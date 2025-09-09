// admin API functions
import { http } from '../../services/http';

export interface TimeFilterParams {
  time_filter: 'today' | 'week' | 'month' | 'custom';
  start_date?: string;
  end_date?: string;
}

export interface AdminOverviewResponse {
  calls_count: number;
  whatsapp_count: number;
  active_businesses: number;
  total_businesses: number;
  avg_call_duration: number;
  recent_activity: Array<{
    id: string;
    time: string;
    type: 'call' | 'whatsapp';
    tenant: string;
    preview: string;
    status: string;
  }>;
  date_range: {
    start: string;
    end: string;
    filter: string;
  };
  provider_status: {
    twilio: { up: boolean; latency: number | null };
    baileys: { up: boolean; latency: number | null };
    db: { up: boolean; latency: number | null };
    stt: number;
    ai: number;
    tts: number;
  };
}

export const adminApi = {
  getOverview: async (params: TimeFilterParams): Promise<AdminOverviewResponse> => {
    const searchParams = new URLSearchParams();
    searchParams.append('time_filter', params.time_filter);
    if (params.start_date) {
      searchParams.append('start_date', params.start_date);
    }
    if (params.end_date) {
      searchParams.append('end_date', params.end_date);
    }
    
    return await http.get<AdminOverviewResponse>(`/api/admin/overview?${searchParams.toString()}`);
  },
  
  getCallsKPI: async (params: TimeFilterParams): Promise<number> => {
    const searchParams = new URLSearchParams();
    searchParams.append('time_filter', params.time_filter);
    if (params.start_date) {
      searchParams.append('start_date', params.start_date);
    }
    if (params.end_date) {
      searchParams.append('end_date', params.end_date);
    }
    
    const response = await http.get<string>(`/api/admin/kpis/calls?${searchParams.toString()}`);
    return parseInt(response) || 0;
  },
  
  getWhatsappKPI: async (params: TimeFilterParams): Promise<number> => {
    const searchParams = new URLSearchParams();
    searchParams.append('time_filter', params.time_filter);
    if (params.start_date) {
      searchParams.append('start_date', params.start_date);
    }
    if (params.end_date) {
      searchParams.append('end_date', params.end_date);
    }
    
    const response = await http.get<string>(`/api/admin/kpis/whatsapp?${searchParams.toString()}`);
    return parseInt(response) || 0;
  }
};