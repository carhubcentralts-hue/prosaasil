// Simple test page without any dependencies
const TestPage = () => {
  console.log('🚨 TEST PAGE LOADED!')
  
  return (
    <div style={{
      backgroundColor: 'red',
      color: 'white',
      padding: '50px',
      fontSize: '24px',
      textAlign: 'center',
      minHeight: '100vh'
    }}>
      <h1>🚨 TEST PAGE WORKS!</h1>
      <p>אם אתה רואה את זה - React עובד!</p>
      <p>הבעיה ב-AuthContext או ProtectedRoute</p>
    </div>
  )
}

export default TestPage