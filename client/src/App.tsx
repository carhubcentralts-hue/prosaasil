import { useState, useEffect } from 'react';
import { ProfessionalLogin } from './components/ProfessionalLogin';
import { BusinessDashboard } from './components/BusinessDashboard';
import { AdminDashboard } from './components/AdminDashboard';
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
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">טוען...</p>
        </div>
      </div>
    );
  }

  if (!user) {
    return <ProfessionalLogin onLoginSuccess={handleLoginSuccess} />;
  }

  // Route based on user role
  if (user.role === 'admin') {
    return <AdminDashboard user={user} onLogout={handleLogout} />;
  } else {
    return <BusinessDashboard user={user} onLogout={handleLogout} />;
  }
}

export default App;