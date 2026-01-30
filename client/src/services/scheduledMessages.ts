/**
 * Scheduled WhatsApp Messages API Client
 * Manages scheduling rules and message queue
 */
import { http } from './http';

export interface ScheduledRule {
  id: number;
  name: string;
  is_active: boolean;
  message_text: string;
  delay_minutes: number;
  template_name?: string;
  send_window_start?: string;
  send_window_end?: string;
  statuses: Array<{
    id: number;
    name: string;
    label: string;
    color?: string;
  }>;
  created_by_user_id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface QueueMessage {
  id: number;
  rule_id: number;
  rule_name?: string;
  lead_id: number;
  lead_name?: string;
  message_text: string;
  remote_jid: string;
  scheduled_for: string;
  status: 'pending' | 'sent' | 'failed' | 'canceled';
  sent_at?: string;
  error_message?: string;
  created_at?: string;
}

export interface QueueResponse {
  items: QueueMessage[];
  total: number;
  page: number;
  per_page: number;
}

export interface StatsResponse {
  pending: number;
  sent: number;
  failed: number;
  canceled: number;
}

export interface CreateRuleRequest {
  name: string;
  message_text: string;
  status_ids: number[];
  delay_minutes: number;
  template_name?: string;
  send_window_start?: string;
  send_window_end?: string;
  is_active?: boolean;
}

export interface UpdateRuleRequest {
  name?: string;
  message_text?: string;
  status_ids?: number[];
  delay_minutes?: number;
  template_name?: string;
  send_window_start?: string;
  send_window_end?: string;
  is_active?: boolean;
}

// === RULES API ===

/**
 * Get all scheduling rules
 */
export async function getRules(isActive?: boolean): Promise<ScheduledRule[]> {
  const params = new URLSearchParams();
  if (isActive !== undefined) {
    params.append('is_active', String(isActive));
  }
  
  const url = `/api/scheduled-messages/rules${params.toString() ? '?' + params.toString() : ''}`;
  
  try {
    const response = await http.get(url);
    
    // Guard: ensure data exists and has rules property
    const payload = response?.data ?? {};
    const rules = Array.isArray(payload.rules) ? payload.rules : [];
    
    return rules;
  } catch (err: any) {
    const status = err?.response?.status;
    
    // If 401 or 403 - no permission or feature disabled, return empty array
    // Don't crash the UI
    if (status === 401 || status === 403) {
      console.warn('No permission to access scheduled messages:', status);
      return [];
    }
    
    // For other errors, rethrow
    throw err;
  }
}

/**
 * Create a new scheduling rule
 */
export async function createRule(data: CreateRuleRequest): Promise<ScheduledRule> {
  const response = await http.post('/api/scheduled-messages/rules', data);
  return response.data.rule;
}

/**
 * Update an existing scheduling rule
 */
export async function updateRule(ruleId: number, data: UpdateRuleRequest): Promise<ScheduledRule> {
  const response = await http.patch(`/api/scheduled-messages/rules/${ruleId}`, data);
  return response.data.rule;
}

/**
 * Delete a scheduling rule
 */
export async function deleteRule(ruleId: number): Promise<void> {
  await http.delete(`/api/scheduled-messages/rules/${ruleId}`);
}

/**
 * Cancel all pending messages for a rule
 */
export async function cancelPendingForRule(ruleId: number): Promise<{ cancelled_count: number }> {
  const response = await http.post(`/api/scheduled-messages/rules/${ruleId}/cancel-pending`);
  return response.data;
}

// === QUEUE API ===

/**
 * Get scheduled messages queue with pagination
 */
export async function getQueue(params?: {
  rule_id?: number;
  status?: string;
  page?: number;
  per_page?: number;
}): Promise<QueueResponse> {
  const searchParams = new URLSearchParams();
  if (params?.rule_id) searchParams.append('rule_id', String(params.rule_id));
  if (params?.status) searchParams.append('status', params.status);
  if (params?.page) searchParams.append('page', String(params.page));
  if (params?.per_page) searchParams.append('per_page', String(params.per_page));
  
  const url = `/api/scheduled-messages/queue${searchParams.toString() ? '?' + searchParams.toString() : ''}`;
  const response = await http.get(url);
  return response.data;
}

/**
 * Cancel a pending message
 */
export async function cancelMessage(messageId: number): Promise<void> {
  await http.post(`/api/scheduled-messages/queue/${messageId}/cancel`);
}

// === STATS API ===

/**
 * Get statistics for scheduled messages
 */
export async function getStats(ruleId?: number): Promise<StatsResponse> {
  const params = new URLSearchParams();
  if (ruleId) params.append('rule_id', String(ruleId));
  
  const url = `/api/scheduled-messages/stats${params.toString() ? '?' + params.toString() : ''}`;
  const response = await http.get(url);
  return response.data;
}
