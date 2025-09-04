import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard } from './layout/AuthGuard';
import { MainLayout } from './layout/MainLayout';

// Auth Pages
import LoginPage from '../pages/Auth/LoginPage';
import ForgotPasswordPage from '../pages/Auth/ForgotPasswordPage';
import ResetPasswordPage from '../pages/Auth/ResetPasswordPage';

// App Pages
import AdminHomePage from '../pages/Admin/AdminHomePage';
import BusinessHomePage from '../pages/Business/BusinessHomePage';

// Placeholder page for upcoming features
function ComingSoonPage() {
  return (
    <div className="flex items-center justify-center min-h-96">
      <div className="text-center">
        <h2 className="text-2xl font-semibold text-gray-900 mb-2">בקרוב!</h2>
        <p className="text-gray-600">הפיצ'ר הזה בפיתוח ויהיה זמין בקרוב</p>
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
      
      {/* Protected Routes */}
      <Route path="/app" element={
        <AuthGuard>
          <MainLayout />
        </AuthGuard>
      }>
        {/* Admin Routes */}
        <Route path="admin/overview" element={
          <AuthGuard requiredRoles={['admin', 'manager']}>
            <AdminHomePage />
          </AuthGuard>
        } />
        
        {/* Business Routes */}
        <Route path="business/overview" element={
          <AuthGuard requiredRoles={['business', 'manager']}>
            <BusinessHomePage />
          </AuthGuard>
        } />
        
        {/* Placeholder routes for sidebar items */}
        <Route path="leads" element={<ComingSoonPage />} />
        <Route path="whatsapp" element={<ComingSoonPage />} />
        <Route path="calls" element={<ComingSoonPage />} />
        <Route path="crm" element={<ComingSoonPage />} />
        <Route path="payments" element={<ComingSoonPage />} />
        <Route path="business-manager" element={<ComingSoonPage />} />
        <Route path="users" element={<ComingSoonPage />} />
        <Route path="settings" element={<ComingSoonPage />} />
        <Route path="calendar" element={<ComingSoonPage />} />
      </Route>
      
      {/* Root redirect */}
      <Route path="/" element={<Navigate to="/login" replace />} />
      
      {/* Catch all - redirect to login */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  );
}