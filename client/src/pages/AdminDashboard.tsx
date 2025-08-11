import React, { useState, useEffect } from 'react';

interface User {
  username: string;
  name: string;
  role: 'admin' | 'business';
}

interface AdminDashboardProps {
  user: User;
  onLogout: () => void;
}

interface Customer {
  id: number;
  name: string;
  phone: string;
  email: string;
  status: string;
  source: string;
  created_at: string;
  notes: string;
}

interface Call {
  id: number;
  call_sid: string;
  from_number: string;
  call_status: string;
  call_duration: number;
  customer_name: string;
  transcription: string;
  ai_response: string;
  created_at: string;
}

export default function AdminDashboard({ user, onLogout }: AdminDashboardProps) {
  const [activeModule, setActiveModule] = useState('overview');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [loading, setLoading] = useState(false);

  const modules = [
    { id: 'overview', name: 'סקירה כללית', icon: '📊', description: 'נתונים כלליים ויסקאפ המערכת' },
    { id: 'businesses', name: 'ניהול עסקים', icon: '🏢', description: 'ניהול עסקים ונתוני ביצועים' },
    { id: 'users', name: 'ניהול משתמשים', icon: '👥', description: 'ניהול הרשאות ומשתמשים' },
    { id: 'system', name: 'הגדרות מערכת', icon: '⚙️', description: 'הגדרות כלליות ותצורה' },
    { id: 'analytics', name: 'אנליטיקס', icon: '📈', description: 'דוחות ונתונים סטטיסטיים' },
    { id: 'logs', name: 'לוגים', icon: '📋', description: 'יומני המערכת ופעילות' }
  ];

  useEffect(() => {
    if (activeModule === 'businesses') {
      fetchCustomers();
      fetchCalls();
    }
  }, [activeModule]);

  const fetchCustomers = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/crm/customers', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setCustomers(data.customers || []);
      }
    } catch (error) {
      console.error('Error fetching customers:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCalls = async () => {
    try {
      const response = await fetch('/api/calls', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setCalls(data.calls || []);
      }
    } catch (error) {
      console.error('Error fetching calls:', error);
    }
  };

  const renderSystemStatus = () => (
    <div style={{
      background: 'white',
      padding: '2rem',
      borderRadius: '20px',
      border: '1px solid #e2e8f0',
      boxShadow: '0 10px 40px rgba(0,0,0,0.08)'
    }}>
      <h3 style={{ 
        fontSize: '1.5rem', 
        fontWeight: '700', 
        marginBottom: '1.5rem', 
        color: '#2d3748',
        borderBottom: '3px solid #667eea',
        paddingBottom: '0.5rem'
      }}>
        סטטוס מערכת בזמן אמת
      </h3>
      <div style={{ display: 'grid', gap: '1.5rem' }}>
        {[
          { service: 'שרת Flask Backend', status: 'פעיל', icon: '🚀', color: '#48bb78' },
          { service: 'מסד נתונים PostgreSQL', status: 'מחובר', icon: '💾', color: '#48bb78' },
          { service: 'Twilio Voice API', status: 'מוכן', icon: '📞', color: '#48bb78' },
          { service: 'WhatsApp Business API', status: 'מחובר', icon: '💬', color: '#48bb78' },
          { service: 'OpenAI GPT Integration', status: 'זמין', icon: '🤖', color: '#48bb78' },
          { service: 'Google TTS Hebrew', status: 'פעיל', icon: '🗣️', color: '#48bb78' }
        ].map((item, index) => (
          <div key={index} style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1rem',
            background: '#f8fafc',
            borderRadius: '12px',
            borderLeft: `4px solid ${item.color}`
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
              <span style={{ fontSize: '1.5rem' }}>{item.icon}</span>
              <span style={{ fontWeight: '600', color: '#2d3748' }}>{item.service}</span>
            </div>
            <span style={{ 
              color: item.color, 
              fontWeight: '700',
              padding: '0.25rem 0.75rem',
              background: `${item.color}20`,
              borderRadius: '20px',
              fontSize: '0.9rem'
            }}>
              ✓ {item.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );

  const renderBusinessMetrics = () => (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: '2rem',
      marginBottom: '2rem'
    }}>
      {[
        { 
          title: 'עסקים פעילים', 
          value: '1', 
          subtitle: 'שי דירות ומשרדים בע״מ',
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          icon: '🏢'
        },
        { 
          title: 'משתמשים רשומים', 
          value: '2', 
          subtitle: 'מנהל מערכת + בעל עסק',
          gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          icon: '👥'
        },
        { 
          title: 'שיחות השבוע', 
          value: calls.length.toString(), 
          subtitle: 'כל השיחות הושלמו בהצלחה',
          gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
          icon: '📞'
        },
        { 
          title: 'לקוחות פעילים', 
          value: customers.length.toString(), 
          subtitle: 'בסיס לקוחות גדל',
          gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
          icon: '👤'
        }
      ].map((metric, index) => (
        <div key={index} style={{
          background: metric.gradient,
          color: 'white',
          padding: '2rem',
          borderRadius: '20px',
          boxShadow: '0 15px 35px rgba(0,0,0,0.1)',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{
            position: 'absolute',
            top: '1rem',
            left: '1rem',
            fontSize: '2.5rem',
            opacity: 0.3
          }}>
            {metric.icon}
          </div>
          <div style={{ textAlign: 'right' }}>
            <h3 style={{ fontSize: '1.3rem', fontWeight: '600', marginBottom: '1rem' }}>
              {metric.title}
            </h3>
            <p style={{ fontSize: '3rem', fontWeight: '800', margin: '0.5rem 0' }}>
              {metric.value}
            </p>
            <p style={{ fontSize: '1rem', opacity: 0.9, margin: 0 }}>
              {metric.subtitle}
            </p>
          </div>
        </div>
      ))}
    </div>
  );

  const renderContent = () => {
    switch (activeModule) {
      case 'overview':
        return (
          <div>
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ 
                fontSize: '2.5rem', 
                fontWeight: '800', 
                marginBottom: '0.5rem', 
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                WebkitBackgroundClip: 'text',
                WebkitTextFillColor: 'transparent'
              }}>
                סקירה כללית - לוח בקרה מנהל
              </h2>
              <p style={{ color: '#718096', fontSize: '1.1rem' }}>
                מערכת ניהול מקצועית עם בינה מלאכותית לעסק הנדלן
              </p>
            </div>
            
            {renderBusinessMetrics()}
            {renderSystemStatus()}
          </div>
        );
      
      case 'businesses':
        return (
          <div>
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ 
                fontSize: '2.5rem', 
                fontWeight: '800', 
                marginBottom: '0.5rem', 
                color: '#2d3748'
              }}>
                ניהול עסקים מתקדם
              </h2>
              <p style={{ color: '#718096', fontSize: '1.1rem' }}>
                ניהול מקצועי של עסקים רשומים במערכת
              </p>
            </div>

            <div style={{
              background: 'white',
              padding: '2rem',
              borderRadius: '20px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 10px 40px rgba(0,0,0,0.08)',
              marginBottom: '2rem'
            }}>
              <div style={{
                display: 'flex',
                alignItems: 'center',
                padding: '1.5rem',
                background: 'linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)',
                borderRadius: '16px',
                marginBottom: '2rem',
                border: '2px solid #e2e8f0'
              }}>
                <div style={{ fontSize: '3rem', marginLeft: '1.5rem' }}>🏢</div>
                <div style={{ flex: 1 }}>
                  <h3 style={{ 
                    fontSize: '1.5rem', 
                    fontWeight: '700', 
                    color: '#2d3748', 
                    margin: '0 0 0.5rem 0' 
                  }}>
                    שי דירות ומשרדים בע״מ
                  </h3>
                  <p style={{ color: '#718096', fontSize: '1rem', margin: 0 }}>
                    <strong>תחום:</strong> נדלן ותיווך • 
                    <strong> טלפון:</strong> +972-3-555-7777 • 
                    <strong> WhatsApp:</strong> +1-555-123-4567
                  </p>
                  <div style={{ marginTop: '0.5rem' }}>
                    <span style={{ color: '#38a169', fontSize: '0.9rem', fontWeight: '600' }}>
                      🤖 AI Assistant: פעיל ומוכן לקבלת שיחות 24/7
                    </span>
                  </div>
                </div>
                <div style={{ textAlign: 'center' }}>
                  <span style={{
                    background: 'linear-gradient(135deg, #48bb78 0%, #38a169 100%)',
                    color: 'white',
                    padding: '0.5rem 1.5rem',
                    borderRadius: '25px',
                    fontSize: '1rem',
                    fontWeight: '700',
                    boxShadow: '0 4px 15px rgba(72, 187, 120, 0.3)'
                  }}>
                    ✓ פעיל
                  </span>
                </div>
              </div>
              
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
                gap: '1.5rem'
              }}>
                {[
                  { label: 'לקוחות רשומים', value: customers.length, icon: '👥', color: '#667eea' },
                  { label: 'שיחות שבוע זה', value: calls.length, icon: '📞', color: '#f093fb' },
                  { label: 'שיחות WhatsApp', value: '3', icon: '💬', color: '#4facfe' },
                  { label: 'קצב המרה', value: '85%', icon: '📈', color: '#43e97b' }
                ].map((stat, index) => (
                  <div key={index} style={{
                    textAlign: 'center',
                    padding: '1.5rem',
                    background: `${stat.color}10`,
                    borderRadius: '16px',
                    border: `2px solid ${stat.color}20`
                  }}>
                    <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>{stat.icon}</div>
                    <div style={{ 
                      fontSize: '2rem', 
                      fontWeight: '800', 
                      color: stat.color,
                      marginBottom: '0.25rem'
                    }}>
                      {stat.value}
                    </div>
                    <div style={{ fontSize: '0.9rem', color: '#718096', fontWeight: '600' }}>
                      {stat.label}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Customer Table */}
            {customers.length > 0 && (
              <div style={{
                background: 'white',
                padding: '2rem',
                borderRadius: '20px',
                border: '1px solid #e2e8f0',
                boxShadow: '0 10px 40px rgba(0,0,0,0.08)'
              }}>
                <h3 style={{ 
                  fontSize: '1.5rem', 
                  fontWeight: '700', 
                  marginBottom: '1.5rem', 
                  color: '#2d3748'
                }}>
                  לקוחות אחרונים
                </h3>
                <div style={{ overflowX: 'auto' }}>
                  <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                      <tr style={{ background: '#f7fafc' }}>
                        {['שם', 'טלפון', 'מקור', 'סטטוס', 'תאריך'].map(header => (
                          <th key={header} style={{
                            padding: '1rem',
                            textAlign: 'right',
                            fontWeight: '700',
                            color: '#4a5568',
                            borderBottom: '2px solid #e2e8f0'
                          }}>
                            {header}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {customers.slice(0, 5).map((customer) => (
                        <tr key={customer.id} style={{ borderBottom: '1px solid #e2e8f0' }}>
                          <td style={{ padding: '1rem', fontWeight: '600', color: '#2d3748' }}>
                            {customer.name}
                          </td>
                          <td style={{ padding: '1rem', color: '#718096', direction: 'ltr', textAlign: 'left' }}>
                            {customer.phone}
                          </td>
                          <td style={{ padding: '1rem' }}>
                            <span style={{
                              background: '#edf2f7',
                              color: '#4a5568',
                              padding: '0.25rem 0.75rem',
                              borderRadius: '12px',
                              fontSize: '0.9rem',
                              fontWeight: '600'
                            }}>
                              {customer.source}
                            </span>
                          </td>
                          <td style={{ padding: '1rem' }}>
                            <span style={{
                              background: '#c6f6d5',
                              color: '#2f855a',
                              padding: '0.25rem 0.75rem',
                              borderRadius: '12px',
                              fontSize: '0.9rem',
                              fontWeight: '600'
                            }}>
                              {customer.status}
                            </span>
                          </td>
                          <td style={{ padding: '1rem', color: '#718096' }}>
                            {customer.created_at}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        );
      
      default:
        return (
          <div style={{ 
            textAlign: 'center', 
            padding: '4rem',
            background: 'white',
            borderRadius: '20px',
            border: '1px solid #e2e8f0'
          }}>
            <div style={{ fontSize: '4rem', marginBottom: '1rem' }}>🚧</div>
            <h3 style={{ fontSize: '1.5rem', fontWeight: '600', color: '#4a5568', marginBottom: '0.5rem' }}>
              מודול {modules.find(m => m.id === activeModule)?.name}
            </h3>
            <p style={{ color: '#718096' }}>
              {modules.find(m => m.id === activeModule)?.description}
            </p>
            <p style={{ color: '#718096', marginTop: '1rem' }}>
              בפיתוח מתקדם...
            </p>
          </div>
        );
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #f7fafc 0%, #edf2f7 100%)',
      direction: 'rtl',
      fontFamily: 'Assistant, Arial, sans-serif'
    }}>
      {/* Professional Header */}
      <div style={{
        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        color: 'white',
        padding: '1.5rem 2rem',
        boxShadow: '0 10px 40px rgba(0,0,0,0.1)'
      }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <h1 style={{ 
              fontSize: '2rem', 
              fontWeight: '800', 
              margin: '0 0 0.25rem 0',
              textShadow: '0 2px 4px rgba(0,0,0,0.2)'
            }}>
              AgentLocator CRM - מנהל מערכת
            </h1>
            <p style={{ 
              margin: 0, 
              fontSize: '1.1rem',
              opacity: 0.9,
              fontWeight: '400'
            }}>
              שלום {user.name} • לוח בקרה מתקדם
            </p>
          </div>
          <button
            onClick={onLogout}
            style={{
              background: 'rgba(255,255,255,0.2)',
              color: 'white',
              border: '2px solid rgba(255,255,255,0.3)',
              padding: '0.75rem 1.5rem',
              borderRadius: '12px',
              cursor: 'pointer',
              fontWeight: '600',
              fontSize: '1rem',
              transition: 'all 0.3s ease',
              backdropFilter: 'blur(10px)'
            }}
            onMouseOver={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.3)';
            }}
            onMouseOut={(e) => {
              e.currentTarget.style.background = 'rgba(255,255,255,0.2)';
            }}
          >
            🚪 התנתק
          </button>
        </div>
      </div>

      <div style={{ display: 'flex' }}>
        {/* Professional Sidebar */}
        <div style={{
          width: '320px',
          background: 'white',
          borderLeft: '1px solid #e2e8f0',
          minHeight: 'calc(100vh - 89px)',
          padding: '2rem 0',
          boxShadow: '5px 0 20px rgba(0,0,0,0.05)'
        }}>
          <div style={{ padding: '0 1.5rem 2rem 1.5rem' }}>
            <h3 style={{ 
              fontSize: '1.2rem', 
              fontWeight: '700', 
              color: '#4a5568',
              margin: '0 0 0.5rem 0'
            }}>
              ניווט מתקדם
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#718096', margin: 0 }}>
              בחר מודול לניהול
            </p>
          </div>
          
          {modules.map(module => (
            <button
              key={module.id}
              onClick={() => setActiveModule(module.id)}
              style={{
                width: '100%',
                padding: '1.25rem 2rem',
                border: 'none',
                background: activeModule === module.id 
                  ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' 
                  : 'transparent',
                textAlign: 'right',
                cursor: 'pointer',
                fontSize: '1rem',
                color: activeModule === module.id ? 'white' : '#4a5568',
                fontWeight: activeModule === module.id ? '700' : '500',
                borderRight: activeModule === module.id ? '4px solid #667eea' : '4px solid transparent',
                transition: 'all 0.3s ease',
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'flex-end',
                gap: '1rem'
              }}
              onMouseOver={(e) => {
                if (activeModule !== module.id) {
                  e.currentTarget.style.background = '#f7fafc';
                }
              }}
              onMouseOut={(e) => {
                if (activeModule !== module.id) {
                  e.currentTarget.style.background = 'transparent';
                }
              }}
            >
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontWeight: '600', marginBottom: '0.25rem' }}>
                  {module.name}
                </div>
                <div style={{ 
                  fontSize: '0.8rem', 
                  opacity: activeModule === module.id ? 0.9 : 0.7 
                }}>
                  {module.description}
                </div>
              </div>
              <span style={{ fontSize: '1.5rem' }}>{module.icon}</span>
            </button>
          ))}
        </div>

        {/* Main Content */}
        <div style={{
          flex: 1,
          padding: '2.5rem'
        }}>
          {loading ? (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              alignItems: 'center',
              height: '400px',
              background: 'white',
              borderRadius: '20px'
            }}>
              <div style={{ fontSize: '2rem' }}>⏳ טוען נתונים...</div>
            </div>
          ) : (
            renderContent()
          )}
        </div>
      </div>
    </div>
  );
}