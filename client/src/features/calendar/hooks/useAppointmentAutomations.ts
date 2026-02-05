import { useState, useCallback, useEffect } from 'react';
import { http } from '../../../services/http';

export interface AppointmentAutomation {
  id: number;
  name: string;
  enabled: boolean;
  trigger_status_ids: string[];
  calendar_ids?: number[] | null;  // Optional: filter by specific calendars (null = all calendars)
  appointment_type_keys?: string[] | null;  // Optional: filter by appointment types (null = all types)
  schedule_offsets: Array<{
    type: 'immediate' | 'before' | 'after';
    minutes?: number;
  }>;
  channel: string;
  message_template: string;
  send_once_per_offset: boolean;
  cancel_on_status_exit: boolean;
  active_weekdays?: number[] | null;  // Optional: Array of weekday indices [0-6] where 0=Sunday, null=all days
  created_at?: string;
  updated_at?: string;
}

export interface AutomationTemplate {
  key: string;
  name: string;
  description: string;
}

export interface AutomationRun {
  id: number;
  appointment_id: number;
  offset_signature: string;
  scheduled_for: string;
  status: 'pending' | 'sent' | 'failed' | 'canceled';
  attempts: number;
  last_error?: string;
  created_at: string;
  sent_at?: string;
  canceled_at?: string;
}

interface UseAppointmentAutomationsResult {
  automations: AppointmentAutomation[];
  templates: AutomationTemplate[];
  loading: boolean;
  error: string | null;
  refreshAutomations: () => Promise<void>;
  createAutomation: (data: Partial<AppointmentAutomation>) => Promise<number>;
  updateAutomation: (id: number, data: Partial<AppointmentAutomation>) => Promise<void>;
  deleteAutomation: (id: number) => Promise<void>;
  getAutomationRuns: (id: number, status?: string) => Promise<AutomationRun[]>;
  testAutomationPreview: (id: number, appointmentId?: number) => Promise<{preview: string, context: any}>;
  loadTemplates: () => Promise<void>;
  createFromTemplate: (templateKey: string, name?: string, enabled?: boolean) => Promise<number>;
  setupDefaultAutomations: () => Promise<number>;
}

const LOG_PREFIX = '[useAppointmentAutomations]';

export function useAppointmentAutomations(): UseAppointmentAutomationsResult {
  const [automations, setAutomations] = useState<AppointmentAutomation[]>([]);
  const [templates, setTemplates] = useState<AutomationTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshAutomations = useCallback(async () => {
    console.log(`${LOG_PREFIX} refreshAutomations called`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} Fetching /api/automations/appointments...`);
      const response = await http.get<{success: boolean, automations: AppointmentAutomation[]}>('/api/automations/appointments');
      console.log(`${LOG_PREFIX} Raw response:`, JSON.stringify(response, null, 2));
      
      const automationList = response?.automations || [];
      console.log(`${LOG_PREFIX} Setting ${automationList.length} automations`);
      setAutomations(automationList);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Failed to fetch automations:`, err);
      setError(err instanceof Error ? err.message : 'Failed to fetch automations');
    } finally {
      setLoading(false);
    }
  }, []);

  const loadTemplates = useCallback(async () => {
    console.log(`${LOG_PREFIX} loadTemplates called`);
    try {
      console.log(`${LOG_PREFIX} Fetching /api/automations/appointments/templates...`);
      const response = await http.get<{success: boolean, templates: AutomationTemplate[]}>('/api/automations/appointments/templates');
      console.log(`${LOG_PREFIX} Templates response:`, JSON.stringify(response, null, 2));
      
      const templateList = response?.templates || [];
      console.log(`${LOG_PREFIX} Setting ${templateList.length} templates`);
      setTemplates(templateList);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Failed to fetch templates:`, err);
    }
  }, []);

  useEffect(() => {
    console.log(`${LOG_PREFIX} Initial mount - calling refreshAutomations and loadTemplates`);
    refreshAutomations();
    loadTemplates();
  }, [refreshAutomations, loadTemplates]);

  const createAutomation = useCallback(async (data: Partial<AppointmentAutomation>): Promise<number> => {
    console.log(`${LOG_PREFIX} createAutomation called with:`, JSON.stringify(data, null, 2));
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} POSTing to /api/automations/appointments...`);
      const response = await http.post<{success: boolean, automation_id: number, message: string}>('/api/automations/appointments', data);
      console.log(`${LOG_PREFIX} Create response:`, JSON.stringify(response, null, 2));
      
      // Refresh the list
      await refreshAutomations();
      
      console.log(`${LOG_PREFIX} Successfully created automation with ID ${response.automation_id}`);
      return response.automation_id;
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Create automation FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה ביצירת אוטומציה';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [refreshAutomations]);

  const updateAutomation = useCallback(async (id: number, data: Partial<AppointmentAutomation>): Promise<void> => {
    console.log(`${LOG_PREFIX} updateAutomation called for ID ${id} with:`, JSON.stringify(data, null, 2));
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} PUTing to /api/automations/appointments/${id}...`);
      const response = await http.put<{success: boolean, message: string}>(`/api/automations/appointments/${id}`, data);
      console.log(`${LOG_PREFIX} Update response:`, JSON.stringify(response, null, 2));
      
      // Refresh the list
      await refreshAutomations();
      
      console.log(`${LOG_PREFIX} Successfully updated automation ${id}`);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Update automation FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה בעדכון אוטומציה';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [refreshAutomations]);

  const deleteAutomation = useCallback(async (id: number): Promise<void> => {
    console.log(`${LOG_PREFIX} deleteAutomation called for ID ${id}`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} DELETEing /api/automations/appointments/${id}...`);
      const response = await http.delete<{success: boolean, message: string}>(`/api/automations/appointments/${id}`);
      console.log(`${LOG_PREFIX} Delete response:`, JSON.stringify(response, null, 2));
      
      // Refresh the list
      await refreshAutomations();
      
      console.log(`${LOG_PREFIX} Successfully deleted automation ${id}`);
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Delete automation FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה במחיקת אוטומציה';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [refreshAutomations]);

  const getAutomationRuns = useCallback(async (id: number, status?: string): Promise<AutomationRun[]> => {
    console.log(`${LOG_PREFIX} getAutomationRuns called for ID ${id}, status: ${status}`);
    try {
      const params = status ? `?status=${status}` : '';
      console.log(`${LOG_PREFIX} GETing /api/automations/appointments/${id}/runs${params}...`);
      const response = await http.get<{success: boolean, runs: AutomationRun[]}>(`/api/automations/appointments/${id}/runs${params}`);
      console.log(`${LOG_PREFIX} Runs response: ${response?.runs?.length || 0} runs`);
      
      return response?.runs || [];
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Get automation runs FAILED:`, err);
      return [];
    }
  }, []);

  const testAutomationPreview = useCallback(async (id: number, appointmentId?: number): Promise<{preview: string, context: any}> => {
    console.log(`${LOG_PREFIX} testAutomationPreview called for ID ${id}, appointmentId: ${appointmentId}`);
    try {
      const body = appointmentId ? { appointment_id: appointmentId } : {};
      console.log(`${LOG_PREFIX} POSTing to /api/automations/appointments/${id}/test...`);
      const response = await http.post<{success: boolean, preview: string, context: any}>(`/api/automations/appointments/${id}/test`, body);
      console.log(`${LOG_PREFIX} Preview response received`);
      
      return {
        preview: response?.preview || '',
        context: response?.context || {}
      };
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Test automation preview FAILED:`, err);
      throw new Error(err?.error || err?.message || 'שגיאה בתצוגה מקדימה');
    }
  }, []);

  const createFromTemplate = useCallback(async (templateKey: string, name?: string, enabled?: boolean): Promise<number> => {
    console.log(`${LOG_PREFIX} createFromTemplate called with template: ${templateKey}`);
    try {
      setLoading(true);
      setError(null);
      
      const body: any = {};
      if (name) body.name = name;
      if (enabled !== undefined) body.enabled = enabled;
      
      console.log(`${LOG_PREFIX} POSTing to /api/automations/appointments/templates/${templateKey}...`);
      const response = await http.post<{success: boolean, automation_id: number, message: string}>(`/api/automations/appointments/templates/${templateKey}`, body);
      console.log(`${LOG_PREFIX} Template create response:`, JSON.stringify(response, null, 2));
      
      // Refresh the list
      await refreshAutomations();
      
      console.log(`${LOG_PREFIX} Successfully created automation from template with ID ${response.automation_id}`);
      return response.automation_id;
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Create from template FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה ביצירת אוטומציה מתבנית';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [refreshAutomations]);

  const setupDefaultAutomations = useCallback(async (): Promise<number> => {
    console.log(`${LOG_PREFIX} setupDefaultAutomations called`);
    try {
      setLoading(true);
      setError(null);
      
      console.log(`${LOG_PREFIX} POSTing to /api/automations/appointments/setup-defaults...`);
      const response = await http.post<{success: boolean, created_count: number, message: string}>('/api/automations/appointments/setup-defaults', {});
      console.log(`${LOG_PREFIX} Setup defaults response:`, JSON.stringify(response, null, 2));
      
      // Refresh the list
      await refreshAutomations();
      
      console.log(`${LOG_PREFIX} Successfully created ${response.created_count} default automations`);
      return response.created_count;
    } catch (err: any) {
      console.error(`${LOG_PREFIX} Setup default automations FAILED:`, err);
      const errorMsg = err?.error || err?.message || 'שגיאה ביצירת אוטומציות ברירת מחדל';
      setError(errorMsg);
      throw new Error(errorMsg);
    } finally {
      setLoading(false);
    }
  }, [refreshAutomations]);

  return {
    automations,
    templates,
    loading,
    error,
    refreshAutomations,
    createAutomation,
    updateAutomation,
    deleteAutomation,
    getAutomationRuns,
    testAutomationPreview,
    loadTemplates,
    createFromTemplate,
    setupDefaultAutomations,
  };
}
