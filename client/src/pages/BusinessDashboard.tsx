import React, { useState } from 'react';

interface User {
  username: string;
  name: string;
  role: 'admin' | 'business';
}

interface BusinessDashboardProps {
  user: User;
  onLogout: () => void;
}

export default function BusinessDashboard({ user, onLogout }: BusinessDashboardProps) {
  const [activeModule, setActiveModule] = useState('dashboard');

  const modules = [
    { id: 'dashboard', name: 'לוח בקרה', icon: '📊' },
    { id: 'customers', name: 'ניהול לקוחות', icon: '👥' },
    { id: 'calls', name: 'מרכז שיחות', icon: '📞' },
    { id: 'whatsapp', name: 'WhatsApp Business', icon: '💬' },
    { id: 'appointments', name: 'פגישות', icon: '📅' },
    { id: 'reports', name: 'דוחות', icon: '📈' }
  ];

  const renderContent = () => {
    switch (activeModule) {
      case 'dashboard':
        return (
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '1.5rem', color: '#2d3748' }}>
              לוח בקרה - שי דירות ומשרדים בע״מ
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
                <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem' }}>לקוחות פעילים</h3>
                <p style={{ fontSize: '2rem', fontWeight: '700' }}>4</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.9 }}>יוסי, רחל, דוד, מירי</p>
              </div>
              <div style={{
                background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                color: 'white',
                padding: '1.5rem',
                borderRadius: '16px'
              }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem' }}>שיחות היום</h3>
                <p style={{ fontSize: '2rem', fontWeight: '700' }}>3</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.9 }}>כולן הושלמו בהצלחה</p>
              </div>
              <div style={{
                background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                color: 'white',
                padding: '1.5rem',
                borderRadius: '16px'
              }}>
                <h3 style={{ fontSize: '1.2rem', fontWeight: '600', marginBottom: '0.5rem' }}>WhatsApp</h3>
                <p style={{ fontSize: '2rem', fontWeight: '700' }}>3</p>
                <p style={{ fontSize: '0.9rem', opacity: 0.9 }}>שיחות פעילות</p>
              </div>
            </div>

            <div style={{
              background: 'white',
              padding: '1.5rem',
              borderRadius: '16px',
              border: '1px solid #e2e8f0',
              marginBottom: '1.5rem'
            }}>
              <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem', color: '#2d3748' }}>
                פעילות אחרונה
              </h3>
              <div style={{ display: 'grid', gap: '1rem' }}>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.75rem',
                  background: '#f7fafc',
                  borderRadius: '8px'
                }}>
                  <div>
                    <span style={{ fontWeight: '600' }}>📞 שיחה מיוסי כהן</span>
                    <div style={{ fontSize: '0.8rem', color: '#718096' }}>מחפש דירה בתל אביב</div>
                  </div>
                  <span style={{ fontSize: '0.8rem', color: '#718096' }}>10:30</span>
                </div>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.75rem',
                  background: '#f7fafc',
                  borderRadius: '8px'
                }}>
                  <div>
                    <span style={{ fontWeight: '600' }}>💬 הודעה מרחל לוי</span>
                    <div style={{ fontSize: '0.8rem', color: '#718096' }}>מתי אפשר לתאם צפייה במשרד?</div>
                  </div>
                  <span style={{ fontSize: '0.8rem', color: '#718096' }}>18:45</span>
                </div>
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '0.75rem',
                  background: '#f7fafc',
                  borderRadius: '8px'
                }}>
                  <div>
                    <span style={{ fontWeight: '600' }}>📞 שיחה מדוד שטרן</span>
                    <div style={{ fontSize: '0.8rem', color: '#718096' }}>מחפש נכס יוקרתי עם נוף לים</div>
                  </div>
                  <span style={{ fontSize: '0.8rem', color: '#718096' }}>15:20</span>
                </div>
              </div>
            </div>

            <div style={{
              background: 'white',
              padding: '1.5rem',
              borderRadius: '16px',
              border: '1px solid #e2e8f0'
            }}>
              <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem', color: '#2d3748' }}>
                מידע עסק
              </h3>
              <div style={{ display: 'grid', gap: '0.5rem', fontSize: '0.95rem' }}>
                <div><strong>שם העסק:</strong> שי דירות ומשרדים בע״מ</div>
                <div><strong>תחום:</strong> נדלן ותיווך</div>
                <div><strong>טלפון ישראלי:</strong> +972-3-555-7777</div>
                <div><strong>WhatsApp אמריקאי:</strong> +1-555-123-4567</div>
                <div><strong>סטטוס AI:</strong> <span style={{ color: '#38a169' }}>פעיל ומוכן לקבלת שיחות</span></div>
              </div>
            </div>
          </div>
        );
      
      case 'customers':
        return (
          <div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: '700', marginBottom: '1.5rem', color: '#2d3748' }}>
              ניהול לקוחות
            </h2>
            <div style={{
              background: 'white',
              padding: '1.5rem',
              borderRadius: '16px',
              border: '1px solid #e2e8f0'
            }}>
              <div style={{ display: 'grid', gap: '1rem' }}>
                {[
                  { name: 'יוסי כהן', phone: '+972-50-123-4567', status: 'פעיל', source: 'שיחה' },
                  { name: 'רחל לוי', phone: '+972-52-987-6543', status: 'פעיל', source: 'WhatsApp' },
                  { name: 'דוד שטרן', phone: '+972-54-555-1234', status: 'פעיל', source: 'אתר' },
                  { name: 'מירי אברהם', phone: '+972-53-777-8888', status: 'פעיל', source: 'הפניה' }
                ].map((customer, index) => (
                  <div key={index} style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '1rem',
                    background: '#f7fafc',
                    borderRadius: '12px'
                  }}>
                    <div>
                      <div style={{ fontWeight: '600', color: '#2d3748' }}>{customer.name}</div>
                      <div style={{ fontSize: '0.9rem', color: '#718096' }}>{customer.phone}</div>
                    </div>
                    <div style={{ textAlign: 'left' }}>
                      <div style={{
                        background: '#c6f6d5',
                        color: '#2f855a',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '20px',
                        fontSize: '0.8rem',
                        fontWeight: '600',
                        marginBottom: '0.25rem'
                      }}>
                        {customer.status}
                      </div>
                      <div style={{ fontSize: '0.8rem', color: '#718096' }}>מקור: {customer.source}</div>
                    </div>
                  </div>
                ))}
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
              AgentLocator CRM - שי דירות ומשרדים
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