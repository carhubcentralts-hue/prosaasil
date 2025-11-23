import React, { useState } from 'react';
import {
  User,
  Mail,
  Shield,
  Building2,
  Eye,
  EyeOff,
  Copy,
  Check,
  Lock,
  LogOut
} from 'lucide-react';
import { Card, Badge } from '../../shared/components/ui/Card';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { useAuth } from '../../features/auth/hooks';
import { useNavigate } from 'react-router-dom';
import http from '../../lib/queryClient';

export function ProfilePage() {
  const { user, tenant, logout } = useAuth();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [copied, setCopied] = useState(false);
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordForm, setPasswordForm] = useState({
    current: '',
    new: '',
    confirm: ''
  });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  if (!user || !tenant) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="text-gray-600 mt-4">טוען פרטים...</p>
        </div>
      </div>
    );
  }

  const handleCopyEmail = () => {
    navigator.clipboard.writeText(user.email || '');
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (passwordForm.new !== passwordForm.confirm) {
      setError('הסיסמאות לא תואמות');
      return;
    }

    if (passwordForm.new.length < 6) {
      setError('סיסמה חייבת להיות לפחות 6 תווים');
      return;
    }

    try {
      await http.put('/api/profile/password', {
        current_password: passwordForm.current,
        new_password: passwordForm.new
      });
      setSuccess('סיסמה שונתה בהצלחה!');
      setPasswordForm({ current: '', new: '', confirm: '' });
      setIsChangingPassword(false);
    } catch (err: any) {
      setError(err.response?.data?.error || 'שגיאה בשינוי סיסמה');
    }
  };

  const handleLogout = async () => {
    try {
      await logout();
      navigate('/login');
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <main className="container mx-auto px-4 py-8 max-w-2xl" dir="rtl">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">פרופיל אישי</h1>
        <p className="text-gray-600 mt-1">ניהול פרטי התחברות וסיסמה</p>
      </div>

      {/* User Information */}
      <Card className="p-6 mb-6 bg-gradient-to-br from-blue-50 to-indigo-50">
        <div className="flex items-center gap-4 mb-6">
          <div className="w-16 h-16 rounded-full bg-blue-600 flex items-center justify-center">
            <User className="w-8 h-8 text-white" />
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{user.name || 'משתמש'}</h2>
            <p className="text-gray-600">{user.email}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Name */}
          <div>
            <label className="text-sm font-medium text-gray-600 block mb-2">שם מלא</label>
            <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-gray-200">
              <User className="w-4 h-4 text-gray-400" />
              <span className="text-gray-900 font-medium">{user.name || 'לא צוין'}</span>
            </div>
          </div>

          {/* Email */}
          <div>
            <label className="text-sm font-medium text-gray-600 block mb-2">דוא"ל</label>
            <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-gray-200">
              <Mail className="w-4 h-4 text-gray-400" />
              <span className="text-gray-900 font-medium flex-1 truncate">{user.email}</span>
              <button
                onClick={handleCopyEmail}
                className="p-1 hover:bg-gray-100 rounded transition"
                title="העתק דוא״ל"
              >
                {copied ? (
                  <Check className="w-4 h-4 text-green-600" />
                ) : (
                  <Copy className="w-4 h-4 text-gray-400" />
                )}
              </button>
            </div>
          </div>

          {/* Role */}
          <div>
            <label className="text-sm font-medium text-gray-600 block mb-2">תפקיד</label>
            <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-gray-200">
              <Shield className="w-4 h-4 text-gray-400" />
              <Badge variant={user.role === 'manager' ? 'success' : 'neutral'}>
                {user.role === 'admin' ? '👨‍💼 מנהל מערכת' : 
                 user.role === 'manager' ? '👔 מנהל עסק' : 
                 '💼 משתמש עסק'}
              </Badge>
            </div>
          </div>

          {/* Business/Tenant */}
          <div>
            <label className="text-sm font-medium text-gray-600 block mb-2">עסק</label>
            <div className="flex items-center gap-2 p-3 bg-white rounded-lg border border-gray-200">
              <Building2 className="w-4 h-4 text-gray-400" />
              <span className="text-gray-900 font-medium">{tenant.name || 'לא צוין'}</span>
            </div>
          </div>
        </div>
      </Card>

      {/* Change Password Section */}
      <Card className="p-6 mb-6">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-bold text-gray-900">שנה סיסמה</h3>
          <Lock className="w-5 h-5 text-gray-400" />
        </div>

        {error && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg mb-4 text-red-600 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg mb-4 text-green-600 text-sm">
            {success}
          </div>
        )}

        {!isChangingPassword ? (
          <Button
            onClick={() => setIsChangingPassword(true)}
            className="bg-blue-600 hover:bg-blue-700 text-white"
            data-testid="button-change-password"
          >
            <Lock className="w-4 h-4 ml-2" />
            שנה סיסמה
          </Button>
        ) : (
          <form onSubmit={handleChangePassword} className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700 block mb-2 text-right">סיסמה נוכחית</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={passwordForm.current}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current: e.target.value })}
                  placeholder="הכנס סיסמה נוכחית"
                  className="w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-right"
                  data-testid="input-current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute left-3 top-1/2 -translate-y-1/2"
                >
                  {showPassword ? (
                    <EyeOff className="w-4 h-4 text-gray-400" />
                  ) : (
                    <Eye className="w-4 h-4 text-gray-400" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-2 text-right">סיסמה חדשה</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={passwordForm.new}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new: e.target.value })}
                  placeholder="לפחות 6 תווים"
                  className="w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-right"
                  data-testid="input-new-password"
                />
              </div>
            </div>

            <div>
              <label className="text-sm font-medium text-gray-700 block mb-2 text-right">אישור סיסמה</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={passwordForm.confirm}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm: e.target.value })}
                  placeholder="חזור על הסיסמה החדשה"
                  className="w-full px-4 py-2 pr-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-right"
                  data-testid="input-confirm-password"
                />
              </div>
            </div>

            <div className="flex gap-3 pt-4">
              <Button
                type="button"
                variant="secondary"
                onClick={() => {
                  setIsChangingPassword(false);
                  setPasswordForm({ current: '', new: '', confirm: '' });
                  setError('');
                }}
                data-testid="button-cancel-password"
              >
                ביטול
              </Button>
              <Button
                type="submit"
                className="flex-1 bg-blue-600 hover:bg-blue-700 text-white"
                data-testid="button-save-password"
              >
                שמור סיסמה חדשה
              </Button>
            </div>
          </form>
        )}
      </Card>

      {/* Logout */}
      <Card className="p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold text-gray-900">התנתק</h3>
            <p className="text-sm text-gray-600 mt-1">התנתק מהחשבון שלך</p>
          </div>
          <Button
            onClick={handleLogout}
            variant="secondary"
            className="border-red-200 text-red-600 hover:bg-red-50"
            data-testid="button-logout"
          >
            <LogOut className="w-4 h-4 ml-2" />
            התנתק
          </Button>
        </div>
      </Card>
    </main>
  );
}
