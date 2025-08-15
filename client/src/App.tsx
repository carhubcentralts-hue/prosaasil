import { useState, useEffect } from 'react';
import { ProfessionalLogin } from './components/ProfessionalLogin';
import { AuthService } from './lib/auth';

function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const userData = await AuthService.getCurrentUser();
      setUser(userData);
    } catch (error) {
      // User not authenticated
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLoginSuccess = (userData: any) => {
    setUser(userData);
  };

  const handleLogout = async () => {
    try {
      await AuthService.logout();
      setUser(null);
    } catch (error) {
      console.error('Logout error:', error);
      setUser(null); // Force logout even if API call fails
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600 font-medium">טוען...</p>
        </div>
      </div>
    );
  }

  // תמיד נראה login - ללא dashboards
  if (!user) {
    return <ProfessionalLogin onLoginSuccess={handleLoginSuccess} />;
  }

  // אם מחובר - נראה הודעת הצלחה ואפשרות logout
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
      <div className="max-w-md w-full space-y-8 bg-white p-8 rounded-xl shadow-lg">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 mb-2">מערכת CRM</h2>
          <p className="text-green-600 font-medium mb-6">התחברת בהצלחה!</p>
          <div className="bg-gray-50 p-4 rounded-lg mb-6">
            <p className="text-sm text-gray-600">משתמש: {user.email}</p>
            <p className="text-sm text-gray-600">תפקיד: {user.role === 'admin' ? 'מנהל' : 'עסק'}</p>
          </div>
          <button
            onClick={handleLogout}
            className="w-full bg-red-600 text-white py-2 px-4 rounded-lg hover:bg-red-700 transition-colors"
          >
            התנתק
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;