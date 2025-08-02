import React from 'react';

function AppSimple() {
  return (
    <div style={{ 
      fontFamily: 'Assistant, sans-serif',
      direction: 'rtl',
      padding: '20px',
      backgroundColor: '#f8f9fa'
    }}>
      <h1 style={{ color: '#333', fontSize: '24px' }}>
        🎯 ברוך הבא למערכת CRM עברית
      </h1>
      <div style={{
        backgroundColor: 'white',
        padding: '20px',
        borderRadius: '8px',
        marginTop: '20px',
        boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
      }}>
        <h2>בדיקת עבודה</h2>
        <p>אם אתה רואה את הטקסט הזה, React עובד תקין!</p>
        <button 
          style={{
            backgroundColor: '#007bff',
            color: 'white', 
            padding: '10px 20px',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
          onClick={() => alert('הכפתור עובד!')}
        >
          לחץ כאן לבדיקה
        </button>
      </div>
    </div>
  );
}

export default AppSimple;