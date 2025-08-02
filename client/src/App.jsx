import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import BusinessDashboard from './pages/BusinessDashboard';
import AdminDashboard from './pages/AdminDashboard';
import BusinessViewPage from './pages/BusinessViewPage';
import LoginPage from './pages/LoginPage';
import PrivateRoute from './components/PrivateRoute';
import './index.css';

function App() {
  return (
    <div className="App">
      <Router>
        <Routes>
          {/* דף התחברות - הדף הראשון */}
          <Route path="/login" element={<LoginPage />} />
          
          {/* דשבורד מנהל - מוגן */}
          <Route 
            path="/admin/dashboard" 
            element={
              <PrivateRoute requiredRole="admin">
                <AdminDashboard />
              </PrivateRoute>
            } 
          />
          
          {/* דשבורד עסק - מוגן */}
          <Route 
            path="/business/dashboard" 
            element={
              <PrivateRoute requiredRole="business">
                <BusinessDashboard />
              </PrivateRoute>
            } 
          />
          
          {/* דף צפייה בעסק ספציפי - מוגן למנהלים בלבד */}
          <Route 
            path="/business/:businessId/dashboard" 
            element={
              <PrivateRoute requiredRole="admin">  
                <BusinessViewPage />
              </PrivateRoute>
            } 
          />
          
          {/* נתיב ברירת מחדל - הפנייה לדף התחברות */}
          <Route 
            path="/" 
            element={<Navigate to="/login" replace />} 
          />
          
          {/* דף לא מוכר */}
          <Route 
            path="*" 
            element={<Navigate to="/login" replace />} 
          />
        </Routes>
      </Router>
    </div>
  );
}

export default App;
