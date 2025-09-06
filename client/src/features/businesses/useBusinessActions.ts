import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  editBusinessAction,
  resetPasswordAction,
  impersonateAction,
  exitImpersonationAction,
  suspendBusinessAction,
  resumeBusinessAction,
  deleteBusinessAction,
  getBusinessCapabilities,
  validateBusinessData
} from './actions';
import { BusinessEditData, Business, BusinessCapabilities } from './types';
import { useAuth } from '../auth/hooks';

interface ConfirmationDialogState {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText: string;
  onConfirm: () => void;
  requiresNameConfirmation?: boolean;
  businessName?: string;
  isDangerous?: boolean;
}

// Simple toast replacement for now - can be enhanced later
const showToast = {
  success: (message: string) => {
    console.log('✅ Success:', message);
    // TODO: Replace with proper toast system
    alert(`✅ ${message}`);
  },
  error: (message: string) => {
    console.error('❌ Error:', message);
    // TODO: Replace with proper toast system  
    alert(`❌ ${message}`);
  }
};

export function useBusinessActions() {
  const navigate = useNavigate();
  const { user, refetch: refetchAuth } = useAuth();
  const [loading, setLoading] = useState<{ [key: string]: boolean }>({});
  const [confirmDialog, setConfirmDialog] = useState<ConfirmationDialogState | null>(null);

  // Get user capabilities
  const capabilities = user ? getBusinessCapabilities(user.role) : {} as BusinessCapabilities;

  // Helper to manage loading states
  const setActionLoading = useCallback((action: string, isLoading: boolean) => {
    setLoading(prev => ({ ...prev, [action]: isLoading }));
  }, []);

  // Helper to show confirmation dialog
  const showConfirmation = useCallback((config: Omit<ConfirmationDialogState, 'isOpen'>) => {
    setConfirmDialog({ ...config, isOpen: true });
  }, []);

  // Helper to hide confirmation dialog
  const hideConfirmation = useCallback(() => {
    setConfirmDialog(null);
  }, []);

  // Edit business
  const editBusiness = useCallback(async (business: Business, data: BusinessEditData) => {
    if (!capabilities.canEdit) {
      showToast.error('אין לך הרשאה לערוך עסקים');
      return;
    }

    // Validate data
    const validationErrors = validateBusinessData(data);
    if (validationErrors.length > 0) {
      showToast.error(validationErrors.join(', '));
      return;
    }

    setActionLoading(`edit-${business.id}`, true);

    try {
      const result = await editBusinessAction(business.id, data);
      if (result.ok) {
        showToast.success('עסק עודכן בהצלחה');
      } else {
        showToast.error(result.message || 'שגיאה בעדכון העסק');
      }
    } catch (error) {
      showToast.error(error instanceof Error ? error.message : 'שגיאה בעדכון העסק');
    } finally {
      setActionLoading(`edit-${business.id}`, false);
    }
  }, [capabilities.canEdit, setActionLoading]);

  // Reset password
  const resetPassword = useCallback(async (business: Business, userId?: number) => {
    if (!capabilities.canResetPassword) {
      showToast.error('אין לך הרשאה לאפס סיסמאות');
      return;
    }

    const userConfirmed = confirm(userId 
      ? 'האם אתה בטוח שאתה רוצה לאפס את סיסמת המשתמש?'
      : `האם אתה בטוח שאתה רוצה לאפס את סיסמאות כל המשתמשים של "${business.name}"?`);
    
    if (!userConfirmed) return;

    setActionLoading(`reset-${business.id}`, true);
    
    try {
      const tempPassword = Math.random().toString(36).slice(-8) + '123';
      const result = await resetPasswordAction(business.id, tempPassword);
      if (result.ok) {
        showToast.success(`${result.message}\nסיסמה זמנית: ${tempPassword}`);
      } else {
        showToast.error(result.message || 'שגיאה באיפוס סיסמה');
      }
    } catch (error) {
      showToast.error(error instanceof Error ? error.message : 'שגיאה באיפוס סיסמה');
    } finally {
      setActionLoading(`reset-${business.id}`, false);
    }
  }, [capabilities.canResetPassword, setActionLoading]);

  // Impersonate business
  const impersonate = useCallback(async (business: Business) => {
    if (!capabilities.canImpersonate) {
      showToast.error('אין לך הרשאה להתחזות לעסקים');
      return;
    }

    const userConfirmed = confirm(`האם אתה בטוח שאתה רוצה להתחזות לעסק "${business.name}"?\nאתה תועבר לדשבורד של העסק.`);
    if (!userConfirmed) return;

    setActionLoading(`impersonate-${business.id}`, true);
    
    try {
      // Store original user data for impersonation banner
      if (user) {
        localStorage.setItem('impersonation_original_user', JSON.stringify({
          name: user.email.split('@')[0] || user.email,
          email: user.email,
          role: user.role
        }));
        localStorage.setItem('is_impersonating', 'true');
        localStorage.setItem('impersonating_business_id', business.id.toString());
        localStorage.setItem('impersonating_business_name', business.name);
        localStorage.setItem('impersonating_business_domain', business.domain);
      }

      const result = await impersonateAction(business.id);
      console.log('התחזות הושלמה:', result);
      
      await refetchAuth(); // Refresh auth state
      showToast.success(`התחזות לעסק "${business.name}" הופעלה`);
      
      // Force page reload to ensure all state is updated correctly
      window.location.href = '/app/business/overview';
    } catch (error) {
      // Clear impersonation data on error
      localStorage.removeItem('impersonation_original_user');
      localStorage.removeItem('is_impersonating');
      localStorage.removeItem('impersonating_business_id');
      localStorage.removeItem('impersonating_business_name');
      localStorage.removeItem('impersonating_business_domain');
      
      showToast.error(error instanceof Error ? error.message : 'שגיאה בהתחזות לעסק');
    } finally {
      setActionLoading(`impersonate-${business.id}`, false);
    }
  }, [capabilities.canImpersonate, navigate, setActionLoading, refetchAuth, user]);

  // Exit impersonation
  const exitImpersonation = useCallback(async () => {
    setActionLoading('exit-impersonation', true);
    
    try {
      const result = await exitImpersonationAction();
      
      // Clear all impersonation data from localStorage
      localStorage.removeItem('impersonation_original_user');
      localStorage.removeItem('is_impersonating');
      localStorage.removeItem('impersonating_business_id');
      localStorage.removeItem('impersonating_business_name');
      localStorage.removeItem('impersonating_business_domain');
      
      await refetchAuth(); // Refresh auth state
      showToast.success('יצאת מהתחזות בהצלחה');
      
      // Navigate back to admin
      navigate('/app/admin/overview');
    } catch (error) {
      showToast.error(error instanceof Error ? error.message : 'שגיאה ביציאה מהתחזות');
    } finally {
      setActionLoading('exit-impersonation', false);
    }
  }, [navigate, setActionLoading, refetchAuth]);

  // Suspend business
  const suspend = useCallback(async (business: Business) => {
    if (!capabilities.canSuspend) {
      showToast.error('אין לך הרשאה להשעות עסקים');
      return;
    }

    const userConfirmed = confirm(`האם אתה בטוח שאתה רוצה להשעות את העסק "${business.name}"?\n\nפעולה זו תמנע מהעסק לבצע פעולות במערכת.`);
    if (!userConfirmed) return;

    setActionLoading(`suspend-${business.id}`, true);
    
    try {
      const result = await suspendBusinessAction(business.id);
      if (result.ok) {
        showToast.success(`העסק "${business.name}" הושעה בהצלחה`);
      } else {
        showToast.error(result.message || 'שגיאה בהשעיית העסק');
      }
    } catch (error) {
      showToast.error(error instanceof Error ? error.message : 'שגיאה בהשעיית העסק');
    } finally {
      setActionLoading(`suspend-${business.id}`, false);
    }
  }, [capabilities.canSuspend, setActionLoading]);

  // Resume business
  const resume = useCallback(async (business: Business) => {
    if (!capabilities.canResume) {
      showToast.error('אין לך הרשאה להפעיל עסקים');
      return;
    }

    const userConfirmed = confirm(`האם אתה בטוח שאתה רוצה להפעיל מחדש את העסק "${business.name}"?`);
    if (!userConfirmed) return;

    setActionLoading(`resume-${business.id}`, true);
    
    try {
      const result = await resumeBusinessAction(business.id);
      if (result.ok) {
        showToast.success(`העסק "${business.name}" הופעל מחדש בהצלחה`);
      } else {
        showToast.error(result.message || 'שגיאה בהפעלת העסק');
      }
    } catch (error) {
      showToast.error(error instanceof Error ? error.message : 'שגיאה בהפעלת העסק');
    } finally {
      setActionLoading(`resume-${business.id}`, false);
    }
  }, [capabilities.canResume, setActionLoading]);

  // Delete business (soft delete)
  const softDelete = useCallback(async (business: Business) => {
    if (!capabilities.canDelete) {
      showToast.error('אין לך הרשאה למחוק עסקים');
      return;
    }

    const userConfirmed = confirm(`⚠️ אזהרה: פעולה זו תמחק את העסק "${business.name}" ואת כל הנתונים הקשורים אליו.\n\nפעולה זו בלתי הפיכה!`);
    if (!userConfirmed) return;

    // Second confirmation with name typing
    const nameConfirmation = prompt(`כדי לאשר מחיקה, הקלד את שם העסק בדיוק: "${business.name}"`);
    if (nameConfirmation !== business.name) {
      showToast.error('שם העסק לא תואם. המחיקה בוטלה.');
      return;
    }

    setActionLoading(`delete-${business.id}`, true);
    
    try {
      const result = await deleteBusinessAction(business.id);
      if (result.ok) {
        showToast.success(`העסק "${business.name}" נמחק בהצלחה`);
        // Navigate back to list
        navigate('/app/admin/businesses');
      } else {
        showToast.error(result.message || 'שגיאה במחיקת העסק');
      }
    } catch (error) {
      showToast.error(error instanceof Error ? error.message : 'שגיאה במחיקת העסק');
    } finally {
      setActionLoading(`delete-${business.id}`, false);
    }
  }, [capabilities.canDelete, navigate, setActionLoading]);

  // View business details
  const viewBusiness = useCallback((business: Business) => {
    navigate(`/app/admin/businesses/${business.id}`);
  }, [navigate]);

  // Check if action is loading
  const isLoading = useCallback((action: string, businessId?: number) => {
    const key = businessId ? `${action}-${businessId}` : action;
    return loading[key] || false;
  }, [loading]);

  return {
    // Action handlers
    editBusiness,
    resetPassword,
    impersonate,
    exitImpersonation,
    suspend,
    resume,
    softDelete,
    viewBusiness,

    // State helpers
    isLoading,
    capabilities,
    
    // Confirmation dialog state (for future use)
    confirmDialog,
    showConfirmation,
    hideConfirmation,
  };
}