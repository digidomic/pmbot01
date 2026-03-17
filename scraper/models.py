"""
SQLAlchemy ORM Models for Polymarket Copy Trading Bot
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, DateTime, 
    Boolean, Text, Index, UniqueConstraint
)
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()


class Trade(Base):
    """
    SQLAlchemy Model for scraped trades from target user.
    Tracks both the original trade and our copy of it.
    """
    __tablename__ = 'trades'
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Source Trade Identification
    source_trade_id = Column(String(255), unique=True, nullable=False, index=True)
    """Einzigartige ID vom Scraping (z.B. Transaction Hash oder Activity ID)"""
    
    # Trader Info
    trader_address = Column(String(42), nullable=False, index=True)
    """Die Wallet-Adresse des Traders (z.B. 0x8dxd)"""
    
    # Market Info
    market_slug = Column(String(255), nullable=True)
    """URL-Slug des Marktes"""
    market_id = Column(String(66), nullable=True)
    """Contract Address oder Market ID"""
    market_name = Column(Text, nullable=False)
    """Name/Frage des Marktes"""
    
    # Trade Details
    outcome = Column(String(50), nullable=False)
    """YES, NO oder spezifische Option"""
    side = Column(String(10), nullable=False)
    """BUY oder SELL"""
    amount_usdc = Column(Float, nullable=False)
    """Betrag in USDC"""
    price = Column(Float, nullable=True, default=0.0)
    """Preis pro Share"""
    
    # Timestamps
    timestamp = Column(DateTime, nullable=False, index=True)
    """Zeitstempel des Original-Trades"""
    tx_hash = Column(String(66), nullable=True)
    """Blockchain Transaction Hash"""
    
    # Detection Tracking
    detected_at = Column(DateTime, server_default=func.now(), nullable=False)
    """Wann wir den Trade entdeckt haben"""
    
    # Copy Tracking
    copied = Column(Boolean, default=False, nullable=False, index=True)
    """Wurde dieser Trade bereits kopiert?"""
    copied_at = Column(DateTime, nullable=True)
    """Wann wir den Trade kopiert haben"""
    our_trade_id = Column(String(255), nullable=True)
    """Referenz zu unserem eigenen Trade (z.B. Order ID)"""
    our_trade_status = Column(String(50), default='pending')
    """Status unseres Trades: pending, executed, failed"""
    our_trade_error = Column(Text, nullable=True)
    """Fehlermeldung falls unser Trade fehlgeschlagen ist"""
    
    # PnL Tracking (für kopierten Trade)
    pnl_usdc = Column(Float, nullable=True)
    """Profit/Loss des kopierten Trades"""
    
    # Metadata
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    # Table Constraints
    __table_args__ = (
        Index('idx_trades_trader_copied', 'trader_address', 'copied'),
        Index('idx_trades_detected_at', 'detected_at'),
        Index('idx_trades_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return (
            f"<Trade(id={self.id}, source_trade_id={self.source_trade_id}, "
            f"market={self.market_name[:30]}..., side={self.side}, "
            f"amount={self.amount_usdc} USDC, copied={self.copied})>"
        )
    
    def to_dict(self) -> dict:
        """Convert trade to dictionary"""
        return {
            'id': self.id,
            'source_trade_id': self.source_trade_id,
            'trader_address': self.trader_address,
            'market_slug': self.market_slug,
            'market_id': self.market_id,
            'market_name': self.market_name,
            'outcome': self.outcome,
            'side': self.side,
            'amount_usdc': self.amount_usdc,
            'price': self.price,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'tx_hash': self.tx_hash,
            'detected_at': self.detected_at.isoformat() if self.detected_at else None,
            'copied': self.copied,
            'copied_at': self.copied_at.isoformat() if self.copied_at else None,
            'our_trade_id': self.our_trade_id,
            'our_trade_status': self.our_trade_status,
            'pnl_usdc': self.pnl_usdc,
        }


class ScraperState(Base):
    """
    Speichert den Zustand des Scrapers (z.B. letzter erfolgreicher Run)
    """
    __tablename__ = 'scraper_state'
    
    id = Column(Integer, primary_key=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<ScraperState(key={self.key}, value={self.value[:50]}...)>"


class ScrapingLog(Base):
    """
    Log-Einträge für Scraping-Versuche
    """
    __tablename__ = 'scraping_logs'
    
    id = Column(Integer, primary_key=True)
    run_at = Column(DateTime, server_default=func.now())
    success = Column(Boolean, default=False)
    trades_found = Column(Integer, default=0)
    new_trades = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    def __repr__(self):
        return (
            f"<ScrapingLog(run_at={self.run_at}, success={self.success}, "
            f"trades_found={self.trades_found}, new_trades={self.new_trades})>"
        )
