import type * as React from 'react';
import { useState, useEffect } from 'react';
import { Users, UserPlus, Shield, Settings, Eye, Edit, Trash2, Mail, Phone } from 'lucide-react';
import { http } from '../../services/http';

// Temporary UI components
const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      {...props}
    >
      {children}
    </button>
  );
};

const Badge = ({ children, className = "", variant = "default" }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "admin" | "manager" | "business" | "agent" | "success" | "warning";
}) => {
  const variantClasses = {
    default: "bg-gray-100 text-gray-800",
    admin: "bg-red-100 text-red-800",
    manager: "bg-purple-100 text-purple-800",
    business: "bg-blue-100 text-blue-800",
    agent: "bg-green-100 text-green-800",
    success: "bg-green-100 text-green-800",
    warning: "bg-yellow-100 text-yellow-800"
  };
  return (
    <span className={`px-2 py-1 text-xs rounded-full ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Input = ({ className = "", ...props }: any) => (
  <input className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${className}`} {...props} />
);

// User interface
interface SystemUser {
  id: string;
  email: string;
  name: string;
  role: 'admin' | 'manager' | 'business_owner' | 'business_agent' | 'read_only';
  business_id?: string;
  business_name?: string;
  status: 'active' | 'inactive' | 'pending';
  last_login?: string;
  created_at: string;
  phone?: string;
  permissions: string[];
}

export function UsersPage() {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showUserModal, setShowUserModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<SystemUser | null>(null);
  const [showImpersonateModal, setShowImpersonateModal] = useState(false);
  const [userForm, setUserForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: 'business_agent'
  });

  useEffect(() => {
    loadUsers();
  }, [searchQuery, roleFilter, statusFilter]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      const response = await http.get('/api/admin/users');
      
      if (response && Array.isArray(response)) {
        setUsers(response);
      } else {
        // Fallback to empty array if API is not available
        setUsers([]);
      }
    } catch (error) {
      console.error('Error loading users:', error);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return 'admin';
      case 'manager': return 'manager';
      case 'business_owner': return 'business';
      case 'business_agent': return 'agent';
      case 'read_only': return 'default';
      default: return 'default';
    }
  };

  const getRoleLabel = (role: string) => {
    switch (role) {
      case 'admin': return 'מנהל מערכת';
      case 'manager': return 'מנהל עסק';
      case 'business_owner': return 'בעל עסק';
      case 'business_agent': return 'סוכן';
      case 'read_only': return 'צפייה בלבד';
      default: return role;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'success';
      case 'inactive': return 'default';
      case 'pending': return 'warning';
      default: return 'default';
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case 'active': return 'פעיל';
      case 'inactive': return 'לא פעיל';
      case 'pending': return 'ממתין';
      default: return status;
    }
  };

  const handleImpersonate = (user: SystemUser) => {
    setSelectedUser(user);
    setShowImpersonateModal(true);
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (!userForm.name || !userForm.email || !userForm.role) {
        alert('נא למלא את כל השדות הנדרשים');
        return;
      }

      const response = await http.post('/api/biz/users', userForm) as any;
      
      if (response && response.success !== false) {
        alert('המשתמש נוצר בהצלחה!');
        setShowUserModal(false);
        setUserForm({ name: '', email: '', phone: '', role: 'business_agent' });
        await loadUsers();
      } else {
        alert('שגיאה ביצירת המשתמש: ' + (response?.message || 'שגיאה לא ידועה'));
      }
    } catch (error) {
      console.error('Error creating user:', error);
      alert('שגיאה ביצירת המשתמש');
    }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = searchQuery === '' || 
      user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.business_name?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesRole = roleFilter === 'all' || user.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || user.status === statusFilter;
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  // Stats calculations
  const totalUsers = users.length;
  const activeUsers = users.filter(u => u.status === 'active').length;
  const pendingUsers = users.filter(u => u.status === 'pending').length;
  const adminUsers = users.filter(u => u.role === 'admin').length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto mb-4"></div>
          <p>טוען משתמשים...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Users className="w-6 h-6 text-indigo-600" />
            <h1 className="text-2xl font-bold text-gray-900">ניהול משתמשים</h1>
            <Badge>{totalUsers} משתמשים</Badge>
          </div>
          
          <div className="flex items-center gap-3">
            <Button variant="outline" size="sm">
              <Shield className="w-4 h-4 mr-2" />
              הרשאות
            </Button>
            <Button onClick={() => setShowUserModal(true)}>
              <UserPlus className="w-4 h-4 mr-2" />
              משתמש חדש
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-full">
                <Users className="w-5 h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">סה״כ משתמשים</p>
                <p className="text-lg font-semibold text-gray-900">{totalUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-full">
                <Users className="w-5 h-5 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">פעילים</p>
                <p className="text-lg font-semibold text-gray-900">{activeUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-yellow-100 rounded-full">
                <Users className="w-5 h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">ממתינים</p>
                <p className="text-lg font-semibold text-gray-900">{pendingUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-red-100 rounded-full">
                <Shield className="w-5 h-5 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-gray-600">מנהלים</p>
                <p className="text-lg font-semibold text-gray-900">{adminUsers}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="חיפוש לפי שם, אימייל, עסק..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex gap-3">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">כל התפקידים</option>
              <option value="admin">מנהל מערכת</option>
              <option value="manager">מנהל עסק</option>
              <option value="business_owner">בעל עסק</option>
              <option value="business_agent">סוכן</option>
              <option value="read_only">צפייה בלבד</option>
            </select>
            
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="active">פעיל</option>
              <option value="inactive">לא פעיל</option>
              <option value="pending">ממתין</option>
            </select>
          </div>
        </div>
      </div>

      {/* Users Table - Desktop */}
      <div className="flex-1 overflow-hidden">
        <Card className="h-full m-6">
          {/* Desktop Table View */}
          <div className="hidden lg:block overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    משתמש
                  </th>
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    עסק
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
                  <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                    פעולות
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                            <span className="text-sm font-medium text-gray-700">
                              {user.name.charAt(0)}
                            </span>
                          </div>
                        </div>
                        <div className="mr-4">
                          <div className="text-sm font-medium text-gray-900">{user.name}</div>
                          <div className="text-sm text-gray-500 flex items-center gap-2">
                            <Mail className="w-3 h-3" />
                            {user.email}
                          </div>
                          {user.phone && (
                            <div className="text-sm text-gray-500 flex items-center gap-2" dir="ltr">
                              <Phone className="w-3 h-3" />
                              {user.phone}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.business_name || '-'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={getRoleColor(user.role)}>
                        {getRoleLabel(user.role)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={getStatusColor(user.status)}>
                        {getStatusLabel(user.status)}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {user.last_login 
                        ? new Date(user.last_login).toLocaleString('he-IL')
                        : 'לא התחבר'
                      }
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                      <div className="flex items-center gap-2">
                        <Button 
                          variant="ghost" 
                          size="sm"
                          onClick={() => handleImpersonate(user)}
                          title="התחזות"
                        >
                          <Eye className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" title="עריכה">
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="sm" title="הגדרות">
                          <Settings className="w-4 h-4" />
                        </Button>
                        {user.role !== 'admin' && (
                          <Button variant="ghost" size="sm" title="מחיקה">
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile Cards View */}
          <div className="lg:hidden">
            <div className="space-y-4 p-4">
              {filteredUsers.map((user) => (
                <Card key={user.id} className="p-4 border border-gray-200">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-center">
                      <div className="flex-shrink-0 h-12 w-12">
                        <div className="h-12 w-12 rounded-full bg-gray-300 flex items-center justify-center">
                          <span className="text-lg font-medium text-gray-700">
                            {user.name.charAt(0)}
                          </span>
                        </div>
                      </div>
                      <div className="mr-3">
                        <div className="text-base font-medium text-gray-900">{user.name}</div>
                        <div className="text-sm text-gray-500 flex items-center gap-1">
                          <Mail className="w-3 h-3" />
                          {user.email}
                        </div>
                        {user.phone && (
                          <div className="text-sm text-gray-500 flex items-center gap-1" dir="ltr">
                            <Phone className="w-3 h-3" />
                            {user.phone}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex gap-1">
                      <Badge variant={getRoleColor(user.role)}>
                        {getRoleLabel(user.role)}
                      </Badge>
                      <Badge variant={getStatusColor(user.status)}>
                        {getStatusLabel(user.status)}
                      </Badge>
                    </div>
                  </div>
                  
                  <div className="grid grid-cols-1 gap-2 mb-3">
                    {user.business_name && (
                      <div>
                        <span className="text-xs font-medium text-gray-500">עסק: </span>
                        <span className="text-sm text-gray-900">{user.business_name}</span>
                      </div>
                    )}
                    <div>
                      <span className="text-xs font-medium text-gray-500">כניסה אחרונה: </span>
                      <span className="text-sm text-gray-900">
                        {user.last_login 
                          ? new Date(user.last_login).toLocaleDateString('he-IL')
                          : 'לא התחבר'
                        }
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2 pt-2 border-t border-gray-100">
                    <Button 
                      variant="ghost" 
                      size="sm"
                      onClick={() => handleImpersonate(user)}
                      title="התחזות"
                      className="flex-1"
                    >
                      <Eye className="w-4 h-4 mr-1" />
                      התחזות
                    </Button>
                    <Button variant="ghost" size="sm" title="עריכה" className="flex-1">
                      <Edit className="w-4 h-4 mr-1" />
                      ערוך
                    </Button>
                    <Button variant="ghost" size="sm" title="הגדרות" className="flex-1">
                      <Settings className="w-4 h-4 mr-1" />
                      הגדרות
                    </Button>
                    {user.role !== 'admin' && (
                      <Button variant="ghost" size="sm" title="מחיקה" className="flex-1">
                        <Trash2 className="w-4 h-4 mr-1 text-red-500" />
                        מחק
                      </Button>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          </div>
          
          {filteredUsers.length === 0 && (
            <div className="text-center py-12">
              <Users className="w-16 h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">אין משתמשים</h3>
              <p className="text-gray-500">אין משתמשים שמתאימים לחיפוש</p>
            </div>
          )}
        </Card>
      </div>

      {/* Add User Modal */}
      {showUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="p-6 max-w-2xl w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              משתמש חדש
            </h3>
            <form className="space-y-4" onSubmit={handleCreateUser}>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא</label>
                  <Input 
                    type="text" 
                    placeholder="הזן שם מלא"
                    value={userForm.name}
                    onChange={(e: any) => setUserForm({...userForm, name: e.target.value})}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">דוא"ל</label>
                  <Input 
                    type="email" 
                    placeholder="הזן דוא״ל"
                    value={userForm.email}
                    onChange={(e: any) => setUserForm({...userForm, email: e.target.value})}
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
                  <Input 
                    type="tel" 
                    placeholder="הזן מספר טלפון"
                    value={userForm.phone}
                    onChange={(e: any) => setUserForm({...userForm, phone: e.target.value})}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">תפקיד</label>
                  <select 
                    className="w-full px-3 py-2 border border-gray-300 rounded-md"
                    value={userForm.role}
                    onChange={(e) => setUserForm({...userForm, role: e.target.value})}
                  >
                    <option value="business_agent">סוכן</option>
                    <option value="business_owner">בעל עסק</option>
                    <option value="manager">מנהל עסק</option>
                    <option value="read_only">צפייה בלבד</option>
                  </select>
                </div>
              </div>
              <div className="flex gap-3 mt-6">
                <Button type="submit">
                  צור משתמש
                </Button>
                <Button 
                  type="button"
                  variant="outline"
                  onClick={() => setShowUserModal(false)}
                >
                  ביטול
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {/* Impersonation Modal */}
      {showImpersonateModal && selectedUser && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">
              התחזות למשתמש
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              האם אתה בטוח שברצונך להתחזות למשתמש <strong>{selectedUser.name}</strong>?
              פעולה זו תעביר אותך לממשק שלו.
            </p>
            <div className="flex gap-3">
              <Button 
                onClick={() => {
                  // TODO: Implement impersonation logic
                  alert(`התחזות ל-${selectedUser.name}`);
                  setShowImpersonateModal(false);
                }}
              >
                אישור
              </Button>
              <Button 
                variant="outline"
                onClick={() => setShowImpersonateModal(false)}
              >
                ביטול
              </Button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}