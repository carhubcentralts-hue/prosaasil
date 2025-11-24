import React, { useState, useEffect } from 'react';
import { 
  Building2, 
  Key, 
  Mail,
  Phone,
  Loader2,
  CheckCircle,
  XCircle
} from 'lucide-react';
import { Card, Badge } from '../../shared/components/ui/Card';
import { Button } from '../../shared/components/ui/Button';
import { Input } from '../../shared/components/ui/Input';
import { apiRequest } from '../../lib/queryClient';

interface Business {
  id: number;
  name: string;
  email: string | null;
  business_type: string;
  phone_number: string | null;
  is_active: boolean;
  created_at: string | null;
}

export function BusinessesManagementPage() {
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [resetPasswordBusiness, setResetPasswordBusiness] = useState<Business | null>(null);
  const [newPassword, setNewPassword] = useState('');
  const [resetting, setResetting] = useState(false);

  useEffect(() => {
    fetchBusinesses();
  }, []);

  const fetchBusinesses = async () => {
    try {
      setLoading(true);
      const response = await apiRequest('/api/admin/businesses');
      setBusinesses(response);
    } catch (error) {
      console.error('Failed to fetch businesses:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetPasswordBusiness || !newPassword) {
      alert('נא להזין סיסמה חדשה');
      return;
    }

    if (newPassword.length < 6) {
      alert('סיסמה חייבת להיות לפחות 6 תווים');
      return;
    }

    try {
      setResetting(true);
      await apiRequest(`/api/admin/businesses/${resetPasswordBusiness.id}/reset-password`, {
        method: 'PUT',
        body: JSON.stringify({ new_password: newPassword }),
        headers: { 'Content-Type': 'application/json' }
      });
      alert(`✅ הסיסמה עודכנה בהצלחה!\n\nעסק: ${resetPasswordBusiness.name}\nמייל: ${resetPasswordBusiness.email}\nסיסמה חדשה: ${newPassword}\n\nשמור את הפרטים במקום בטוח!`);
      setNewPassword('');
      setResetPasswordBusiness(null);
    } catch (error: any) {
      alert(error.message || 'שגיאה באיפוס סיסמה');
    } finally {
      setResetting(false);
    }
  };

  const closeModal = () => {
    setResetPasswordBusiness(null);
    setNewPassword('');
  };

  return (
    <main className="container mx-auto px-4 py-8 max-w-7xl" dir="rtl">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-2">
          <Building2 className="w-8 h-8 text-blue-600" />
          <h1 className="text-3xl font-bold text-gray-900">ניהול עסקים</h1>
        </div>
        <p className="text-gray-600">צפה בכל העסקים במערכת ואפס סיסמאות</p>
      </div>

      {/* Businesses Table */}
      <Card className="overflow-hidden">
        {loading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto mb-4 text-gray-400" />
            <p className="text-gray-600">טוען עסקים...</p>
          </div>
        ) : businesses.length === 0 ? (
          <div className="p-12 text-center">
            <Building2 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <p className="text-gray-600">אין עסקים במערכת</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">ID</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">שם העסק</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">דוא"ל</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">סוג עסק</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">טלפון</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">סטטוס</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">תאריך יצירה</th>
                  <th className="px-6 py-3 text-right text-sm font-medium text-gray-700">פעולות</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {businesses.map((business) => (
                  <tr key={business.id} className="hover:bg-gray-50" data-testid={`row-business-${business.id}`}>
                    <td className="px-6 py-4 text-gray-900 font-mono text-sm">
                      {business.id}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-2">
                        <Building2 className="w-4 h-4 text-gray-400" />
                        <span className="font-medium">{business.name}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {business.email ? (
                        <div className="flex items-center gap-2">
                          <Mail className="w-4 h-4 text-gray-400" />
                          <span className="text-gray-600 font-mono text-sm" dir="ltr">
                            {business.email}
                          </span>
                        </div>
                      ) : (
                        <span className="text-gray-400 text-sm">לא הוגדר</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-gray-600">
                      {business.business_type === 'real_estate' ? 'נדל"ן' : business.business_type}
                    </td>
                    <td className="px-6 py-4">
                      {business.phone_number ? (
                        <div className="flex items-center gap-2">
                          <Phone className="w-4 h-4 text-gray-400" />
                          <span className="text-gray-600 font-mono text-sm" dir="ltr">
                            {business.phone_number}
                          </span>
                        </div>
                      ) : (
                        <span className="text-gray-400 text-sm">לא הוגדר</span>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      {business.is_active ? (
                        <Badge variant="success" className="flex items-center gap-1 w-fit">
                          <CheckCircle className="w-3 h-3" />
                          פעיל
                        </Badge>
                      ) : (
                        <Badge variant="danger" className="flex items-center gap-1 w-fit">
                          <XCircle className="w-3 h-3" />
                          לא פעיל
                        </Badge>
                      )}
                    </td>
                    <td className="px-6 py-4 text-gray-600 text-sm">
                      {business.created_at 
                        ? new Date(business.created_at).toLocaleDateString('he-IL')
                        : 'לא ידוע'}
                    </td>
                    <td className="px-6 py-4">
                      <Button
                        size="sm"
                        onClick={() => setResetPasswordBusiness(business)}
                        className="bg-orange-600 hover:bg-orange-700 text-white"
                        data-testid={`button-reset-password-${business.id}`}
                      >
                        <Key className="w-4 h-4 ml-2" />
                        אפס סיסמא
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Reset Password Modal */}
      {resetPasswordBusiness && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md p-6 bg-white">
            <div className="mb-6">
              <div className="flex items-center gap-3 mb-2">
                <Key className="w-6 h-6 text-orange-600" />
                <h2 className="text-xl font-bold text-right">איפוס סיסמה</h2>
              </div>
              <p className="text-gray-600 text-sm">
                עסק: <span className="font-medium">{resetPasswordBusiness.name}</span>
              </p>
              {resetPasswordBusiness.email && (
                <p className="text-gray-600 text-sm font-mono" dir="ltr">
                  {resetPasswordBusiness.email}
                </p>
              )}
            </div>

            <form onSubmit={handleResetPassword} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2 text-right">
                  סיסמה חדשה
                </label>
                <Input
                  type="text"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="לפחות 6 תווים"
                  className="text-left font-mono"
                  data-testid="input-new-password"
                  autoFocus
                />
                <p className="text-xs text-gray-500 mt-1 text-right">
                  הסיסמה תוצג לאחר האיפוס - שמור אותה במקום בטוח
                </p>
              </div>

              <div className="flex gap-3 pt-4">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeModal}
                  className="flex-1"
                  disabled={resetting}
                  data-testid="button-cancel-reset"
                >
                  ביטול
                </Button>
                <Button
                  type="submit"
                  className="flex-1 bg-orange-600 hover:bg-orange-700 text-white"
                  disabled={resetting}
                  data-testid="button-confirm-reset"
                >
                  {resetting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin ml-2" />
                      מעדכן...
                    </>
                  ) : (
                    <>
                      <Key className="w-4 h-4 ml-2" />
                      אפס סיסמא
                    </>
                  )}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </main>
  );
}
