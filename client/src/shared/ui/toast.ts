/**
 * ProSaaS unified toast system — wraps `sonner`.
 *
 * Usage:
 *   import { showToast } from '@/shared/ui/toast';
 *   showToast.success('הצלחה!');
 *   showToast.error('שגיאה');
 *
 * The <Toaster /> component must be rendered once at the app root
 * (see App.tsx).  Re-export it here for convenience.
 */
import { toast, Toaster } from 'sonner';

export { Toaster };

export const showToast = {
  success(message: string) {
    toast.success(message);
  },
  error(message: string) {
    toast.error(message);
  },
  info(message: string) {
    toast.info(message);
  },
  warning(message: string) {
    toast.warning(message);
  },
} as const;
