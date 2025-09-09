import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Building2, 
  Search, 
  Filter, 
  Plus, 
  MoreVertical,
  Users,
  Globe,
  Phone,
  Calendar,
  Eye,
  Edit,
  Key,
  Pause,
  Play,
  Trash2,
  CheckCircle,
  XCircle,
  Clock,
  UserX,
  Bot
} from 'lucide-react';
import { BusinessEditModal } from '../../features/businesses/components/BusinessEditModal';
import { useBusinessActions } from '../../features/businesses/useBusinessActions';
import { Business } from '../../features/businesses/types';
import { businessAPI } from '../../features/businesses/api';
import { cn } from '../../shared/utils/cn';
import { useAuth } from '../../features/auth/hooks';

// Business interface is imported from the centralized types

// Real data fetching - replaced mock data

interface BusinessTableProps {
  businesses: Business[];
  onBusinessClick: (business: Business) => void;
  onActionClick: (action: string, business: Business) => void;
}

function BusinessTable({ businesses, onBusinessClick, onActionClick }: BusinessTableProps) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="hidden md:block bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-slate-50 border-b border-slate-200">
            <tr>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">שם העסק</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">תחום עסקי</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">טלפון/WhatsApp</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">משתמשים</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">סטטוס</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">נוצר</th>
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">פעולות</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {businesses.map((business) => (
              <tr 
                key={business.id} 
                className="hover:bg-slate-50 transition-colors cursor-pointer"
                onClick={() => onBusinessClick(business)}
              >
                <td className="py-4 px-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                      <Building2 className="h-5 w-5 text-white" />
                    </div>
                    <div>
                      <p className="font-medium text-slate-900">{business.name}</p>
                      <p className="text-sm text-slate-500">ID: {business.id}</p>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <span className="inline-flex items-center px-2 py-1 text-xs font-medium bg-blue-100 text-blue-800 rounded-full">
                      {business.business_type}
                    </span>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Phone className="h-3 w-3 text-slate-400" />
                      <span className="text-xs text-slate-600 direction-ltr">{business.phone || 'לא הוגדר'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-green-600">WA</span>
                      <span className="text-xs text-slate-500 direction-ltr truncate max-w-[120px]">
                        {business.whatsapp || 'לא הוגדר'}
                      </span>
                    </div>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-slate-400" />
                    <span className="text-sm font-medium text-slate-700">{business.users}</span>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <span className={cn(
                    'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                    business.status === 'active' 
                      ? 'bg-green-100 text-green-800' 
                      : 'bg-red-100 text-red-800'
                  )}>
                    {business.status === 'active' ? (
                      <>
                        <CheckCircle className="h-3 w-3 ml-1" />
                        פעיל
                      </>
                    ) : (
                      <>
                        <XCircle className="h-3 w-3 ml-1" />
                        מושעה
                      </>
                    )}
                  </span>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-4 w-4 text-slate-400" />
                    <span className="text-sm text-slate-600">{formatDate(business.created_at)}</span>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="flex items-center gap-1">
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('view', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                      title="צפייה"
                      data-testid={`button-view-${business.id}`}
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('agent', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      title="AI Agent"
                      data-testid={`button-agent-${business.id}`}
                    >
                      <Bot className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('edit', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                      title="עריכה"
                      data-testid={`button-edit-${business.id}`}
                    >
                      <Edit className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('impersonate', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-purple-600 hover:bg-purple-50 rounded-lg transition-colors"
                      title="התחזות"
                      data-testid={`button-impersonate-${business.id}`}
                    >
                      <UserX className="h-4 w-4" />
                    </button>
                    {business.status === 'active' ? (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onActionClick('suspend', business);
                        }}
                        className="p-1.5 text-slate-500 hover:text-orange-600 hover:bg-orange-50 rounded-lg transition-colors"
                        title="השעה"
                        data-testid={`button-suspend-${business.id}`}
                      >
                        <Pause className="h-4 w-4" />
                      </button>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onActionClick('resume', business);
                        }}
                        className="p-1.5 text-slate-500 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                        title="הפעל"
                        data-testid={`button-resume-${business.id}`}
                      >
                        <Play className="h-4 w-4" />
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('more', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                      title="עוד פעולות"
                      data-testid={`button-more-${business.id}`}
                    >
                      <MoreVertical className="h-4 w-4" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface BusinessCardListProps {
  businesses: Business[];
  onBusinessClick: (business: Business) => void;
  onActionClick: (action: string, business: Business) => void;
}

function BusinessCardList({ businesses, onBusinessClick, onActionClick }: BusinessCardListProps) {
  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <div className="md:hidden space-y-4">
      {businesses.map((business) => (
        <div 
          key={business.id}
          className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 cursor-pointer hover:shadow-md transition-shadow"
          onClick={() => onBusinessClick(business)}
        >
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center">
                <Building2 className="h-6 w-6 text-white" />
              </div>
              <div>
                <h3 className="font-medium text-slate-900 leading-tight">{business.name}</h3>
                <p className="text-sm text-slate-500">ID: {business.id}</p>
              </div>
            </div>
            <span className={cn(
              'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
              business.status === 'active' 
                ? 'bg-green-100 text-green-800' 
                : 'bg-red-100 text-red-800'
            )}>
              {business.status === 'active' ? (
                <>
                  <CheckCircle className="h-3 w-3 ml-1" />
                  פעיל
                </>
              ) : (
                <>
                  <XCircle className="h-3 w-3 ml-1" />
                  מושעה
                </>
              )}
            </span>
          </div>
          
          <div className="space-y-2 mb-4">
            <div className="flex items-center gap-2">
              <Globe className="h-4 w-4 text-slate-400" />
              <span className="text-sm text-slate-600">{business.business_type}</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-slate-400" />
              <span className="text-sm text-slate-600 direction-ltr">{business.phone || 'לא הוגדר'}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-slate-400" />
                <span className="text-sm text-slate-600">{business.users} משתמשים</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-slate-400" />
                <span className="text-sm text-slate-600">{formatDate(business.created_at)}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center justify-between pt-3 border-t border-slate-100">
            <div className="flex items-center gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onActionClick('view', business);
                }}
                className="flex items-center gap-2 px-3 py-1.5 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors text-sm"
                data-testid={`card-view-${business.id}`}
              >
                <Eye className="h-4 w-4" />
                צפייה
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onActionClick('edit', business);
                }}
                className="flex items-center gap-2 px-3 py-1.5 text-green-600 hover:bg-green-50 rounded-lg transition-colors text-sm"
                data-testid={`card-edit-${business.id}`}
              >
                <Edit className="h-4 w-4" />
                עריכה
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onActionClick('impersonate', business);
                }}
                className="flex items-center gap-2 px-3 py-1.5 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors text-sm"
                data-testid={`card-impersonate-${business.id}`}
              >
                <UserX className="h-4 w-4" />
                התחזות
              </button>
            </div>
            <button
              onClick={(e) => {
                e.stopPropagation();
                onActionClick('more', business);
              }}
              className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
              title="עוד פעולות"
            >
              <MoreVertical className="h-4 w-4" />
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}

export function BusinessManagerPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'suspended'>('all');
  const [allBusinesses, setAllBusinesses] = useState<Business[]>([]);
  const [filteredBusinesses, setFilteredBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();
  
  // Use centralized business actions
  const businessActions = useBusinessActions();

  // Fetch businesses from API using the proper business API
  const fetchBusinesses = async () => {
    try {
      setLoading(true);
      setError(null);
      
      console.log('🔄 DEBUG: מתחיל טעינת עסקים...');
      
      // ✅ משתמש בBusinessAPI שמכיל את כל ההגדרות הנכונות
      const data = await businessAPI.getBusinesses();
      
      console.log('📊 תגובת API:', data);
      
      // Convert API response to Business format - תיקון חובה למיפוי שדות
      const businesses = data.items?.map((item: any) => ({
        id: item.id,
        name: item.name,
        business_type: item.business_type || 'real_estate',
        phone: item.phone_e164 || '',  // ✅ CRITICAL: השרת שולח phone_e164
        whatsapp: item.whatsapp_number || item.phone_e164 || '', // fallback לטלפון אם אין WhatsApp נפרד
        users: 0, // TODO: עדיין לא מחושב בשרת
        status: item.status as 'active' | 'inactive' | 'suspended',
        created_at: item.created_at,
        
        // שדות נוספים שנדרשים לעריכה
        phone_number: item.phone_e164 || '',
        whatsapp_number: item.whatsapp_number || '',
        phone_e164: item.phone_e164 || '',
        
        // נתונים נוספים לצורך debug
        call_status: item.call_status,
        whatsapp_status: item.whatsapp_status
      })) || [];
      
      console.log('🔍 DEBUG MAPPING - Input from server:', data.items?.[0]);
      console.log('🔍 DEBUG MAPPING - Output after mapping:', businesses?.[0]);
      
      console.log('🏢 עסקים אחרי עיבוד:', businesses);
      
      setAllBusinesses(businesses);
      setFilteredBusinesses(businesses); // ✅ חובה: עדכון המסננים!
    } catch (err) {
      console.error('❌ שגיאה בטעינת עסקים:', err);
      setError(err instanceof Error ? err.message : 'שגיאה לא ידועה');
    } finally {
      setLoading(false);
    }
  };

  // Load businesses on component mount - with small delay to ensure session is ready
  useEffect(() => {
    const loadBusinesses = async () => {
      // Small delay to ensure session is fully established
      await new Promise(resolve => setTimeout(resolve, 100));
      fetchBusinesses();
    };
    loadBusinesses();
  }, []);


  // Filter businesses based on search and status
  useEffect(() => {
    let filtered = allBusinesses;

    // Apply search filter
    if (searchQuery.trim()) {
      filtered = filtered.filter(business => 
        business.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        business.business_type.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Apply status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(business => business.status === statusFilter);
    }

    setFilteredBusinesses(filtered);
  }, [allBusinesses, searchQuery, statusFilter]);

  const handleBusinessClick = (business: Business) => {
    businessActions.viewBusiness(business);
  };

  const handleActionClick = (action: string, business: Business) => {
    switch (action) {
      case 'view':
        businessActions.viewBusiness(business);
        break;
      case 'agent':
        navigate(`/app/admin/businesses/${business.id}/agent`);
        break;
      case 'edit':
        setSelectedBusiness(business);
        setEditModalOpen(true);
        break;
      case 'impersonate':
        businessActions.impersonate(business);
        break;
      case 'suspend':
        businessActions.suspend(business);
        break;
      case 'resume':
        businessActions.resume(business);
        break;
      case 'delete':
        businessActions.softDelete(business);
        break;
      case 'reset':
        businessActions.resetPassword(business);
        break;
      case 'more':
        // Show action menu for mobile
        const actionChoice = prompt(`בחר פעולה עבור "${business.name}":\n\n1. התחזות לעסק\n2. ${business.status === 'active' ? 'השעה' : 'הפעל'} עסק\n3. מחק עסק\n4. איפוס סיסמאות משתמשים\n\nהכנס מספר (1-4):`);
        
        switch (actionChoice) {
          case '1':
            businessActions.impersonate(business);
            break;
          case '2':
            business.status === 'active' ? businessActions.suspend(business) : businessActions.resume(business);
            break;
          case '3':
            businessActions.softDelete(business);
            break;
          case '4':
            businessActions.resetPassword(business);
            break;
          default:
            // User canceled or entered invalid choice
            break;
        }
        break;
      default:
        break;
    }
  };

  const handleNewBusiness = () => {
    // פותח מודל עריכה עם עסק חדש (null = יצירת עסק חדש)
    setSelectedBusiness(null);
    setEditModalOpen(true);
  };

  const handleCreateBusiness = async (data: any) => {
    try {
      // ✅ יוצר עסק חדש בשרת
      await businessActions.createBusiness(data);
      setEditModalOpen(false);
      setSelectedBusiness(null);
      
      // ✅ מרענן את הרשימה מהשרת אחרי יצירה
      await fetchBusinesses();
    } catch (error) {
      console.error('שגיאה ביצירת עסק:', error);
      // אם יש שגיאה, לא סוגרים את המודל כדי שהמשתמש יכול לנסות שוב
    }
  };

  const handleSaveBusiness = async (data: any) => {
    if (!selectedBusiness) return;
    
    try {
      await businessActions.editBusiness(selectedBusiness, data);
      setEditModalOpen(false);
      setSelectedBusiness(null);
      
      // ✅ עכשיו מרענן מהשרת אוטומטית אחרי עריכה
      await fetchBusinesses();
    } catch (error) {
      console.error('שגיאה בעדכון עסק:', error);
      // אם יש שגיאה, לא סוגרים את המודל כדי שהמשתמש יכול לנסות שוב
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-4 md:p-6" dir="rtl">
      <div className="max-w-7xl mx-auto">
        {/* Page Header */}
        <div className="mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h1 className="text-2xl md:text-3xl font-semibold text-slate-900 flex items-center gap-3">
                <Building2 className="h-8 w-8 text-blue-600" />
                ניהול עסקים
              </h1>
              <p className="text-slate-600 mt-1">
                נהל את כל העסקים במערכת, הוסף עסקים חדשים ועדכן הגדרות
              </p>
            </div>
            <button
              onClick={handleNewBusiness}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors"
              disabled
            >
              <Plus className="h-5 w-5" />
              עסק חדש
            </button>
          </div>
        </div>

        {/* Filters & Search */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-4 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            {/* Search */}
            <div className="flex-1 relative">
              <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-slate-400" />
              <input
                type="text"
                placeholder="חפש עסק לפי שם או דומיין..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pr-10 pl-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
                dir="rtl"
              />
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <Filter className="h-5 w-5 text-slate-400" />
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as 'all' | 'active' | 'suspended')}
                className="px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none bg-white"
              >
                <option value="all">כל הסטטוסים</option>
                <option value="active">פעיל</option>
                <option value="suspended">מושעה</option>
              </select>
            </div>
          </div>
        </div>

        {/* Results Summary */}
        <div className="mb-4">
          <p className="text-sm text-slate-600">
            מציג {filteredBusinesses.length} מתוך {allBusinesses.length} עסקים
            {searchQuery && ` • חיפוש: "${searchQuery}"`}
            {statusFilter !== 'all' && ` • סטטוס: ${statusFilter === 'active' ? 'פעיל' : 'מושעה'}`}
          </p>
        </div>

        {/* Business List */}
        {filteredBusinesses.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-12 text-center">
            <Building2 className="h-12 w-12 mx-auto mb-4 text-slate-300" />
            <h3 className="text-lg font-medium text-slate-900 mb-2">לא נמצאו עסקים</h3>
            <p className="text-slate-600 mb-4">
              {searchQuery || statusFilter !== 'all' 
                ? 'נסה לשנות את הפילטרים או החיפוש' 
                : 'אין עסקים במערכת כרגע'}
            </p>
            {(searchQuery || statusFilter !== 'all') && (
              <button
                onClick={() => {
                  setSearchQuery('');
                  setStatusFilter('all');
                }}
                className="px-4 py-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
              >
                נקה פילטרים
              </button>
            )}
          </div>
        ) : loading ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8">
            <div className="flex items-center justify-center">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 ml-3"></div>
              <span className="text-slate-600">טוען עסקים...</span>
            </div>
          </div>
        ) : error ? (
          <div className="bg-red-50 border border-red-200 rounded-xl p-6">
            <div className="flex items-center gap-3 text-red-700">
              <XCircle className="h-5 w-5" />
              <div>
                <p className="font-medium">שגיאה בטעינת נתונים</p>
                <p className="text-sm text-red-600">{error}</p>
                <button 
                  onClick={fetchBusinesses}
                  className="text-sm underline hover:no-underline mt-1"
                >
                  נסה שוב
                </button>
              </div>
            </div>
          </div>
        ) : (
          <>
            {/* Desktop Table */}
            <BusinessTable 
              businesses={filteredBusinesses}
              onBusinessClick={handleBusinessClick}
              onActionClick={handleActionClick}
            />

            {/* Mobile Cards */}
            <BusinessCardList 
              businesses={filteredBusinesses}
              onBusinessClick={handleBusinessClick}
              onActionClick={handleActionClick}
            />
          </>
        )}
      </div>

      {/* Edit Business Modal */}
      <BusinessEditModal
        business={selectedBusiness}
        isOpen={editModalOpen}
        onClose={() => {
          setEditModalOpen(false);
          setSelectedBusiness(null);
        }}
        onSave={selectedBusiness ? handleSaveBusiness : handleCreateBusiness}
        isLoading={businessActions.isLoading('edit', selectedBusiness?.id)}
      />
    </div>
  );
}