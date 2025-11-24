import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  Trash2, 
  Edit2,
  Users,
  Mail,
  UserCheck,
  Loader2 
} from 'lucide-react';
import { Card, Badge } from '../../shared/components/ui/Card';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { Select, SelectOption } from '../../shared/components/ui/Select';
import { apiRequest } from '../../lib/queryClient';
import { useAuth } from '../../features/auth/hooks';

interface User {
  id: number;
  name: string;
  email: string;
  role: 'business' | 'manager' | 'admin';
  business_id: number;
  created_at: string;
  last_login: string | null;
}

export function UsersManagementPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    password: '',
    role: ('business' as const) as 'business' | 'manager' | 'admin'
  });

  // Permission check: only admin/manager/superadmin can create users
  const canCreateUsers = currentUser && ['admin', 'manager', 'superadmin'].includes(currentUser.role);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const response = await apiRequest('/api/admin/users');
      setUsers(response);
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!formData.name || !formData.email || !formData.password) {
      alert('אנא מלא את כל השדות');
      return;
    }

    try {
      await apiRequest('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify(formData),
        headers: { 'Content-Type': 'application/json' }
      });
      alert('משתמש נוצר בהצלחה!');
      setFormData({ name: '', email: '', password: '', role: 'business' });
      setIsCreateModalOpen(false);
      fetchUsers();
    } catch (error: any) {
      alert(error.message || 'שגיאה ביצירת משתמש');
    }
  };

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;

    try {
      await apiRequest(`/api/admin/users/${editingUser.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: formData.name,
          password: formData.password || undefined,
          role: formData.role
        }),
        headers: { 'Content-Type': 'application/json' }
      });
      alert('משתמש עודכן בהצלחה!');
      setFormData({ name: '', email: '', password: '', role: 'business' });
      setEditingUser(null);
      fetchUsers();
    } catch (error: any) {
      alert(error.message || 'שגיאה בעדכון משתמש');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק את המשתמש הזה?')) return;

    try {
      await apiRequest(`/api/admin/users/${userId}`, {
        method: 'DELETE'
      });
      alert('משתמש נמחק בהצלחה!');
      fetchUsers();
    } catch (error: any) {
      alert(error.message || 'שגיאה במחיקת משתמש');
    }
  };

  const openEditModal = (user: User) => {
    if (!canCreateUsers) return;
    setFormData({
      name: user.name,
      email: user.email,
      password: '',
      role: user.role
    });
    setEditingUser(user);
  };

  // Get available roles based on current user's role
  const getAvailableRoles = () => {
    if (currentUser?.role === 'manager') {
      // Manager can only create business/manager
      return ['business', 'manager'];
    }
    // Admin and superadmin can create all
    return ['business', 'manager', 'admin'];
  };

  const closeModals = () => {
    setIsCreateModalOpen(false);
    setEditingUser(null);
    setFormData({ name: '', email: '', password: '', role: 'business' });
  };

  return (
    <main className="container mx-auto px-4 py-8 max-w-6xl" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">ניהול משתמשים</h1>
          <p className="text-gray-600 mt-1">
            {canCreateUsers ? 'צור וניהול משתמשי עסק' : 'צפה במשתמשים'}
          </p>
        </div>
        {canCreateUsers && (
          <Button 
            onClick={() => setIsCreateModalOpen(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="button-create-user"
          >
            <Plus className="w-4 h-4 ml-2" />
            משתמש חדש
          </Button>
        )}
      </div>

      {/* Users Table */}
      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-gray-400" />
            <p className="text-gray-600">טוען משתמשים...</p>
          </div>
        ) : users.length === 0 ? (
          <div className="p-12 text-center">
            <Users className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600 mb-4">אין משתמשים עדיין</p>
            {canCreateUsers && (
              <Button 
                onClick={() => setIsCreateModalOpen(true)}
                className="bg-blue-600 hover:bg-blue-700 text-white"
              >
                צור משתמש ראשון
              </Button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">שם</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">דוא"ל</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">תפקיד</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">כניסה אחרונה</th>
                  {canCreateUsers && (
                    <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">פעולות</th>
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <UserCheck className="w-4 h-4 text-gray-400" />
                        {user.name}
                      </div>
                    </td>
                    <td className="px-6 py-4 text-gray-600">{user.email}</td>
                    <td className="px-6 py-4">
                      <Badge variant={
                        user.role === 'admin' ? 'danger' :
                        user.role === 'manager' ? 'success' : 'neutral'
                      }>
                        {user.role === 'admin' ? 'ממנהל' : 
                         user.role === 'manager' ? 'מנהל' : 'עסק'}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 text-gray-600 text-sm">
                      {user.last_login 
                        ? new Date(user.last_login).toLocaleDateString('he-IL')
                        : 'לעולם לא'}
                    </td>
                    {canCreateUsers && (
                      <td className="px-6 py-4">
                        <div className="flex gap-2">
                          <button
                            onClick={() => openEditModal(user)}
                            className="p-2 hover:bg-gray-100 rounded-lg transition"
                            data-testid={`button-edit-user-${user.id}`}
                          >
                            <Edit2 className="w-4 h-4 text-gray-600" />
                          </button>
                          <button
                            onClick={() => handleDeleteUser(user.id)}
                            className="p-2 hover:bg-red-50 rounded-lg transition"
                            data-testid={`button-delete-user-${user.id}`}
                          >
                            <Trash2 className="w-4 h-4 text-red-600" />
                          </button>
                        </div>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Create/Edit Modal */}
      {(isCreateModalOpen || editingUser) && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md p-6 bg-white">
            <h2 className="text-xl font-bold mb-6 text-right">
              {editingUser ? 'עריכת משתמש' : 'משתמש חדש'}
            </h2>

            <form onSubmit={editingUser ? handleUpdateUser : handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 text-right">שם מלא</label>
                <Input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="שם המשתמש"
                  className="text-right"
                  data-testid="input-user-name"
                />
              </div>

              {!editingUser && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2 text-right">דוא"ל</label>
                  <Input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="user@example.com"
                    className="text-right"
                    data-testid="input-user-email"
                    dir="ltr"
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 text-right">
                  {editingUser ? 'סיסמה חדשה (optional)' : 'סיסמה'}
                </label>
                <Input
                  type="password"
                  value={formData.password}
                  onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                  placeholder="לפחות 6 תווים"
                  data-testid="input-user-password"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 text-right">תפקיד</label>
                <Select
                  value={formData.role}
                  onChange={(e) => setFormData({ ...formData, role: e.target.value as any })}
                  data-testid="select-user-role"
                >
                  <SelectOption value="business">משתמש עסק</SelectOption>
                  <SelectOption value="manager">מנהל</SelectOption>
                  {currentUser && ['admin', 'superadmin'].includes(currentUser.role) && (
                    <SelectOption value="admin">ממנהל</SelectOption>
                  )}
                </Select>
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeModals}
                  className="flex-1"
                  data-testid="button-cancel"
                >
                  ביטול
                </Button>
                <Button
                  type="submit"
                  className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                  data-testid={editingUser ? "button-update-user" : "button-create-user-submit"}
                >
                  {editingUser ? 'עדכן' : 'צור'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </main>
  );
}
