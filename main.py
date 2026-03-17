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
from database.db import TradeDatabase, Trade
from scraper.polymarket_scraper import PolymarketScraper
from trader.clob_trader import ClobTrader

# Import dashboard conditionally
try:
    from dashboard.app import run_dashboard, emit_trade_update, emit_stats_update
    DASHBOARD_AVAILABLE = True
except ImportError:
    DASHBOARD_AVAILABLE = False

# Global state
running = True
db: TradeDatabase = None
trader: ClobTrader = None
scraper: PolymarketScraper = None

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
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def process_new_trades():
    """Main loop: Check for new trades and execute copies"""
    global running
    
    logger.info(f"Starting trade monitoring for target: {config.TARGET_USERNAME}")
    
    while running:
        try:
            # Fetch recent activity from target user
            logger.debug("Fetching target user activity...")
            raw_trades = scraper.fetch_activity(limit=config.MAX_TRADES_TO_TRACK)
            
            if not raw_trades:
                logger.debug("No trades found")
                time.sleep(config.POLL_INTERVAL)
                continue
            
            logger.info(f"Found {len(raw_trades)} trades")
            
            for raw_trade in raw_trades:
                # Check if we already processed this trade
                existing = db.get_trade(raw_trade.trade_id)
                
                if existing:
                    logger.debug(f"Trade already processed: {raw_trade.trade_id}")
                    continue
                
                logger.info(f"New trade detected: {raw_trade.side} {raw_trade.outcome} "
                          f"on '{raw_trade.market_question[:50]}...' "
                          f"({raw_trade.amount} USDC)")
                
                # Save target trade
                target_trade = Trade(
                    trade_id=raw_trade.trade_id,
                    market_slug=raw_trade.market_slug,
                    market_question=raw_trade.market_question,
                    side=raw_trade.side,
                    outcome=raw_trade.outcome,
                    original_amount=raw_trade.amount,
                    price=raw_trade.price,
                    timestamp=raw_trade.timestamp,
                    original_timestamp=raw_trade.timestamp,
                    status='detected',
                    is_target_trade=True
                )
                db.save_trade(target_trade)
                
                # Emit to dashboard
                if DASHBOARD_AVAILABLE:
                    try:
                        emit_trade_update(target_trade)
                    except Exception as e:
                        logger.warning(f"Failed to emit trade update: {e}")
                
                # Execute copy trade
                copy_trade = Trade(
                    trade_id=f"copy_{raw_trade.trade_id}",
                    market_slug=raw_trade.market_slug,
                    market_question=raw_trade.market_question,
                    side=raw_trade.side,
                    outcome=raw_trade.outcome,
                    original_amount=raw_trade.amount,
                    price=raw_trade.price,
                    timestamp=datetime.now(),
                    original_timestamp=raw_trade.timestamp,
                    is_target_trade=False
                )
                
                success, error = trader.execute_trade(copy_trade)
                
                if success:
                    logger.info(f"Trade copied successfully: {copy_trade.trade_id}")
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


def main():
    """Main entry point"""
    global logger, db, trader, scraper
    
    parser = argparse.ArgumentParser(description='PM Bot - Polymarket Copy Trading')
    parser.add_argument('--dashboard-only', action='store_true', 
                       help='Run only the dashboard without trading')
    parser.add_argument('--trade-only', action='store_true',
                       help='Run only trading without dashboard')
    parser.add_argument('--host', default=None, help='Dashboard host')
    parser.add_argument('--port', type=int, default=None, help='Dashboard port')
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging()
    logger.info("=" * 50)
    logger.info("PM Bot Starting...")
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
    
    # Initialize components
    logger.info("Initializing database...")
    db = TradeDatabase(config.DATABASE_PATH)
    
    if not args.dashboard_only:
        logger.info("Initializing trader...")
        trader = ClobTrader(db)
        
        if not trader.initialized:
            logger.warning("CLOB trader not initialized - check credentials")
        
        logger.info("Initializing scraper...")
        scraper = PolymarketScraper(config.TARGET_USERNAME)
    
    # Start components
    threads = []
    
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
