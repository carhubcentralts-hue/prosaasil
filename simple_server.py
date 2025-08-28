#!/usr/bin/env python3
"""
Simple working server for testing
"""
from flask import Flask, render_template_string

app = Flask(__name__)
app.secret_key = 'test-key'

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>התחברות - מקסימוס נדל״ן</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <style>body { font-family: 'Assistant', sans-serif; }</style>
</head>
<body class="bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 min-h-screen flex items-center justify-center p-4">
    <div class="bg-white/95 backdrop-blur-sm border border-white/20 rounded-3xl p-10 w-full max-w-md shadow-2xl">
        <div class="text-center mb-8">
            <div class="w-20 h-20 bg-gradient-to-br from-blue-500 to-blue-700 rounded-3xl flex items-center justify-center mx-auto mb-6 shadow-lg">
                <span class="text-white text-3xl font-semibold">🏢</span>
            </div>
            <h1 class="text-4xl font-bold text-slate-800 mb-3">מקסימוס נדל״ן</h1>
            <p class="text-slate-500 text-sm">כניסה למערכת ניהול לקוחות</p>
        </div>

        <form class="space-y-6">
            <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">כתובת אימייל</label>
                <input type="email" class="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-right bg-slate-50 hover:bg-white focus:bg-white" placeholder="admin@maximus.co.il" />
            </div>

            <div>
                <label class="block text-sm font-medium text-slate-700 mb-2">סיסמה</label>
                <input type="password" class="w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200 text-right bg-slate-50 hover:bg-white focus:bg-white" placeholder="admin123" />
            </div>

            <button type="button" onclick="alert('✅ המערכת עובדת! השרת רץ כמו שצריך')" class="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 px-4 rounded-xl font-semibold hover:from-blue-700 hover:to-purple-700 transition-all duration-300 transform hover:scale-[1.02] shadow-xl focus:ring-4 focus:ring-blue-200">
                כניסה למערכת
            </button>
        </form>

        <div class="mt-10 pt-6 border-t border-slate-200 text-center">
            <p class="text-xs text-slate-500">✅ השרת עובד! המערכת החדשה מוכנה</p>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def home():
    return '<h1>🎯 השרת עובד!</h1><p><a href="/login" style="color:blue;">לדף התחברות</a></p>'

@app.route('/login')
def login():
    return render_template_string(LOGIN_HTML)

@app.route('/test')
def test():
    return '<h1>✅ Test Success!</h1><p>The server is working perfectly!</p>'

if __name__ == '__main__':
    print("🚀 Starting simple working server...")
    app.run(host='0.0.0.0', port=5000, debug=False)