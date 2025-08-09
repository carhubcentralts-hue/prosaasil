from flask import Blueprint, send_from_directory, send_file
import os

frontend_bp = Blueprint('frontend', __name__)

# Path to the React build directory
CLIENT_BUILD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'client', 'dist')

@frontend_bp.route('/')
def serve_react_app():
    """Serve the main React app"""
    try:
        return send_file(os.path.join(CLIENT_BUILD_DIR, 'index.html'))
    except Exception as e:
        return f"""
        <html>
        <head>
            <title>שי דירות ומשרדים בע״מ</title>
            <meta charset="utf-8">
            <style>
                body {{ 
                    font-family: Arial, sans-serif; 
                    text-align: center; 
                    margin: 50px; 
                    background-color: white;
                    direction: rtl;
                }}
                .container {{ 
                    max-width: 400px; 
                    margin: 0 auto; 
                    padding: 40px; 
                    border: 1px solid #ddd; 
                    border-radius: 10px; 
                }}
                input {{ 
                    width: 100%; 
                    padding: 12px; 
                    margin: 10px 0; 
                    border: 2px solid #ddd; 
                    border-radius: 5px; 
                    box-sizing: border-box;
                }}
                button {{ 
                    width: 100%; 
                    padding: 15px; 
                    background-color: #007bff; 
                    color: white; 
                    border: none; 
                    border-radius: 5px; 
                    font-size: 18px; 
                    cursor: pointer;
                }}
                .demo {{ 
                    background-color: #f8f9fa; 
                    padding: 20px; 
                    margin-top: 20px; 
                    border-radius: 5px; 
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>שי דירות ומשרדים בע״מ</h1>
                <p>מערכת ניהול לקוחות עם AI</p>
                
                <form action="/auth/login" method="post">
                    <label>שם משתמש:</label>
                    <input type="text" name="username" required placeholder="הזן שם משתמש">
                    
                    <label>סיסמה:</label>
                    <input type="password" name="password" required placeholder="הזן סיסמה">
                    
                    <button type="submit">התחבר</button>
                </form>
                
                <div class="demo">
                    <h3>פרטי התחברות לדמו:</h3>
                    <p><strong>מנהל:</strong> admin / admin123</p>
                    <p><strong>עסק:</strong> business / business123</p>
                </div>
            </div>
        </body>
        </html>
        """, 200

@frontend_bp.route('/assets/<path:filename>')
def serve_static_assets(filename):
    """Serve static assets from React build"""
    try:
        return send_from_directory(os.path.join(CLIENT_BUILD_DIR, 'assets'), filename)
    except:
        return "File not found", 404

@frontend_bp.route('/<path:path>')
def serve_react_routes(path):
    """Serve React app for all other routes (client-side routing)"""
    try:
        return send_file(os.path.join(CLIENT_BUILD_DIR, 'index.html'))
    except:
        # Fallback to home route
        return serve_react_app()