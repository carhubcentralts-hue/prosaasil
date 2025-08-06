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
        const name = localStorage.getItem('userName') || 'משתמש';
        
        console.log('Auth check:', { token: !!token, role, name });
        
        if (token && role) {
          setUser({
            id: 1,
            name: name,
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
      const { username, password, role } = credentials;
      
      if (username && password) {
        const token = localStorage.getItem('authToken') || 'mock-token-' + Date.now();
        const userRole = role || 'business';
        const userName = localStorage.getItem('userName') || username;
        
        // עדכן localStorage אם עדיין לא קיים
        localStorage.setItem('authToken', token);
        localStorage.setItem('userRole', userRole);
        localStorage.setItem('userName', userName);
        
        // עדכן את המשתמש ב-state
        setUser({
          id: 1,
          name: userName,
          role: userRole,
          token: token
        });
        
        console.log('Auth updated:', { name: userName, role: userRole, token: !!token });
        
        return { success: true, user: { name: userName, role: userRole } };
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
    localStorage.removeItem('userName');
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