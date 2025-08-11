import React, { useState } from "react";
import { useAuth } from "../contexts/AuthContext";
import "./LoginPage.css";

export default function LoginPage() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setIsLoading(true);

    try {
      await login(email, password);
    } catch (err: any) {
      setError(err.message || "האימייל או הסיסמה שגויים");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card">
        <div className="login-header">
          <h1>🏢 AgentLocator CRM</h1>
          <p>מערכת ניהול לקוחות עם בינה מלאכותית</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="email">כתובת אימייל</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              disabled={isLoading}
              placeholder="הזן כתובת אימייל"
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">סיסמה</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              placeholder="הזן סיסמה"
            />
          </div>

          {error && (
            <div className="error-message">
              {error}
            </div>
          )}

          <button 
            type="submit" 
            className="login-button"
            disabled={isLoading}
          >
            {isLoading ? "מתחבר..." : "כניסה למערכת"}
          </button>
        </form>

        <div className="demo-credentials">
          <h3>פרטי התחברות לדמו:</h3>
          <div className="credential-row">
            <strong>מנהל מערכת:</strong> admin@example.com / admin123
          </div>
          <div className="credential-row">
            <strong>עסק שי דירות:</strong> shai@example.com / shai123
          </div>
        </div>
      </div>
    </div>
  );
}