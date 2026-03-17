#!/usr/bin/env python3
"""
PM Bot Dashboard - Start Script
Fixes static/template folder paths for proper CSS/JS loading
"""
import sys
import os

# Get the directory where this script is located (repo root)
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_PATH)

from dashboard.app import app, socketio
from config import config

# CRITICAL: Explicitly set static and template folders
# This fixes 404 errors for CSS/JS files
app.static_folder = os.path.join(REPO_PATH, 'static')
app.template_folder = os.path.join(REPO_PATH, 'dashboard/templates')

print("=" * 60)
print("🚀 PM Bot Dashboard - Starting...")
print("=" * 60)
print(f"📁 Repository: {REPO_PATH}")
print(f"📁 Static folder: {app.static_folder}")
print(f"📁 Template folder: {app.template_folder}")
print(f"📊 Static folder exists: {os.path.exists(app.static_folder)}")
print(f"📄 CSS file exists: {os.path.exists(os.path.join(app.static_folder, 'css/style.css'))}")
print(f"🌐 Dashboard URL: http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
print(f"🔧 Dry Run Mode: {config.DRY_RUN}")
print("=" * 60)
print("Features: 🎮 Play/Pause | 👤 Profile Selector | 📊 Live Trades")
print("=" * 60)

if __name__ == '__main__':
    socketio.run(
        app, 
        host=config.DASHBOARD_HOST, 
        port=config.DASHBOARD_PORT,
        debug=False, 
        allow_unsafe_werkzeug=True
    )
