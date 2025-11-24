import React, { lazy, Suspense } from 'react';
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
import { AgentPromptsPage } from '../pages/Admin/AgentPromptsPage';
import { AdminPromptsOverviewPage } from '../pages/Admin/AdminPromptsOverviewPage';
import { BusinessPromptsSelector } from '../pages/Admin/BusinessPromptsSelector';
// Lazy loading AdminSupportPage to isolate JSX compilation errors
const AdminSupportPage = lazy(() => import('../pages/Admin/AdminSupportPage').then(module => ({
  default: module.AdminSupportPage
})));
import { CalendarPage } from '../pages/Calendar/CalendarPage';
import LeadsPage from '../pages/Leads/LeadsPage';
import LeadDetailPage from '../pages/Leads/LeadDetailPage';
import { NotificationsPage } from '../pages/Notifications/NotificationsPage';
import { WhatsAppPage } from '../pages/wa/WhatsAppPage';
import { CallsPage } from '../pages/calls/CallsPage';
import { CrmPage } from '../pages/crm/CrmPage';
import { BillingPage } from '../pages/billing/BillingPage';
import { UsersPage } from '../pages/users/UsersPage';
import { UsersManagementPage } from '../pages/Admin/UsersManagementPage';
import { BusinessesManagementPage } from '../pages/Admin/BusinessesManagementPage';
import { ProfilePage } from '../pages/Profile/ProfilePage';
import { SettingsPage } from '../pages/settings/SettingsPage';
import CustomerIntelligencePage from '../pages/Intelligence/CustomerIntelligencePage';

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
          path="admin/businesses/:businessId/agent"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <AgentPromptsPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/prompts"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <AdminPromptsOverviewPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/agent-prompts"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <BusinessPromptsSelector />
            </RoleGuard>
          }
        />
        <Route
          path="admin/support"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <Suspense fallback={<div className="flex items-center justify-center py-12"><div>טוען דף תמיכה...</div></div>}>
                <AdminSupportPage />
              </Suspense>
            </RoleGuard>
          }
        />

        {/* Business Routes */}
        <Route
          path="business/agent-prompts"
          element={
            <RoleGuard roles={['business', 'admin']}>
              <AgentPromptsPage />
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
            <RoleGuard roles={['business', 'admin']}>
              <BusinessHomePage />
            </RoleGuard>
          }
        />

        {/* Calendar Routes */}
        <Route
          path="calendar"
          element={<CalendarPage />}
        />

        {/* Leads Routes */}
        <Route
          path="leads"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <LeadsPage />
            </RoleGuard>
          }
        />
        <Route
          path="leads/:id"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <LeadDetailPage />
            </RoleGuard>
          }
        />

        {/* WhatsApp Routes */}
        <Route
          path="whatsapp"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <WhatsAppPage />
            </RoleGuard>
          }
        />

        {/* Calls Routes */}
        <Route
          path="calls"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <CallsPage />
            </RoleGuard>
          }
        />

        {/* CRM Routes */}
        <Route
          path="crm"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <CrmPage />
            </RoleGuard>
          }
        />

        {/* Billing Routes */}
        <Route
          path="billing"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <BillingPage />
            </RoleGuard>
          }
        />

        {/* Users Routes */}
        <Route
          path="users"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <UsersPage />
            </RoleGuard>
          }
        />

        {/* Admin Users Management */}
        <Route
          path="admin/users"
          element={
            <RoleGuard roles={['admin', 'manager']}>
              <UsersManagementPage />
            </RoleGuard>
          }
        />

        {/* Admin Businesses Management - Superadmin Only */}
        <Route
          path="admin/businesses-management"
          element={
            <RoleGuard roles={['superadmin']}>
              <BusinessesManagementPage />
            </RoleGuard>
          }
        />

        {/* Profile Routes */}
        <Route
          path="profile"
          element={<ProfilePage />}
        />

        {/* Settings Routes */}
        <Route
          path="settings"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <SettingsPage />
            </RoleGuard>
          }
        />

        {/* Notifications Routes */}
        <Route
          path="notifications"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <NotificationsPage />
            </RoleGuard>
          }
        />

        {/* Customer Intelligence Dashboard */}
        <Route
          path="intelligence"
          element={
            <RoleGuard roles={['business', 'admin', 'manager']}>
              <CustomerIntelligencePage />
            </RoleGuard>
          }
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