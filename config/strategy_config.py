"""
Configuration for Bitcoin Arbitrage Strategy
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


@dataclass
class ArbitrageConfig:
    """Bitcoin Arbitrage Strategy Configuration"""
    
    # Coinbase WebSocket
    COINBASE_WS_URL: str = os.getenv('COINBASE_WS_URL', 'wss://ws-feed.exchange.coinbase.com')
    COINBASE_PRODUCT_ID: str = os.getenv('COINBASE_PRODUCT_ID', 'BTC-USD')
    
    # Arbitrage Thresholds
    ARBITRAGE_THRESHOLD: float = float(os.getenv('ARBITRAGE_THRESHOLD', '0.001'))  # 0.1% = 0.001
    PRICE_HISTORY_SIZE: int = int(os.getenv('PRICE_HISTORY_SIZE', '100'))  # Anzahl der Preis-Punkte im Cache
    
    # Position Management
    MAX_POSITION_SIZE: float = float(os.getenv('MAX_POSITION_SIZE', '50'))  # Max 50 USDC pro Position
    MIN_POSITION_SIZE: float = float(os.getenv('MIN_POSITION_SIZE', '5'))   # Min 5 USDC pro Position
    
    # Profit Targets & Stop Loss
    PROFIT_TARGET: float = float(os.getenv('PROFIT_TARGET', '0.02'))  # 2% Profit Target
    STOP_LOSS: float = float(os.getenv('STOP_LOSS', '0.01'))  # 1% Stop Loss
    STOP_LOSS_TIMEOUT: int = int(os.getenv('STOP_LOSS_TIMEOUT', '300'))  # 5 Minuten Timeout
    
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
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
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
        
        return errors


# Global config instance
arbitrage_config = ArbitrageConfig()
