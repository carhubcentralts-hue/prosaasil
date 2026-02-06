import React from 'react'; // ✅ CRITICAL: Explicit React import for classic JSX
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from './routes';
import { AuthProvider } from '../features/auth/hooks';
import { NotificationProvider } from '../shared/contexts/NotificationContext';
import { queryClient } from '../lib/queryClient';
import { Toaster } from '../shared/ui/toast';

// 🚀 Clean App component with advanced AuthProvider
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <NotificationProvider>
            <AppRoutes />
            <Toaster position="top-center" dir="rtl" richColors />
          </NotificationProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}