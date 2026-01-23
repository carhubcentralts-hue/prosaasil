/**
 * Production-safe logger utility
 * Logs only in development mode, no-op in production
 */

const isDevelopment = import.meta.env.DEV;

export const logger = {
  debug: (...args: any[]) => {
    if (isDevelopment) {
      console.log('[DEBUG]', ...args);
    }
  },
  
  info: (...args: any[]) => {
    if (isDevelopment) {
      console.info('[INFO]', ...args);
    }
  },
  
  warn: (...args: any[]) => {
    if (isDevelopment) {
      console.warn('[WARN]', ...args);
    }
  },
  
  error: (...args: any[]) => {
    // Errors are logged in production but without sensitive data
    if (isDevelopment) {
      console.error('[ERROR]', ...args);
    } else {
      // In production, only log error messages, not full objects
      const safeArgs = args.map(arg => {
        if (typeof arg === 'string') return arg;
        if (arg instanceof Error) return arg.message;
        return '[Object]';
      });
      console.error('[ERROR]', ...safeArgs);
    }
  }
};
