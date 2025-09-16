import { http } from './http';

// Settings Types
export interface BusinessSettings {
  id: number;
  name: string;
  timezone: string;
  phone_e164?: string;
  whatsapp_jid?: string;
  default_wa_provider: 'baileys' | 'twilio';
  working_hours?: {
    start: string;
    end: string;
    days: string[];
  };
}

export interface AIPrompts {
  calls_prompt: string;
  whatsapp_prompt: string;
  model: string;
  max_tokens: number;
  temperature: number;
}

export interface IntegrationStatus {
  twilio: {
    configured: boolean;
    account_sid?: string;
    status: 'active' | 'inactive' | 'error';
  };
  baileys: {
    connected: boolean;
    qr_needed: boolean;
    status: 'connected' | 'disconnected' | 'error';
  };
  openai: {
    configured: boolean;
    status: 'active' | 'inactive';
  };
}

// Settings Service
class SettingsService {
  // Business Settings
  async getBusinessSettings(): Promise<BusinessSettings> {
    return http.get('/api/admin/settings/business');
  }

  async updateBusinessSettings(data: Partial<BusinessSettings>): Promise<BusinessSettings> {
    return http.put('/api/admin/settings/business', data);
  }

  // AI Prompts
  async getAIPrompts(): Promise<AIPrompts> {
    return http.get('/api/admin/settings/prompts');
  }

  async updateAIPrompts(data: Partial<AIPrompts>): Promise<AIPrompts> {
    return http.put('/api/admin/settings/prompts', data);
  }

  // Integrations
  async getIntegrationsStatus(): Promise<IntegrationStatus> {
    return http.get('/api/admin/integrations/status');
  }

  async updateTwilioConfig(data: {
    account_sid: string;
    auth_token: string;
    phone_number: string;
  }): Promise<{ ok: boolean; message: string }> {
    return http.post('/api/admin/integrations/twilio', data);
  }

  async refreshBaileys(): Promise<{ ok: boolean; qr_code?: string }> {
    return http.post('/api/admin/integrations/baileys/refresh', {});
  }

  // Feature Flags
  async getFeatureFlags(): Promise<Record<string, boolean>> {
    return http.get('/api/admin/settings/features');
  }

  async updateFeatureFlag(flag: string, enabled: boolean): Promise<{ ok: boolean }> {
    return http.put(`/api/admin/settings/features/${flag}`, { enabled });
  }
}

export const settingsService = new SettingsService();