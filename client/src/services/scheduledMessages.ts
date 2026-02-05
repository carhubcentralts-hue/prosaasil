/**
 * Scheduled WhatsApp Messages API Client
 * Manages scheduling rules and message queue
 */
import { http } from './http';

export interface RuleStep {
  id: number;
  step_index: number;
  message_template: string;
  delay_seconds: number;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface ScheduledRule {
  id: number;
  name: string;
  is_active: boolean;
  message_text: string;
  delay_minutes: number;
  delay_seconds?: number;  // NEW: Delay in seconds (preferred over delay_minutes)
  provider?: string;  // NEW: "baileys" | "meta" | "auto" - WhatsApp provider choice
  template_name?: string;
  send_window_start?: string;
  send_window_end?: string;
  send_immediately_on_enter?: boolean;
  immediate_message?: string;  // NEW: Message to send immediately on entering status (if different from scheduled message)
  apply_mode?: string;  // "ON_ENTER_ONLY" | "WHILE_IN_STATUS"
  steps?: Array<RuleStep>;
  active_weekdays?: number[] | null;  // NEW: Array of weekday indices [0-6] where 0=Sunday, null=all days
  schedule_type?: string;  // NEW: "STATUS_CHANGE" | "RECURRING_TIME" - scheduling mode
  recurring_times?: string[] | null;  // NEW: Array of times in "HH:MM" format, e.g. ["09:00", "15:00"]
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
  delay_minutes?: number;  // Optional for backward compatibility
  delay_seconds?: number;  // NEW: Preferred over delay_minutes
  provider?: string;  // NEW: "baileys" | "meta" | "auto" - defaults to "baileys"
  template_name?: string;
  send_window_start?: string;
  send_window_end?: string;
  is_active?: boolean;
  send_immediately_on_enter?: boolean;
  immediate_message?: string;  // NEW: Message to send immediately on entering status
  apply_mode?: string;
  steps?: Array<{step_index: number, message_template: string, delay_seconds: number, enabled?: boolean}>;
  schedule_type?: string;  // NEW: "STATUS_CHANGE" | "RECURRING_TIME"
  recurring_times?: string[];  // NEW: Array of times in "HH:MM" format
  active_weekdays?: number[] | null;  // NEW: Array of weekday indices [0-6] where 0=Sunday, null=all days
}

export interface UpdateRuleRequest {
  name?: string;
  message_text?: string;
  status_ids?: number[];
  delay_minutes?: number;
  delay_seconds?: number;  // NEW: Preferred over delay_minutes
  provider?: string;  // NEW: "baileys" | "meta" | "auto"
  template_name?: string;
  send_window_start?: string;
  send_window_end?: string;
  is_active?: boolean;
  send_immediately_on_enter?: boolean;
  immediate_message?: string;  // NEW: Message to send immediately on entering status
  apply_mode?: string;
  steps?: Array<{step_index: number, message_template: string, delay_seconds: number, enabled?: boolean}>;
  schedule_type?: string;  // NEW: "STATUS_CHANGE" | "RECURRING_TIME"
  recurring_times?: string[];  // NEW: Array of times in "HH:MM" format
  active_weekdays?: number[] | null;  // NEW: Array of weekday indices [0-6] where 0=Sunday, null=all days
}

export interface ManualTemplate {
  id: number;
  name: string;
  message_text: string;
  created_at?: string;
  updated_at?: string;
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
    const response = await http.get<any>(url);
    
    // Guard: http.get returns the parsed JSON directly, check if it has rules property
    const rules = Array.isArray(response?.rules) ? response.rules : [];
    
    return rules;
  } catch (err: any) {
    const status = err?.status;
    
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
  const response = await http.post<any>('/api/scheduled-messages/rules', data);
  return response?.rule || response;
}

/**
 * Update an existing scheduling rule
 */
export async function updateRule(ruleId: number, data: UpdateRuleRequest): Promise<ScheduledRule> {
  const response = await http.patch<any>(`/api/scheduled-messages/rules/${ruleId}`, data);
  return response?.rule || response;
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
  const response = await http.post<any>(`/api/scheduled-messages/rules/${ruleId}/cancel-pending`);
  return response;
}

// === RULE STEPS API ===

/**
 * Add a new step to a scheduling rule
 */
export async function addRuleStep(
  ruleId: number,
  data: {step_index: number, message_template: string, delay_seconds: number, enabled?: boolean}
): Promise<RuleStep> {
  const response = await http.post<any>(`/api/scheduled-messages/rules/${ruleId}/steps`, data);
  return response?.step || response;
}

/**
 * Update an existing rule step
 */
export async function updateRuleStep(
  ruleId: number,
  stepId: number,
  data: {message_template?: string, delay_seconds?: number, enabled?: boolean}
): Promise<RuleStep> {
  const response = await http.patch<any>(`/api/scheduled-messages/rules/${ruleId}/steps/${stepId}`, data);
  return response?.step || response;
}

/**
 * Delete a rule step
 */
export async function deleteRuleStep(ruleId: number, stepId: number): Promise<void> {
  await http.delete(`/api/scheduled-messages/rules/${ruleId}/steps/${stepId}`);
}

/**
 * Reorder rule steps
 */
export async function reorderRuleSteps(ruleId: number, step_ids: number[]): Promise<void> {
  await http.put(`/api/scheduled-messages/rules/${ruleId}/steps/reorder`, { step_ids });
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
  const response = await http.get<QueueResponse>(url);
  return response;
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
  const response = await http.get<StatsResponse>(url);
  return response;
}

// === TEMPLATES API ===

/**
 * Get all WhatsApp manual templates
 */
export async function getManualTemplates(): Promise<ManualTemplate[]> {
  try {
    const response = await http.get<any>('/api/whatsapp/manual-templates');
    // API returns {templates: [...]} not {items: [...]}
    const templates = Array.isArray(response?.templates) ? response.templates : [];
    return templates;
  } catch (err: any) {
    console.warn('Failed to load templates:', err);
    return [];
  }
}
