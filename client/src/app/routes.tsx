import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from './layout/AuthGuard';

// Auth Pages
import { LoginPage } from '../pages/Auth/LoginPage';
import { ForgotPasswordPage } from '../pages/Auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/Auth/ResetPasswordPage';

// Simple success page after login
function LoggedInPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
      <div className="bg-white p-8 rounded-2xl shadow-sm border border-gray-200 text-center max-w-md w-full mx-4">
        <div className="mb-6">
          <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7"></path>
            </svg>
          </div>
          <h1 className="text-2xl font-bold text-gray-900 mb-2">
            התחברת בהצלחה! ✅
          </h1>
          <p className="text-gray-600">
            מערכת שי דירות ומשרדים
          </p>
        </div>
        <div className="text-sm text-gray-500">
          הדפים הראשיים יוגדרו בקרוב
        </div>
      </div>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot" element={<ForgotPasswordPage />} />
      <Route path="/reset" element={<ResetPasswordPage />} />

      {/* Simple logged in page */}
      <Route
        path="/app"
        element={
          <AuthGuard>
            <LoggedInPage />
          </AuthGuard>
        }
      />

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      
      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}