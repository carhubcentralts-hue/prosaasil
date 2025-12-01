import React, { useState, useEffect } from 'react';
import { Users, UserPlus, Shield, Edit, Trash2, Mail, Phone, CheckSquare, Square, X } from 'lucide-react';
import { http } from '../../services/http';

const Card = ({ children, className = "" }: any) => (
  <div className={`border border-gray-200 rounded-lg bg-white ${className}`}>{children}</div>
);

const Button = ({ children, className = "", variant = "default", size = "default", disabled = false, ...props }: {
  children: React.ReactNode;
  className?: string;
  variant?: "default" | "outline" | "ghost" | "destructive";
  size?: "default" | "sm";
  disabled?: boolean;
  [key: string]: any;
}) => {
  const baseClasses = "px-4 py-2 rounded-md font-medium transition-colors inline-flex items-center justify-center disabled:opacity-50 disabled:cursor-not-allowed";
  const variantClasses = {
    default: "bg-blue-600 text-white hover:bg-blue-700",
    outline: "border border-gray-300 bg-white text-gray-700 hover:bg-gray-50",
    ghost: "text-gray-700 hover:bg-gray-100",
    destructive: "bg-red-600 text-white hover:bg-red-700"
  };
  const sizeClasses = {
    default: "px-4 py-2",
    sm: "px-3 py-1.5 text-sm"
  };
  return (
    <button 
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`} 
      disabled={disabled}
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
    <span className={`px-2 py-1 text-xs rounded-full whitespace-nowrap ${variantClasses[variant]} ${className}`}>
      {children}
    </span>
  );
};

const Input = ({ className = "", ...props }: any) => (
  <input className={`w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 ${className}`} {...props} />
);

interface SystemUser {
  id: string;
  email: string;
  name: string;
  role: 'system_admin' | 'owner' | 'admin' | 'agent' | 'read_only';
  business_id?: number;
  business_name?: string;
  status: 'active' | 'inactive' | 'pending';
  is_active?: boolean;
  last_login?: string;
  created_at: string;
  phone?: string;
}

interface Business {
  id: number;
  name: string;
}

export function UsersPage() {
  const [users, setUsers] = useState<SystemUser[]>([]);
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [showUserModal, setShowUserModal] = useState(false);
  const [selectedUsers, setSelectedUsers] = useState<Set<string>>(new Set());
  const [bulkDeleteLoading, setBulkDeleteLoading] = useState(false);
  const [userForm, setUserForm] = useState({
    name: '',
    email: '',
    phone: '',
    password: '',
    role: 'agent',
    business_id: 0
  });
  const [createLoading, setCreateLoading] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      
      // Load user info and users list in parallel for faster page load
      const [meRes, usersRes] = await Promise.all([
        http.get('/api/auth/me').catch(() => null) as Promise<any>,
        http.get('/api/admin/users').catch(() => []) as Promise<any>
      ]);
      
      const currentRole = meRes?.user?.role || meRes?.role;
      const currentBusinessId = meRes?.user?.business_id || meRes?.business_id;
      const currentBusinessName = meRes?.user?.business_name || meRes?.business_name;
      
      if (Array.isArray(usersRes)) {
        const mappedUsers = usersRes.map((u: any) => ({
          ...u,
          status: u.is_active ? 'active' : 'inactive'
        }));
        setUsers(mappedUsers);
      }
      
      // For system_admin, load all businesses
      // For owner/admin, use their own business
      if (currentRole === 'system_admin') {
        const businessesRes = await http.get('/api/admin/businesses').catch(() => ({ items: [] })) as any;
        const items = businessesRes?.items || businessesRes?.businesses || [];
        if (Array.isArray(items)) {
          setBusinesses(items);
          if (items.length > 0 && userForm.business_id === 0) {
            setUserForm(prev => ({ ...prev, business_id: items[0].id }));
          }
        }
      } else if (currentBusinessId) {
        // Non-system-admin: use their own business
        setBusinesses([{ id: currentBusinessId, name: currentBusinessName || 'העסק שלי' }]);
        if (userForm.business_id === 0) {
          setUserForm(prev => ({ ...prev, business_id: currentBusinessId }));
        }
      }
    } catch (error) {
      console.error('Error loading data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'system_admin': return 'admin';
      case 'owner': return 'business';
      case 'admin': return 'manager';
      case 'agent': return 'agent';
      case 'read_only': return 'default';
      default: return 'default';
    }
  };

  const getRoleLabel = (role: string) => {
    switch (role) {
      case 'system_admin': return 'מנהל מערכת';
      case 'owner': return 'בעלים';
      case 'admin': return 'מנהל';
      case 'agent': return 'סוכן';
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

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!userForm.name || !userForm.email || !userForm.password || !userForm.business_id) {
      alert('נא למלא את כל השדות הנדרשים (שם, אימייל, סיסמה ועסק)');
      return;
    }

    setCreateLoading(true);
    try {
      const nameParts = userForm.name.split(' ');
      const firstName = nameParts[0] || '';
      const lastName = nameParts.slice(1).join(' ') || '';
      
      const response = await http.post(`/api/admin/businesses/${userForm.business_id}/users`, {
        email: userForm.email,
        password: userForm.password,
        first_name: firstName,
        last_name: lastName,
        role: userForm.role
      }) as any;
      
      if (response && response.success) {
        alert('המשתמש נוצר בהצלחה!');
        setShowUserModal(false);
        setUserForm({ name: '', email: '', phone: '', password: '', role: 'agent', business_id: businesses[0]?.id || 0 });
        await loadData();
      } else {
        alert('שגיאה ביצירת המשתמש: ' + (response?.error || response?.message || 'שגיאה לא ידועה'));
      }
    } catch (error: any) {
      console.error('Error creating user:', error);
      alert('שגיאה ביצירת המשתמש: ' + (error?.message || 'שגיאה לא ידועה'));
    } finally {
      setCreateLoading(false);
    }
  };

  const handleDeleteUser = async (user: SystemUser) => {
    if (!window.confirm(`האם אתה בטוח שברצונך למחוק את המשתמש ${user.name}?`)) {
      return;
    }
    
    try {
      const businessId = user.business_id || 0;
      if (!businessId) {
        alert('לא ניתן למחוק משתמש ללא עסק משויך');
        return;
      }
      
      const response = await http.delete(`/api/admin/businesses/${businessId}/users/${user.id}`) as any;
      
      if (response && response.success) {
        alert('המשתמש נמחק בהצלחה');
        await loadData();
      } else {
        alert('שגיאה במחיקת המשתמש: ' + (response?.error || response?.message || 'שגיאה לא ידועה'));
      }
    } catch (error: any) {
      console.error('Error deleting user:', error);
      alert('שגיאה במחיקת המשתמש: ' + (error?.message || 'שגיאה לא ידועה'));
    }
  };

  const toggleUserSelection = (userId: string) => {
    setSelectedUsers(prev => {
      const newSet = new Set(prev);
      if (newSet.has(userId)) {
        newSet.delete(userId);
      } else {
        newSet.add(userId);
      }
      return newSet;
    });
  };

  const toggleSelectAll = () => {
    if (selectedUsers.size === filteredUsers.length) {
      setSelectedUsers(new Set());
    } else {
      setSelectedUsers(new Set(filteredUsers.map(u => u.id)));
    }
  };

  const handleBulkDelete = async () => {
    if (selectedUsers.size === 0) return;
    
    const usersToDelete = filteredUsers.filter(u => selectedUsers.has(u.id) && u.role !== 'system_admin');
    
    if (usersToDelete.length === 0) {
      alert('לא ניתן למחוק מנהלי מערכת');
      return;
    }
    
    if (!window.confirm(`האם אתה בטוח שברצונך למחוק ${usersToDelete.length} משתמשים?`)) {
      return;
    }
    
    setBulkDeleteLoading(true);
    let successCount = 0;
    let errorCount = 0;
    
    for (const user of usersToDelete) {
      try {
        const businessId = user.business_id || 0;
        if (!businessId) {
          errorCount++;
          continue;
        }
        
        const response = await http.delete(`/api/admin/businesses/${businessId}/users/${user.id}`) as any;
        if (response?.success) {
          successCount++;
        } else {
          errorCount++;
        }
      } catch {
        errorCount++;
      }
    }
    
    setBulkDeleteLoading(false);
    setSelectedUsers(new Set());
    
    if (errorCount === 0) {
      alert(`נמחקו ${successCount} משתמשים בהצלחה`);
    } else {
      alert(`נמחקו ${successCount} משתמשים, ${errorCount} נכשלו`);
    }
    
    await loadData();
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = searchQuery === '' || 
      user.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.email?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      user.business_name?.toLowerCase().includes(searchQuery.toLowerCase());
    
    const matchesRole = roleFilter === 'all' || user.role === roleFilter;
    const matchesStatus = statusFilter === 'all' || user.status === statusFilter;
    
    return matchesSearch && matchesRole && matchesStatus;
  });

  const totalUsers = users.length;
  const activeUsers = users.filter(u => u.status === 'active').length;
  const pendingUsers = users.filter(u => u.status === 'pending').length;
  const adminUsers = users.filter(u => u.role === 'system_admin' || u.role === 'admin').length;

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
    <div className="flex flex-col min-h-[calc(100vh-4rem)] bg-gray-50">
      {/* Header - Responsive */}
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 sm:w-6 sm:h-6 text-indigo-600" />
            <h1 className="text-xl sm:text-2xl font-bold text-gray-900">ניהול משתמשים</h1>
            <Badge>{totalUsers}</Badge>
          </div>
          
          <div className="flex items-center gap-2 sm:gap-3">
            {selectedUsers.size > 0 && (
              <Button 
                variant="destructive" 
                size="sm"
                onClick={handleBulkDelete}
                disabled={bulkDeleteLoading}
                data-testid="button-bulk-delete"
              >
                <Trash2 className="w-4 h-4 ml-1" />
                מחק ({selectedUsers.size})
              </Button>
            )}
            <Button variant="outline" size="sm" className="hidden sm:inline-flex">
              <Shield className="w-4 h-4 ml-1" />
              הרשאות
            </Button>
            <Button onClick={() => setShowUserModal(true)} size="sm" data-testid="button-add-user">
              <UserPlus className="w-4 h-4 ml-1" />
              <span className="hidden sm:inline">משתמש חדש</span>
              <span className="sm:hidden">הוסף</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Summary Cards - Responsive Grid */}
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
          <Card className="p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="p-1.5 sm:p-2 bg-blue-100 rounded-full">
                <Users className="w-4 h-4 sm:w-5 sm:h-5 text-blue-600" />
              </div>
              <div>
                <p className="text-xs sm:text-sm text-gray-600">סה״כ</p>
                <p className="text-base sm:text-lg font-semibold text-gray-900">{totalUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="p-1.5 sm:p-2 bg-green-100 rounded-full">
                <Users className="w-4 h-4 sm:w-5 sm:h-5 text-green-600" />
              </div>
              <div>
                <p className="text-xs sm:text-sm text-gray-600">פעילים</p>
                <p className="text-base sm:text-lg font-semibold text-gray-900">{activeUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="p-1.5 sm:p-2 bg-yellow-100 rounded-full">
                <Users className="w-4 h-4 sm:w-5 sm:h-5 text-yellow-600" />
              </div>
              <div>
                <p className="text-xs sm:text-sm text-gray-600">ממתינים</p>
                <p className="text-base sm:text-lg font-semibold text-gray-900">{pendingUsers}</p>
              </div>
            </div>
          </Card>
          
          <Card className="p-3 sm:p-4">
            <div className="flex items-center gap-2 sm:gap-3">
              <div className="p-1.5 sm:p-2 bg-red-100 rounded-full">
                <Shield className="w-4 h-4 sm:w-5 sm:h-5 text-red-600" />
              </div>
              <div>
                <p className="text-xs sm:text-sm text-gray-600">מנהלים</p>
                <p className="text-base sm:text-lg font-semibold text-gray-900">{adminUsers}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>

      {/* Filters - Responsive */}
      <div className="bg-white border-b border-gray-200 px-4 sm:px-6 py-4">
        <div className="flex flex-col gap-3">
          <input
            type="text"
            placeholder="חיפוש לפי שם, אימייל, עסק..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
            data-testid="input-search-users"
          />
          
          <div className="flex gap-2 overflow-x-auto pb-1">
            <select
              value={roleFilter}
              onChange={(e) => setRoleFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm min-w-[120px]"
              data-testid="select-role-filter"
            >
              <option value="all">כל התפקידים</option>
              <option value="system_admin">מנהל מערכת</option>
              <option value="owner">בעלים</option>
              <option value="admin">מנהל</option>
              <option value="agent">סוכן</option>
              <option value="read_only">צפייה בלבד</option>
            </select>
            
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm min-w-[120px]"
              data-testid="select-status-filter"
            >
              <option value="all">כל הסטטוסים</option>
              <option value="active">פעיל</option>
              <option value="inactive">לא פעיל</option>
              <option value="pending">ממתין</option>
            </select>
          </div>
        </div>
      </div>

      {/* Users List - Responsive */}
      <div className="flex-1 overflow-auto p-4 sm:p-6">
        <Card className="overflow-hidden">
          {/* Select All Header */}
          {filteredUsers.length > 0 && (
            <div className="bg-gray-50 border-b border-gray-200 px-4 py-2 flex items-center gap-3">
              <button
                onClick={toggleSelectAll}
                className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900"
                data-testid="button-select-all"
              >
                {selectedUsers.size === filteredUsers.length ? (
                  <CheckSquare className="w-4 h-4 text-blue-600" />
                ) : (
                  <Square className="w-4 h-4" />
                )}
                {selectedUsers.size === filteredUsers.length ? 'בטל בחירה' : 'בחר הכל'}
              </button>
              {selectedUsers.size > 0 && (
                <span className="text-sm text-gray-500">({selectedUsers.size} נבחרו)</span>
              )}
            </div>
          )}
          
          {/* Desktop Table View */}
          <div className="hidden lg:block overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase w-10"></th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">משתמש</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">עסק</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">תפקיד</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">סטטוס</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">כניסה אחרונה</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">פעולות</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredUsers.map((user) => (
                  <tr key={user.id} className={`hover:bg-gray-50 ${selectedUsers.has(user.id) ? 'bg-blue-50' : ''}`}>
                    <td className="px-4 py-4">
                      <button
                        onClick={() => toggleUserSelection(user.id)}
                        className="text-gray-400 hover:text-gray-600"
                        data-testid={`checkbox-user-${user.id}`}
                      >
                        {selectedUsers.has(user.id) ? (
                          <CheckSquare className="w-5 h-5 text-blue-600" />
                        ) : (
                          <Square className="w-5 h-5" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center">
                        <div className="flex-shrink-0 h-10 w-10">
                          <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                            <span className="text-sm font-medium text-gray-700">
                              {(user.name || user.email || '?').charAt(0).toUpperCase()}
                            </span>
                          </div>
                        </div>
                        <div className="mr-4">
                          <div className="text-sm font-medium text-gray-900">{user.name || user.email}</div>
                          <div className="text-sm text-gray-500 flex items-center gap-2">
                            <Mail className="w-3 h-3" />
                            {user.email}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-900">
                      {user.business_name || '-'}
                    </td>
                    <td className="px-4 py-4">
                      <Badge variant={getRoleColor(user.role)}>
                        {getRoleLabel(user.role)}
                      </Badge>
                    </td>
                    <td className="px-4 py-4">
                      <Badge variant={getStatusColor(user.status)}>
                        {getStatusLabel(user.status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-4 text-sm text-gray-900">
                      {user.last_login 
                        ? new Date(user.last_login).toLocaleString('he-IL')
                        : 'לא התחבר'
                      }
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" title="עריכה" data-testid={`button-edit-user-${user.id}`}>
                          <Edit className="w-4 h-4" />
                        </Button>
                        {user.role !== 'system_admin' && (
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            title="מחיקה"
                            onClick={() => handleDeleteUser(user)}
                            data-testid={`button-delete-user-${user.id}`}
                          >
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

          {/* Mobile Cards View - Improved */}
          <div className="lg:hidden divide-y divide-gray-200">
            {filteredUsers.map((user) => (
              <div 
                key={user.id} 
                className={`p-4 ${selectedUsers.has(user.id) ? 'bg-blue-50' : ''}`}
                data-testid={`user-card-${user.id}`}
              >
                <div className="flex items-start gap-3">
                  {/* Checkbox */}
                  <button
                    onClick={() => toggleUserSelection(user.id)}
                    className="mt-1 text-gray-400 hover:text-gray-600 flex-shrink-0"
                  >
                    {selectedUsers.has(user.id) ? (
                      <CheckSquare className="w-5 h-5 text-blue-600" />
                    ) : (
                      <Square className="w-5 h-5" />
                    )}
                  </button>
                  
                  {/* Avatar */}
                  <div className="flex-shrink-0 h-10 w-10">
                    <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                      <span className="text-sm font-medium text-gray-700">
                        {(user.name || user.email || '?').charAt(0).toUpperCase()}
                      </span>
                    </div>
                  </div>
                  
                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <h3 className="text-sm font-medium text-gray-900 truncate">
                        {user.name || user.email}
                      </h3>
                      <div className="flex gap-1 flex-shrink-0">
                        <Badge variant={getRoleColor(user.role)}>
                          {getRoleLabel(user.role)}
                        </Badge>
                      </div>
                    </div>
                    
                    <div className="text-xs text-gray-500 truncate mb-1">
                      <Mail className="w-3 h-3 inline ml-1" />
                      {user.email}
                    </div>
                    
                    {user.business_name && (
                      <div className="text-xs text-gray-500 mb-1">
                        עסק: {user.business_name}
                      </div>
                    )}
                    
                    <div className="flex items-center justify-between mt-2">
                      <div className="flex items-center gap-2">
                        <Badge variant={getStatusColor(user.status)}>
                          {getStatusLabel(user.status)}
                        </Badge>
                        <span className="text-xs text-gray-400">
                          {user.last_login 
                            ? new Date(user.last_login).toLocaleDateString('he-IL')
                            : 'לא התחבר'
                          }
                        </span>
                      </div>
                      
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" title="עריכה">
                          <Edit className="w-4 h-4" />
                        </Button>
                        {user.role !== 'system_admin' && (
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            title="מחיקה"
                            onClick={() => handleDeleteUser(user)}
                          >
                            <Trash2 className="w-4 h-4 text-red-500" />
                          </Button>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          
          {filteredUsers.length === 0 && (
            <div className="text-center py-12 px-4">
              <Users className="w-12 h-12 sm:w-16 sm:h-16 text-gray-400 mx-auto mb-4" />
              <h3 className="text-base sm:text-lg font-medium text-gray-900 mb-2">אין משתמשים</h3>
              <p className="text-sm text-gray-500">אין משתמשים שמתאימים לחיפוש</p>
            </div>
          )}
        </Card>
      </div>

      {/* Add User Modal - Responsive */}
      {showUserModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <Card className="p-4 sm:p-6 w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                משתמש חדש
              </h3>
              <button 
                onClick={() => setShowUserModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <form className="space-y-4" onSubmit={handleCreateUser}>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">שם מלא *</label>
                  <Input 
                    type="text" 
                    placeholder="הזן שם מלא"
                    value={userForm.name}
                    onChange={(e: any) => setUserForm({...userForm, name: e.target.value})}
                    required
                    data-testid="input-user-name"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">דוא"ל *</label>
                  <Input 
                    type="email" 
                    placeholder="הזן דוא״ל"
                    value={userForm.email}
                    onChange={(e: any) => setUserForm({...userForm, email: e.target.value})}
                    required
                    data-testid="input-user-email"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">סיסמה *</label>
                  <Input 
                    type="password" 
                    placeholder="הזן סיסמה"
                    value={userForm.password}
                    onChange={(e: any) => setUserForm({...userForm, password: e.target.value})}
                    required
                    data-testid="input-user-password"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">טלפון</label>
                  <Input 
                    type="tel" 
                    placeholder="מספר טלפון"
                    value={userForm.phone}
                    onChange={(e: any) => setUserForm({...userForm, phone: e.target.value})}
                    data-testid="input-user-phone"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">תפקיד *</label>
                  <select 
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    value={userForm.role}
                    onChange={(e) => setUserForm({...userForm, role: e.target.value})}
                    data-testid="select-user-role"
                  >
                    <option value="agent">סוכן</option>
                    <option value="admin">מנהל</option>
                    <option value="owner">בעלים</option>
                  </select>
                </div>
                <div className="sm:col-span-2">
                  <label className="block text-sm font-medium text-gray-700 mb-1">עסק *</label>
                  <select 
                    className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
                    value={userForm.business_id}
                    onChange={(e) => setUserForm({...userForm, business_id: parseInt(e.target.value)})}
                    required
                    data-testid="select-user-business"
                  >
                    <option value={0}>בחר עסק...</option>
                    {businesses.map(biz => (
                      <option key={biz.id} value={biz.id}>{biz.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div className="flex flex-col-reverse sm:flex-row gap-3 mt-6 pt-4 border-t">
                <Button 
                  type="button"
                  variant="outline"
                  onClick={() => setShowUserModal(false)}
                  className="w-full sm:w-auto"
                >
                  ביטול
                </Button>
                <Button 
                  type="submit" 
                  disabled={createLoading}
                  className="w-full sm:w-auto"
                  data-testid="button-submit-user"
                >
                  {createLoading ? 'יוצר...' : 'צור משתמש'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
}
