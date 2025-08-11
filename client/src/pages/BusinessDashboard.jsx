import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

// Simple icons without lucide-react dependency
const IconBuilding = () => <span>🏢</span>;
const IconLogOut = () => <span>⇐</span>;
const IconPhone = () => <span>📞</span>;
const IconMessage = () => <span>💬</span>;
const IconUsers = () => <span>👥</span>;
const IconHome = () => <span>🏠</span>;
const IconActivity = () => <span>📊</span>;
const IconChart = () => <span>📈</span>;
const IconLock = () => <span>🔒</span>;

const BusinessDashboard = () => {
  const { user, logout } = useAuth();
  const [customers, setCustomers] = useState([]);

  useEffect(() => {
    // Load business data
    loadBusinessData();
  }, []);

  const loadBusinessData = async () => {
    try {
      const response = await fetch('/api/customers', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setCustomers(data.customers || []);
      }
    } catch (error) {
      console.error('Failed to load business data:', error);
    }
  };

  const businessInfo = {
    name: 'שי דירות ומשרדים בע״מ',
    type: 'נדל"ן ותיווך',
    phone: '+972-3-555-7777',
    whatsapp: '+1-555-123-4567',
    status: 'פעיל',
    totalCalls: 127,
    totalContacts: 45,
    lastActivity: 'פעיל עכשיו'
  };

  const systemModules = [
    {
      id: 'crm',
      name: 'מערכת CRM שלי',
      icon: IconUsers,
      description: 'ניהול הלקוחות שלי',
      businessDescription: 'רק הלקוחות של שי דירות',
      color: 'background: linear-gradient(135deg, #3b82f6, #1d4ed8)',
      stats: `הלקוחות שלי: ${businessInfo.totalContacts}`,
      restricted: false
    },
    {
      id: 'calls',
      name: 'שיחות שלי',
      icon: IconPhone,
      description: 'השיחות של העסק שלי',
      businessDescription: 'רק השיחות של שי דירות',
      color: 'background: linear-gradient(135deg, #10b981, #059669)',
      stats: `השיחות שלי: ${businessInfo.totalCalls}`,
      restricted: false
    },
    {
      id: 'whatsapp',
      name: 'WhatsApp שלי',
      icon: IconMessage,
      description: 'הודעות WhatsApp שלי',
      businessDescription: 'רק הודעות WhatsApp של שי דירות',
      color: 'background: linear-gradient(135deg, #8b5cf6, #7c3aed)',
      stats: 'ההודעות שלי: 23',
      restricted: false
    }
  ];

  const handleSystemAccess = (systemId, systemName) => {
    alert(`כניסה למערכת ${systemName} - תצוגת עסק\nרואה רק את הנתונים של ${businessInfo.name}`);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="dashboard-title">
          <IconBuilding /> {businessInfo.name}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 'bold' }}>
              {user?.name || 'בעל עסק'}
            </div>
            <div style={{ fontSize: '0.8rem', opacity: 0.8 }}>
              תצוגת עסק
            </div>
          </div>
          <button onClick={handleLogout} className="btn-logout">
            <IconLogOut /> יציאה
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="dashboard-content">
        {/* Welcome Section */}
        <div style={{
          background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          borderRadius: '12px',
          padding: '2rem',
          color: 'white',
          marginBottom: '2rem',
          textAlign: 'center'
        }}>
          <IconHome style={{ fontSize: '3rem', marginBottom: '1rem' }} />
          <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>
            ברוכים הבאים לדשבורד העסק שלכם
          </h2>
          <p style={{ opacity: 0.9 }}>
            אתם רואים ומנהלים רק את הנתונים של {businessInfo.name}
          </p>
        </div>

        {/* Business Info Card */}
        <div style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">
            <IconBuilding /> פרטי העסק
          </h3>
          <div className="content-card" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '1rem' }}>
              <div>
                <strong>שם העסק:</strong> {businessInfo.name}
              </div>
              <div>
                <strong>סוג עסק:</strong> {businessInfo.type}
              </div>
              <div>
                <strong>טלפון:</strong> {businessInfo.phone}
              </div>
              <div>
                <strong>WhatsApp:</strong> {businessInfo.whatsapp}
              </div>
              <div>
                <strong>סטטוס:</strong> <span className="status-active">● {businessInfo.status}</span>
              </div>
              <div>
                <strong>פעילות אחרונה:</strong> {businessInfo.lastActivity}
              </div>
            </div>
          </div>
        </div>

        {/* Business Stats */}
        <div style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">
            <IconChart /> הסטטיסטיקות שלי
          </h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-number">{businessInfo.totalCalls}</div>
              <div className="stat-label">סה״כ שיחות שלי</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">{businessInfo.totalContacts}</div>
              <div className="stat-label">הלקוחות שלי</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">23</div>
              <div className="stat-label">הודעות WhatsApp שלי</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">1</div>
              <div className="stat-label">עסק פעיל</div>
            </div>
          </div>
        </div>

        {/* Business Systems */}
        <div style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">
            <IconActivity /> המערכות שלי
          </h3>
          <div className="stats-grid">
            {systemModules.map(module => (
              <div 
                key={module.id}
                className="stat-card"
                style={{ 
                  cursor: 'pointer',
                  transition: 'transform 0.2s',
                  border: '2px solid transparent'
                }}
                onClick={() => handleSystemAccess(module.id, module.name)}
                onMouseOver={(e) => {
                  e.target.style.transform = 'translateY(-4px)';
                  e.target.style.borderColor = '#667eea';
                }}
                onMouseOut={(e) => {
                  e.target.style.transform = 'translateY(0)';
                  e.target.style.borderColor = 'transparent';
                }}
              >
                <div style={{ 
                  fontSize: '2rem', 
                  marginBottom: '1rem',
                  display: 'flex',
                  justifyContent: 'center'
                }}>
                  <module.icon />
                </div>
                <h4 style={{ 
                  fontSize: '1.1rem', 
                  marginBottom: '0.5rem',
                  color: '#2d3748'
                }}>
                  {module.name}
                </h4>
                <p style={{ 
                  fontSize: '0.9rem', 
                  color: '#718096',
                  marginBottom: '1rem'
                }}>
                  {module.businessDescription}
                </p>
                <div style={{ 
                  fontSize: '0.8rem',
                  color: '#667eea',
                  fontWeight: 'bold'
                }}>
                  {module.stats}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Customers */}
        <div>
          <h3 className="section-title">
            <IconUsers /> הלקוחות האחרונים שלי
          </h3>
          <div className="content-card">
            <table className="table">
              <thead>
                <tr>
                  <th>הערות</th>
                  <th>תאריך יצירה</th>
                  <th>מקור</th>
                  <th>סטטוס</th>
                  <th>אימייל</th>
                  <th>טלפון</th>
                  <th>שם</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>לקוח פוטנציאלי</td>
                  <td>2025-08-11</td>
                  <td>שיחה</td>
                  <td><span className="status-active">● פעיל</span></td>
                  <td>yossi@example.com</td>
                  <td>+972-50-123-4567</td>
                  <td>יוסי כהן</td>
                </tr>
                <tr>
                  <td>מעוניינת במשרד</td>
                  <td>2025-08-11</td>
                  <td>WhatsApp</td>
                  <td><span className="status-active">● פעיל</span></td>
                  <td>rachel@example.com</td>
                  <td>+972-52-987-6543</td>
                  <td>רחל לוי</td>
                </tr>
                <tr>
                  <td>השקעה בנדלן</td>
                  <td>2025-08-11</td>
                  <td>אתר</td>
                  <td><span className="status-active">● פעיל</span></td>
                  <td>david@example.com</td>
                  <td>+972-54-555-1234</td>
                  <td>דוד שטרן</td>
                </tr>
                <tr>
                  <td>נדלן מסחרי</td>
                  <td>2025-08-11</td>
                  <td>הפניה</td>
                  <td><span className="status-active">● פעיל</span></td>
                  <td>miri@example.com</td>
                  <td>+972-53-777-8888</td>
                  <td>מירי אברהם</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default BusinessDashboard;