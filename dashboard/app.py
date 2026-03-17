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
from database.db import TradeDatabase, Trade

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pmbot-secret-key-change-in-production'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global database instance
db = TradeDatabase(config.DATABASE_PATH)


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
    trades = db.get_all_trades(limit=limit)
    
    return jsonify([{
        'trade_id': t.trade_id,
        'market_question': t.market_question,
        'side': t.side,
        'outcome': t.outcome,
        'original_amount': t.original_amount,
        'copied_amount': t.copied_amount,
        'price': t.price,
        'timestamp': t.timestamp.isoformat() if t.timestamp else None,
        'original_timestamp': t.original_timestamp.isoformat() if t.original_timestamp else None,
        'copied_timestamp': t.copied_timestamp.isoformat() if t.copied_timestamp else None,
        'latency_seconds': t.latency_seconds,
        'status': t.status,
        'pnl': t.pnl,
        'is_target_trade': t.is_target_trade
    } for t in trades])


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
    
    # Update in-memory config (would need persistence for production)
    if 'max_trade_amount' in data:
        config.MAX_TRADE_AMOUNT_USDC = float(data['max_trade_amount'])
    if 'trade_percentage' in data:
        config.TRADE_PERCENTAGE = float(data['trade_percentage'])
    if 'max_trades_to_track' in data:
        config.MAX_TRADES_TO_TRACK = int(data['max_trades_to_track'])
    if 'poll_interval' in data:
        config.POLL_INTERVAL = int(data['poll_interval'])
    
    # TODO: Persist to database or file
    
    emit_config_update()
    return jsonify({'success': True})


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
    socketio.emit('new_trade', {
        'trade_id': trade.trade_id,
        'market_question': trade.market_question,
        'side': trade.side,
        'outcome': trade.outcome,
        'original_amount': trade.original_amount,
        'copied_amount': trade.copied_amount,
        'price': trade.price,
        'timestamp': trade.timestamp.isoformat() if trade.timestamp else None,
        'status': trade.status,
        'is_target_trade': trade.is_target_trade
    })


def emit_stats_update():
    """Emit stats update to all clients"""
    socketio.emit('stats_update', db.get_stats())


@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    logger.info("Client connected")
    emit('config_update', {
        'max_trade_amount': config.MAX_TRADE_AMOUNT_USDC,
        'trade_percentage': config.TRADE_PERCENTAGE,
        'max_trades_to_track': config.MAX_TRADES_TO_TRACK,
        'poll_interval': config.POLL_INTERVAL
    })


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
