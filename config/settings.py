"""
Configuration management for PM Bot
"""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=env_path)


@dataclass
class Config:
    """Application configuration"""
    # Polymarket API
    POLYMARKET_API_KEY: str = os.getenv('POLYMARKET_API_KEY', '')
    POLYMARKET_SECRET: str = os.getenv('POLYMARKET_SECRET', '')
    POLYMARKET_PASSPHRASE: str = os.getenv('POLYMARKET_PASSPHRASE', '')
    
    # Target User
    TARGET_USER_URL: str = os.getenv('TARGET_USER_URL', 'https://polymarket.com/profile/@0x8dxd')
    TARGET_USERNAME: str = os.getenv('TARGET_USERNAME', '0x8dxd')
    
    # Trading Settings
    MAX_TRADE_AMOUNT_USDC: float = float(os.getenv('MAX_TRADE_AMOUNT_USDC', '50'))
    TRADE_PERCENTAGE: float = float(os.getenv('TRADE_PERCENTAGE', '10'))
    MAX_TRADES_TO_TRACK: int = int(os.getenv('MAX_TRADES_TO_TRACK', '20'))
    DAILY_SPENDING_LIMIT_USDC: float = float(os.getenv('DAILY_SPENDING_LIMIT_USDC', '250'))
    DRY_RUN: bool = os.getenv('DRY_RUN', 'true').lower() in ('true', '1', 'yes', 'on')
    
    # Dashboard
    DASHBOARD_HOST: str = os.getenv('DASHBOARD_HOST', '0.0.0.0')
    DASHBOARD_PORT: int = int(os.getenv('DASHBOARD_PORT', '8080'))
    
    # Database
    DATABASE_PATH: str = os.getenv('DATABASE_PATH', 'database/trades.db')
    
    # Logging
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # Polling
    POLL_INTERVAL: int = int(os.getenv('POLL_INTERVAL', '30'))
    
    def validate(self) -> list[str]:
        """Validate configuration and return list of errors"""
        errors = []
        
        if not self.POLYMARKET_API_KEY or self.POLYMARKET_API_KEY == 'your_api_key_here':
            errors.append("POLYMARKET_API_KEY not configured")
        if not self.POLYMARKET_SECRET or self.POLYMARKET_SECRET == 'your_secret_here':
            errors.append("POLYMARKET_SECRET not configured")
        if not self.POLYMARKET_PASSPHRASE or self.POLYMARKET_PASSPHRASE == 'your_passphrase_here':
            errors.append("POLYMARKET_PASSPHRASE not configured")

        if not self.TARGET_USERNAME or self.TARGET_USERNAME in ['0x', 'unknown']:
            errors.append("TARGET_USERNAME must be a valid Polymarket username")

        if self.MAX_TRADE_AMOUNT_USDC <= 0:
            errors.append("MAX_TRADE_AMOUNT_USDC must be positive")
        if not (0 < self.TRADE_PERCENTAGE <= 100):
            errors.append("TRADE_PERCENTAGE must be between 0 and 100")

        # Check database path
        if not self.DATABASE_PATH:
            errors.append("DATABASE_PATH is not set")

        return errors


# Global config instance
config = Config()
