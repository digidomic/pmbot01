#!/usr/bin/env python3
"""
PM Bot - Polymarket Copy Trading Bot
Main entry point
"""
import os
import sys
import time
import signal
import logging
import argparse
from datetime import datetime
from threading import Thread

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from database.db import DatabaseManager
from scraper.models import Trade, BotState, TargetProfile
from scraper.polymarket_scraper import PolymarketScraper
from trader.clob_trader import ClobTrader

# Import strategies conditionally
try:
    from strategies import create_bitcoin_arbitrage_strategy, Signal
    STRATEGIES_AVAILABLE = True
except ImportError as e:
    STRATEGIES_AVAILABLE = False
    logging.warning(f"Strategies module not available: {e}")

# Import dashboard conditionally
try:
    from dashboard.app import run_dashboard, emit_trade_update, emit_stats_update
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False

# Global state
running = True
db: DatabaseManager = None
trader: ClobTrader = None
scraper: PolymarketScraper = None

# Strategy components
bitcoin_strategy = None
bitcoin_ws_client = None

# Setup logging
def setup_logging():
    """Configure logging"""
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('pmbot.log')
        ]
    )
    
    return logging.getLogger(__name__)

logger = None


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running, bitcoin_strategy, bitcoin_ws_client
    logger.info(f"Received signal {signum}, shutting down...")
    running = False
    
    # Stop strategy components
    if bitcoin_ws_client:
        logger.info("Stopping Bitcoin WebSocket client...")
        bitcoin_ws_client.stop()
    if bitcoin_strategy:
        logger.info("Stopping Bitcoin strategy...")
        bitcoin_strategy.stop()


def is_bot_running() -> bool:
    """Check if bot is in running state"""
    try:
        with db.get_session() as session:
            state = session.query(BotState).first()
            if not state:
                # Default to paused if no state exists
                state = BotState(state='paused')
                session.add(state)
                session.commit()
                return False
            return state.state == 'running'
    except Exception as e:
        logger.error(f"Failed to check bot state: {e}")
        return False  # Default to paused on error


def get_active_profile():
    """Get currently active target profile as dict"""
    try:
        with db.get_session() as session:
            profile = session.query(TargetProfile).filter_by(is_active=True).first()
            if profile:
                # Convert to dict while session is still open
                return {
                    'id': profile.id,
                    'username': profile.username,
                    'profile_url': profile.profile_url,
                    'is_active': profile.is_active
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get active profile: {e}")
        return None


def process_new_trades():
    """Main loop: Check for new trades and execute copies"""
    global running, scraper
    
    logger.info(f"Starting trade monitoring for target: {config.TARGET_USERNAME}")
    
    while running:
        try:
            # Check bot state - skip trading if paused
            if not is_bot_running():
                logger.debug("Bot is paused, skipping trade execution")
                time.sleep(config.POLL_INTERVAL)
                continue
            
            # Check if we need to update scraper (profile changed)
            active_profile = get_active_profile()
            if active_profile and active_profile['username'] != config.TARGET_USERNAME:
                logger.info(f"Switching to profile: {active_profile['username']}")
                config.TARGET_USERNAME = active_profile['username']
                config.TARGET_USER_URL = active_profile['profile_url']
                scraper = PolymarketScraper(config.TARGET_USERNAME)
            
            # Fetch recent activity from target user
            logger.debug("Fetching target user activity...")
            raw_trades = scraper.fetch_activity(limit=config.MAX_TRADES_TO_TRACK)
            
            if not raw_trades:
                logger.debug("No trades found")
                time.sleep(config.POLL_INTERVAL)
                continue
            
            logger.info(f"Found {len(raw_trades)} trades")
            
            for raw_trade in raw_trades:
                # Check bot state again before each trade
                if not is_bot_running():
                    logger.info("Bot paused during trade processing")
                    break
                
                # Check if we already processed this trade
                with db.get_session() as session:
                    existing = session.query(Trade).filter_by(source_trade_id=raw_trade.trade_id).first()
                    
                    if existing:
                        logger.debug(f"Trade already processed: {raw_trade.trade_id}")
                        continue
                    
                    logger.info(f"New trade detected: {raw_trade.side} {raw_trade.outcome} "
                              f"on '{raw_trade.market_question[:50]}...' "
                              f"({raw_trade.amount} USDC)")
                    
                    # Save target trade
                    target_trade = Trade(
                        source_trade_id=raw_trade.trade_id,
                        trader_address=config.TARGET_USERNAME,
                        market_slug=raw_trade.market_slug,
                        market_name=raw_trade.market_question,
                        outcome=raw_trade.outcome,
                        side=raw_trade.side,
                        amount_usdc=raw_trade.amount,
                        price=raw_trade.price,
                        timestamp=raw_trade.timestamp,
                        tx_hash=raw_trade.tx_hash,
                        copied=False,
                        is_target_trade=True
                    )
                    session.add(target_trade)
                    session.commit()
                    
                    # Emit to dashboard
                    if DASHBOARD_AVAILABLE:
                        try:
                            emit_trade_update(target_trade)
                        except Exception as e:
                            logger.warning(f"Failed to emit trade update: {e}")
                    
                    # Execute copy trade
                    copy_trade = Trade(
                        source_trade_id=f"copy_{raw_trade.trade_id}",
                        trader_address=config.TARGET_USERNAME,
                        market_slug=raw_trade.market_slug,
                        market_name=raw_trade.market_question,
                        outcome=raw_trade.outcome,
                        side=raw_trade.side,
                        amount_usdc=raw_trade.amount,
                        price=raw_trade.price,
                        timestamp=datetime.now(),
                        copied=False,
                        is_target_trade=False
                    )
                    
                    success, error = trader.execute_trade(copy_trade)
                    
                    if success:
                        logger.info(f"Trade copied successfully: {copy_trade.source_trade_id}")
                    else:
                        logger.error(f"Failed to copy trade: {error}")
                    
                    # Emit stats update
                    if DASHBOARD_AVAILABLE:
                        try:
                            emit_stats_update()
                        except Exception as e:
                            logger.warning(f"Failed to emit stats update: {e}")
            
        except Exception as e:
            logger.error(f"Error in process loop: {e}", exc_info=True)
        
        # Wait before next poll
        time.sleep(config.POLL_INTERVAL)
    
    logger.info("Trade monitoring stopped")


def init_default_profile():
    """Initialize default profile from config if none exists"""
    try:
        with db.get_session() as session:
            # Check if any profiles exist
            count = session.query(TargetProfile).count()
            if count == 0:
                # Create default profile from config
                profile = TargetProfile(
                    username=config.TARGET_USERNAME,
                    profile_url=config.TARGET_USER_URL,
                    is_active=True
                )
                session.add(profile)
                session.commit()
                logger.info(f"Created default profile: {config.TARGET_USERNAME}")
    except Exception as e:
        logger.error(f"Failed to init default profile: {e}")


def init_bot_state():
    """Initialize bot state to paused if not exists"""
    try:
        with db.get_session() as session:
            state = session.query(BotState).first()
            if not state:
                state = BotState(state='paused')
                session.add(state)
                session.commit()
                logger.info("Initialized bot state: paused")
    except Exception as e:
        logger.error(f"Failed to init bot state: {e}")


def main():
    """Main entry point"""
    global logger, db, trader, scraper, running
    global bitcoin_strategy, bitcoin_ws_client
    
    parser = argparse.ArgumentParser(description='PM Bot - Polymarket Copy Trading')
    parser.add_argument('--dashboard-only', action='store_true', 
                       help='Run only the dashboard without trading')
    parser.add_argument('--trade-only', action='store_true',
                       help='Run only trading without dashboard')
    parser.add_argument('--host', default=None, help='Dashboard host')
    parser.add_argument('--port', type=int, default=None, help='Dashboard port')
    parser.add_argument('--strategy', type=str, default=None, 
                       choices=['copy', 'bitcoin_arbitrage'],
                       help='Trading strategy to use (default: copy)')
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    logger.info("=" * 50)
    
    # Strategy selection
    if args.strategy == 'bitcoin_arbitrage':
        logger.info("PM Bot Starting - Bitcoin Up/Down Strategy")
    else:
        logger.info("PM Bot Starting - Copy Trading Strategy")
    
    logger.info("=" * 50)
    
    # Validate config
    errors = config.validate()
    if errors:
        for error in errors:
            logger.error(f"Config error: {error}")
        if not args.dashboard_only:
            logger.error("Fix configuration errors or run with --dashboard-only")
            sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Initialize database
    logger.info("Initializing database...")
    db = DatabaseManager(config.DATABASE_PATH)
    
    # Initialize bot state and default profile
    init_bot_state()
    init_default_profile()
    
    # Initialize trader (needed for most modes)
    if not args.dashboard_only:
        logger.info("Initializing trader...")
        trader = ClobTrader(db)
        
        if not trader.initialized:
            logger.warning("CLOB trader not initialized - check credentials")
    
    # Initialize and run based on strategy
    threads = []
    
    if args.strategy == 'bitcoin_arbitrage':
        if not STRATEGIES_AVAILABLE:
            logger.error("Bitcoin Up/Down strategy not available - check dependencies")
            sys.exit(1)
        
        logger.info("🚀 Starting Bitcoin Up/Down Strategy...")
        
        # Create strategy and WebSocket client
        bitcoin_strategy, bitcoin_ws_client = create_bitcoin_arbitrage_strategy(trader)
        
        # Start strategy processing
        bitcoin_strategy.start()
        
        # Connect to Coinbase WebSocket
        bitcoin_ws_client.start()
        
        # Get market type from strategy config
        from config.strategy_config import arbitrage_config, get_current_market_slug, get_current_condition_id
        market_type = arbitrage_config.MARKET_TYPE
        
        # Log market resolver status
        if arbitrage_config.MARKET_RESOLVER_ENABLED:
            logger.info(f"🔍 Market Resolver: ENABLED (interval: {arbitrage_config.MARKET_RESOLVER_INTERVAL}s)")
            current_slug = get_current_market_slug()
            current_condition = get_current_condition_id()
            logger.info(f"   Current Market: {current_slug}")
            logger.info(f"   Condition ID: {current_condition[:30]}...")
        else:
            logger.info(f"🔍 Market Resolver: DISABLED (using static values)")
        
        logger.info(f"📡 Connected to Coinbase WebSocket")
        logger.info(f"📊 Market Type: {market_type}")
        logger.info(f"📊 Strategy: BTC rises → BUY YES | BTC falls → BUY NO")
        logger.info(f"⏱️  Max Hold Time: {'5 minutes' if market_type == 'updown_5m' else '15 minutes'}")
        
        # Stats reporting thread
        def report_stats():
            while running:
                time.sleep(60)  # Every minute
                if bitcoin_strategy:
                    stats = bitcoin_strategy.get_stats()
                    logger.info(
                        f"📈 Strategy Stats: {stats['signals_generated']} signals, "
                        f"{stats['trades_executed']} trades, "
                        f"PnL: {stats['total_pnl']:+.2%}"
                    )
        
        stats_thread = Thread(target=report_stats, daemon=True)
        stats_thread.start()
        threads.append(stats_thread)
        
        # Keep main thread alive
        try:
            while running:
                time.sleep(1)
                
                # Check WebSocket health
                if bitcoin_ws_client and not bitcoin_ws_client.is_connected():
                    logger.warning("WebSocket disconnected, attempting reconnect...")
                    
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        
        # Cleanup
        logger.info("Shutting down Bitcoin Arbitrage Strategy...")
        if bitcoin_ws_client:
            bitcoin_ws_client.stop()
        if bitcoin_strategy:
            bitcoin_strategy.stop()
            
    else:
        # Default: Copy Trading Strategy
        if not args.dashboard_only:
            logger.info(f"Initializing scraper for target: {config.TARGET_USERNAME}")
            scraper = PolymarketScraper(config.TARGET_USERNAME)
        
        # Start components
        if not args.dashboard_only:
            logger.info("Starting trade monitor...")
            monitor_thread = Thread(target=process_new_trades, daemon=True)
            monitor_thread.start()
            threads.append(monitor_thread)
        
        if not args.trade_only and DASHBOARD_AVAILABLE:
            logger.info("Starting dashboard...")
            dashboard_thread = Thread(
                target=run_dashboard,
                args=(args.host, args.port, False),
                daemon=True
            )
            dashboard_thread.start()
            threads.append(dashboard_thread)
            logger.info(f"Dashboard available at http://{config.DASHBOARD_HOST}:{config.DASHBOARD_PORT}")
        
        # Keep main thread alive
        try:
            while running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
    
    logger.info("Shutdown complete")


if __name__ == '__main__':
    main()
