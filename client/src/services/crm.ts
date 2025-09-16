import { http } from './http';

// CRM Types
export interface CRMTask {
  id: string;
  title: string;
  description?: string;
  status: 'todo' | 'doing' | 'done';
  priority: 'low' | 'medium' | 'high';
  owner_id?: number;
  lead_id?: number;
  due_date?: string;
  created_at: string;
  updated_at: string;
}

export interface CRMContact {
  id: string;
  name: string;
  email?: string;
  phone?: string;
  company?: string;
  notes?: string;
  tags: string[];
  created_at: string;
}

// CRM Service
class CRMService {
  // Tasks Management
  async getTasks(params: {
    tenant?: number;
    status?: string;
    owner?: number;
    q?: string;
  } = {}): Promise<{ items: CRMTask[]; total: number }> {
    const query = new URLSearchParams();
    if (params.tenant) query.set('tenant', params.tenant.toString());
    if (params.status) query.set('status', params.status);
    if (params.owner) query.set('owner', params.owner.toString());
    if (params.q) query.set('q', params.q);
    
    return http.get(`/api/crm/tasks?${query}`);
  }

  async createTask(data: {
    title: string;
    description?: string;
    status?: 'todo' | 'doing' | 'done';
    priority?: 'low' | 'medium' | 'high';
    owner_id?: number;
    lead_id?: number;
    due_date?: string;
  }): Promise<CRMTask> {
    return http.post('/api/crm/tasks', data);
  }

  async updateTask(taskId: string, data: Partial<CRMTask>): Promise<CRMTask> {
    return http.patch(`/api/crm/tasks/${taskId}`, data);
  }

  async deleteTask(taskId: string): Promise<void> {
    return http.delete(`/api/crm/tasks/${taskId}`);
  }

  // Contacts Management
  async getContacts(params: {
    tenant?: number;
    q?: string;
  } = {}): Promise<{ items: CRMContact[]; total: number }> {
    const query = new URLSearchParams();
    if (params.tenant) query.set('tenant', params.tenant.toString());
    if (params.q) query.set('q', params.q);
    
    return http.get(`/api/crm/contacts?${query}`);
  }

  async createContact(data: {
    name: string;
    email?: string;
    phone?: string;
    company?: string;
    notes?: string;
    tags?: string[];
  }): Promise<CRMContact> {
    return http.post('/api/crm/contacts', data);
  }

  async updateContact(contactId: string, data: Partial<CRMContact>): Promise<CRMContact> {
    return http.patch(`/api/crm/contacts/${contactId}`, data);
  }

  async deleteContact(contactId: string): Promise<void> {
    return http.delete(`/api/crm/contacts/${contactId}`);
  }
}

export const crmService = new CRMService();