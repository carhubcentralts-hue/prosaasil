import React, { useState, useEffect, useMemo } from 'react';
import axios from 'axios';
import { 
  Search, 
  Filter, 
  Plus, 
  Edit3, 
  Phone, 
  Mail, 
  Calendar,
  User,
  Building2,
  MapPin,
  Tag,
  Star,
  Download,
  Upload,
  MoreVertical,
  Eye,
  Trash2,
  Archive,
  PhoneCall,
  MessageSquare,
  UserPlus,
  TrendingUp,
  TrendingDown,
  AlertCircle,
  CheckCircle,
  Clock,
  Activity
} from 'lucide-react';

const AdvancedCRM = () => {
  // State Management
  const [leads, setLeads] = useState([]);
  const [filteredLeads, setFilteredLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [filters, setFilters] = useState({
    status: '',
    source: '',
    priority: '',
    dateRange: '',
    assignedTo: '',
    tags: []
  });
  const [sortConfig, setSortConfig] = useState({
    key: 'created_at',
    direction: 'desc'
  });
  const [selectedLeads, setSelectedLeads] = useState([]);
  const [viewMode, setViewMode] = useState('table'); // table, cards, kanban
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingLead, setEditingLead] = useState(null);
  const [stats, setStats] = useState({});

  // Business Info
  const businessId = localStorage.getItem('business_id') || localStorage.getItem('impersonated_business_id') || 1;
  const userRole = localStorage.getItem('user_role');

  // Fetch Data
  useEffect(() => {
    fetchLeads();
    fetchStats();
  }, [businessId]);

  const fetchLeads = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`/api/crm/leads?business_id=${businessId}`);
      setLeads(response.data);
      setFilteredLeads(response.data);
    } catch (error) {
      console.error('Error fetching leads:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`/api/crm/stats?business_id=${businessId}`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  // Advanced Search and Filter Logic
  const performAdvancedSearch = useMemo(() => {
    let result = [...leads];

    // Search in multiple fields
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      result = result.filter(lead => 
        lead.name?.toLowerCase().includes(term) ||
        lead.email?.toLowerCase().includes(term) ||
        lead.phone?.includes(term) ||
        lead.company?.toLowerCase().includes(term) ||
        lead.notes?.toLowerCase().includes(term) ||
        lead.tags?.some(tag => tag.toLowerCase().includes(term))
      );
    }

    // Apply filters
    if (filters.status) {
      result = result.filter(lead => lead.status === filters.status);
    }
    if (filters.source) {
      result = result.filter(lead => lead.source === filters.source);
    }
    if (filters.priority) {
      result = result.filter(lead => lead.priority === filters.priority);
    }
    if (filters.assignedTo) {
      result = result.filter(lead => lead.assigned_to === filters.assignedTo);
    }
    if (filters.tags.length > 0) {
      result = result.filter(lead => 
        filters.tags.some(tag => lead.tags?.includes(tag))
      );
    }

    // Date range filter
    if (filters.dateRange) {
      const now = new Date();
      let startDate;
      switch (filters.dateRange) {
        case 'today':
          startDate = new Date(now.getFullYear(), now.getMonth(), now.getDate());
          break;
        case 'week':
          startDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          break;
        case 'month':
          startDate = new Date(now.getFullYear(), now.getMonth(), 1);
          break;
        case '3months':
          startDate = new Date(now.getFullYear(), now.getMonth() - 3, 1);
          break;
        default:
          startDate = null;
      }
      if (startDate) {
        result = result.filter(lead => new Date(lead.created_at) >= startDate);
      }
    }

    // Sorting
    result.sort((a, b) => {
      let aVal = a[sortConfig.key];
      let bVal = b[sortConfig.key];
      
      if (typeof aVal === 'string') {
        aVal = aVal.toLowerCase();
        bVal = bVal.toLowerCase();
      }
      
      if (aVal < bVal) {
        return sortConfig.direction === 'asc' ? -1 : 1;
      }
      if (aVal > bVal) {
        return sortConfig.direction === 'asc' ? 1 : -1;
      }
      return 0;
    });

    return result;
  }, [leads, searchTerm, filters, sortConfig]);

  useEffect(() => {
    setFilteredLeads(performAdvancedSearch);
  }, [performAdvancedSearch]);

  // Status Icons and Colors
  const getStatusIcon = (status) => {
    switch (status) {
      case 'new': return <Clock className="w-4 h-4 text-blue-500" />;
      case 'contacted': return <PhoneCall className="w-4 h-4 text-yellow-500" />;
      case 'qualified': return <CheckCircle className="w-4 h-4 text-green-500" />;
      case 'proposal': return <TrendingUp className="w-4 h-4 text-purple-500" />;
      case 'negotiation': return <Activity className="w-4 h-4 text-orange-500" />;
      case 'closed_won': return <Star className="w-4 h-4 text-green-600" />;
      case 'closed_lost': return <TrendingDown className="w-4 h-4 text-red-500" />;
      default: return <AlertCircle className="w-4 h-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'new': return 'bg-blue-100 text-blue-800';
      case 'contacted': return 'bg-yellow-100 text-yellow-800';
      case 'qualified': return 'bg-green-100 text-green-800';
      case 'proposal': return 'bg-purple-100 text-purple-800';
      case 'negotiation': return 'bg-orange-100 text-orange-800';
      case 'closed_won': return 'bg-green-200 text-green-900';
      case 'closed_lost': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high': return 'text-red-600';
      case 'medium': return 'text-yellow-600';
      case 'low': return 'text-green-600';
      default: return 'text-gray-600';
    }
  };

  // Hebrew Date Formatting
  const formatHebrewDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('he-IL', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  // Handlers
  const handleSort = (key) => {
    setSortConfig(prevConfig => ({
      key,
      direction: prevConfig.key === key && prevConfig.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  const handleSelectLead = (leadId) => {
    setSelectedLeads(prev => 
      prev.includes(leadId) 
        ? prev.filter(id => id !== leadId)
        : [...prev, leadId]
    );
  };

  const handleSelectAll = () => {
    setSelectedLeads(
      selectedLeads.length === filteredLeads.length 
        ? [] 
        : filteredLeads.map(lead => lead.id)
    );
  };

  const handleBulkAction = async (action) => {
    try {
      await axios.post(`/api/crm/bulk-action`, {
        business_id: businessId,
        lead_ids: selectedLeads,
        action
      });
      fetchLeads();
      setSelectedLeads([]);
    } catch (error) {
      console.error('Bulk action error:', error);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center" dir="rtl">
        <div className="text-center font-hebrew">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">טוען נתוני לידים...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50" dir="rtl">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 font-hebrew mb-2">
              CRM מתקדם - ניהול לידים
            </h1>
            <p className="text-gray-600 font-hebrew">
              מערכת ניהול לקוחות פוטנציאליים ברמת Monday.com
            </p>
          </div>
          <div className="flex gap-3 mt-4 lg:mt-0">
            <button
              onClick={() => setShowAddModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-hebrew"
            >
              <Plus className="w-4 h-4" />
              הוסף ליד חדש
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-hebrew">
              <Upload className="w-4 h-4" />
              ייבא נתונים
            </button>
            <button className="flex items-center gap-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 font-hebrew">
              <Download className="w-4 h-4" />
              ייצא לExcel
            </button>
          </div>
        </div>

        {/* Stats Cards - Monday.com Style */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 font-hebrew">סה"כ לידים</p>
                <p className="text-2xl font-bold text-gray-900">{stats.total_leads || 0}</p>
              </div>
              <div className="p-3 bg-blue-100 rounded-lg">
                <Users className="w-6 h-6 text-blue-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <TrendingUp className="w-4 h-4 text-green-500 ml-1" />
              <span className="text-green-600 font-medium">+12%</span>
              <span className="text-gray-600 font-hebrew mr-2">מהחודש הקודם</span>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 font-hebrew">מחכים למעקב</p>
                <p className="text-2xl font-bold text-gray-900">{stats.pending_followup || 0}</p>
              </div>
              <div className="p-3 bg-yellow-100 rounded-lg">
                <Clock className="w-6 h-6 text-yellow-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <AlertCircle className="w-4 h-4 text-yellow-500 ml-1" />
              <span className="text-yellow-600 font-hebrew">דורש תשומת לב</span>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 font-hebrew">עסקאות סגורות</p>
                <p className="text-2xl font-bold text-gray-900">{stats.closed_won || 0}</p>
              </div>
              <div className="p-3 bg-green-100 rounded-lg">
                <CheckCircle className="w-6 h-6 text-green-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <Star className="w-4 h-4 text-green-500 ml-1" />
              <span className="text-green-600 font-medium">₪{stats.total_revenue || 0}</span>
              <span className="text-gray-600 font-hebrew mr-2">הכנסות</span>
            </div>
          </div>

          <div className="bg-white rounded-lg p-6 shadow-sm border border-gray-200">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600 font-hebrew">שיעור המרה</p>
                <p className="text-2xl font-bold text-gray-900">{stats.conversion_rate || 0}%</p>
              </div>
              <div className="p-3 bg-purple-100 rounded-lg">
                <TrendingUp className="w-6 h-6 text-purple-600" />
              </div>
            </div>
            <div className="mt-4 flex items-center text-sm">
              <Activity className="w-4 h-4 text-purple-500 ml-1" />
              <span className="text-purple-600 font-hebrew">ביצועים מעולים</span>
            </div>
          </div>
        </div>

        {/* Advanced Search and Filters */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-8">
          <div className="flex flex-col lg:flex-row gap-4">
            {/* Search Bar */}
            <div className="flex-1 relative">
              <Search className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-5 h-5" />
              <input
                type="text"
                placeholder="חיפוש לפי שם, טלפון, אימייל, חברה או הערות..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pr-10 pl-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-hebrew"
              />
            </div>

            {/* Filters */}
            <div className="flex flex-wrap gap-3">
              <select
                value={filters.status}
                onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
                className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל הסטטוסים</option>
                <option value="new">חדש</option>
                <option value="contacted">נוצר קשר</option>
                <option value="qualified">מוכשר</option>
                <option value="proposal">הצעה</option>
                <option value="negotiation">משא ומתן</option>
                <option value="closed_won">נסגר בהצלחה</option>
                <option value="closed_lost">נסגר ללא הצלחה</option>
              </select>

              <select
                value={filters.source}
                onChange={(e) => setFilters(prev => ({ ...prev, source: e.target.value }))}
                className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל המקורות</option>
                <option value="website">אתר</option>
                <option value="phone">טלפון</option>
                <option value="whatsapp">WhatsApp</option>
                <option value="facebook">Facebook</option>
                <option value="google">Google</option>
                <option value="referral">הפניה</option>
              </select>

              <select
                value={filters.priority}
                onChange={(e) => setFilters(prev => ({ ...prev, priority: e.target.value }))}
                className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל העדיפויות</option>
                <option value="high">גבוהה</option>
                <option value="medium">בינונית</option>
                <option value="low">נמוכה</option>
              </select>

              <select
                value={filters.dateRange}
                onChange={(e) => setFilters(prev => ({ ...prev, dateRange: e.target.value }))}
                className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-hebrew"
              >
                <option value="">כל התאריכים</option>
                <option value="today">היום</option>
                <option value="week">השבוע</option>
                <option value="month">החודש</option>
                <option value="3months">3 חודשים אחרונים</option>
              </select>

              <button
                onClick={() => setFilters({ status: '', source: '', priority: '', dateRange: '', assignedTo: '', tags: [] })}
                className="px-4 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 font-hebrew"
              >
                נקה מסננים
              </button>
            </div>
          </div>
        </div>

        {/* Results Summary and Actions */}
        {selectedLeads.length > 0 && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-blue-600" />
                <span className="font-hebrew text-blue-800">
                  נבחרו {selectedLeads.length} לידים
                </span>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleBulkAction('update_status')}
                  className="px-3 py-1 bg-blue-600 text-white rounded font-hebrew text-sm"
                >
                  עדכן סטטוס
                </button>
                <button
                  onClick={() => handleBulkAction('assign')}
                  className="px-3 py-1 bg-green-600 text-white rounded font-hebrew text-sm"
                >
                  הקצה למשתמש
                </button>
                <button
                  onClick={() => handleBulkAction('delete')}
                  className="px-3 py-1 bg-red-600 text-white rounded font-hebrew text-sm"
                >
                  מחק
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Results Table - Monday.com Style */}
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <div className="flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900 font-hebrew">
                תוצאות חיפוש ({filteredLeads.length} לידים)
              </h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setViewMode('table')}
                  className={`p-2 rounded ${viewMode === 'table' ? 'bg-blue-100 text-blue-600' : 'text-gray-400'}`}
                >
                  <Activity className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setViewMode('cards')}
                  className={`p-2 rounded ${viewMode === 'cards' ? 'bg-blue-100 text-blue-600' : 'text-gray-400'}`}
                >
                  <Building2 className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>

          {filteredLeads.length === 0 ? (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 font-hebrew mb-2">
                לא נמצאו לידים
              </h3>
              <p className="text-gray-600 font-hebrew">
                נסה לשנות את קריטריוני החיפוש או הוסף ליד חדש
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                      <input
                        type="checkbox"
                        checked={selectedLeads.length === filteredLeads.length}
                        onChange={handleSelectAll}
                        className="rounded border-gray-300"
                      />
                    </th>
                    <th 
                      className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 font-hebrew"
                      onClick={() => handleSort('name')}
                    >
                      שם הליד
                      {sortConfig.key === 'name' && (
                        <span className="mr-1">
                          {sortConfig.direction === 'asc' ? '↑' : '↓'}
                        </span>
                      )}
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                      פרטי קשר
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                      חברה
                    </th>
                    <th 
                      className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 font-hebrew"
                      onClick={() => handleSort('status')}
                    >
                      סטטוס
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                      עדיפות
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                      מקור
                    </th>
                    <th 
                      className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100 font-hebrew"
                      onClick={() => handleSort('created_at')}
                    >
                      תאריך יצירה
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider font-hebrew">
                      פעולות
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredLeads.map((lead) => (
                    <tr key={lead.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <input
                          type="checkbox"
                          checked={selectedLeads.includes(lead.id)}
                          onChange={() => handleSelectLead(lead.id)}
                          className="rounded border-gray-300"
                        />
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          <div className="flex-shrink-0 h-10 w-10">
                            <div className="h-10 w-10 rounded-full bg-gray-200 flex items-center justify-center">
                              <User className="w-5 h-5 text-gray-600" />
                            </div>
                          </div>
                          <div className="mr-4">
                            <div className="text-sm font-medium text-gray-900 font-hebrew">
                              {lead.name}
                            </div>
                            {lead.tags && lead.tags.length > 0 && (
                              <div className="flex gap-1 mt-1">
                                {lead.tags.slice(0, 2).map((tag, index) => (
                                  <span key={index} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                                    {tag}
                                  </span>
                                ))}
                                {lead.tags.length > 2 && (
                                  <span className="text-xs text-gray-500">+{lead.tags.length - 2}</span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          {lead.phone && (
                            <div className="flex items-center gap-1 mb-1">
                              <Phone className="w-3 h-3 text-gray-400" />
                              <span className="font-hebrew">{lead.phone}</span>
                            </div>
                          )}
                          {lead.email && (
                            <div className="flex items-center gap-1">
                              <Mail className="w-3 h-3 text-gray-400" />
                              <span className="font-hebrew">{lead.email}</span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-hebrew">
                        {lead.company || '-'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusColor(lead.status)}`}>
                          {getStatusIcon(lead.status)}
                          <span className="mr-1 font-hebrew">
                            {lead.status === 'new' && 'חדש'}
                            {lead.status === 'contacted' && 'נוצר קשר'}
                            {lead.status === 'qualified' && 'מוכשר'}
                            {lead.status === 'proposal' && 'הצעה'}
                            {lead.status === 'negotiation' && 'משא ומתן'}
                            {lead.status === 'closed_won' && 'נסגר בהצלחה'}
                            {lead.status === 'closed_lost' && 'נסגר ללא הצלחה'}
                          </span>
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`text-sm font-medium ${getPriorityColor(lead.priority)}`}>
                          <span className="font-hebrew">
                            {lead.priority === 'high' && 'גבוהה'}
                            {lead.priority === 'medium' && 'בינונית'}
                            {lead.priority === 'low' && 'נמוכה'}
                            {!lead.priority && '-'}
                          </span>
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-hebrew">
                        {lead.source === 'website' && 'אתר'}
                        {lead.source === 'phone' && 'טלפון'}
                        {lead.source === 'whatsapp' && 'WhatsApp'}
                        {lead.source === 'facebook' && 'Facebook'}
                        {lead.source === 'google' && 'Google'}
                        {lead.source === 'referral' && 'הפניה'}
                        {!['website', 'phone', 'whatsapp', 'facebook', 'google', 'referral'].includes(lead.source) && (lead.source || '-')}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 font-hebrew">
                        {formatHebrewDate(lead.created_at)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <div className="flex items-center gap-2">
                          <button className="text-indigo-600 hover:text-indigo-900">
                            <Eye className="w-4 h-4" />
                          </button>
                          <button 
                            onClick={() => {
                              setEditingLead(lead);
                              setShowEditModal(true);
                            }}
                            className="text-green-600 hover:text-green-900"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button className="text-blue-600 hover:text-blue-900">
                            <PhoneCall className="w-4 h-4" />
                          </button>
                          <button className="text-orange-600 hover:text-orange-900">
                            <MessageSquare className="w-4 h-4" />
                          </button>
                          <button className="text-red-600 hover:text-red-900">
                            <Trash2 className="w-4 h-4" />
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
};

export default AdvancedCRM;