import React, { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from './layout/AuthGuard';
import { RoleGuard } from './layout/RoleGuard';
import { MainLayout } from './layout/MainLayout';
import { useAuth } from '../features/auth/hooks';

// Auth Pages (kept eager - needed for initial load)
import { LoginPage } from '../pages/Auth/LoginPage';
import { ForgotPasswordPage } from '../pages/Auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/Auth/ResetPasswordPage';

// ⚡ BUILD 168.2: Lazy loading for heavy pages - faster initial load
const AdminHomePage = lazy(() => import('../pages/Admin/AdminHomePage').then(m => ({ default: m.AdminHomePage })));
const BusinessHomePage = lazy(() => import('../pages/Business/BusinessHomePage').then(m => ({ default: m.BusinessHomePage })));
const BusinessManagerPage = lazy(() => import('../pages/Admin/BusinessManagerPage').then(m => ({ default: m.BusinessManagerPage })));
const BusinessDetailsPage = lazy(() => import('../pages/Admin/BusinessDetailsPage').then(m => ({ default: m.BusinessDetailsPage })));
const BusinessViewPage = lazy(() => import('../pages/Admin/BusinessViewPage').then(m => ({ default: m.BusinessViewPage })));
const AgentPromptsPage = lazy(() => import('../pages/Admin/AgentPromptsPage').then(m => ({ default: m.AgentPromptsPage })));
const AdminPromptsOverviewPage = lazy(() => import('../pages/Admin/AdminPromptsOverviewPage').then(m => ({ default: m.AdminPromptsOverviewPage })));
const BusinessPromptsSelector = lazy(() => import('../pages/Admin/BusinessPromptsSelector').then(m => ({ default: m.BusinessPromptsSelector })));
const AdminSupportPage = lazy(() => import('../pages/Admin/AdminSupportPage').then(m => ({ default: m.AdminSupportPage })));
const CalendarPage = lazy(() => import('../pages/Calendar/CalendarPage').then(m => ({ default: m.CalendarPage })));
const LeadsPage = lazy(() => import('../pages/Leads/LeadsPage'));
const LeadDetailPage = lazy(() => import('../pages/Leads/LeadDetailPage'));
const WhatsAppPage = lazy(() => import('../pages/wa/WhatsAppPage').then(m => ({ default: m.WhatsAppPage })));
const CallsPage = lazy(() => import('../pages/calls/CallsPage').then(m => ({ default: m.CallsPage })));
const CrmPage = lazy(() => import('../pages/crm/CrmPage').then(m => ({ default: m.CrmPage })));
const BillingPage = lazy(() => import('../pages/billing/BillingPage').then(m => ({ default: m.BillingPage })));
const UsersPage = lazy(() => import('../pages/users/UsersPage').then(m => ({ default: m.UsersPage })));
const SettingsPage = lazy(() => import('../pages/settings/SettingsPage').then(m => ({ default: m.SettingsPage })));

// Loading fallback component
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[200px]">
    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
  </div>
);

// BUILD 135: Smart redirect based on role
function DefaultRedirect() {
  const { user } = useAuth();
  
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  
  // System admin goes to admin dashboard
  if (user.role === 'system_admin') {
    return <Navigate to="/app/admin/overview" replace />;
  }
  
  // All other roles (owner, admin, agent) go to business dashboard
  return <Navigate to="/app/business/overview" replace />;
}

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
        {/* BUILD 135: Admin Routes - SYSTEM_ADMIN ONLY */}
        <Route
          path="admin/overview"
          element={
            <RoleGuard roles={['system_admin']}>
              <AdminHomePage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses"
          element={
            <RoleGuard roles={['system_admin']}>
              <BusinessManagerPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:businessId/view"
          element={
            <RoleGuard roles={['system_admin']}>
              <BusinessViewPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/businesses/:businessId/agent"
          element={
            <RoleGuard roles={['system_admin']}>
              <AgentPromptsPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/prompts"
          element={
            <RoleGuard roles={['system_admin']}>
              <AdminPromptsOverviewPage />
            </RoleGuard>
          }
        />
        <Route
          path="admin/agent-prompts"
          element={
            <RoleGuard roles={['system_admin']}>
              <BusinessPromptsSelector />
            </RoleGuard>
          }
        />
        <Route
          path="admin/support"
          element={
            <RoleGuard roles={['system_admin']}>
              <AdminSupportPage />
            </RoleGuard>
          }
        />

        {/* BUILD 157: AI Prompts moved to System Settings only - removed from business routes */}

        {/* Business Routes */}
        <Route
          path="business/overview"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
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

        {/* DISABLED: Notifications full page - replaced by bell icon modal only */}
        <Route path="notifications" element={<Navigate to="/app/leads" replace />} />

        {/* DISABLED: Customer Intelligence - removed from product */}
        <Route path="intelligence" element={<Navigate to="/app/leads" replace />} />

        {/* BUILD 135: Smart default redirect based on role */}
        <Route path="" element={<DefaultRedirect />} />
      </Route>

      {/* Default redirect */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      
      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}