import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'

// Simple Test Component to check if React works
const SimpleTest = () => {
  console.log('✅ React is working!')
  
  return (
    <div style={{
      backgroundColor: '#10b981',
      color: 'white',
      padding: '50px',
      fontSize: '24px',
      textAlign: 'center',
      minHeight: '100vh',
      fontFamily: 'Arial, sans-serif'
    }}>
      <h1 style={{ fontSize: '48px', marginBottom: '20px' }}>✅ SUCCESS!</h1>
      <h2 style={{ fontSize: '32px', marginBottom: '20px' }}>React 19 עובד!</h2>
      <p style={{ fontSize: '20px', marginBottom: '10px' }}>הניתוב עובד נכון</p>
      <p style={{ fontSize: '18px', color: '#dcfce7' }}>עכשיו נחזיר את העיצוב המלא...</p>
      <div style={{ marginTop: '30px', fontSize: '16px', color: '#dcfce7' }}>
        נתיב נוכחי: {window.location.pathname}
      </div>
    </div>
  )
}

function App() {
  console.log('🚀 App component loading...')
  
  return (
    <Router>
      <Routes>
        {/* Super simple test routes */}
        <Route path="/test" element={<SimpleTest />} />
        <Route path="/app/admin/overview" element={<SimpleTest />} />
        <Route path="/" element={<SimpleTest />} />
        <Route path="*" element={<SimpleTest />} />
      </Routes>
    </Router>
  )
}

export default App