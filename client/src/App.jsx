import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import './index.css';

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [userRole, setUserRole] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // בדיקה אם משתמש מחובר
    const token = localStorage.getItem('auth_token');
    const role = localStorage.getItem('user_role');
    
    console.log('Auth check:', { token: !!token, role });
    
    if (token && role) {
      setIsAuthenticated(true);
      setUserRole(role);
    } else {
      setIsAuthenticated(false);
      setUserRole(null);
    }
    setLoading(false);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600 font-hebrew">טוען מערכת...</p>
        </div>
      </div>
    );
  }

  // אם לא מחובר - הצג רק דף התחברות
  if (!isAuthenticated) {
    return (
      <div className="App">
        <Router>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </Routes>
        </Router>
      </div>
    );
  }

  // זמנית - הצג הודעה שהמערכת בבנייה
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center font-hebrew rtl">
      <div className="bg-white p-8 rounded-lg shadow-lg text-center">
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          המערכת בבנייה
        </h1>
        <p className="text-gray-600 mb-6">
          המערכת נבנית שלב אחר שלב. בחזרה בקרוב!
        </p>
        <p className="text-sm text-gray-500 mb-4">
          מחובר כ: {userRole === 'admin' ? 'מנהל' : 'עסק'}
        </p>
        <button
          onClick={() => {
            localStorage.removeItem('auth_token');
            localStorage.removeItem('user_role');
            window.location.reload();
          }}
          className="bg-red-600 text-white px-4 py-2 rounded-lg hover:bg-red-700"
        >
          יציאה מהמערכת
        </button>
      </div>
    </div>
  );
}

export default App;
