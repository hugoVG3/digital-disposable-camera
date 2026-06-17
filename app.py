"""
Entry point for running the app directly (e.g. `python app.py` during
development on the Pi). For production, run it under a proper WSGI
server instead -- see docs/raspberry-pi-setup.md.
"""

import os

from dotenv import load_dotenv

load_dotenv()

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "development"))

if __name__ == "__main__":
    # host="0.0.0.0" so other devices on the network (or the router's
    # port-forward) can reach it -- not just localhost on the Pi itself.
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
