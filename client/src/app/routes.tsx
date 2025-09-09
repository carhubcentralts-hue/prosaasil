import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from './layout/AuthGuard';
import { RoleGuard } from './layout/RoleGuard';
import { MainLayout } from './layout/MainLayout';

// Auth Pages
import { LoginPage } from '../pages/Auth/LoginPage';
import { ForgotPasswordPage } from '../pages/Auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/Auth/ResetPasswordPage';

// Protected Pages  
import { AdminHomePage } from '../pages/Admin/AdminHomePage';
import { BusinessHomePage } from '../pages/Business/BusinessHomePage';
import { BusinessManagerPage } from '../pages/Admin/BusinessManagerPage';
import { BusinessDetailsPage } from '../pages/Admin/BusinessDetailsPage';
import { BusinessViewPage } from '../pages/Admin/BusinessViewPage';
import { CalendarPage } from '../pages/Calendar/CalendarPage';

export function AppRoutes() {
  return (
    <Routes>
      {/* Public Routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot" element={<ForgotPasswordPage />} />
      <Route path="/reset" element={<ResetPasswordPage />} />

      {/* Protected Routes */}
      <Route
        path="/app"
        element={
          <AuthGuard>
            <MainLayout />
          </AuthGuard>
        }
      >
        {/* Admin Routes */}
        <Route
          path="admin/overview"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <AdminHomePage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <BusinessManagerPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:businessId/view"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <BusinessViewPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:id"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <BusinessDetailsPage />
            </RoleGuard>
          }
        />

        {/* Business Routes */}
        <Route
          path="business/overview"
          element={
            <RoleGuard roles={['business']}>
              <BusinessHomePage />
            </RoleGuard>
          }
        />

        {/* Calendar Routes */}
        <Route
          path="calendar"
          element={<CalendarPage />}
        />

        {/* Default redirect based on role handled by AuthGuard */}
        <Route path="" element={<Navigate to="/app/admin/overview" replace />} />
      </Route>

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      
      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}