import React, { lazy, Suspense } from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from './layout/AuthGuard';
import { RoleGuard } from './layout/RoleGuard';
import { PageGuard } from '../features/permissions/PageGuard';
import { MainLayout } from './layout/MainLayout';
import { useAuth } from '../features/auth/hooks';

// Auth Pages (kept eager - needed for initial load)
import { LoginPage } from '../pages/Auth/LoginPage';
import { ForgotPasswordPage } from '../pages/Auth/ForgotPasswordPage';
import { ResetPasswordPage } from '../pages/Auth/ResetPasswordPage';

// Error Pages (kept eager - needed for error handling)
import { ForbiddenPage } from '../pages/Error/ForbiddenPage';

// Legal Pages (kept eager - needed for app store compliance)
import { PrivacyPolicyPage } from '../pages/Legal/PrivacyPolicyPage';
import { TermsOfServicePage } from '../pages/Legal/TermsOfServicePage';

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
const BusinessMinutesPage = lazy(() => import('../pages/Admin/BusinessMinutesPage').then(m => ({ default: m.BusinessMinutesPage })));
const PromptStudioPage = lazy(() => import('../pages/Admin/PromptStudioPage').then(m => ({ default: m.PromptStudioPage })));
const CalendarPage = lazy(() => import('../pages/Calendar/CalendarPage').then(m => ({ default: m.CalendarPage })));
const LeadsPage = lazy(() => import('../pages/Leads/LeadsPage'));
const LeadDetailPage = lazy(() => import('../pages/Leads/LeadDetailPage'));
const WhatsAppPage = lazy(() => import('../pages/wa/WhatsAppPage').then(m => ({ default: m.WhatsAppPage })));
const WhatsAppBroadcastPage = lazy(() => import('../pages/wa/WhatsAppBroadcastPage').then(m => ({ default: m.WhatsAppBroadcastPage })));
const ScheduledMessagesPage = lazy(() => import('../pages/ScheduledMessages/ScheduledMessagesPage').then(m => ({ default: m.ScheduledMessagesPage })));
const InboundCallsPage = lazy(() => import('../pages/calls/InboundCallsPage').then(m => ({ default: m.InboundCallsPage })));
const OutboundCallsPage = lazy(() => import('../pages/calls/OutboundCallsPage').then(m => ({ default: m.OutboundCallsPage })));
const CrmPage = lazy(() => import('../pages/crm/CrmPage').then(m => ({ default: m.CrmPage })));
const BillingPage = lazy(() => import('../pages/billing/BillingPage').then(m => ({ default: m.BillingPage })));
const UsersPage = lazy(() => import('../pages/users/UsersPage').then(m => ({ default: m.UsersPage })));
const SettingsPage = lazy(() => import('../pages/settings/SettingsPage').then(m => ({ default: m.SettingsPage })));
const EmailsPage = lazy(() => import('../pages/emails/EmailsPage').then(m => ({ default: m.EmailsPage })));
const StatisticsPage = lazy(() => import('../pages/statistics/StatisticsPage').then(m => ({ default: m.StatisticsPage })));
const ContractsPage = lazy(() => import('../pages/contracts/ContractsPage').then(m => ({ default: m.ContractsPage })));
const PublicSigningPage = lazy(() => import('../pages/contracts/PublicSigningPage').then(m => ({ default: m.PublicSigningPage })));
const AssetsPage = lazy(() => import('../pages/assets/AssetsPage'));
const ReceiptsPage = lazy(() => import('../pages/receipts/ReceiptsPage'));

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
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      
      {/* Legal Pages - Public (required for App Store/Play Store compliance) */}
      <Route path="/privacy" element={<PrivacyPolicyPage />} />
      <Route path="/terms" element={<TermsOfServicePage />} />

      {/* Public Contract Signing - NO AUTH */}
      <Route path="/contracts/sign/:token" element={<Suspense fallback={<PageLoader />}><PublicSigningPage /></Suspense>} />

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
          path="admin/prompt-studio"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <Suspense fallback={<PageLoader />}>
                <PromptStudioPage />
              </Suspense>
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
        {/* BUILD 180: Business Minutes Management - Admin only */}
        <Route
          path="admin/business-minutes"
          element={
            <RoleGuard roles={['system_admin']}>
              <BusinessMinutesPage />
            </RoleGuard>
          }
        />

        {/* BUILD 157: AI Prompts moved to System Settings only - removed from business routes */}

        {/* Business Routes */}
        <Route
          path="business/overview"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="dashboard">
                <BusinessHomePage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Calendar Routes */}
        <Route
          path="calendar"
          element={
            <PageGuard pageKey="calendar">
              <CalendarPage />
            </PageGuard>
          }
        />

        {/* Leads Routes */}
        <Route
          path="leads"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="crm_leads">
                <LeadsPage />
              </PageGuard>
            </RoleGuard>
          }
        />
        <Route
          path="leads/:id"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="crm_leads">
                <LeadDetailPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* WhatsApp Routes */}
        <Route
          path="whatsapp"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="whatsapp_inbox">
                <WhatsAppPage />
              </PageGuard>
            </RoleGuard>
          }
        />
        <Route
          path="whatsapp-broadcast"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <PageGuard pageKey="whatsapp_broadcast">
                <Suspense fallback={<PageLoader />}>
                  <WhatsAppBroadcastPage />
                </Suspense>
              </PageGuard>
            </RoleGuard>
          }
        />
        <Route
          path="scheduled-messages"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <PageGuard pageKey="scheduled_messages">
                <Suspense fallback={<PageLoader />}>
                  <ScheduledMessagesPage />
                </Suspense>
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Calls Routes - Inbound Calls (lead-centric view) */}
        <Route
          path="calls"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="calls_inbound">
                <InboundCallsPage />
              </PageGuard>
            </RoleGuard>
          }
        />
        
        {/* BUILD 174: Outbound Calls */}
        <Route
          path="outbound-calls"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="calls_outbound">
                <OutboundCallsPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* CRM Routes */}
        <Route
          path="crm"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="crm_customers">
                <CrmPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Email Routes */}
        <Route
          path="emails"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="emails">
                <EmailsPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Statistics Routes */}
        <Route
          path="statistics"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="statistics">
                <StatisticsPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Contracts Routes */}
        <Route
          path="contracts"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="contracts">
                <Suspense fallback={<PageLoader />}>
                  <ContractsPage />
                </Suspense>
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Assets Library Routes (מאגר) */}
        <Route
          path="assets"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="assets">
                <Suspense fallback={<PageLoader />}>
                  <AssetsPage />
                </Suspense>
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Gmail Receipts Routes (קבלות) */}
        <Route
          path="receipts"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin']}>
              <PageGuard pageKey="gmail_receipts">
                <Suspense fallback={<PageLoader />}>
                  <ReceiptsPage />
                </Suspense>
              </PageGuard>
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
              <PageGuard pageKey="users">
                <UsersPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* Settings Routes */}
        <Route
          path="settings"
          element={
            <RoleGuard roles={['system_admin', 'owner', 'admin', 'agent']}>
              <PageGuard pageKey="settings">
                <SettingsPage />
              </PageGuard>
            </RoleGuard>
          }
        />

        {/* DISABLED: Notifications full page - replaced by bell icon modal only */}
        <Route path="notifications" element={<Navigate to="/app/leads" replace />} />

        {/* DISABLED: Customer Intelligence - removed from product */}
        <Route path="intelligence" element={<Navigate to="/app/leads" replace />} />

        {/* 403 Forbidden Page */}
        <Route path="forbidden" element={<ForbiddenPage />} />

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