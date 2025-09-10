import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Bot, 
  Search, 
  Phone, 
  MessageSquare,
  ChevronLeft,
  Settings
} from 'lucide-react';
import { http } from '../../services/http';

interface Business {
  id: number;
  name: string;
  business_type: string;
  phone: string;
  status: string;
  created_at: string;
}

export function BusinessPromptsSelector() {
  const navigate = useNavigate();
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  // Load businesses
  useEffect(() => {
    const loadBusinesses = async () => {
      try {
        setLoading(true);
        console.log('🔄 Loading businesses for prompts management...');
        
        const response = await http.get<{ 
          items: Business[]; 
          total: number; 
          page: number; 
          pageSize: number 
        }>('/api/admin/businesses');
        
        setBusinesses(response.items);
        console.log('✅ Loaded businesses for prompts:', response.items);
      } catch (err) {
        console.error('❌ Failed to load businesses:', err);
      } finally {
        setLoading(false);
      }
    };

    loadBusinesses();
  }, []);

  // Filter businesses by search query
  const filteredBusinesses = businesses.filter(business =>
    business.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    business.phone.includes(searchQuery)
  );

  const handleBusinessSelect = (business: Business) => {
    console.log(`🎯 Selected business ${business.name} for prompts management`);
    navigate(`/app/admin/businesses/${business.id}/agent`);
  };

  if (loading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 ml-3"></div>
          <span className="text-slate-600">טוען עסקים...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => navigate('/app/admin/overview')}
            className="p-2 text-slate-500 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          >
            <ChevronLeft className="h-5 w-5" />
          </button>
          <Bot className="h-6 w-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-slate-900">ניהול פרומפטים לעסקים</h1>
        </div>
        
        <p className="text-slate-600">
          בחר עסק כדי לערוך את הפרומפטים של ה-AI Agent עבור שיחות ו-WhatsApp
        </p>
      </div>

      {/* Search Bar */}
      <div className="relative mb-6">
        <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-slate-400 h-5 w-5" />
        <input
          type="text"
          placeholder="חפש לפי שם עסק או טלפון..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pr-10 pl-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
          dir="rtl"
        />
      </div>

      {/* Businesses Grid */}
      {filteredBusinesses.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredBusinesses.map((business) => (
            <div
              key={business.id}
              onClick={() => handleBusinessSelect(business)}
              className="bg-white border border-slate-200 rounded-xl p-6 hover:shadow-md hover:border-purple-300 transition-all cursor-pointer group"
            >
              <div className="flex items-start justify-between mb-4">
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-slate-900 group-hover:text-purple-700 transition-colors">
                    {business.name}
                  </h3>
                  <p className="text-sm text-slate-600 mt-1">
                    {business.business_type === 'real_estate' ? 'נדל״ן' : business.business_type}
                  </p>
                </div>
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center group-hover:bg-purple-200 transition-colors">
                  <Settings className="h-5 w-5 text-purple-600" />
                </div>
              </div>

              <div className="space-y-2 mb-4">
                <div className="flex items-center gap-2 text-sm text-slate-600">
                  <Phone className="h-4 w-4" />
                  <span>{business.phone || 'לא מוגדר'}</span>
                </div>
              </div>

              <div className="flex items-center gap-3 pt-4 border-t border-slate-100">
                <div className="flex items-center gap-1">
                  <Phone className="h-4 w-4 text-blue-600" />
                  <span className="text-xs text-slate-600">שיחות</span>
                </div>
                <div className="flex items-center gap-1">
                  <MessageSquare className="h-4 w-4 text-green-600" />
                  <span className="text-xs text-slate-600">WhatsApp</span>
                </div>
                <div className="mr-auto">
                  <span className={`text-xs px-2 py-1 rounded-full ${
                    business.status === 'active' 
                      ? 'bg-green-100 text-green-700' 
                      : 'bg-red-100 text-red-700'
                  }`}>
                    {business.status === 'active' ? 'פעיל' : 'לא פעיל'}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="text-center py-12">
          <Bot className="h-16 w-16 text-slate-300 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-slate-900 mb-2">לא נמצאו עסקים</h3>
          <p className="text-slate-600">
            {searchQuery ? 'לא נמצאו עסקים התואמים לחיפוש' : 'אין עסקים במערכת'}
          </p>
        </div>
      )}

      {/* Summary */}
      <div className="mt-8 bg-purple-50 border border-purple-200 rounded-lg p-4">
        <div className="flex items-center gap-3">
          <Bot className="h-5 w-5 text-purple-600 flex-shrink-0" />
          <div className="text-purple-800">
            <p className="font-medium">ניהול פרומפטים</p>
            <p className="text-sm mt-1">
              עריכת הפרומפטים תשפיע על כל השיחות וההודעות החדשות באותו עסק.
              כל עסק יכול להיות עם פרומפטים שונים המותאמים לצרכים שלו.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}