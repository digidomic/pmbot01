#!/usr/bin/env python3
"""
Run Bot Only (Scraper + Trader)
For separated architecture where dashboard runs on a different host
Uses proxy configuration for external API calls
"""
import os
import sys
import logging
import signal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from config.proxy_config import USE_PROXY, validate_proxy_config, PROXY_HOST, PROXY_PORT
from config.network_config import validate_network_config, get_connection_info
from database.db import init_db_manager

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
running = True


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global running
    logger.info(f"Received signal {signum}, shutting down...")
    running = False


def main():
    """Main entry point for bot-only mode"""
    logger.info("=" * 60)
    logger.info("PM Bot - Bot Only Mode")
    logger.info("=" * 60)
    
    # Validate configurations
    proxy_errors = validate_proxy_config()
    if proxy_errors:
        logger.error("Proxy configuration errors:")
        for error in proxy_errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    network_errors = validate_network_config()
    if network_errors:
        logger.error("Network configuration errors:")
        for error in network_errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    # Log configuration
    logger.info(f"Database: {get_connection_info()}")
    
    if USE_PROXY:
        logger.info(f"Proxy: Enabled ({PROXY_HOST}:{PROXY_PORT})")
    else:
        logger.info("Proxy: Disabled")
    
    # Initialize database
    logger.info("Initializing database connection...")
    try:
        db = init_db_manager(config.DATABASE_PATH)
        if not db.check_connection():
            logger.error("Failed to connect to database!")
            sys.exit(1)
        logger.info(f"Connected to {db.get_db_type()} database")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Import and initialize components
    logger.info("Initializing trading components...")
    
    try:
        from trader.clob_trader import ClobTrader
        from scraper.polymarket_scraper import PolymarketScraper
        from scraper.activity_scraper import ActivityScraper
        
        # Initialize trader
        trader = ClobTrader(
            api_key=config.POLYMARKET_API_KEY,
            secret=config.POLYMARKET_SECRET,
            passphrase=config.POLYMARKET_PASSPHRASE
        )
        
        if not trader.client:
            logger.error("Failed to initialize CLOB trader!")
            sys.exit(1)
        
        logger.info("CLOB Trader initialized successfully")
        
        # Initialize scraper with proxy support
        scraper = PolymarketScraper(target_username=config.TARGET_USERNAME)
        
        # Initialize activity scraper
        activity_scraper = ActivityScraper(
            target_username=config.TARGET_USERNAME,
            target_url=config.TARGET_USER_URL
        )
        
        logger.info("Starting bot main loop...")
        logger.info(f"Target: {config.TARGET_USERNAME}")
        logger.info(f"Max Trade: ${config.MAX_TRADE_AMOUNT_USDC}")
        logger.info(f"Trade %: {config.TRADE_PERCENTAGE}%")
        logger.info(f"Dry Run: {config.DRY_RUN}")
        logger.info("=" * 60)
        
        # Main loop
        loop_count = 0
        while running:
            try:
                loop_count += 1
                logger.debug(f"Bot loop iteration {loop_count}")
                
                # Scrape for new trades
                new_trades = activity_scraper.check_for_new_trades()
                
                if new_trades:
                    logger.info(f"Found {len(new_trades)} new trades to process")
                    
                    for trade_data in new_trades:
                        if not running:
                            break
                        
                        logger.info(f"Processing trade: {trade_data.get('side')} {trade_data.get('outcome')} - ${trade_data.get('amount')}")
                        
                        if not config.DRY_RUN:
                            try:
                                # Execute trade via CLOB
                                result = trader.execute_trade(trade_data)
                                if result:
                                    logger.info(f"Trade executed successfully: {result.get('id', 'unknown')}")
                                else:
                                    logger.warning("Trade execution returned no result")
                            except Exception as e:
                                logger.error(f"Trade execution failed: {e}")
                        else:
                            logger.info("DRY RUN - Trade not executed")
                
                # Sleep until next poll
                import time
                time.sleep(config.POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                time.sleep(config.POLL_INTERVAL)
        
        logger.info("Bot shutdown complete")
        
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        logger.error("Make sure all dependencies are installed: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
