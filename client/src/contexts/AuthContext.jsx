import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext();

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Check if user is logged in
  useEffect(() => {
    const checkAuth = async () => {
      try {
        const token = localStorage.getItem('authToken');
        const role = localStorage.getItem('userRole');
        
        console.log('Auth check:', { token: !!token, role });
        
        if (token && role) {
          // Mock user data for testing
          setUser({
            id: 1,
            name: 'Test User',
            role: role,
            token: token
          });
        }
      } catch (error) {
        console.error('Auth check error:', error);
        localStorage.removeItem('authToken');
        localStorage.removeItem('userRole');
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, []);

  const login = async (credentials) => {
    try {
      // Mock login for testing
      const { username, password, role } = credentials;
      
      if (username && password) {
        const token = 'mock-token-' + Date.now();
        const userRole = role || 'business';
        
        localStorage.setItem('authToken', token);
        localStorage.setItem('userRole', userRole);
        
        setUser({
          id: 1,
          name: username,
          role: userRole,
          token: token
        });
        
        return { success: true, user: { name: username, role: userRole } };
      }
      
      throw new Error('Invalid credentials');
    } catch (error) {
      console.error('Login error:', error);
      throw error;
    }
  };

  const logout = () => {
    localStorage.removeItem('authToken');
    localStorage.removeItem('userRole');
    setUser(null);
  };

  const value = {
    user,
    login,
    logout,
    loading,
    isAuthenticated: !!user
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};