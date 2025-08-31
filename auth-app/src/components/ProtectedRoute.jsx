import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '@/contexts/AuthContext'

const ProtectedRoute = ({ children, requiredRole, requiredPermission }) => {
  const { user, loading, hasPermission } = useAuth()
  const location = useLocation()

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/auth/login" state={{ from: location }} replace />
  }

  // Check role requirement
  if (requiredRole) {
    const allowedRoles = Array.isArray(requiredRole) ? requiredRole : [requiredRole]
    
    // Special case: Admin impersonating business
    const isImpersonating = sessionStorage.getItem('impersonating_business_id')
    const isAdminImpersonating = isImpersonating && (user.role === 'admin' || user.role === 'superadmin')
    
    // Allow access if user has required role OR admin is impersonating
    if (!allowedRoles.includes(user.role) && !isAdminImpersonating) {
      return <Navigate to="/unauthorized" replace />
    }
  }

  // Check permission requirement
  if (requiredPermission && !hasPermission(requiredPermission)) {
    return <Navigate to="/unauthorized" replace />
  }

  return children
}

export default ProtectedRoute