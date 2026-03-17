"""
Web Dashboard for PM Bot
Flask + SocketIO for real-time updates
"""
import json
import logging
from datetime import datetime
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit

from config import config
from database.db import DatabaseManager
from scraper.models import Trade, BotState, TargetProfile

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pmbot-secret-key-change-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global database instance
db = DatabaseManager(config.DATABASE_PATH)


@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')


@app.route('/api/stats')
def get_stats():
    """Get trading statistics"""
    return jsonify(db.get_stats())


@app.route('/api/trades')
def get_trades():
    """Get recent trades"""
    limit = request.args.get('limit', 50, type=int)
    
    with db.get_session() as session:
        trades = session.query(Trade).order_by(Trade.detected_at.desc()).limit(limit).all()
        return jsonify([t.to_dict() for t in trades])


@app.route('/api/config')
def get_config():
    """Get current configuration (safe values only)"""
    return jsonify({
        'target_username': config.TARGET_USERNAME,
        'target_url': config.TARGET_USER_URL,
        'max_trade_amount': config.MAX_TRADE_AMOUNT_USDC,
        'trade_percentage': config.TRADE_PERCENTAGE,
        'max_trades_to_track': config.MAX_TRADES_TO_TRACK,
        'poll_interval': config.POLL_INTERVAL,
        'log_level': config.LOG_LEVEL
    })


@app.route('/api/config', methods=['POST'])
def update_config():
    """Update configuration"""
    data = request.json
    
    if 'max_trade_amount' in data:
        config.MAX_TRADE_AMOUNT_USDC = float(data['max_trade_amount'])
    if 'trade_percentage' in data:
        config.TRADE_PERCENTAGE = float(data['trade_percentage'])
    if 'max_trades_to_track' in data:
        config.MAX_TRADES_TO_TRACK = int(data['max_trades_to_track'])
    if 'poll_interval' in data:
        config.POLL_INTERVAL = int(data['poll_interval'])
    
    emit_config_update()
    return jsonify({'success': True})


# ===== BOT STATE (Play/Pause) =====

@app.route('/api/bot/state')
def get_bot_state():
    """Get current bot state (running/paused)"""
    with db.get_session() as session:
        state = session.query(BotState).first()
        if not state:
            state = BotState(state='paused')
            session.add(state)
            session.commit()
        return jsonify(state.to_dict())


@app.route('/api/bot/state', methods=['POST'])
def update_bot_state():
    """Toggle or set bot state"""
    data = request.json or {}
    new_state = data.get('state')
    
    with db.get_session() as session:
        state = session.query(BotState).first()
        if not state:
            state = BotState(state='paused')
            session.add(state)
        
        if new_state in ['running', 'paused']:
            state.state = new_state
        else:
            # Toggle if no state provided
            state.state = 'paused' if state.state == 'running' else 'running'
        
        session.commit()
        result = state.to_dict()
    
    # Broadcast state change to all clients
    socketio.emit('bot_state_update', result)
    logger.info(f"Bot state changed to: {result['state']}")
    return jsonify(result)


# ===== PROFILE MANAGEMENT =====

@app.route('/api/profiles')
def get_profiles():
    """Get all target profiles"""
    with db.get_session() as session:
        profiles = session.query(TargetProfile).order_by(TargetProfile.added_at.desc()).all()
        return jsonify([p.to_dict() for p in profiles])


@app.route('/api/profiles', methods=['POST'])
def add_profile():
    """Add new target profile"""
    data = request.json
    username = data.get('username', '').strip()
    profile_url = data.get('profile_url', '').strip()
    
    if not username:
        return jsonify({'error': 'Username required'}), 400
    
    # Auto-generate URL if not provided
    if not profile_url:
        profile_url = f"https://polymarket.com/profile/@{username}"
    
    with db.get_session() as session:
        # Check if profile exists
        existing = session.query(TargetProfile).filter_by(username=username).first()
        if existing:
            return jsonify({'error': 'Profile already exists'}), 400
        
        profile = TargetProfile(
            username=username,
            profile_url=profile_url,
            is_active=False  # Default inactive
        )
        session.add(profile)
        session.commit()
        
        result = profile.to_dict()
    
    socketio.emit('profile_added', result)
    logger.info(f"Profile added: {username}")
    return jsonify(result), 201


@app.route('/api/profiles/<int:profile_id>/activate', methods=['PUT'])
def activate_profile(profile_id):
    """Activate a profile (deactivates all others)"""
    with db.get_session() as session:
        # Deactivate all profiles
        session.query(TargetProfile).update({TargetProfile.is_active: False})
        
        # Activate selected profile
        profile = session.query(TargetProfile).get(profile_id)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        profile.is_active = True
        session.commit()
        
        # Update config for scraper
        config.TARGET_USERNAME = profile.username
        config.TARGET_USER_URL = profile.profile_url
        
        result = profile.to_dict()
    
    socketio.emit('profile_activated', result)
    logger.info(f"Profile activated: {profile.username}")
    return jsonify(result)


@app.route('/api/profiles/<int:profile_id>', methods=['DELETE'])
def delete_profile(profile_id):
    """Delete a profile (cannot delete active profile)"""
    with db.get_session() as session:
        profile = session.query(TargetProfile).get(profile_id)
        if not profile:
            return jsonify({'error': 'Profile not found'}), 404
        
        if profile.is_active:
            return jsonify({'error': 'Cannot delete active profile'}), 400
        
        username = profile.username
        session.delete(profile)
        session.commit()
    
    socketio.emit('profile_deleted', {'id': profile_id, 'username': username})
    logger.info(f"Profile deleted: {username}")
    return jsonify({'success': True})


# ===== WEBSOCKET HELPERS =====

def emit_config_update():
    """Emit config update to all clients"""
    socketio.emit('config_update', {
        'max_trade_amount': config.MAX_TRADE_AMOUNT_USDC,
        'trade_percentage': config.TRADE_PERCENTAGE,
        'max_trades_to_track': config.MAX_TRADES_TO_TRACK,
        'poll_interval': config.POLL_INTERVAL
    })


def emit_trade_update(trade: Trade):
    """Emit new trade to all connected clients"""
    socketio.emit('new_trade', trade.to_dict())


def emit_stats_update():
    """Emit stats update to all clients"""
    socketio.emit('stats_update', db.get_stats())


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    
    # Send current config
    emit('config_update', {
        'max_trade_amount': config.MAX_TRADE_AMOUNT_USDC,
        'trade_percentage': config.TRADE_PERCENTAGE,
        'max_trades_to_track': config.MAX_TRADES_TO_TRACK,
        'poll_interval': config.POLL_INTERVAL
    })
    
    # Send bot state
    with db.get_session() as session:
        state = session.query(BotState).first()
        if state:
            emit('bot_state_update', state.to_dict())
        else:
            emit('bot_state_update', {'state': 'paused', 'is_running': False})
    
    # Send active profile
    with db.get_session() as session:
        active = session.query(TargetProfile).filter_by(is_active=True).first()
        if active:
            emit('profile_activated', active.to_dict())


@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection"""
    logger.info("Client disconnected")


def run_dashboard(host: str = None, port: int = None, debug: bool = False):
    """Run the dashboard server"""
    host = host or config.DASHBOARD_HOST
    port = port or config.DASHBOARD_PORT
    
    logger.info(f"Starting dashboard on {host}:{port}")
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)


if __name__ == '__main__':
    run_dashboard(debug=True)
