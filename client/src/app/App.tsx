import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClientProvider } from '@tanstack/react-query';
import { AppRoutes } from './routes';
import { AuthProvider } from '../features/auth/hooks';
import { queryClient } from '../lib/queryClient';

// 🚀 Clean App component with advanced AuthProvider
export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}