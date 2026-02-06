/**
 * User Context Hook - Provides user permissions and page access
 * הנחיית-על: ניהול הרשאות דפים
 */
import { useState, useEffect, useCallback } from 'react';
import { meetsRoleRequirement } from '../../shared/constants/roles';

export interface PageConfig {
  page_key: string;
  title_he: string;
  route: string;
  min_role: string;
  category: string;
  api_tags: string[];
  icon?: string;
  description?: string;
  is_system_admin_only: boolean;
}

export interface UserContext {
  user: {
    id: number;
    email: string;
    name: string;
    role: string;
  };
  business: {
    id: number;
    name: string;
    business_type: string;
  } | null;
  enabled_pages: string[];
  page_registry: Record<string, PageConfig>;
  is_impersonating: boolean;
}

export function useUserContext() {
  const [context, setContext] = useState<UserContext | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchContext = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch('/api/me/context', {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('Failed to fetch user context');
      }

      const data = await response.json();
      setContext(data);
    } catch (err) {
      console.error('Error fetching user context:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchContext();
  }, [fetchContext]);

  const hasPageAccess = useCallback((pageKey: string): boolean => {
    if (!context) return false;
    return context.enabled_pages.includes(pageKey);
  }, [context]);

  const hasRoleAccess = useCallback((minRole: string): boolean => {
    if (!context) return false;
    return meetsRoleRequirement(context.user.role, minRole);
  }, [context]);

  const canAccessPage = useCallback((pageKey: string): boolean => {
    if (!context) return false;

    const page = context.page_registry[pageKey];
    if (!page) return false;

    // Check if page is enabled for business
    if (!hasPageAccess(pageKey)) return false;

    // Check if user role meets requirements
    if (!hasRoleAccess(page.min_role)) return false;

    return true;
  }, [context, hasPageAccess, hasRoleAccess]);

  return {
    context,
    loading,
    error,
    hasPageAccess,
    hasRoleAccess,
    canAccessPage,
    refetch: fetchContext,
  };
}
