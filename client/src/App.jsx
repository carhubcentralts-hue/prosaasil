import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
// Modern SaaS Components
import LoginPage from './pages/LoginPage';
import ModernDashboard from './pages/ModernDashboard';
import ModernCRM from './pages/ModernCRM';
import AdvancedCRM from './pages/AdvancedCRM';
import ModernCalls from './pages/ModernCalls';
import ModernWhatsApp from './pages/ModernWhatsApp';
import ModernSettings from './pages/ModernSettings';
import ModernAnalytics from './pages/ModernAnalytics';
import AdminBusinesses from './pages/AdminBusinesses';
import AdminSystem from './pages/AdminSystem';
import AdminSecurity from './pages/AdminSecurity';
import { Toaster } from './components/ui/toaster';

function App() {
  console.log('🌐 App: Current location:', window.location.pathname);

  return (
    <div className="App">
      <AuthProvider>
        <Router>
          <Routes>
            {/* דף התחברות */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* נתיבים מוגנים למנהל */}
            <Route path="/admin/dashboard" element={
              <PrivateRoute requiredRole="admin">
                <ModernDashboard />
              </PrivateRoute>
            } />
            
            <Route path="/admin/crm/advanced" element={
              <PrivateRoute requiredRole="admin">
                <ModernCRM />
              </PrivateRoute>
            } />
            
            <Route path="/admin/calls" element={
              <PrivateRoute requiredRole="admin">
                <ModernCalls />
              </PrivateRoute>
            } />
            
            <Route path="/admin/whatsapp" element={
              <PrivateRoute requiredRole="admin">
                <ModernWhatsApp />
              </PrivateRoute>
            } />
            
            <Route path="/admin/businesses" element={
              <PrivateRoute requiredRole="admin">
                <AdminBusinesses />
              </PrivateRoute>
            } />
            
            <Route path="/admin/system" element={
              <PrivateRoute requiredRole="admin">
                <AdminSystem />
              </PrivateRoute>
            } />
            
            <Route path="/admin/analytics" element={
              <PrivateRoute requiredRole="admin">
                <ModernAnalytics />
              </PrivateRoute>
            } />
            
            <Route path="/admin/security" element={
              <PrivateRoute requiredRole="admin">
                <AdminSecurity />
              </PrivateRoute>
            } />
            
            <Route path="/admin/*" element={
              <PrivateRoute requiredRole="admin">
                <ModernDashboard />
              </PrivateRoute>
            } />
            
            {/* נתיבים מוגנים לעסקים */}
            <Route path="/business/dashboard" element={
              <PrivateRoute requiredRole="business">
                <ModernDashboard />
              </PrivateRoute>
            } />
            
            <Route path="/business/crm/advanced" element={
              <PrivateRoute requiredRole="business">
                <ModernCRM />
              </PrivateRoute>
            } />
            
            <Route path="/crm" element={
              <PrivateRoute requiredRole="business">
                <ModernCRM />
              </PrivateRoute>
            } />
            
            <Route path="/advanced-crm" element={
              <PrivateRoute requiredRole="business">
                <AdvancedCRM />
              </PrivateRoute>
            } />
            
            <Route path="/calls" element={
              <PrivateRoute requiredRole="business">
                <ModernCalls />
              </PrivateRoute>
            } />
            
            <Route path="/business/calls" element={
              <PrivateRoute requiredRole="business">
                <ModernCalls />
              </PrivateRoute>
            } />
            
            <Route path="/whatsapp" element={
              <PrivateRoute requiredRole="business">
                <ModernWhatsApp />
              </PrivateRoute>
            } />
            
            <Route path="/business/whatsapp" element={
              <PrivateRoute requiredRole="business">
                <ModernWhatsApp />
              </PrivateRoute>
            } />
            
            <Route path="/analytics" element={
              <PrivateRoute requiredRole="business">
                <ModernAnalytics />
              </PrivateRoute>
            } />
            
            <Route path="/settings" element={
              <PrivateRoute requiredRole="business">
                <ModernSettings />
              </PrivateRoute>
            } />
            
            {/* נתיב ברירת מחדל */}
            <Route path="/" element={
              <PrivateRoute requiredRole="business">
                <ModernDashboard />
              </PrivateRoute>
            } />
            
            {/* נתיב לדפים לא נמצאו */}
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </Router>
      </AuthProvider>
      <Toaster />
    </div>
  );
}

export default App;