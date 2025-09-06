import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../auth/hooks';
import { businessAPI } from '../api';

interface ImpersonationState {
  isImpersonating: boolean;
  originalUser: any | null;
  impersonatedBusiness: any | null;
}

export function useImpersonation() {
  const [impersonationState, setImpersonationState] = useState<ImpersonationState>({
    isImpersonating: false,
    originalUser: null,
    impersonatedBusiness: null
  });
  
  const { user, refetch } = useAuth();

  // Check for impersonation state on mount and auth changes
  useEffect(() => {
    checkImpersonationState();
  }, [user]);

  const checkImpersonationState = useCallback(() => {
    // Check if we're in impersonation mode
    const isImpersonating = localStorage.getItem('is_impersonating') === 'true';
    const originalUserData = localStorage.getItem('impersonation_original_user');
    const businessId = localStorage.getItem('impersonating_business_id');

    if (isImpersonating && originalUserData && businessId) {
      try {
        const originalUser = JSON.parse(originalUserData);
        
        // Mock business data - in real app, fetch from API
        const impersonatedBusiness = {
          id: parseInt(businessId),
          name: businessId === '1' ? 'שי דירות ומשרדים בע״מ' : 'עסק לא ידוע',
          domain: businessId === '1' ? 'shai-realestate.co.il' : 'unknown.co.il'
        };

        setImpersonationState({
          isImpersonating: true,
          originalUser,
          impersonatedBusiness
        });
      } catch (error) {
        console.error('שגיאה בטעינת מצב התחזות:', error);
        clearImpersonationState();
      }
    } else {
      setImpersonationState({
        isImpersonating: false,
        originalUser: null,
        impersonatedBusiness: null
      });
    }
  }, []);

  const startImpersonation = useCallback(async (businessId: number) => {
    try {
      // Step 1: Call the impersonation API and wait
      console.log('🔄 Starting impersonation for business:', businessId);
      const result = await businessAPI.impersonate(businessId);
      console.log('✅ Impersonation API call successful:', result);
      
      // Step 2: Immediately check /api/auth/me to confirm impersonation 
      const authResponse = await fetch('/api/auth/me', {
        method: 'GET',
        credentials: 'include'
      });
      
      if (!authResponse.ok) {
        throw new Error('Failed to verify impersonation');
      }
      
      const authData = await authResponse.json();
      console.log('🔍 Auth check after impersonation:', authData);
      
      // Step 3: Verify we're impersonating or have business role
      if (!authData.impersonating && authData.user?.role !== 'business') {
        throw new Error('Impersonation was not successful');
      }
      
      // Store impersonation state in localStorage for UI state
      if (user) {
        localStorage.setItem('impersonation_original_user', JSON.stringify({
          name: user.email.split('@')[0] || user.email,
          email: user.email,
          role: user.role
        }));
        localStorage.setItem('is_impersonating', 'true');
        localStorage.setItem('impersonating_business_id', businessId.toString());
      }
      
      // Refresh auth to get new permissions in the React context
      await refetch();
      
      // Update local state
      checkImpersonationState();
      
      console.log('🎉 Impersonation completed successfully');
      return result;
    } catch (error) {
      console.error('❌ שגיאה בהתחלת התחזות:', error);
      throw error;
    }
  }, [user, refetch, checkImpersonationState]);

  const exitImpersonation = useCallback(async () => {
    try {
      console.log('🔄 Exiting impersonation...');
      
      // Call the exit impersonation API
      await businessAPI.exitImpersonation();
      console.log('✅ Exit impersonation API call successful');
      
      // Clear impersonation state
      clearImpersonationState();
      
      // Refresh auth to restore original permissions
      await refetch();
      
      console.log('🎉 Successfully exited impersonation');
      return { ok: true };
    } catch (error) {
      console.error('❌ שגיאה ביציאה מהתחזות:', error);
      throw error;
    }
  }, [refetch, clearImpersonationState]);

  const clearImpersonationState = useCallback(() => {
    localStorage.removeItem('impersonation_original_user');
    localStorage.removeItem('is_impersonating');
    localStorage.removeItem('impersonating_business_id');
    
    setImpersonationState({
      isImpersonating: false,
      originalUser: null,
      impersonatedBusiness: null
    });
  }, []);

  return {
    ...impersonationState,
    startImpersonation,
    exitImpersonation,
    clearImpersonationState,
    checkImpersonationState
  };
}