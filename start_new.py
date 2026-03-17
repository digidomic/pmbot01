import sys
sys.path.insert(0, '/tmp/pmbot01-new')

from dashboard.app import app, socketio

# Disable caching
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

print("=" * 50)
print("🚀 PM Bot Dashboard with NEW Features:")
print("   🎮 Play/Pause Button")
print("   👤 Profile Selector")
print("   ➕ Add Profile Modal")
print("=" * 50)

socketio.run(app, host='0.0.0.0', port=3000, debug=False, allow_unsafe_werkzeug=True)
