"""
Configuration for Bitcoin Arbitrage Strategy
"""
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


@dataclass
class ArbitrageConfig:
    """Bitcoin Arbitrage Strategy Configuration"""
    
    # Market Type: "updown_5m" oder "updown_15m"
    MARKET_TYPE: str = os.getenv('MARKET_TYPE', 'updown_5m')
    
    # Market Resolver Settings
    MARKET_RESOLVER_ENABLED: bool = os.getenv('MARKET_RESOLVER_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    MARKET_RESOLVER_INTERVAL: int = int(os.getenv('MARKET_RESOLVER_INTERVAL', '60'))  # Seconds between checks
    
    # Polymarket Condition IDs für Up/Down Märkte (FALLBACK values)
    # These are used when market resolver fails or is disabled
    # 5m Market: https://polymarket.com/event/btc-updown-5m-...
    UPDOWN_5M_CONDITION_ID: str = os.getenv('UPDOWN_5M_CONDITION_ID', '0x8bebabda22b19d30df59c9e63f3f730f0f4bb32e3c6669522cf549863f85be1d')
    # 15m Market: https://polymarket.com/event/btc-updown-15m-...
    UPDOWN_15M_CONDITION_ID: str = os.getenv('UPDOWN_15M_CONDITION_ID', '0x0a29940b17ba72bc8eb2a5534445bb18eb126a3d6e0c8e06de5e74da97c3480d')
    
    # Market Slugs (FALLBACK values)
    UPDOWN_5M_SLUG: str = os.getenv('UPDOWN_5M_SLUG', 'btc-updown-5m-1773835200')
    UPDOWN_15M_SLUG: str = os.getenv('UPDOWN_15M_SLUG', 'btc-updown-15m-1773835200')
    
    # Coinbase WebSocket
    COINBASE_WS_URL: str = os.getenv('COINBASE_WS_URL', 'wss://ws-feed.exchange.coinbase.com')
    COINBASE_PRODUCT_ID: str = os.getenv('COINBASE_PRODUCT_ID', 'BTC-USD')
    
    # Arbitrage Thresholds
    ARBITRAGE_THRESHOLD: float = float(os.getenv('ARBITRAGE_THRESHOLD', '0.0005'))  # 0.05% = für kurzfristige Märkte empfohlen
    PRICE_HISTORY_SIZE: int = int(os.getenv('PRICE_HISTORY_SIZE', '100'))  # Anzahl der Preis-Punkte im Cache
    
    # Position Management
    MAX_POSITION_SIZE: float = float(os.getenv('MAX_POSITION_SIZE', '50'))  # Max 50 USDC pro Position
    MIN_POSITION_SIZE: float = float(os.getenv('MIN_POSITION_SIZE', '5'))   # Min 5 USDC pro Position
    
    # Profit Targets & Stop Loss (für kurzfristige Märkte weniger relevant, da automatisch ausgezahlt)
    PROFIT_TARGET: float = float(os.getenv('PROFIT_TARGET', '0.02'))  # 2% Profit Target
    STOP_LOSS: float = float(os.getenv('STOP_LOSS', '0.01'))  # 1% Stop Loss
    # Für Up/Down Märkte: Max Hold Time = 5 oder 15 Minuten (Markt resolved automatisch)
    STOP_LOSS_TIMEOUT: int = int(os.getenv('STOP_LOSS_TIMEOUT', '360'))  # 6 Minuten (5m Markt + Buffer)
    
    # Trading Settings
    COOLDOWN_SECONDS: int = int(os.getenv('COOLDOWN_SECONDS', '60'))  # Mindestabstand zwischen Trades
    MAX_DAILY_TRADES: int = int(os.getenv('MAX_DAILY_TRADES', '20'))  # Max 20 Trades pro Tag
    
    # Market Filter
    MIN_MARKET_LIQUIDITY: float = float(os.getenv('MIN_MARKET_LIQUIDITY', '10000'))  # Min $10k Liquidity
    MAX_SPREAD: float = float(os.getenv('MAX_SPREAD', '0.02'))  # Max 2% Spread
    
    # WebSocket Settings
    WS_RECONNECT_DELAY: int = int(os.getenv('WS_RECONNECT_DELAY', '5'))  # Sekunden bis Reconnect
    WS_HEARTBEAT_INTERVAL: int = int(os.getenv('WS_HEARTBEAT_INTERVAL', '30'))  # Heartbeat alle 30s
    
    # Logging
    LOG_TRADES: bool = os.getenv('LOG_TRADES', 'true').lower() in ('true', '1', 'yes', 'on')
    VERBOSE_LOGGING: bool = os.getenv('VERBOSE_LOGGING', 'false').lower() in ('true', '1', 'yes', 'on')
    
    def __post_init__(self):
        """Initialize market resolver if enabled"""
        self._market_resolver = None
        self._last_resolver_update = 0
        self._current_condition_id = None
        self._current_market_slug = None
        
        if self.MARKET_RESOLVER_ENABLED:
            try:
                from market_resolver import MarketResolver
                
                market_type = "5m" if self.MARKET_TYPE == 'updown_5m' else "15m"
                self._market_resolver = MarketResolver(
                    market_type=market_type,
                    update_interval=self.MARKET_RESOLVER_INTERVAL
                )
                
                # Set fallback values from config
                if market_type == "5m":
                    self._market_resolver.set_fallback(
                        condition_id=self.UPDOWN_5M_CONDITION_ID,
                        market_slug=self.UPDOWN_5M_SLUG
                    )
                else:
                    self._market_resolver.set_fallback(
                        condition_id=self.UPDOWN_15M_CONDITION_ID,
                        market_slug=self.UPDOWN_15M_SLUG
                    )
                
                # Initial update
                if self._market_resolver.update():
                    market_info = self._market_resolver.get_market_info()
                    if market_info:
                        self._current_condition_id = market_info.condition_id
                        self._current_market_slug = market_info.market_slug
                        logger.info(f"MarketResolver initialized: {market_info.market_slug}")
                else:
                    logger.warning("MarketResolver initial update failed, using fallbacks")
                    self._use_fallback_values()
                    
            except Exception as e:
                logger.error(f"Failed to initialize MarketResolver: {e}")
                self._use_fallback_values()
    
    def _use_fallback_values(self):
        """Set current values to fallback values"""
        if self.MARKET_TYPE == 'updown_5m':
            self._current_condition_id = self.UPDOWN_5M_CONDITION_ID
            self._current_market_slug = self.UPDOWN_5M_SLUG
        else:
            self._current_condition_id = self.UPDOWN_15M_CONDITION_ID
            self._current_market_slug = self.UPDOWN_15M_SLUG
        logger.info(f"Using fallback values: {self._current_market_slug}")
    
    def get_current_condition_id(self) -> str:
        """
        Get current condition ID (dynamic or fallback)
        
        Returns:
            Current active condition ID for the configured market type
        """
        if not self.MARKET_RESOLVER_ENABLED or not self._market_resolver:
            return self._current_condition_id or self.UPDOWN_5M_CONDITION_ID
        
        # Update if needed
        if self._market_resolver.should_update():
            old_id = self._current_condition_id
            
            if self._market_resolver.update():
                market_info = self._market_resolver.get_market_info()
                if market_info:
                    self._current_condition_id = market_info.condition_id
                    
                    # Log if changed
                    if old_id and old_id != self._current_condition_id:
                        logger.info(
                            f"🔄 Condition ID updated: {old_id[:20]}... -> "
                            f"{self._current_condition_id[:20]}..."
                        )
            else:
                logger.warning("MarketResolver update failed, using last known values")
        
        return self._current_condition_id or self.UPDOWN_5M_CONDITION_ID
    
    def get_current_market_slug(self) -> str:
        """
        Get current market slug (dynamic or fallback)
        
        Returns:
            Current active market slug for the configured market type
        """
        if not self.MARKET_RESOLVER_ENABLED or not self._market_resolver:
            return self._current_market_slug or self.UPDOWN_5M_SLUG
        
        # Update if needed (get_condition_id also updates)
        _ = self.get_current_condition_id()
        
        return self._current_market_slug or self.UPDOWN_5M_SLUG
    
    def get_market_resolver_status(self) -> dict:
        """
        Get market resolver status for monitoring
        
        Returns:
            Dict with resolver status info
        """
        if not self._market_resolver:
            return {
                'enabled': self.MARKET_RESOLVER_ENABLED,
                'initialized': False,
                'fresh': False,
                'condition_id': self._current_condition_id,
                'market_slug': self._current_market_slug
            }
        
        return {
            'enabled': self.MARKET_RESOLVER_ENABLED,
            'initialized': True,
            'fresh': self._market_resolver.is_fresh(),
            'last_update': self._market_resolver.get_last_update_time(),
            'condition_id': self._current_condition_id,
            'market_slug': self._current_market_slug
        }
    
    def force_market_refresh(self) -> bool:
        """
        Force immediate refresh of market info
        
        Returns:
            True if refresh was successful
        """
        if not self._market_resolver:
            logger.warning("MarketResolver not available")
            return False
        
        logger.info("Forcing market refresh...")
        
        if self._market_resolver.force_refresh():
            market_info = self._market_resolver.get_market_info()
            if market_info:
                self._current_condition_id = market_info.condition_id
                self._current_market_slug = market_info.market_slug
                logger.info(f"Market refreshed: {market_info.market_slug}")
                return True
        
        logger.error("Market refresh failed")
        return False
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        # Validate market type
        if self.MARKET_TYPE not in ('updown_5m', 'updown_15m'):
            errors.append(f"MARKET_TYPE must be 'updown_5m' or 'updown_15m', got '{self.MARKET_TYPE}'")
        
        if self.ARBITRAGE_THRESHOLD <= 0:
            errors.append("ARBITRAGE_THRESHOLD must be positive")
        if self.ARBITRAGE_THRESHOLD > 0.1:
            errors.append("ARBITRAGE_THRESHOLD seems too high (>10%)")
        
        if self.MAX_POSITION_SIZE <= 0:
            errors.append("MAX_POSITION_SIZE must be positive")
        if self.MIN_POSITION_SIZE < 1:
            errors.append("MIN_POSITION_SIZE must be at least 1 USDC")
        if self.MIN_POSITION_SIZE >= self.MAX_POSITION_SIZE:
            errors.append("MIN_POSITION_SIZE must be less than MAX_POSITION_SIZE")
        
        if self.PROFIT_TARGET <= 0:
            errors.append("PROFIT_TARGET must be positive")
        if self.STOP_LOSS <= 0:
            errors.append("STOP_LOSS must be positive")
        
        if self.COOLDOWN_SECONDS < 10:
            errors.append("COOLDOWN_SECONDS should be at least 10 seconds")
        
        if self.MARKET_RESOLVER_INTERVAL < 30:
            errors.append("MARKET_RESOLVER_INTERVAL should be at least 30 seconds")
        
        return errors


# Global config instance
arbitrage_config = ArbitrageConfig()


# Convenience functions
def get_current_condition_id() -> str:
    """Get current condition ID from global config"""
    return arbitrage_config.get_current_condition_id()


def get_current_market_slug() -> str:
    """Get current market slug from global config"""
    return arbitrage_config.get_current_market_slug()
