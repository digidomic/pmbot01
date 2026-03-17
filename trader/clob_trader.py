"""
CLOB Trader - Polymarket trade execution via CLOB client
"""
import logging
import time
from datetime import datetime
from typing import Optional

# Import CLOB client
try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, OrderArgs
    CLOB_AVAILABLE = True
except ImportError:
    CLOB_AVAILABLE = False
    logging.warning("py-clob-client not installed. Trading functionality will be disabled.")

from config import config
from database.db import TradeDatabase, Trade

logger = logging.getLogger(__name__)


class ClobTrader:
    """Executes trades via Polymarket CLOB"""
    
    def __init__(self, db: TradeDatabase):
        self.db = db
        self.client: Optional[ClobClient] = None
        self.api_creds: Optional[ApiCreds] = None
        self.initialized = False
        
        if CLOB_AVAILABLE:
            self._init_client()
    
    def _init_client(self):
        """Initialize CLOB client with credentials"""
        try:
            # Chain ID for Polygon (Polymarket)
            chain_id = 137
            
            # Create API credentials
            self.api_creds = ApiCreds(
                api_key=config.POLYMARKET_API_KEY,
                api_secret=config.POLYMARKET_SECRET,
                api_passphrase=config.POLYMARKET_PASSPHRASE
            )
            
            # Initialize client
            self.client = ClobClient(
                host="https://clob.polymarket.com",
                chain_id=chain_id,
                creds=self.api_creds
            )
            
            # Test connection by getting API keys
            self.client.get_api_keys()
            
            self.initialized = True
            logger.info("CLOB client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize CLOB client: {e}")
            self.initialized = False
    
    def calculate_trade_amount(self, original_amount: float) -> float:
        """
        Calculate the amount to trade based on config
        Returns the smaller of:
        - Percentage of original trade
        - Maximum allowed amount
        """
        # Calculate percentage amount
        percent_amount = original_amount * (config.TRADE_PERCENTAGE / 100)
        
        # Take the smaller value
        trade_amount = min(percent_amount, config.MAX_TRADE_AMOUNT_USDC)
        
        # Round to 2 decimal places
        return round(trade_amount, 2)
    
    def execute_trade(self, trade: Trade) -> tuple[bool, Optional[str]]:
        """
        Execute a copy trade
        Returns (success, error_message)
        """
        if not self.initialized:
            error = "CLOB client not initialized"
            logger.error(error)
            self.db.update_trade_status(trade.trade_id, 'failed', error)
            return False, error
        
        try:
            logger.info(f"Executing trade: {trade.market_slug} {trade.side} {trade.outcome}")
            
            # Calculate trade amount
            trade_amount = self.calculate_trade_amount(trade.original_amount)
            trade.copied_amount = trade_amount
            
            if trade_amount < 1:  # Minimum trade size
                error = f"Trade amount too small: {trade_amount} USDC"
                logger.warning(error)
                self.db.update_trade_status(trade.trade_id, 'failed', error)
                return False, error
            
            # Get market info - we need the condition_id and token_id
            # This is simplified - actual implementation needs proper market lookup
            logger.info(f"Would execute: {trade_amount} USDC on {trade.market_question}")
            
            # Note: Actual order creation requires:
            # 1. Get market condition_id from slug
            # 2. Get token_id for the outcome (YES/NO)
            # 3. Create and sign order
            # 4. Submit to CLOB
            
            # For now, simulate the trade
            # TODO: Implement actual order creation once market resolution is working
            
            copied_timestamp = datetime.now()
            latency = (copied_timestamp - trade.original_timestamp).total_seconds() if trade.original_timestamp else 0
            
            trade.copied_timestamp = copied_timestamp
            trade.latency_seconds = latency
            trade.status = 'executed'
            
            self.db.save_trade(trade)
            
            logger.info(f"Trade executed successfully: {trade.trade_id} (latency: {latency:.2f}s)")
            return True, None
            
        except Exception as e:
            error = str(e)
            logger.error(f"Trade execution failed: {error}")
            self.db.update_trade_status(trade.trade_id, 'failed', error)
            return False, error
    
    def get_market_info(self, market_slug: str) -> Optional[dict]:
        """Get market information by slug"""
        if not self.initialized:
            return None
        
        try:
            # This would use the CLOB API to get market details
            # For now, return placeholder
            return {
                'slug': market_slug,
                'condition_id': None,  # Would be populated from API
                'tokens': []
            }
        except Exception as e:
            logger.error(f"Failed to get market info: {e}")
            return None
    
    def get_balance(self) -> dict:
        """Get USDC balance"""
        if not self.initialized:
            return {'usdc': 0, 'error': 'Client not initialized'}
        
        try:
            # Get balance from CLOB
            # This is a placeholder - actual implementation would query the API
            return {
                'usdc': 0,
                'locked': 0
            }
        except Exception as e:
            logger.error(f"Failed to get balance: {e}")
            return {'usdc': 0, 'error': str(e)}
