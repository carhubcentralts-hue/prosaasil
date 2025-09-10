import { businessAPI } from './api';
import { BusinessEditData, BusinessActionResponse, ImpersonationData, BusinessCapabilities } from './types';

/**
 * Pure action functions for business management
 * These handle the business logic and API calls
 */

export async function editBusinessAction(
  id: number, 
  data: BusinessEditData
): Promise<BusinessActionResponse> {
  try {
    const result = await businessAPI.editBusiness(id, data);
    return {
      ok: true,
      message: 'עסק עודכן בהצלחה',
      data: result
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה בעדכון העסק'
    };
  }
}

export async function createBusinessAction(
  data: BusinessEditData
): Promise<BusinessActionResponse> {
  try {
    const result = await businessAPI.createBusiness(data);
    return {
      ok: true,
      message: 'עסק נוצר בהצלחה',
      data: result
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה ביצירת העסק'
    };
  }
}

export async function resetPasswordAction(
  id: number, 
  password: string
): Promise<BusinessActionResponse> {
  try {
    await businessAPI.resetPassword(id, password);
    return {
      ok: true,
      message: 'סיסמה אופסה בהצלחה'
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה באיפוס סיסמה'
    };
  }
}

export async function impersonateAction(id: number): Promise<{ ok: boolean; tenant_id: number } | null> {
  try {
    const result = await businessAPI.impersonate(id);
    return result;
  } catch (error) {
    throw new Error(error instanceof Error ? error.message : 'שגיאה בהתחזות לעסק');
  }
}

export async function exitImpersonationAction(): Promise<BusinessActionResponse> {
  try {
    const result = await businessAPI.exitImpersonation();
    return {
      ok: true,
      message: 'יצאת מהתחזות בהצלחה',
      data: result
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה ביציאה מהתחזות'
    };
  }
}

export async function suspendBusinessAction(id: number): Promise<BusinessActionResponse> {
  try {
    const result = await businessAPI.suspend(id);
    return {
      ok: true,
      message: 'העסק הושעה בהצלחה',
      data: result
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה בהשעיית העסק'
    };
  }
}

export async function resumeBusinessAction(id: number): Promise<BusinessActionResponse> {
  try {
    const result = await businessAPI.resume(id);
    return {
      ok: true,
      message: 'העסק הופעל מחדש בהצלחה',
      data: result
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה בהפעלת העסק'
    };
  }
}

export async function deleteBusinessAction(id: number): Promise<BusinessActionResponse> {
  try {
    const result = await businessAPI.softDelete(id);
    return {
      ok: true,
      message: 'העסק נמחק בהצלחה',
      data: result
    };
  } catch (error) {
    return {
      ok: false,
      message: error instanceof Error ? error.message : 'שגיאה במחיקת העסק'
    };
  }
}

export function getBusinessCapabilities(userRole: string): BusinessCapabilities {
  const isAdmin = userRole === 'admin';
  const isManager = userRole === 'manager';
  const isBusiness = userRole === 'business';
  
  return {
    canEdit: isAdmin || isManager,
    canImpersonate: isAdmin || isManager,
    canSuspend: isAdmin || isManager,
    canResume: isAdmin || isManager,
    canDelete: isAdmin, // Only admin can delete
    canResetPassword: isAdmin || isManager,
    canViewUsers: isAdmin || isManager || isBusiness,
    canManageUsers: isAdmin || isManager
  };
}

export function validateBusinessData(data: BusinessEditData): string[] {
  const errors: string[] = [];

  if (!data.name?.trim()) {
    errors.push('שם העסק נדרש');
  }

  if (!data.domain?.trim()) {
    errors.push('דומיין נדרש');
  } else if (!/^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9]\.[a-zA-Z]{2,}$/.test(data.domain)) {
    errors.push('פורמט דומיין לא תקין');
  }

  if (!data.defaultPhoneE164?.trim()) {
    errors.push('מספר טלפון נדרש');
  } else if (!/^\+[1-9]\d{1,14}$/.test(data.defaultPhoneE164)) {
    errors.push('פורמט טלפון לא תקין (חייב להתחיל ב-+)');
  }

  if (!data.whatsappJid?.trim()) {
    errors.push('מספר WhatsApp נדרש');
  } else if (!/^\+[1-9]\d{1,14}$/.test(data.whatsappJid.replace('@s.whatsapp.net', ''))) {
    errors.push('פורמט מספר WhatsApp לא תקין (חייב להתחיל ב-+)');
  }

  return errors;
}