import { useState, useEffect } from 'react';
import {
  Users,
  Plus,
  Edit,
  Trash2,
  Crown,
  X
} from 'lucide-react';
import { http } from '../../../services/http';

interface User {
  id: number;
  email: string;
  first_name?: string;
  last_name?: string;
  name: string;
  role: 'owner' | 'admin' | 'agent';
  is_active: boolean;
  created_at?: string;
  last_login?: string;
}

interface BusinessUsersModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  businessId: number;
  businessName: string;
}

export function BusinessUsersModal({
  open,
  onOpenChange,
  businessId,
  businessName
}: BusinessUsersModalProps) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddUser, setShowAddUser] = useState(false);
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Form state for add/edit user
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    first_name: '',
    last_name: '',
    role: 'agent' as 'owner' | 'admin' | 'agent'
  });

  // Load users when modal opens
  useEffect(() => {
    if (open && businessId) {
      fetchUsers();
    }
  }, [open, businessId]);

  const showMessage = (type: 'success' | 'error', message: string) => {
    if (type === 'success') {
      setSuccess(message);
      setError(null);
      setTimeout(() => setSuccess(null), 3000);
    } else {
      setError(message);
      setSuccess(null);
    }
  };

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await http.get<{
        users: User[];
        business_name: string;
        total: number;
      }>(`/api/admin/businesses/${businessId}/users`);
      setUsers(response.users);
    } catch (err) {
      showMessage('error', 'לא הצלחנו לטעון את רשימת המשתמשים');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!formData.email || !formData.password) {
      showMessage('error', 'נא למלא אימייל וסיסמה');
      return;
    }

    try {
      await http.post(`/api/admin/businesses/${businessId}/users`, formData);

      showMessage('success', 'המשתמש נוצר בהצלחה');

      // Reset form and reload users
      setFormData({
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        role: 'agent'
      });
      setShowAddUser(false);
      fetchUsers();
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'לא הצלחנו ליצור משתמש');
    }
  };

  const handleUpdateUser = async (userId: number) => {
    if (!editingUser) return;

    try {
      // ✅ CRITICAL FIX: Only include password if user explicitly set a new one
      const updatePayload: Record<string, any> = {
        email: formData.email,
        first_name: formData.first_name,
        last_name: formData.last_name,
        role: formData.role
      };
      
      // Only include password if it's non-empty (user explicitly changed it)
      if (formData.password && formData.password.trim() !== '') {
        updatePayload.password = formData.password;
      }

      await http.put(`/api/admin/businesses/${businessId}/users/${userId}`, updatePayload);

      showMessage('success', 'המשתמש עודכן בהצלחה');

      setEditingUser(null);
      setFormData({
        email: '',
        password: '',
        first_name: '',
        last_name: '',
        role: 'agent'
      });
      fetchUsers();
    } catch (err) {
      showMessage('error', 'לא הצלחנו לעדכן משתמש');
    }
  };

  const handleDeleteUser = async (userId: number) => {
    if (!confirm('האם אתה בטוח שברצונך למחוק משתמש זה?')) {
      return;
    }

    try {
      await http.delete(`/api/admin/businesses/${businessId}/users/${userId}`);

      showMessage('success', 'המשתמש נמחק בהצלחה');
      fetchUsers();
    } catch (err) {
      showMessage('error', err instanceof Error ? err.message : 'לא הצלחנו למחוק משתמש');
    }
  };

  const handleSetOwner = async (userId: number) => {
    if (!confirm('האם אתה בטוח שברצונך להפוך משתמש זה לבעלים?')) {
      return;
    }

    try {
      await http.post(`/api/admin/businesses/${businessId}/owner`, { user_id: userId });

      showMessage('success', 'המשתמש הוגדר כבעלים');
      fetchUsers();
    } catch (err) {
      showMessage('error', 'לא הצלחנו להגדיר כבעלים');
    }
  };

  const startEditUser = (user: User) => {
    setEditingUser(user);
    setFormData({
      email: user.email,
      password: '',
      first_name: user.first_name || '',
      last_name: user.last_name || '',
      role: user.role
    });
  };

  const cancelEdit = () => {
    setEditingUser(null);
    setShowAddUser(false);
    setFormData({
      email: '',
      password: '',
      first_name: '',
      last_name: '',
      role: 'agent'
    });
  };

  const getRoleBadge = (role: string) => {
    const roleConfig = {
      owner: { label: 'בעלים', color: 'bg-purple-100 text-purple-800' },
      admin: { label: 'מנהל', color: 'bg-blue-100 text-blue-800' },
      agent: { label: 'סוכן', color: 'bg-gray-100 text-gray-800' }
    };

    const config = roleConfig[role as keyof typeof roleConfig] || roleConfig.agent;

    return (
      <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${config.color}`}>
        {config.label}
      </span>
    );
  };

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" dir="rtl">
      <div className="bg-white rounded-xl shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <div>
            <h2 className="text-xl font-semibold text-slate-900 flex items-center gap-2">
              <Users className="h-5 w-5" />
              ניהול משתמשים - {businessName}
            </h2>
            <p className="text-sm text-slate-600 mt-1">צפייה ועריכה של המשתמשים העובדים בעסק זה</p>
          </div>
          <button
            onClick={() => onOpenChange(false)}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg transition-colors"
            data-testid="button-close-modal"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Messages */}
          {error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">
              {error}
            </div>
          )}
          {success && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-800 text-sm">
              {success}
            </div>
          )}

          {/* Add User Button */}
          {!showAddUser && !editingUser && (
            <button
              onClick={() => setShowAddUser(true)}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              data-testid="button-add-user"
            >
              <Plus className="h-4 w-4" />
              הוסף משתמש חדש
            </button>
          )}

          {/* Add/Edit User Form */}
          {(showAddUser || editingUser) && (
            <div className="border rounded-lg p-4 bg-slate-50 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-medium">
                  {editingUser ? 'עריכת משתמש' : 'הוספת משתמש חדש'}
                </h3>
                <button
                  onClick={cancelEdit}
                  className="p-1 text-slate-400 hover:text-slate-600 transition-colors"
                  data-testid="button-cancel-edit"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">אימייל</label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="user@example.com"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                    data-testid="input-email"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    סיסמה {editingUser && '(השאר ריק לשמירה)'}
                  </label>
                  <input
                    type="password"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder={editingUser ? 'השאר ריק אם לא רוצה לשנות' : 'סיסמה'}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                    data-testid="input-password"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">שם פרטי</label>
                  <input
                    type="text"
                    value={formData.first_name}
                    onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
                    placeholder="שם פרטי"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                    data-testid="input-first-name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">שם משפחה</label>
                  <input
                    type="text"
                    value={formData.last_name}
                    onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
                    placeholder="שם משפחה"
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                    data-testid="input-last-name"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">תפקיד</label>
                  <select
                    value={formData.role}
                    onChange={(e) => setFormData({ ...formData, role: e.target.value as 'owner' | 'admin' | 'agent' })}
                    className="w-full px-3 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-white"
                    data-testid="select-role"
                  >
                    <option value="owner">בעלים</option>
                    <option value="admin">מנהל</option>
                    <option value="agent">סוכן</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={editingUser ? () => handleUpdateUser(editingUser.id) : handleCreateUser}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  data-testid="button-save-user"
                >
                  {editingUser ? 'עדכן משתמש' : 'צור משתמש'}
                </button>
                <button
                  onClick={cancelEdit}
                  className="px-4 py-2 border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                  data-testid="button-cancel-form"
                >
                  ביטול
                </button>
              </div>
            </div>
          )}

          {/* Users Table */}
          {loading ? (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
              <p className="text-slate-600">טוען משתמשים...</p>
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-8 text-slate-500">אין משתמשים בעסק זה</div>
          ) : (
            <div className="border rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">אימייל</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">שם</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">תפקיד</th>
                    <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">פעולות</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {users.map((user) => (
                    <tr key={user.id} className="hover:bg-slate-50 transition-colors">
                      <td className="text-right py-3 px-4 font-medium text-slate-900">
                        {user.email}
                      </td>
                      <td className="text-right py-3 px-4 text-slate-700">
                        {user.first_name && user.last_name
                          ? `${user.first_name} ${user.last_name}`
                          : user.name}
                      </td>
                      <td className="text-right py-3 px-4">
                        {getRoleBadge(user.role)}
                      </td>
                      <td className="text-right py-3 px-4">
                        <div className="flex gap-2 justify-end">
                          <button
                            onClick={() => startEditUser(user)}
                            className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            title="עריכה"
                            data-testid={`button-edit-user-${user.id}`}
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          {user.role !== 'owner' && (
                            <button
                              onClick={() => handleSetOwner(user.id)}
                              className="p-1.5 text-slate-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                              title="הפוך לבעלים"
                              data-testid={`button-set-owner-${user.id}`}
                            >
                              <Crown className="h-4 w-4" />
                            </button>
                          )}
                          <button
                            onClick={() => handleDeleteUser(user.id)}
                            className="p-1.5 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="מחיקה"
                            data-testid={`button-delete-user-${user.id}`}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
