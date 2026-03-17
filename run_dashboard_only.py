#!/usr/bin/env python3
"""
Run Dashboard Only
For separated architecture where bot runs on a different host (e.g., VPS with proxy)
Dashboard is stateless and communicates via database
"""
import os
import sys
import logging
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from config import config
from config.network_config import validate_network_config, get_connection_info, DASHBOARD_HOST, DASHBOARD_PORT
from database.db import init_db_manager

# Setup logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for dashboard-only mode"""
    logger.info("=" * 60)
    logger.info("PM Bot - Dashboard Only Mode")
    logger.info("=" * 60)
    
    # Validate configuration
    network_errors = validate_network_config()
    if network_errors:
        logger.error("Network configuration errors:")
        for error in network_errors:
            logger.error(f"  - {error}")
        sys.exit(1)
    
    # Log configuration
    db_info = get_connection_info()
    logger.info(f"Database: {db_info['type']} at {db_info.get('host') or db_info.get('path')}")
    logger.info(f"Dashboard: http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
    
    # Check if using remote database
    if db_info['type'] == 'PostgreSQL':
        logger.info("Using remote PostgreSQL database - dashboard is stateless")
    else:
        logger.warning("Using local SQLite database - ensure database file is accessible")
    
    # Initialize database
    logger.info("Initializing database connection...")
    try:
        db = init_db_manager(config.DATABASE_PATH)
        if not db.check_connection():
            logger.error("Failed to connect to database!")
            sys.exit(1)
        logger.info(f"Connected to {db.get_db_type()} database successfully")
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        sys.exit(1)
    
    # Start dashboard
    logger.info("Starting dashboard server...")
    try:
        from dashboard.app import run_dashboard
        
        logger.info("=" * 60)
        logger.info(f"Dashboard ready at http://{DASHBOARD_HOST}:{DASHBOARD_PORT}")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)
        
        run_dashboard(
            host=DASHBOARD_HOST,
            port=DASHBOARD_PORT,
            debug=False
        )
        
    except ImportError as e:
        logger.error(f"Failed to import dashboard: {e}")
        logger.error("Make sure Flask is installed: pip install flask flask-socketio")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Dashboard error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
