import { useCallback } from 'react';
import { useAuth } from '../../auth/hooks';
import { businessAPI } from '../api';

interface ImpersonationState {
  isImpersonating: boolean;
  originalUser: any | null;
  impersonatedBusiness: any | null;
}

export function useImpersonation() {
  const { user, tenant, impersonating, original_user, refetch } = useAuth();

  // Use actual original_user from server response instead of deriving from current user
  const impersonationState: ImpersonationState = {
    isImpersonating: impersonating || false,
    originalUser: original_user ? {
      name: original_user.name || original_user.email.split('@')[0],
      email: original_user.email,
      role: original_user.role
    } : null,
    impersonatedBusiness: impersonating && tenant ? {
      id: tenant.id,
      name: tenant.name,
      domain: `${tenant.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}.co.il`
    } : null
  };

  const startImpersonation = useCallback(async (businessId: number, navigate: (path: string) => void) => {
    try {
      console.log('🔄 Starting impersonation for business:', businessId);
      
      // Step 1: ✅ לפני ההתחזות לקרוא CSRF (לפי ההנחיות)
      await fetch('/api/auth/csrf', { credentials: 'include' });
      
      // Step 2: Call impersonation API
      await businessAPI.impersonate(businessId);
      console.log('✅ Impersonation API call successful');
      
      // Step 3: ✅ אחרי 200: await authStore.refresh() ונווט (לפי ההנחיות)
      await refetch(); // קריאת /api/auth/me - this will update server session state
      
      // Step 4: Navigate
      navigate('/app/business/overview');
      
      console.log('🎉 Successfully started impersonation');
      return { ok: true };
    } catch (error) {
      console.error('❌ שגיאה בהתחלת התחזות:', error);
      throw error;
    }
  }, [refetch]);

  const exitImpersonation = useCallback(async () => {
    try {
      console.log('🔄 Exiting impersonation...');
      
      // Call the exit impersonation API
      await businessAPI.exitImpersonation();
      console.log('✅ Exit impersonation API call successful');
      
      // Refresh auth to restore original permissions and clear server session
      await refetch();
      
      console.log('🎉 Successfully exited impersonation');
      return { ok: true };
    } catch (error) {
      console.error('❌ שגיאה ביציאה מהתחזות:', error);
      throw error;
    }
  }, [refetch]);

  return {
    ...impersonationState,
    startImpersonation,
    exitImpersonation
  };
}