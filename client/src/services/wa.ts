import { http } from './http';

// WhatsApp Types
export interface WAThread {
  id: string;
  lead_id: number;
  phone_e164: string;
  last_msg: string;
  unread: number;
  provider: 'baileys' | 'twilio';
  updated_at: string;
}

export interface WAMessage {
  id: string;
  from: string;
  to: string;
  text?: string;
  mediaUrl?: string;
  at: string;
  direction: 'inbound' | 'outbound';
}

export interface WAThreadDetail {
  thread: WAThread;
  messages: WAMessage[];
  lead: {
    id: number;
    name: string;
    phone_e164: string;
  };
}

// WhatsApp Service
class WhatsAppService {
  // Get threads list with pagination and filters
  async getThreads(params: {
    tenant?: number;
    q?: string;
    page?: number;
    pageSize?: number;
  } = {}): Promise<{ items: WAThread[]; total: number }> {
    const query = new URLSearchParams();
    if (params.tenant) query.set('tenant', params.tenant.toString());
    if (params.q) query.set('q', params.q);
    if (params.page) query.set('page', params.page.toString());
    if (params.pageSize) query.set('pageSize', params.pageSize.toString());
    
    return http.get(`/api/wa/threads?${query}`);
  }

  // Get specific thread with messages
  async getThread(threadId: string): Promise<WAThreadDetail> {
    return http.get(`/api/wa/threads/${threadId}`);
  }

  // Send message to thread
  async sendMessage(threadId: string, data: {
    text?: string;
    mediaUrl?: string;
    provider?: 'baileys' | 'twilio';
  }): Promise<{ ok: boolean; message: WAMessage }> {
    return http.post(`/api/wa/threads/${threadId}/message`, data);
  }

  // Broadcast message to multiple leads
  async broadcast(data: {
    lead_ids: number[];
    text: string;
  }): Promise<{ ok: boolean; sent: number; failed: number }> {
    return http.post('/api/wa/broadcast', data);
  }

  // Mark thread as read
  async markRead(threadId: string): Promise<void> {
    return http.post(`/api/wa/threads/${threadId}/read`, {});
  }

  // Get provider status
  async getStatus(): Promise<{
    baileys: { ready: boolean; connected: boolean };
    twilio: { ready: boolean; configured: boolean };
  }> {
    return http.get('/api/wa/status');
  }
}

export const waService = new WhatsAppService();