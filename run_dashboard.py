import sys
import os
sys.path.insert(0, '/tmp/pmbot01-new')
os.chdir('/tmp/pmbot01-new')

from dashboard.app import app, socketio

# WICHTIG: Static folder explizit setzen
app.static_folder = '/tmp/pmbot01-new/static'
app.template_folder = '/tmp/pmbot01-new/dashboard/templates'

print("🚀 Starting Dashboard...")
print(f"📁 Template folder: {app.template_folder}")
print(f"📁 Static folder: {app.static_folder}")
print(f"📊 Static exists: {os.path.exists(app.static_folder)}")
print(f"📄 CSS exists: {os.path.exists(app.static_folder + '/css/style.css')}")

socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True)
