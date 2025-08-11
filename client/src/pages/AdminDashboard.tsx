import React, { useState } from 'react';

interface User {
  username: string;
  name: string;
  role: 'admin' | 'business';
}

interface AdminDashboardProps {
  user: User;
  onLogout: () => void;
}

export default function AdminDashboard({ user, onLogout }: AdminDashboardProps) {
  const [activeModule, setActiveModule] = useState('overview');

  const modules = [
    { id: 'overview', name: 'סקירה כללית', icon: '📊' },
    { id: 'businesses', name: 'ניהול עסקים', icon: '🏢' },
    { id: 'users', name: 'ניהול משתמשים', icon: '👥' },
    { id: 'system', name: 'הגדרות מערכת', icon: '⚙️' },
    { id: 'analytics', name: 'אנליטיקס', icon: '📈' },
    { id: 'logs', name: 'לוגים', icon: '📋' }
  ];

  const renderContent = () => {
    switch (activeModule) {
      case 'overview':
        return (
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '1.5rem', color: '#2d3748' }}>
              סקירה כללית - מנהל מערכת
            </h2>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
              gap: '1.5rem',
              marginBottom: '2rem'
            }}>
              <div style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                padding: '1.5rem',
                borderRadius: '16px'
              }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem' }}>עסקים פעילים</h3>
                <p style={{ fontSize: '2rem', fontWeight: '700' }}>1</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.9 }}>שי דירות ומשרדים בע״מ</p>
              </div>
              <div style={{
                background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                color: 'white',
                padding: '1.5rem',
                borderRadius: '16px'
              }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem' }}>משתמשים</h3>
                <p style={{ fontSize: '2rem', fontWeight: '700' }}>2</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.9 }}>מנהל + בעל עסק</p>
              </div>
              <div style={{
                background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                color: 'white',
                padding: '1.5rem',
                borderRadius: '16px'
              }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem' }}>שיחות היום</h3>
                <p style={{ fontSize: '2rem', fontWeight: '700' }}>3</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.9 }}>כל השיחות הושלמו בהצלחה</p>
              </div>
            </div>
            
            <div style={{
              background: 'white',
              padding: '1.5rem',
              borderRadius: '16px',
              border: '1px solid #e2e8f0'
            }}>
              <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem', color: '#2d3748' }}>
                סטטוס מערכת
              </h3>
              <div style={{ display: 'grid', gap: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>שרת Flask</span>
                  <span style={{ color: '#38a169', fontWeight: '600' }}>🟢 פעיל</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>מסד נתונים PostgreSQL</span>
                  <span style={{ color: '#38a169', fontWeight: '600' }}>🟢 מחובר</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>Twilio (שיחות)</span>
                  <span style={{ color: '#38a169', fontWeight: '600' }}>🟢 מוכן</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span>WhatsApp Business</span>
                  <span style={{ color: '#38a169', fontWeight: '600' }}>🟢 מחובר</span>
                </div>
              </div>
            </div>
          </div>
        );
      
      case 'businesses':
        return (
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '1.5rem', color: '#2d3748' }}>
              ניהול עסקים
            </h2>
            <div style={{
              background: 'white',
              padding: '1.5rem',
              borderRadius: '16px',
              border: '1px solid #e2e8f0'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                padding: '1rem',
                background: '#f7fafc',
                borderRadius: '12px',
                marginBottom: '1rem'
              }}>
                <div style={{ fontSize: '2rem', marginLeft: '1rem' }}>🏢</div>
                <div style={{ flex: 1 }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: '600', color: '#2d3748', margin: 0 }}>
                    שי דירות ומשרדים בע״מ
                  </h3>
                  <p style={{ color: '#718096', fontSize: '0.9rem', margin: 0 }}>
                    תחום: נדלן ותיווך • טלפון: +972-3-555-7777 • WhatsApp: +1-555-123-4567
                  </p>
                </div>
                <span style={{
                  background: '#c6f6d5',
                  color: '#2f855a',
                  padding: '0.25rem 0.75rem',
                  borderRadius: '20px',
                  fontSize: '0.8rem',
                  fontWeight: '600'
                }}>
                  פעיל
                </span>
              </div>
              
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                gap: '1rem',
                marginTop: '1.5rem'
              }}>
                <div style={{ textAlign: 'center', padding: '1rem' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2d3748' }}>4</div>
                  <div style={{ fontSize: '0.9rem', color: '#718096' }}>לקוחות</div>
                </div>
                <div style={{ textAlign: 'center', padding: '1rem' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2d3748' }}>3</div>
                  <div style={{ fontSize: '0.9rem', color: '#718096' }}>שיחות</div>
                </div>
                <div style={{ textAlign: 'center', padding: '1rem' }}>
                  <div style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2d3748' }}>3</div>
                  <div style={{ fontSize: '0.9rem', color: '#718096' }}>WhatsApp</div>
                </div>
              </div>
            </div>
          </div>
        );
      
      default:
        return (
          <div style={{ textAlign: 'center', padding: '3rem', color: '#718096' }}>
            <h3>מודול {modules.find(m => m.id === activeModule)?.name}</h3>
            <p>בפיתוח...</p>
          </div>
        );
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: '#f7fafc',
      direction: 'rtl',
      fontFamily: 'Assistant, Arial, sans-serif'
    }}>
      {/* Header */}
      <div style={{
        background: 'white',
        borderBottom: '1px solid #e2e8f0',
        padding: '1rem 2rem'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h1 style={{ fontSize: '1.5rem', fontWeight: '700', color: '#2d3748', margin: 0 }}>
              AgentLocator CRM - מנהל מערכת
            </h1>
            <p style={{ color: '#718096', margin: 0, fontSize: '0.9rem' }}>
              שלום {user.name}
            </p>
          </div>
          <button
            onClick={onLogout}
            style={{
              background: '#fed7d7',
              color: '#c53030',
              border: 'none',
              padding: '0.5rem 1rem',
              borderRadius: '8px',
              cursor: 'pointer',
              fontWeight: '600'
            }}
          >
            התנתק
          </button>
        </div>
      </div>

      <div style={{ display: 'flex' }}>
        {/* Sidebar */}
        <div style={{
          width: '280px',
          background: 'white',
          borderLeft: '1px solid #e2e8f0',
          minHeight: 'calc(100vh - 73px)',
          padding: '2rem 0'
        }}>
          {modules.map(module => (
            <button
              key={module.id}
              onClick={() => setActiveModule(module.id)}
              style={{
                width: '100%',
                padding: '1rem 2rem',
                border: 'none',
                background: activeModule === module.id ? '#edf2f7' : 'transparent',
                textAlign: 'right',
                cursor: 'pointer',
                fontSize: '1rem',
                color: activeModule === module.id ? '#2d3748' : '#718096',
                fontWeight: activeModule === module.id ? '600' : '400',
                borderRight: activeModule === module.id ? '3px solid #667eea' : '3px solid transparent',
                transition: 'all 0.2s ease'
              }}
            >
              <span style={{ marginLeft: '0.75rem' }}>{module.icon}</span>
              {module.name}
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div style={{
          flex: 1,
          padding: '2rem'
        }}>
          {renderContent()}
        </div>
      </div>
    </div>
  );
}