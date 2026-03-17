import sys
import os
sys.path.insert(0, '/tmp/pmbot01-new')
os.chdir('/tmp/pmbot01-new')

print("📂 Current directory:", os.getcwd())
print("📁 Template folder exists:", os.path.exists('templates'))
print("📄 index.html exists:", os.path.exists('templates/index.html'))
print("📊 index.html size:", os.path.getsize('templates/index.html'), "bytes")

# Read first 50 lines of template
with open('templates/index.html', 'r') as f:
    lines = f.readlines()
    print(f"📋 Template has {len(lines)} lines")
    print("\n📝 First 20 lines:")
    for i, line in enumerate(lines[:20]):
        print(f"  {i+1}: {line[:80].rstrip()}")

from dashboard.app import app, socketio
app.template_folder = '/tmp/pmbot01-new/templates'
app.static_folder = '/tmp/pmbot01-new/static'
app.config['TEMPLATES_AUTO_RELOAD'] = True

print(f"\n✅ Template folder set to: {app.template_folder}")
print(f"✅ Static folder set to: {app.static_folder}")

socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True)
