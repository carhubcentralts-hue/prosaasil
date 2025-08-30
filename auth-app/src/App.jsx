import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import Layout from '@/components/Layout'
import AppShell from '@/components/shell/AppShell'
import ProtectedRoute from '@/components/ProtectedRoute'
import Login from '@/pages/Login'
import ForgotPassword from '@/pages/ForgotPassword'
import ResetPassword from '@/pages/ResetPassword'
import AdminOverview from '@/pages/admin/AdminOverview'
import BusinessOverview from '@/pages/business/BusinessOverview'
import { ToastProvider } from '@/components/Toast'
import { AuthProvider } from '@/contexts/AuthContext'

// Unauthorized page
const Unauthorized = () => (
  <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
    <motion.div
      className="text-center p-8"
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
    >
      <h1 className="text-2xl font-bold text-red-600 mb-4">אין הרשאה</h1>
      <p className="text-slate-600 mb-6">אין לך הרשאה לגשת לדף זה</p>
      <button
        onClick={() => window.history.back()}
        className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
      >
        חזור אחורה
      </button>
    </motion.div>
  </div>
)

function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <Router>
          <Routes>
            {/* Auth Routes */}
            <Route path="/auth/login" element={
              <Layout>
                <Login />
              </Layout>
            } />
            <Route path="/auth/forgot" element={
              <Layout>
                <ForgotPassword />
              </Layout>
            } />
            <Route path="/auth/reset" element={
              <Layout>
                <ResetPassword />
              </Layout>
            } />
            
            {/* Admin Routes */}
            <Route path="/app/admin/*" element={
              <ProtectedRoute requiredRole={['superadmin', 'admin']}>
                <AppShell>
                  <Routes>
                    <Route path="overview" element={<AdminOverview />} />
                    <Route path="businesses" element={<div>עסקים (בבנייה)</div>} />
                    <Route path="users" element={<div>משתמשים (בבנייה)</div>} />
                    <Route path="whatsapp" element={<div>WhatsApp Panorama (בבנייה)</div>} />
                    <Route path="calls" element={<div>שיחות מערכתיות (בבנייה)</div>} />
                    <Route path="finance" element={<div>כספים (בבנייה)</div>} />
                    <Route path="settings" element={<div>הגדרות מערכת (בבנייה)</div>} />
                    <Route path="" element={<Navigate to="overview" replace />} />
                  </Routes>
                </AppShell>
              </ProtectedRoute>
            } />
            
            {/* Business Routes */}
            <Route path="/app/biz/*" element={
              <ProtectedRoute requiredRole={['business_owner', 'business_agent', 'read_only']}>
                <AppShell>
                  <Routes>
                    <Route path="overview" element={<BusinessOverview />} />
                    <Route path="whatsapp" element={<div>WhatsApp (בבנייה)</div>} />
                    <Route path="calls" element={<div>שיחות (בבנייה)</div>} />
                    <Route path="crm" element={<div>CRM (בבנייה)</div>} />
                    <Route path="finance" element={<div>תשלומים וחוזים (בבנייה)</div>} />
                    <Route path="users" element={
                      <ProtectedRoute requiredPermission="manage_business_users">
                        <div>משתמשי העסק (בבנייה)</div>
                      </ProtectedRoute>
                    } />
                    <Route path="settings" element={<div>הגדרות העסק (בבנייה)</div>} />
                    <Route path="" element={<Navigate to="overview" replace />} />
                  </Routes>
                </AppShell>
              </ProtectedRoute>
            } />
            
            {/* Other Routes */}
            <Route path="/unauthorized" element={<Unauthorized />} />
            <Route path="/" element={<Navigate to="/auth/login" replace />} />
            <Route path="*" element={<Navigate to="/auth/login" replace />} />
          </Routes>
        </Router>
      </ToastProvider>
    </AuthProvider>
  )
}

export default App