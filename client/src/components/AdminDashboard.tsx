import { useState, useEffect } from 'react';
import { useAuth } from '../hooks/useAuth';
// Use local User interface
interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: string;
  businessId: string | null;
  isActive: boolean;
  lastLogin?: Date | null;
}

interface AdminDashboardProps {
  onBack: () => void;
}

export function AdminDashboard({ onBack }: AdminDashboardProps) {
  const { user } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/admin/users', {
        credentials: 'include',
      });

      if (!response.ok) {
        throw new Error('שגיאה בטעינת משתמשים');
      }

      const usersData = await response.json();
      setUsers(usersData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'שגיאה בטעינת נתונים');
    } finally {
      setIsLoading(false);
    }
  };

  const getRoleText = (role: string) => {
    switch (role) {
      case 'admin': return 'מנהל מערכת';
      case 'business': return 'מנהל עסק';
      default: return 'משתמש';
    }
  };

  const getStatusText = (isActive: boolean) => isActive ? 'פעיל' : 'לא פעיל';

  if (isLoading) {
    return (
      <div className="min-h-screen bg-white flex items-center justify-center">
        <div className="text-xl text-gray-600" dir="rtl">טוען נתונים...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-white">
      <div className="max-w-7xl mx-auto py-8 px-4 sm:px-6 lg:px-8">
        {/* Header */}
        <div className="mb-8" dir="rtl">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-3xl font-bold text-gray-900">פאנל ניהול מנהל</h1>
            <button
              onClick={onBack}
              className="bg-gray-600 text-white px-4 py-2 rounded-md hover:bg-gray-700 transition-colors"
              data-testid="button-back"
            >
              חזור לתפריט ראשי
            </button>
          </div>
          <p className="text-gray-600">
            שלום {user?.firstName} {user?.lastName} • ניהול משתמשים ומערכת
          </p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6" data-testid="text-error">
            {error}
          </div>
        )}

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-6" data-testid="card-total-users">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600">{users.length}</div>
              <div className="text-blue-800 font-medium" dir="rtl">סך משתמשים</div>
            </div>
          </div>
          
          <div className="bg-green-50 border border-green-200 rounded-lg p-6" data-testid="card-active-users">
            <div className="text-center">
              <div className="text-3xl font-bold text-green-600">
                {users.filter(u => u.isActive).length}
              </div>
              <div className="text-green-800 font-medium" dir="rtl">משתמשים פעילים</div>
            </div>
          </div>

          <div className="bg-purple-50 border border-purple-200 rounded-lg p-6" data-testid="card-admin-users">
            <div className="text-center">
              <div className="text-3xl font-bold text-purple-600">
                {users.filter(u => u.role === 'admin').length}
              </div>
              <div className="text-purple-800 font-medium" dir="rtl">מנהלי מערכת</div>
            </div>
          </div>

          <div className="bg-orange-50 border border-orange-200 rounded-lg p-6" data-testid="card-business-users">
            <div className="text-center">
              <div className="text-3xl font-bold text-orange-600">
                {users.filter(u => u.role === 'business').length}
              </div>
              <div className="text-orange-800 font-medium" dir="rtl">מנהלי עסקים</div>
            </div>
          </div>
        </div>

        {/* Business Info */}
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 mb-8">
          <h2 className="text-xl font-bold text-gray-900 mb-4" dir="rtl">עסק במערכת</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4" dir="rtl">
            <div>
              <strong>שם העסק:</strong> שי דירות ומשרדים בע״מ
            </div>
            <div>
              <strong>תחום:</strong> נדל״ן
            </div>
            <div>
              <strong>טלפון:</strong> +972-50-123-4567
            </div>
            <div>
              <strong>אימייל:</strong> info@shai-realestate.co.il
            </div>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <h2 className="text-xl font-bold text-gray-900" dir="rtl">רשימת משתמשים</h2>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200" dir="rtl">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    שם מלא
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    אימייל
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    תפקיד
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    סטטוס
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    כניסה אחרונה
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {users.map((userData) => (
                  <tr key={userData.id} data-testid={`row-user-${userData.id}`}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        {userData.firstName} {userData.lastName}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-900">{userData.email}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        userData.role === 'admin' 
                          ? 'bg-purple-100 text-purple-800'
                          : userData.role === 'business'
                          ? 'bg-blue-100 text-blue-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {getRoleText(userData.role)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                        userData.isActive
                          ? 'bg-green-100 text-green-800'
                          : 'bg-red-100 text-red-800'
                      }`}>
                        {getStatusText(userData.isActive)}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {userData.lastLogin 
                        ? new Date(userData.lastLogin).toLocaleDateString('he-IL')
                        : 'אף פעם'
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}