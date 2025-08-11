import React, { useState, useEffect } from 'react';

interface User {
  username: string;
  name: string;
  role: 'admin' | 'business';
}

interface BusinessDashboardProps {
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

interface WhatsAppConversation {
  id: string;
  contact: string;
  name: string;
  last_message: string;
  timestamp: string;
  unread: boolean;
  message_count: number;
}

export default function BusinessDashboard({ user, onLogout }: BusinessDashboardProps) {
  const [activeModule, setActiveModule] = useState('dashboard');
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [calls, setCalls] = useState<Call[]>([]);
  const [whatsappConversations, setWhatsappConversations] = useState<WhatsAppConversation[]>([]);
  const [loading, setLoading] = useState(false);

  const modules = [
    { id: 'dashboard', name: 'לוח בקרה', icon: '📊', description: 'סקירה כללית ופעילות' },
    { id: 'customers', name: 'ניהול לקוחות', icon: '👥', description: 'בסיס הלקוחות שלך' },
    { id: 'calls', name: 'מרכז שיחות', icon: '📞', description: 'ניהול שיחות נכנסות' },
    { id: 'whatsapp', name: 'WhatsApp Business', icon: '💬', description: 'שיחות ועסקה' },
    { id: 'appointments', name: 'פגישות', icon: '📅', description: 'ניהול לוח זמנים' },
    { id: 'reports', name: 'דוחות', icon: '📈', description: 'אנליטיקס ותובנות' }
  ];

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      await Promise.all([
        fetchCustomers(),
        fetchCalls(),
        fetchWhatsappConversations()
      ]);
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchCustomers = async () => {
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

  const fetchWhatsappConversations = async () => {
    try {
      const response = await fetch('/api/whatsapp/conversations', {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setWhatsappConversations(data.conversations || []);
      }
    } catch (error) {
      console.error('Error fetching WhatsApp conversations:', error);
    }
  };

  const renderBusinessMetrics = () => (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
      gap: '2rem',
      marginBottom: '3rem'
    }}>
      {[
        { 
          title: 'לקוחות פעילים', 
          value: customers.length.toString(), 
          subtitle: customers.slice(0, 3).map(c => c.name.split(' ')[0]).join(', '),
          gradient: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
          icon: '👥',
          trend: '+12%'
        },
        { 
          title: 'שיחות השבוע', 
          value: calls.length.toString(), 
          subtitle: 'כולן הושלמו בהצלחה',
          gradient: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
          icon: '📞',
          trend: '+8%'
        },
        { 
          title: 'WhatsApp פעיל', 
          value: whatsappConversations.length.toString(), 
          subtitle: 'שיחות פתוחות',
          gradient: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
          icon: '💬',
          trend: '+15%'
        },
        { 
          title: 'קצב המרה', 
          value: '85%', 
          subtitle: 'מפניות להזמנות',
          gradient: 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
          icon: '📈',
          trend: '+5%'
        }
      ].map((metric, index) => (
        <div key={index} style={{
          background: metric.gradient,
          color: 'white',
          padding: '2rem',
          borderRadius: '20px',
          boxShadow: '0 15px 35px rgba(0,0,0,0.15)',
          position: 'relative',
          overflow: 'hidden',
          border: '1px solid rgba(255,255,255,0.2)'
        }}>
          <div style={{
            position: 'absolute',
            top: '1rem',
            left: '1rem',
            fontSize: '3rem',
            opacity: 0.2
          }}>
            {metric.icon}
          </div>
          <div style={{ textAlign: 'right', position: 'relative', zIndex: 1 }}>
            <div style={{ 
              display: 'flex', 
              justifyContent: 'space-between', 
              alignItems: 'flex-start',
              marginBottom: '0.5rem'
            }}>
              <span style={{
                background: 'rgba(255,255,255,0.2)',
                padding: '0.25rem 0.75rem',
                borderRadius: '20px',
                fontSize: '0.8rem',
                fontWeight: '600'
              }}>
                {metric.trend}
              </span>
              <h3 style={{ fontSize: '1.3rem', fontWeight: '600', margin: 0 }}>
                {metric.title}
              </h3>
            </div>
            <p style={{ fontSize: '3.5rem', fontWeight: '900', margin: '1rem 0 0.5rem 0', lineHeight: 1 }}>
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

  const renderRecentActivity = () => (
    <div style={{
      background: 'white',
      padding: '2rem',
      borderRadius: '20px',
      border: '1px solid #e2e8f0',
      boxShadow: '0 10px 40px rgba(0,0,0,0.08)',
      marginBottom: '2rem'
    }}>
      <h3 style={{ 
        fontSize: '1.5rem', 
        fontWeight: '700', 
        marginBottom: '1.5rem', 
        color: '#2d3748',
        borderBottom: '3px solid #667eea',
        paddingBottom: '0.5rem'
      }}>
        פעילות אחרונה
      </h3>
      <div style={{ display: 'grid', gap: '1rem' }}>
        {[
          {
            type: 'call',
            icon: '📞',
            title: 'שיחה מיוסי כהן',
            description: 'מחפש דירה בתל אביב, 3 חדרים',
            time: '10:30',
            color: '#667eea'
          },
          {
            type: 'whatsapp',
            icon: '💬',
            title: 'הודעה מרחל לוי',
            description: 'מתי אפשר לתאם צפייה במשרד?',
            time: '18:45',
            color: '#25d366'
          },
          {
            type: 'call',
            icon: '📞',
            title: 'שיחה מדוד שטרן',
            description: 'מחפש נכס יוקרתי עם נוף לים',
            time: '15:20',
            color: '#667eea'
          },
          {
            type: 'appointment',
            icon: '📅',
            title: 'פגישה נקבעה',
            description: 'עם מירי אברהם - סיור במשרדים',
            time: 'מחר 14:00',
            color: '#f093fb'
          }
        ].map((activity, index) => (
          <div key={index} style={{
            display: 'flex',
            alignItems: 'center',
            padding: '1.5rem',
            background: '#f8fafc',
            borderRadius: '16px',
            borderRight: `4px solid ${activity.color}`,
            boxShadow: '0 2px 10px rgba(0,0,0,0.05)'
          }}>
            <div style={{
              fontSize: '2rem',
              marginLeft: '1rem',
              padding: '0.75rem',
              background: `${activity.color}20`,
              borderRadius: '12px'
            }}>
              {activity.icon}
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ 
                fontWeight: '700', 
                color: '#2d3748',
                fontSize: '1.1rem',
                marginBottom: '0.25rem'
              }}>
                {activity.title}
              </div>
              <div style={{ fontSize: '0.95rem', color: '#718096' }}>
                {activity.description}
              </div>
            </div>
            <div style={{
              background: activity.color,
              color: 'white',
              padding: '0.5rem 1rem',
              borderRadius: '20px',
              fontSize: '0.9rem',
              fontWeight: '600'
            }}>
              {activity.time}
            </div>
          </div>
        ))}
      </div>
    </div>
  );

  const renderBusinessInfo = () => (
    <div style={{
      background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
      color: 'white',
      padding: '2rem',
      borderRadius: '20px',
      marginBottom: '2rem',
      position: 'relative',
      overflow: 'hidden'
    }}>
      <div style={{
        position: 'absolute',
        top: '-50px',
        left: '-50px',
        fontSize: '8rem',
        opacity: 0.1
      }}>
        🏢
      </div>
      <div style={{ position: 'relative', zIndex: 1 }}>
        <h3 style={{ 
          fontSize: '1.5rem', 
          fontWeight: '700', 
          marginBottom: '1.5rem'
        }}>
          פרטי העסק
        </h3>
        <div style={{ 
          display: 'grid', 
          gap: '1rem', 
          fontSize: '1rem',
          gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>🏢</span>
            <div>
              <strong>שם העסק:</strong><br />
              שי דירות ומשרדים בע״מ
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>🏠</span>
            <div>
              <strong>תחום:</strong><br />
              נדלן ותיווך מקצועי
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>📞</span>
            <div>
              <strong>טלפון ישראלי:</strong><br />
              +972-3-555-7777
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.5rem' }}>💬</span>
            <div>
              <strong>WhatsApp:</strong><br />
              +1-555-123-4567
            </div>
          </div>
        </div>
        
        <div style={{
          marginTop: '2rem',
          padding: '1.5rem',
          background: 'rgba(255,255,255,0.1)',
          borderRadius: '16px',
          backdropFilter: 'blur(10px)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '2rem' }}>🤖</span>
            <div>
              <div style={{ fontWeight: '700', fontSize: '1.1rem' }}>
                סטטוס AI Assistant
              </div>
              <div style={{ opacity: 0.9 }}>
                פעיל ומוכן לקבלת שיחות 24/7 • תמיכה בעברית מלאה
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeModule) {
      case 'dashboard':
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
                לוח בקרה עסקי מתקדם
              </h2>
              <p style={{ color: '#718096', fontSize: '1.1rem' }}>
                מערכת ניהול מקצועית לעסק הנדלן שלך
              </p>
            </div>
            
            {renderBusinessMetrics()}
            {renderRecentActivity()}
            {renderBusinessInfo()}
          </div>
        );
      
      case 'customers':
        return (
          <div>
            <div style={{ marginBottom: '2rem' }}>
              <h2 style={{ 
                fontSize: '2.5rem', 
                fontWeight: '800', 
                marginBottom: '0.5rem', 
                color: '#2d3748'
              }}>
                ניהול לקוחות מתקדם
              </h2>
              <p style={{ color: '#718096', fontSize: '1.1rem' }}>
                בסיס הלקוחות המקצועי שלך
              </p>
            </div>
            
            <div style={{
              background: 'white',
              padding: '2rem',
              borderRadius: '20px',
              border: '1px solid #e2e8f0',
              boxShadow: '0 10px 40px rgba(0,0,0,0.08)'
            }}>
              <div style={{ display: 'grid', gap: '1.5rem' }}>
                {customers.map((customer) => (
                  <div key={customer.id} style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '1.5rem',
                    background: 'linear-gradient(135deg, #f8fafc 0%, #edf2f7 100%)',
                    borderRadius: '16px',
                    border: '1px solid #e2e8f0',
                    boxShadow: '0 4px 15px rgba(0,0,0,0.05)'
                  }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                      <div style={{
                        width: '50px',
                        height: '50px',
                        borderRadius: '50%',
                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        color: 'white',
                        fontSize: '1.5rem',
                        fontWeight: '700'
                      }}>
                        {customer.name.charAt(0)}
                      </div>
                      <div>
                        <div style={{ fontWeight: '700', color: '#2d3748', fontSize: '1.1rem' }}>
                          {customer.name}
                        </div>
                        <div style={{ fontSize: '0.95rem', color: '#718096' }}>
                          {customer.phone} • {customer.email}
                        </div>
                        <div style={{ fontSize: '0.9rem', color: '#4a5568', marginTop: '0.25rem' }}>
                          {customer.notes}
                        </div>
                      </div>
                    </div>
                    <div style={{ textAlign: 'left' }}>
                      <div style={{
                        background: '#c6f6d5',
                        color: '#2f855a',
                        padding: '0.5rem 1rem',
                        borderRadius: '25px',
                        fontSize: '0.9rem',
                        fontWeight: '700',
                        marginBottom: '0.5rem'
                      }}>
                        {customer.status}
                      </div>
                      <div style={{
                        background: '#bee3f8',
                        color: '#2b6cb0',
                        padding: '0.25rem 0.75rem',
                        borderRadius: '20px',
                        fontSize: '0.8rem',
                        fontWeight: '600'
                      }}>
                        מקור: {customer.source}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
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
              AgentLocator CRM - שי דירות ומשרדים
            </h1>
            <p style={{ 
              margin: 0, 
              fontSize: '1.1rem',
              opacity: 0.9,
              fontWeight: '400'
            }}>
              שלום {user.name} • מערכת ניהול מקצועית
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
              ניווט עסקי
            </h3>
            <p style={{ fontSize: '0.9rem', color: '#718096', margin: 0 }}>
              כלים לניהול העסק
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
              flexDirection: 'column',
              justifyContent: 'center',
              alignItems: 'center',
              height: '400px',
              background: 'white',
              borderRadius: '20px',
              gap: '1rem'
            }}>
              <div style={{ fontSize: '3rem' }}>⏳</div>
              <div style={{ fontSize: '1.2rem', color: '#4a5568' }}>טוען נתונים...</div>
            </div>
          ) : (
            renderContent()
          )}
        </div>
      </div>
    </div>
  );
}