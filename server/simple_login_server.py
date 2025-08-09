from flask import Flask, send_from_directory, jsonify
import os

app = Flask(__name__, static_folder="../client/dist", static_url_path="/")

@app.route("/health")
def health(): 
    return jsonify(ok=True), 200

# שאר הראוטים/בלופרינטים/וובהוקים – אל תיגע!

# הגשת האפליקציה (SPA)
@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    file_path = os.path.join(app.static_folder, path)
    if path and os.path.exists(file_path):
        return send_from_directory(app.static_folder, path)
    return send_from_directory(app.static_folder, "index.html")

if __name__ == '__main__':
    print("🚀 AgentLocator Simple Login Server")
    print("📱 Starting on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)