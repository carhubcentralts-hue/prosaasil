import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

// Simple icons without lucide-react dependency
const IconShield = () => <span>🛡️</span>;
const IconLogOut = () => <span>⇐</span>;
const IconPhone = () => <span>📞</span>;
const IconMessage = () => <span>💬</span>;
const IconUsers = () => <span>👥</span>;
const IconBuilding = () => <span>🏢</span>;
const IconSettings = () => <span>⚙️</span>;
const IconActivity = () => <span>📊</span>;
const IconChart = () => <span>📈</span>;
const IconCrown = () => <span>👑</span>;
const IconEye = () => <span>👁️</span>;
const IconUserCheck = () => <span>✅</span>;

const AdminDashboard = () => {
  const { user, logout } = useAuth();
  const [stats, setStats] = useState({});

  useEffect(() => {
    // Load admin stats
    loadAdminData();
  }, []);

  const loadAdminData = async () => {
    try {
      const response = await fetch('/api/admin/stats', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to load admin data:', error);
    }
  };

  const businesses = [
    {
      id: 1,
      name: 'שי דירות ומשרדים בע״מ',
      type: 'נדל"ן ותיווך',
      phone: '+972-3-555-7777',
      whatsapp: '+1-555-123-4567',
      status: 'פעיל',
      totalCalls: 127,
      totalContacts: 45,
      lastActivity: 'פעיל עכשיו'
    }
  ];

  const systemModules = [
    {
      id: 'crm',
      name: 'מערכת CRM',
      icon: IconUsers,
      description: 'ניהול לקוחות ורכישות',
      adminDescription: 'צפייה בכל הלקוחות של כל העסקים',
      color: 'background: linear-gradient(135deg, #3b82f6, #1d4ed8)',
      stats: 'כל הלקוחות: 1,247'
    },
    {
      id: 'calls',
      name: 'מערכת שיחות',
      icon: IconPhone,
      description: 'ניהול שיחות וטלפוניה',
      adminDescription: 'צפייה בכל השיחות של כל העסקים',
      color: 'background: linear-gradient(135deg, #10b981, #059669)',
      stats: 'כל השיחות: 3,891'
    },
    {
      id: 'whatsapp',
      name: 'מערכת WhatsApp',
      icon: IconMessage,
      description: 'ניהול הודעות WhatsApp',
      adminDescription: 'צפייה בכל הודעות WhatsApp של כל העסקים',
      color: 'background: linear-gradient(135deg, #8b5cf6, #7c3aed)',
      stats: 'כל ההודעות: 892'
    },
    {
      id: 'admin',
      name: 'ניהול מערכת',
      icon: IconSettings,
      description: 'הגדרות ותצורת מערכת',
      adminDescription: 'ניהול עסקים, משתמשים ותצורות',
      color: 'background: linear-gradient(135deg, #f59e0b, #d97706)',
      stats: 'עסקים פעילים: 1'
    }
  ];

  const handleSystemAccess = (systemId, systemName) => {
    alert(`כניסה למערכת ${systemName} - תצוגת מנהל\nרואה את כל הנתונים של כל העסקים`);
  };

  const handleLogout = () => {
    logout();
  };

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="dashboard-title">
          <IconCrown /> מנהל מערכת - AgentLocator CRM
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontWeight: 'bold' }}>
              {user?.name || 'מנהל מערכת'}
            </div>
            <div style={{ fontSize: '0.8rem', opacity: 0.8 }}>
              רמת הרשאה: מנהל כללי
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
          <IconCrown style={{ fontSize: '3rem', marginBottom: '1rem' }} />
          <h2 style={{ fontSize: '1.5rem', marginBottom: '0.5rem' }}>
            ברוכים הבאים למערכת הניהול הכללית
          </h2>
          <p style={{ opacity: 0.9 }}>
            אתם רואים ומנהלים את כל הנתונים של כל העסקים במערכת
          </p>
        </div>

        {/* Business Overview */}
        <div style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">
            <IconBuilding /> עסקים במערכת
          </h3>
          <div className="content-card">
            <table className="table">
              <thead>
                <tr>
                  <th>סטטוס</th>
                  <th>פעילות אחרונה</th>
                  <th>לקוחות</th>
                  <th>שיחות</th>
                  <th>WhatsApp</th>
                  <th>טלפון</th>
                  <th>סוג</th>
                  <th>שם עסק</th>
                </tr>
              </thead>
              <tbody>
                {businesses.map(business => (
                  <tr key={business.id}>
                    <td>
                      <span className="status-active">● {business.status}</span>
                    </td>
                    <td>{business.lastActivity}</td>
                    <td>{business.totalContacts}</td>
                    <td>{business.totalCalls}</td>
                    <td>{business.whatsapp}</td>
                    <td>{business.phone}</td>
                    <td>{business.type}</td>
                    <td style={{ fontWeight: 'bold' }}>{business.name}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* System Stats */}
        <div style={{ marginBottom: '2rem' }}>
          <h3 className="section-title">
            <IconChart /> סטטיסטיקות המערכת
          </h3>
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-number">1</div>
              <div className="stat-label">עסקים פעילים</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">127</div>
              <div className="stat-label">סה״כ שיחות</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">45</div>
              <div className="stat-label">סה״כ לקוחות</div>
            </div>
            <div className="stat-card">
              <div className="stat-number">23</div>
              <div className="stat-label">הודעות WhatsApp</div>
            </div>
          </div>
        </div>

        {/* System Modules */}
        <div>
          <h3 className="section-title">
            <IconSettings /> מודולי המערכת
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
                  {module.adminDescription}
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
      </div>
    </div>
  );
};

export default AdminDashboard;