import React from "react";
import { useAuth } from "../contexts/AuthContext";
import "./Dashboard.css";

export default function BusinessDashboard() {
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
          <h1>🏢 {user?.business_name || "שי דירות ומשרדים בע״מ"}</h1>
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
          <h2>ברוכים הבאים למערכת ניהול הלקוחות</h2>
          <p>נהל את הלקוחות שלך, שיחות טלפון והודעות WhatsApp במקום אחד</p>
        </div>

        <div className="modules-grid">
          <div className="module-card crm" onClick={() => window.location.href = '/business/crm'}>
            <div className="module-icon">👥</div>
            <h3>ניהול לקוחות (CRM)</h3>
            <p>ניהול מאגר הלקוחות, הוספת לקוחות חדשים ומעקב אחר פעילות</p>
            <div className="module-stats">
              <span>לקוחות פעילים</span>
            </div>
          </div>

          <div className="module-card calls" onClick={() => window.location.href = '/business/calls'}>
            <div className="module-icon">📞</div>
            <h3>ניהול שיחות</h3>
            <p>צפייה בהיסטוריית השיחות, תמלילים ועיבוד בינה מלאכותית</p>
            <div className="module-stats">
              <span>מספר ישראלי: +972-3-555-7777</span>
            </div>
          </div>

          <div className="module-card whatsapp" onClick={() => window.location.href = '/business/whatsapp'}>
            <div className="module-icon">💬</div>
            <h3>WhatsApp Business</h3>
            <p>ניהול הודעות ושיחות WhatsApp עם לקוחות</p>
            <div className="module-stats">
              <span>מספר אמריקאי: +1-555-123-4567</span>
            </div>
          </div>
        </div>

        <div className="business-info">
          <h3>פרטי העסק</h3>
          <div className="info-grid">
            <div className="info-item">
              <span className="info-label">שם העסק:</span>
              <span className="info-value">שי דירות ומשרדים בע״מ</span>
            </div>
            <div className="info-item">
              <span className="info-label">תחום עיסוק:</span>
              <span className="info-value">נדלן ותיווך</span>
            </div>
            <div className="info-item">
              <span className="info-label">טלפון עסק:</span>
              <span className="info-value">+972-3-555-7777</span>
            </div>
            <div className="info-item">
              <span className="info-label">WhatsApp עסק:</span>
              <span className="info-value">+1-555-123-4567</span>
            </div>
          </div>
        </div>

        <div className="quick-actions">
          <h3>פעולות מהירות</h3>
          <div className="actions-grid">
            <button className="action-btn primary">
              <span className="action-icon">📞</span>
              <span>בדיקת חיבור טלפון</span>
            </button>
            <button className="action-btn primary">
              <span className="action-icon">💬</span>
              <span>בדיקת חיבור WhatsApp</span>
            </button>
            <button className="action-btn secondary">
              <span className="action-icon">🔄</span>
              <span>סנכרון נתונים</span>
            </button>
            <button className="action-btn secondary">
              <span className="action-icon">📋</span>
              <span>דוח יומי</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}