import React, { useState, useEffect } from 'react';
import BusinessDashboard from './pages/BusinessDashboard';
import AdminDashboard from './pages/AdminDashboard';
import './index.css';

function App() {
  const [userRole, setUserRole] = useState('business'); // 'admin' או 'business'
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // בדיקת תפקיד המשתמש
    const checkUserRole = async () => {
      try {
        // כאן נבדוק עם הAPI מה התפקיד של המשתמש
        // לעת עתה נשתמש בפרמטר URL או localStorage
        const urlParams = new URLSearchParams(window.location.search);
        const roleParam = urlParams.get('role');
        
        if (roleParam === 'admin') {
          setUserRole('admin');
        } else {
          setUserRole('business');
        }
      } catch (error) {
        console.error('Error checking user role:', error);
        setUserRole('business'); // ברירת מחדל
      } finally {
        setLoading(false);
      }
    };

    checkUserRole();
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

  return (
    <div className="App">
      {userRole === 'admin' ? <AdminDashboard /> : <BusinessDashboard />}
    </div>
  );
}

export default App;
