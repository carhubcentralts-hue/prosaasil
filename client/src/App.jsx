import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider } from './contexts/AuthContext';
import PrivateRoute from './components/PrivateRoute';
// נניתוח נתיבים
import LoginPage from './pages/LoginPage';
import AdminDashboard from './pages/AdminDashboard';
import BusinessDashboard from './pages/BusinessDashboard';
import AdvancedCRMPage from './pages/AdvancedCRMPage';
import CallSystemPage from './pages/CallSystemPage';
import WhatsAppPage from './pages/WhatsAppPage';
import AgentLocatorDashboard from './components/AgentLocatorDashboard';
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
                <AdminDashboard />
              </PrivateRoute>
            } />
            
            <Route path="/admin/crm/advanced" element={
              <PrivateRoute requiredRole="admin">
                <AdvancedCRMPage />
              </PrivateRoute>
            } />
            
            <Route path="/admin/phone-analysis" element={
              <PrivateRoute requiredRole="admin">
                <CallSystemPage />
              </PrivateRoute>
            } />
            
            <Route path="/admin/whatsapp" element={
              <PrivateRoute requiredRole="admin">
                <WhatsAppPage />
              </PrivateRoute>
            } />
            
            <Route path="/admin/*" element={
              <PrivateRoute requiredRole="admin">
                <AdminDashboard />
              </PrivateRoute>
            } />
            
            {/* נתיבים מוגנים לעסקים */}
            <Route path="/business/dashboard" element={
              <PrivateRoute requiredRole="business">
                <BusinessDashboard />
              </PrivateRoute>
            } />
            
            <Route path="/business/crm/advanced" element={
              <PrivateRoute requiredRole="business">
                <AdvancedCRMPage />
              </PrivateRoute>
            } />
            
            <Route path="/calls" element={
              <PrivateRoute requiredRole="business">
                <CallSystemPage />
              </PrivateRoute>
            } />
            
            <Route path="/business/calls" element={
              <PrivateRoute requiredRole="business">
                <CallSystemPage />
              </PrivateRoute>
            } />
            
            <Route path="/whatsapp" element={
              <PrivateRoute requiredRole="business">
                <WhatsAppPage />
              </PrivateRoute>
            } />
            
            <Route path="/business/whatsapp" element={
              <PrivateRoute requiredRole="business">
                <WhatsAppPage />
              </PrivateRoute>
            } />
            
            {/* דשבורד AgentLocator */}
            <Route path="/agentlocator" element={
              <PrivateRoute requiredRole="business">
                <AgentLocatorDashboard />
              </PrivateRoute>
            } />
            
            {/* נתיב ברירת מחדל */}
            <Route path="/" element={
              <PrivateRoute requiredRole="business">
                <BusinessDashboard />
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