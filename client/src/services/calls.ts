import { http } from './http';

// Call Types
export interface Call {
  sid: string;
  lead_id?: number;
  from_e164: string;
  to_e164: string;
  duration: number;
  status: string;
  at: string;
  direction: 'inbound' | 'outbound';
}

export interface CallDetail extends Call {
  transcript?: string;
  recordingUrl?: string;
  summary?: string;
}

// Calls Service
class CallsService {
  // Get calls list with filters
  async getCalls(params: {
    tenant?: number;
    q?: string;
    from?: string;
    to?: string;
    page?: number;
    pageSize?: number;
  } = {}): Promise<{ items: Call[]; total: number }> {
    const query = new URLSearchParams();
    if (params.tenant) query.set('tenant', params.tenant.toString());
    if (params.q) query.set('q', params.q);
    if (params.from) query.set('from', params.from);
    if (params.to) query.set('to', params.to);
    if (params.page) query.set('page', params.page.toString());
    if (params.pageSize) query.set('pageSize', params.pageSize.toString());
    
    return http.get(`/api/calls?${query}`);
  }

  // Get specific call details
  async getCall(sid: string): Promise<CallDetail> {
    return http.get(`/api/calls/${sid}`);
  }

  // Start outbound call
  async makeCall(sid: string): Promise<{ ok: boolean; message: string }> {
    return http.post(`/api/calls/${sid}/callback`, {});
  }

  // Create reminder from call
  async createReminder(callSid: string, data: {
    lead_id: number;
    reminder_text: string;
    due_date: string;
  }): Promise<{ ok: boolean; reminder_id: string }> {
    return http.post(`/api/calls/${callSid}/reminder`, data);
  }

  // Download recording
  getRecordingUrl(sid: string): string {
    return `/api/calls/${sid}/recording`;
  }

  // Outbound Queue Management
  async getQueueStatus(jobId: number): Promise<{
    job_id: number;
    status: string;
    total: number;
    processed: number;
    success: number;
    failed: number;
    in_progress: number;
    queued: number;
    progress_pct: number;
    can_cancel: boolean;
    cancel_requested: boolean;
    created_at: string | null;
    completed_at: string | null;
  }> {
    return http.get(`/api/outbound_calls/jobs/${jobId}/status`);
  }

  async cancelQueue(jobId: number): Promise<{ success: boolean; message: string }> {
    return http.post(`/api/outbound_calls/jobs/${jobId}/cancel`, {});
  }

  async getActiveQueue(): Promise<{
    job_id: number;
    status: string;
    total: number;
    processed: number;
    success: number;
    failed: number;
    in_progress: number;
    queued: number;
    progress_pct: number;
    can_cancel: boolean;
    cancel_requested: boolean;
    created_at: string | null;
    completed_at: string | null;
  } | null> {
    try {
      return await http.get('/api/outbound_calls/jobs/active');
    } catch (error: any) {
      // 404 means no active queue - return null
      if (error?.response?.status === 404) {
        return null;
      }
      throw error;
    }
  }
}

export const callsService = new CallsService();