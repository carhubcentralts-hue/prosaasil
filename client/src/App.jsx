import React, { useState } from 'react';
import LoginPage from './pages/LoginPage';
import './index.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);

  // בדיקה אם משתמש מחובר
  React.useEffect(() => {
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    
    console.log('Auth check:', { token: !!token, role });
    
    if (token && role) {
      setIsAuthenticated(true);
      setUserRole(role);
    }
  }, []);

  // אם לא מחובר - הצג רק דף התחברות
  if (!isAuthenticated) {
    return (
      <div className="App">
        <LoginPage />
      </div>
    );
  }

  // אם מחובר - הצג הודעת הצלחה זמנית
  return (
    <div className="App">
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white p-8 rounded-lg shadow-lg max-w-md w-full text-center">
          <h1 className="text-2xl font-bold text-green-600 mb-4 font-hebrew">
            ✅ התחברות הצליחה!
          </h1>
          <p className="text-gray-600 mb-4 font-hebrew">
            שלום {userRole === 'admin' ? 'מנהל' : 'משתמש עסק'}
          </p>
          <p className="text-sm text-gray-500 mb-6 font-hebrew">
            מערכת Agent Locator - CRM מתקדמת
          </p>
          <button
            onClick={() => {
              localStorage.removeItem('auth_token');
              localStorage.removeItem('user_role');
              setIsAuthenticated(false);
              setUserRole(null);
            }}
            className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700 transition-colors font-hebrew"
          >
            יציאה מהמערכת
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;