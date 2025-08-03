import React, { useState, useEffect } from 'react';
import { Settings, Users, Phone, MessageCircle, Eye, Edit, Key, Plus, Activity } from 'lucide-react';

const AdminDashboard = () => {
  console.log('AdminDashboard component loaded');

  return (
    <div className="min-h-screen bg-red-100 p-8">
      <div className="max-w-4xl mx-auto">
        <div className="bg-white p-8 rounded-lg shadow-lg">
          <h1 className="text-3xl font-bold text-center text-gray-900 mb-6">
            ✅ דשבורד מנהל - Agent Locator
          </h1>
          
          <div className="text-center mb-8">
            <p className="text-gray-600 mb-4">המערכת עובדת!</p>
            <button
              onClick={() => {
                alert('כפתור עובד!');
              }}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 text-lg"
            >
              בדיקת כפתור
            </button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <div className="bg-blue-50 p-4 rounded-lg text-center">
              <h3 className="font-bold text-blue-800">📋 CRM</h3>
              <button
                onClick={() => alert('CRM נלחץ!')}
                className="mt-2 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
              >
                כניסה ל-CRM
              </button>
            </div>
            
            <div className="bg-green-50 p-4 rounded-lg text-center">
              <h3 className="font-bold text-green-800">📞 שיחות</h3>
              <button
                onClick={() => alert('שיחות נלחץ!')}
                className="mt-2 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
              >
                כניסה לשיחות
              </button>
            </div>
            
            <div className="bg-purple-50 p-4 rounded-lg text-center">
              <h3 className="font-bold text-purple-800">💬 WhatsApp</h3>
              <button
                onClick={() => alert('WhatsApp נלחץ!')}
                className="mt-2 bg-purple-600 text-white px-4 py-2 rounded hover:bg-purple-700"
              >
                כניסה ל-WhatsApp
              </button>
            </div>
          </div>

          <div className="text-center">
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
      </div>
    </div>
  );
};

export default AdminDashboard;