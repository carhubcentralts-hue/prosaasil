import { http } from './http';

// Billing Types
export interface BillingDoc {
  id: string;
  type: 'contract' | 'invoice' | 'payment-link';
  lead_id: number;
  amount?: number;
  currency?: string;
  link: string;
  status: 'sent' | 'viewed' | 'signed' | 'paid' | 'expired';
  created_at: string;
  expires_at?: string;
}

export interface ContractTemplate {
  id: string;
  name: string;
  content: string;
  variables: string[];
}

// Billing Service
class BillingService {
  // Contract Management
  async createContract(data: {
    lead_id: number;
    template_id?: string;
    vars?: Record<string, any>;
  }): Promise<{ link: string; status: string }> {
    return http.post('/api/billing/contract', data);
  }

  async getContractTemplates(): Promise<ContractTemplate[]> {
    return http.get('/api/billing/contract-templates');
  }

  // Invoice Management
  async createInvoice(data: {
    lead_id: number;
    amount: number;
    currency?: string;
    description?: string;
  }): Promise<{ link: string; status: string }> {
    return http.post('/api/billing/invoice', data);
  }

  // Payment Links
  async createPaymentLink(data: {
    lead_id: number;
    amount: number;
    currency?: string;
    description?: string;
  }): Promise<{ link: string; expires_at: string }> {
    return http.post('/api/billing/payment-link', data);
  }

  // History
  async getBillingHistory(params: {
    lead_id?: number;
    type?: 'contract' | 'invoice' | 'payment-link';
  } = {}): Promise<{ items: BillingDoc[] }> {
    const query = new URLSearchParams();
    if (params.lead_id) query.set('lead_id', params.lead_id.toString());
    if (params.type) query.set('type', params.type);
    
    return http.get(`/api/billing/history?${query}`);
  }

  // Document Preview
  getDocumentUrl(docId: string): string {
    return `/api/billing/docs/${docId}`;
  }
}

export const billingService = new BillingService();