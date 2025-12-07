// ✅ Type fix: LeadStatus is now a string to support dynamic statuses from API
export type LeadStatus = string;

export type LeadSource = 'phone' | 'whatsapp';

export interface Lead {
  id: number;
  tenant_id: number;
  business_id?: number;
  business_name?: string;
  first_name?: string;
  last_name?: string;
  name?: string; // ✅ Server returns this field
  phone?: string; // ✅ Server returns this field  
  phone_e164?: string;
  email?: string;
  source: LeadSource;
  external_id?: string;
  status: LeadStatus;
  order_index?: number;
  owner_user_id?: number;
  tags?: string[];
  notes?: string;
  created_at: string;
  updated_at: string;
  last_contact_at?: string;
  full_name?: string;
  display_phone?: string;
  whatsapp_last_summary?: string;
  whatsapp_last_summary_at?: string;
}

export interface LeadReminder {
  id: number;
  lead_id: number;
  due_at: string;
  note?: string;
  channel: 'ui' | 'email' | 'push' | 'whatsapp';
  delivered_at?: string;
  completed_at?: string;
  created_by?: number;
}

export interface LeadActivity {
  id: number;
  lead_id: number;
  type: string;
  payload?: any;
  at: string;
  created_by?: number;
}

export interface LeadCall {
  id: number;
  lead_id: number;
  call_type: 'incoming' | 'outgoing';
  duration: number;
  recording_url?: string;
  notes?: string;
  summary?: string;
  created_at: string;
  status: 'completed' | 'missed' | 'busy';
}

export interface LeadAppointment {
  id: number;
  title: string;
  description?: string;
  start_time: string;
  end_time: string;
  location?: string;
  status: 'scheduled' | 'confirmed' | 'paid' | 'unpaid' | 'cancelled' | string;
  appointment_type?: 'viewing' | 'meeting' | 'signing' | 'call_followup' | 'phone_call' | string;
  priority?: 'low' | 'medium' | 'high' | 'urgent' | string;
  contact_name?: string;
  contact_phone?: string;
  notes?: string;
  call_summary?: string;
}

export interface LeadConversation {
  id: number;
  lead_id: number;
  platform: 'whatsapp' | 'sms' | 'email';
  direction: 'incoming' | 'outgoing';
  message: string;
  created_at: string;
  read: boolean;
}

export interface LeadTask {
  id: number;
  lead_id: number;
  title: string;
  description?: string;
  due_date?: string;
  completed: boolean;
  created_at: string;
  priority: 'low' | 'medium' | 'high';
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