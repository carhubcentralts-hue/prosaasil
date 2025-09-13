export type LeadStatus = 
  | 'New' 
  | 'Attempting' 
  | 'Contacted' 
  | 'Qualified' 
  | 'Won' 
  | 'Lost' 
  | 'Unqualified';

export type LeadSource = 'call' | 'whatsapp' | 'form' | 'manual';

export interface Lead {
  id: number;
  tenant_id: number;
  first_name: string;
  last_name: string;
  phone_e164?: string;
  email?: string;
  source: LeadSource;
  external_id?: string;
  status: LeadStatus;
  order_index: number;
  owner_user_id?: number;
  tags?: string[];
  notes?: string;
  created_at: string;
  updated_at: string;
  last_contact_at?: string;
  full_name: string;
  display_phone?: string;
}

export interface LeadReminder {
  id: number;
  lead_id: number;
  due_at: string;
  note?: string;
  channel: 'ui' | 'email' | 'push' | 'whatsapp';
  delivered_at?: string;
  completed_at?: string;
  created_at: string;
  created_by?: number;
}

export interface LeadActivity {
  id: number;
  lead_id: number;
  type: string;
  payload?: Record<string, any>;
  at: string;
  created_by?: number;
}

export interface LeadFilters {
  search?: string;
  status?: LeadStatus;
  source?: LeadSource;
  owner_user_id?: number;
  page?: number;
  pageSize?: number;
}

export interface MoveLeadRequest {
  status?: LeadStatus;
  beforeId?: number;
  afterId?: number;
}

export interface CreateLeadRequest {
  first_name: string;
  last_name: string;
  phone_e164?: string;
  email?: string;
  source?: LeadSource;
  status?: LeadStatus;
  notes?: string;
  tags?: string[];
}

export interface UpdateLeadRequest extends Partial<CreateLeadRequest> {
  owner_user_id?: number;
}

export interface BulkUpdateRequest {
  lead_ids: number[];
  updates: {
    status?: LeadStatus;
    owner_user_id?: number;
    tags?: string[];
  };
}