import React from "react";
import { useAuth } from "../contexts/AuthContext";
import "./Dashboard.css";

export default function AdminDashboard() {
  const { user, logout } = useAuth();

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout failed:', error);
    }
  };

  return (
    <div className="dashboard-container">
      <div className="dashboard-header">
        <div className="header-content">
          <h1>🏢 AgentLocator CRM - מנהל מערכת</h1>
          <div className="user-info">
            <span>שלום, {user?.name}</span>
            <button className="logout-btn" onClick={handleLogout}>
              יציאה
            </button>
          </div>
        </div>
      </div>

      <div className="dashboard-main">
        <div className="welcome-section">
          <h2>ברוכים הבאים לפאנל הניהול</h2>
          <p>כמנהל מערכת, אתה יכול לגשת לכל העסקים ולנהל את המערכת</p>
        </div>

        <div className="modules-grid">
          <div className="module-card crm" onClick={() => window.location.href = '/admin/crm'}>
            <div className="module-icon">👥</div>
            <h3>ניהול לקוחות (CRM)</h3>
            <p>ניהול מאגר הלקוחות של כל העסקים במערכת</p>
            <div className="module-stats">
              <span>צפייה בכל הלקוחות</span>
            </div>
          </div>

          <div className="module-card calls" onClick={() => window.location.href = '/admin/calls'}>
            <div className="module-icon">📞</div>
            <h3>ניהול שיחות</h3>
            <p>היסטוריית שיחות וניתוח בינה מלאכותית של כל העסקים</p>
            <div className="module-stats">
              <span>תמלילים ועיבוד AI</span>
            </div>
          </div>

          <div className="module-card whatsapp" onClick={() => window.location.href = '/admin/whatsapp'}>
            <div className="module-icon">💬</div>
            <h3>WhatsApp Business</h3>
            <p>ניהול הודעות WhatsApp ואוטומציה לכל העסקים</p>
            <div className="module-stats">
              <span>חיבור למספרים אמריקאיים</span>
            </div>
          </div>

          <div className="module-card businesses" onClick={() => window.location.href = '/admin/businesses'}>
            <div className="module-icon">🏢</div>
            <h3>ניהול עסקים</h3>
            <p>הוספה, עריכה וניהול עסקים במערכת</p>
            <div className="module-stats">
              <span>הוספת עסקים חדשים</span>
            </div>
          </div>

          <div className="module-card analytics" onClick={() => window.location.href = '/admin/analytics'}>
            <div className="module-icon">📊</div>
            <h3>דוחות וסטטיסטיקות</h3>
            <p>ניתוח נתונים ותובנות עסקיות כלליות</p>
            <div className="module-stats">
              <span>דוחות מתקדמים</span>
            </div>
          </div>

          <div className="module-card settings" onClick={() => window.location.href = '/admin/settings'}>
            <div className="module-icon">⚙️</div>
            <h3>הגדרות מערכת</h3>
            <p>הגדרות כלליות ותצורת המערכת</p>
            <div className="module-stats">
              <span>תצורת שרתים ו-API</span>
            </div>
          </div>
        </div>

        <div className="system-status">
          <h3>סטטוס המערכת</h3>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">שיחות Twilio:</span>
              <span className="status-value online">פעיל</span>
            </div>
            <div className="status-item">
              <span className="status-label">WhatsApp Baileys:</span>
              <span className="status-value online">מחובר</span>
            </div>
            <div className="status-item">
              <span className="status-label">בינה מלאכותית:</span>
              <span className="status-value online">פעיל</span>
            </div>
            <div className="status-item">
              <span className="status-label">תמלול עברית:</span>
              <span className="status-value online">פעיל</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}