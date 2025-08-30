import { createContext, useContext, useState, useEffect } from 'react'

const AuthContext = createContext()

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [impersonating, setImpersonating] = useState(null)

  // Check authentication status
  const checkAuth = async () => {
    try {
      const response = await fetch('/api/auth/me', {
        credentials: 'include'
      })
      
      if (response.ok) {
        const userData = await response.json()
        setUser(userData)
      } else {
        setUser(null)
      }
    } catch (error) {
      console.error('Auth check failed:', error)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  // Login function
  const login = async (email, password) => {
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({ email, password })
      })

      if (response.ok) {
        const userData = await response.json()
        // Fix: Server returns nested user object
        setUser(userData.user || userData)
        return { success: true }
      } else {
        const error = await response.json()
        return { success: false, error: error.message }
      }
    } catch (error) {
      return { success: false, error: 'שגיאה בהתחברות' }
    }
  }

  // Logout function
  const logout = async () => {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include'
      })
    } catch (error) {
      console.error('Logout error:', error)
    } finally {
      setUser(null)
      setImpersonating(null)
    }
  }

  // Quick Actions - Admin tools for business management
  const quickViewBusiness = async (businessId) => {
    if (!hasPermission('manage_businesses')) return null
    
    try {
      const response = await fetch(`/api/businesses/${businessId}/quick-view`, {
        credentials: 'include'
      })

      if (response.ok) {
        return await response.json()
      }
    } catch (error) {
      console.error('Quick view error:', error)
    }
    return null
  }

  const quickCreateLead = async (businessId, leadData) => {
    if (!hasPermission('manage_businesses')) return false
    
    try {
      const response = await fetch(`/api/businesses/${businessId}/leads`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify(leadData)
      })

      return response.ok
    } catch (error) {
      console.error('Quick lead creation error:', error)
      return false
    }
  }

  const quickSendMessage = async (businessId, phoneNumber, message) => {
    if (!hasPermission('manage_businesses')) return false
    
    try {
      const response = await fetch(`/api/businesses/${businessId}/send-message`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({ phone: phoneNumber, message })
      })

      return response.ok
    } catch (error) {
      console.error('Quick message error:', error)
      return false
    }
  }

  const quickToggleIntegration = async (businessId, integration, enabled) => {
    if (!hasPermission('manage_businesses')) return false
    
    try {
      const response = await fetch(`/api/businesses/${businessId}/integrations/${integration}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({ enabled })
      })

      return response.ok
    } catch (error) {
      console.error('Quick integration toggle error:', error)
      return false
    }
  }

  // Stop impersonating (legacy - keeping for compatibility)
  const stopImpersonating = () => {
    setImpersonating(null)
  }

  // Permission check
  const hasPermission = (permission) => {
    if (!user) return false
    
    // Superadmin has all permissions
    if (user.role === 'superadmin') return true
    
    // Check specific permissions
    return user.permissions?.includes(permission) || user.permissions?.includes('all')
  }

  // Role checks
  const isAdmin = () => user?.role === 'admin' || user?.role === 'superadmin'
  const isBusiness = () => ['business_owner', 'business_agent', 'read_only'].includes(user?.role)
  const isBusinessOwner = () => user?.role === 'business_owner'

  // Get effective business ID (considering impersonation)
  const getBusinessId = () => {
    if (impersonating) return impersonating.id
    return user?.business_id
  }

  useEffect(() => {
    checkAuth()
  }, [])

  const value = {
    user,
    loading,
    impersonating,
    login,
    logout,
    quickViewBusiness,
    quickCreateLead,
    quickSendMessage,
    quickToggleIntegration,
    stopImpersonating,
    hasPermission,
    isAdmin,
    isBusiness,
    isBusinessOwner,
    getBusinessId,
    checkAuth
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}