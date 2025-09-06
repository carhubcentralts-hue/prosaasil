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
  Clock
} from 'lucide-react';
import { BusinessEditModal } from '../../shared/components/ui/BusinessEditModal';
import { cn } from '../../shared/utils/cn';
import { useAuth } from '../../features/auth/hooks';

interface Business {
  id: number;
  name: string;
  domain: string;
  defaultPhoneE164: string;
  whatsappJid: string;
  users: number;
  status: 'active' | 'suspended';
  createdAt: string;
  prompt?: string;
  permissions?: string[];
}

// Mock data - In real app this would come from API
const mockBusinesses: Business[] = [
  {
    id: 1,
    name: 'שי דירות ומשרדים בע״מ',
    domain: 'shai-realestate.co.il',
    defaultPhoneE164: '+972-3-376-3805',
    whatsappJid: '972501234567@s.whatsapp.net',
    users: 8,
    status: 'active',
    createdAt: '2024-08-01T10:22:00Z'
  },
  {
    id: 2,
    name: 'נדלן טופ - יזמות והשקעות',
    domain: 'nadlan-top.co.il', 
    defaultPhoneE164: '+972-9-888-7777',
    whatsappJid: '972509876543@s.whatsapp.net',
    users: 3,
    status: 'active',
    createdAt: '2024-09-15T14:30:00Z'
  },
  {
    id: 3,
    name: 'משרדי פרימיום',
    domain: 'premium-offices.co.il',
    defaultPhoneE164: '+972-2-567-8901',
    whatsappJid: '972502468135@s.whatsapp.net',
    users: 5,
    status: 'suspended',
    createdAt: '2024-07-20T09:15:00Z'
  },
  {
    id: 4,
    name: 'דירות יוקרה ברמת אביב',
    domain: 'luxury-ramat-aviv.co.il',
    defaultPhoneE164: '+972-3-123-4567',
    whatsappJid: '972503691470@s.whatsapp.net',
    users: 2,
    status: 'active',
    createdAt: '2024-10-01T16:45:00Z'
  }
];

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
              <th className="text-right py-3 px-4 text-sm font-medium text-slate-700">דומיין</th>
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
                    <Globe className="h-4 w-4 text-slate-400" />
                    <span className="text-sm text-slate-600 direction-ltr">{business.domain}</span>
                  </div>
                </td>
                <td className="py-4 px-4">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <Phone className="h-3 w-3 text-slate-400" />
                      <span className="text-xs text-slate-600 direction-ltr">{business.defaultPhoneE164}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-green-600">WA</span>
                      <span className="text-xs text-slate-500 direction-ltr truncate max-w-[120px]">
                        {business.whatsappJid.split('@')[0]}
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
                    <span className="text-sm text-slate-600">{formatDate(business.createdAt)}</span>
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
                    >
                      <Eye className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('edit', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-green-600 hover:bg-green-50 rounded-lg transition-colors"
                      title="עריכה"
                    >
                      <Edit className="h-4 w-4" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onActionClick('more', business);
                      }}
                      className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                      title="עוד פעולות"
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
              <span className="text-sm text-slate-600 direction-ltr">{business.domain}</span>
            </div>
            <div className="flex items-center gap-2">
              <Phone className="h-4 w-4 text-slate-400" />
              <span className="text-sm text-slate-600 direction-ltr">{business.defaultPhoneE164}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Users className="h-4 w-4 text-slate-400" />
                <span className="text-sm text-slate-600">{business.users} משתמשים</span>
              </div>
              <div className="flex items-center gap-2">
                <Calendar className="h-4 w-4 text-slate-400" />
                <span className="text-sm text-slate-600">{formatDate(business.createdAt)}</span>
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
              >
                <Edit className="h-4 w-4" />
                עריכה
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
  const [filteredBusinesses, setFilteredBusinesses] = useState<Business[]>(mockBusinesses);
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(null);
  const { user } = useAuth();
  const navigate = useNavigate();

  // Filter businesses based on search and status
  useEffect(() => {
    let filtered = mockBusinesses;

    // Apply search filter
    if (searchQuery.trim()) {
      filtered = filtered.filter(business => 
        business.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        business.domain.toLowerCase().includes(searchQuery.toLowerCase())
      );
    }

    // Apply status filter
    if (statusFilter !== 'all') {
      filtered = filtered.filter(business => business.status === statusFilter);
    }

    setFilteredBusinesses(filtered);
  }, [searchQuery, statusFilter]);

  const handleBusinessClick = (business: Business) => {
    navigate(`/app/admin/businesses/${business.id}`);
  };

  const handleActionClick = (action: string, business: Business) => {
    switch (action) {
      case 'view':
        navigate(`/app/admin/businesses/${business.id}`);
        break;
      case 'edit':
        console.log(`עריכת עסק: ${business.name}`);
        setSelectedBusiness(business);
        setEditModalOpen(true);
        break;
      case 'more':
        // Show dropdown with all additional actions
        const actionChoice = prompt(`בחר פעולה עבור "${business.name}":\n\n1. התחזות לעסק\n2. השעה/הפעל עסק\n3. מחק עסק\n4. איפוס סיסמאות משתמשים\n\nהכנס מספר (1-4):`);
        
        switch (actionChoice) {
          case '1':
            handleImpersonate(business);
            break;
          case '2':
            handleToggleSuspension(business);
            break;
          case '3':
            handleDeleteBusiness(business);
            break;
          case '4':
            handleResetPasswords(business);
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
    // Create new business functionality
    const businessName = prompt('הכנס את שם העסק החדש:');
    if (businessName && businessName.trim()) {
      alert(`העסק "${businessName}" נוסף בהצלחה למערכת!`);
      console.log(`עסק חדש נוצר: ${businessName}`);
    }
  };

  const handleSaveBusiness = (updatedBusiness: Business) => {
    setFilteredBusinesses(prev => prev.map(b => 
      b.id === updatedBusiness.id ? updatedBusiness : b
    ));
    console.log('עסק עודכן:', updatedBusiness);
  };

  const handleImpersonate = (business: Business) => {
    // Confirm impersonation
    const confirmed = confirm(`האם אתה בטוח שאתה רוצה להתחזות לעסק "${business.name}"?\nאתה תועבר לדשבורד של העסק.`);
    if (confirmed) {
      // Store original user data for exit impersonation
      const originalUser = JSON.stringify(user);
      localStorage.setItem('impersonation_original_user', originalUser);
      localStorage.setItem('is_impersonating', 'true');
      localStorage.setItem('impersonating_business_id', business.id.toString());
      
      // Navigate to business dashboard
      console.log(`התחזות לעסק: ${business.name}`);
      alert(`התחזות מופעלת! מועבר לדשבורד עסק: ${business.name}`);
      navigate('/app/business/dashboard');
    }
  };

  const handleToggleSuspension = (business: Business) => {
    const actionText = business.status === 'active' ? 'השעה' : 'הפעל';
    const confirmed = confirm(`האם אתה בטוח שאתה רוצה ל${actionText} את העסק "${business.name}"?`);
    if (confirmed) {
      const newStatus = business.status === 'active' ? 'suspended' : 'active';
      
      // Update the business in the list
      setFilteredBusinesses(prev => prev.map(b => 
        b.id === business.id ? { ...b, status: newStatus } : b
      ));
      
      alert(`העסק "${business.name}" ${newStatus === 'active' ? 'הופעל' : 'הושעה'} בהצלחה!`);
    }
  };

  const handleDeleteBusiness = (business: Business) => {
    const confirmed = confirm(`⚠️ אזהרה: האם אתה בטוח שאתה רוצה למחוק את העסק "${business.name}"?\n\nפעולה זו תמחק:\n- את כל הנתונים של העסק\n- את כל המשתמשים\n- את כל השיחות וההתראות\n\nפעולה זו בלתי הפיכה!`);
    
    if (confirmed) {
      const secondConfirm = prompt(`כדי לאשר מחיקה, הקלד את שם העסק בדיוק: "${business.name}"`);
      if (secondConfirm === business.name) {
        // Remove from the list
        setFilteredBusinesses(prev => prev.filter(b => b.id !== business.id));
        alert(`העסק "${business.name}" נמחק בהצלחה מהמערכת.`);
      } else {
        alert('שם העסק לא תואם. המחיקה בוטלה.');
      }
    }
  };

  const handleResetPasswords = (business: Business) => {
    const confirmed = confirm(`האם אתה בטוח שאתה רוצה לאפס את סיסמאות כל המשתמשים של "${business.name}"?\n\nהסיסמאות החדשות יישלחו למשתמשים במייל.`);
    if (confirmed) {
      alert(`איפוס סיסמאות בוצע בהצלחה!\n\nסיסמאות חדשות נשלחו למייל של ${business.users} משתמשים.`);
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
            מציג {filteredBusinesses.length} מתוך {mockBusinesses.length} עסקים
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
        isOpen={editModalOpen}
        onClose={() => setEditModalOpen(false)}
        business={selectedBusiness}
        onSave={handleSaveBusiness}
      />
    </div>
  );
}