import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app_factory import create_app

if __name__ == "__main__":
    app = create_app("config.DevConfig")
    app.run(host="0.0.0.0", port=5000, debug=True)