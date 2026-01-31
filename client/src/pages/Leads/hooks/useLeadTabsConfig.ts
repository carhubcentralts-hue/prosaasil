/**
 * Hook for managing flexible lead tabs configuration
 * Loads and applies business-specific tab configuration
 */
import { useState, useEffect } from 'react';
import { http } from '../../../services/http';

export interface LeadTabConfig {
  primary?: string[];
  secondary?: string[];
}

export interface BusinessWithTabs {
  lead_tabs_config: LeadTabConfig | null;
}

/**
 * Hook to fetch and use lead tabs configuration
 * Returns default tabs if no configuration is set
 */
export function useLeadTabsConfig() {
  const [tabsConfig, setTabsConfig] = useState<LeadTabConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTabsConfig();
  }, []);

  const loadTabsConfig = async () => {
    try {
      setLoading(true);
      const response = await http.get<BusinessWithTabs>('/api/business/current');
      setTabsConfig(response.lead_tabs_config);
      setError(null);
    } catch (err) {
      console.error('Failed to load tabs configuration:', err);
      setError('שגיאה בטעינת הגדרות טאבים');
      // Use default tabs on error
      setTabsConfig(null);
    } finally {
      setLoading(false);
    }
  };

  const updateTabsConfig = async (newConfig: LeadTabConfig | null) => {
    try {
      // Save to backend
      await http.put('/api/business/current/settings', {
        lead_tabs_config: newConfig
      });
      
      // ✅ Don't update state optimistically - let the caller refresh
      // This ensures we always show what's actually in the DB
      return true;
    } catch (err) {
      console.error('Failed to update tabs configuration:', err);
      throw err;
    }
  };

  return {
    tabsConfig,
    loading,
    error,
    updateTabsConfig,
    refreshConfig: loadTabsConfig
  };
}
