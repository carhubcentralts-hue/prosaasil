import { useState } from 'react'
import './App.css'

function App() {
  const [callStatus, setCallStatus] = useState('מחכה לשיחות...')

  return (
    <div className="app" dir="rtl">
      <header className="header">
        <h1>🏢 AgentLocator - מערכת CRM עברית</h1>
        <p>מערכת ניהול שיחות AI עם לאה הסוכנת</p>
      </header>
      
      <main className="main">
        <div className="card">
          <h2>📞 מצב השיחות</h2>
          <p className="status">{callStatus}</p>
          <div className="phone-numbers">
            <div>📱 נכנס: +972504294724</div>
            <div>📞 יוצא: +97233763805</div>
          </div>
        </div>

        <div className="card">
          <h2>🤖 לאה - הסוכנת החכמה</h2>
          <ul>
            <li>✅ זיהוי דיבור עברית (Google STT)</li>
            <li>✅ תגובות טבעיות (OpenAI GPT-4o-mini)</li>
            <li>✅ דיבור עברית (Google TTS Wavenet)</li>
            <li>✅ איסוף מידע לידים ותיאום פגישות</li>
          </ul>
        </div>

        <div className="card">
          <h2>💼 ניהול CRM</h2>
          <div className="crm-actions">
            <button>📋 לידים חדשים</button>
            <button>📞 היסטוריית שיחות</button>
            <button>💬 הודעות וואטסאפ</button>
            <button>📊 דוחות</button>
          </div>
        </div>
      </main>
      
      <footer className="footer">
        <p>שי דירות ומשרדים בע״מ | מערכת AI מתקדמת</p>
      </footer>
    </div>
  )
}

export default App