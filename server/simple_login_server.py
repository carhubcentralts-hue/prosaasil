from flask import Flask, send_file, jsonify
import os

app = Flask(__name__)

@app.route("/health")
def health(): 
    return jsonify(ok=True), 200

@app.route("/")
def home():
    """דף התחברות פשוט"""
    # בדיקה אם יש build של React
    dist_path = os.path.join(os.path.dirname(__file__), '..', 'client', 'dist', 'index.html')
    if os.path.exists(dist_path):
        return send_file(dist_path)
    
    # דף התחברות פשוט כגיבוי
    return '''<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>התחברות - AgentLocator CRM</title>
    <style>
        body { 
            font-family: "Assistant", Arial, sans-serif; 
            margin: 0;
            direction: rtl;
            background: white;
            min-height: 100vh;
            display: grid;
            place-items: center;
        }
        .login-form {
            width: 100%;
            max-width: 380px;
            padding: 24px;
            background: white;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            border: 1px solid #ddd;
        }
        h1 { margin-bottom: 16px; font-weight: 700; color: #333; }
        label { display: block; margin-bottom: 8px; color: #333; }
        input { 
            width: 100%; 
            padding: 12px; 
            margin-bottom: 12px; 
            border-radius: 10px; 
            border: 1px solid #ddd;
            box-sizing: border-box;
        }
        button { 
            width: 100%; 
            padding: 12px; 
            border-radius: 10px; 
            border: none; 
            background: #007bff;
            color: white;
            font-weight: 700; 
            cursor: pointer;
        }
        .demo { margin-top: 16px; font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <form class="login-form">
        <h1>התחברות</h1>
        <label>אימייל</label>
        <input type="email" required>
        <label>סיסמה</label>
        <input type="password" required>
        <button type="submit">כניסה</button>
        <div class="demo">דמו: admin@example.com / demo123</div>
    </form>
</body>
</html>'''

if __name__ == "__main__":
    print("🚀 AgentLocator Simple Login Server") 
    print("📱 Starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

if __name__ == '__main__':
    print("🚀 AgentLocator Simple Login Server")
    print("📱 Starting on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)