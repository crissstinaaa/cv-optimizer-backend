import os
from flask import Flask
from routes import register_routes

app = Flask(__name__)
register_routes(app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # default to 5000 for local dev
    app.run(host="0.0.0.0", port=port, debug=True)
