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
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <AdminHomePage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <BusinessManagerPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:businessId/view"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <BusinessViewPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:businessId/agent"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <AgentPromptsPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/prompts"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <AdminPromptsOverviewPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/agent-prompts"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <BusinessPromptsSelector />
            </RoleGuard>
          }
        />
        <Route
          path="admin/support"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
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
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <AgentPromptsPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:id"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <BusinessDetailsPage />
            </RoleGuard>
          }
        />

        {/* Business Routes */}
        <Route
          path="business/overview"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
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
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <LeadsPage />
            </RoleGuard>
          }
        />
        <Route
          path="leads/:id"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <LeadDetailPage />
            </RoleGuard>
          }
        />

        {/* WhatsApp Routes */}
        <Route
          path="whatsapp"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <WhatsAppPage />
            </RoleGuard>
          }
        />

        {/* Calls Routes */}
        <Route
          path="calls"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <CallsPage />
            </RoleGuard>
          }
        />

        {/* CRM Routes */}
        <Route
          path="crm"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <CrmPage />
            </RoleGuard>
          }
        />

        {/* Billing Routes - DISABLED until payments feature is activated */}
        {/* <Route
          path="billing"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <BillingPage />
            </RoleGuard>
          }
        /> */}

        {/* Users Routes */}
        <Route
          path="users"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <UsersPage />
            </RoleGuard>
          }
        />

        {/* Settings Routes */}
        <Route
          path="settings"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <SettingsPage />
            </RoleGuard>
          }
        />

        {/* Notifications Routes */}
        <Route
          path="notifications"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <NotificationsPage />
            </RoleGuard>
          }
        />

        {/* Customer Intelligence Dashboard */}
        <Route
          path="intelligence"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
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