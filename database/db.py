"""
SQLite database management for trade tracking
"""
import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class Trade:
    """Represents a trade"""
    id: Optional[int] = None
    trade_id: str = ""
    market_slug: str = ""
    market_question: str = ""
    side: str = ""  # BUY or SELL
    outcome: str = ""  # YES or NO
    original_amount: float = 0.0
    copied_amount: float = 0.0
    price: float = 0.0
    timestamp: Optional[datetime] = None
    original_timestamp: Optional[datetime] = None
    copied_timestamp: Optional[datetime] = None
    latency_seconds: float = 0.0
    status: str = "pending"  # pending, executed, failed
    pnl: Optional[float] = None
    error_message: Optional[str] = None
    is_target_trade: bool = True  # True if from target user, False if our copy


class TradeDatabase:
    """Manages trade data in SQLite"""
    
    def __init__(self, db_path: str = "database/trades.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_db(self):
        """Initialize database tables"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT UNIQUE,
                    market_slug TEXT,
                    market_question TEXT,
                    side TEXT,
                    outcome TEXT,
                    original_amount REAL,
                    copied_amount REAL,
                    price REAL,
                    timestamp TEXT,
                    original_timestamp TEXT,
                    copied_timestamp TEXT,
                    latency_seconds REAL DEFAULT 0,
                    status TEXT DEFAULT 'pending',
                    pnl REAL,
                    error_message TEXT,
                    is_target_trade INTEGER DEFAULT 1,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_trade_id ON trades(trade_id)
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON trades(timestamp)
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def save_trade(self, trade: Trade) -> bool:
        """Save or update a trade"""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO trades (
                        trade_id, market_slug, market_question, side, outcome,
                        original_amount, copied_amount, price, timestamp,
                        original_timestamp, copied_timestamp, latency_seconds,
                        status, pnl, error_message, is_target_trade
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade.trade_id, trade.market_slug, trade.market_question,
                    trade.side, trade.outcome, trade.original_amount,
                    trade.copied_amount, trade.price,
                    trade.timestamp.isoformat() if trade.timestamp else None,
                    trade.original_timestamp.isoformat() if trade.original_timestamp else None,
                    trade.copied_timestamp.isoformat() if trade.copied_timestamp else None,
                    trade.latency_seconds, trade.status, trade.pnl,
                    trade.error_message, 1 if trade.is_target_trade else 0
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving trade: {e}")
            return False
    
    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get a trade by ID"""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM trades WHERE trade_id = ?",
                (trade_id,)
            ).fetchone()
            
            if row:
                return self._row_to_trade(row)
            return None
    
    def get_recent_trades(self, limit: int = 20, is_target: bool = True) -> list[Trade]:
        """Get recent trades"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM trades 
                WHERE is_target_trade = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (1 if is_target else 0, limit)).fetchall()
            
            return [self._row_to_trade(row) for row in rows]
    
    def get_all_trades(self, limit: int = 100) -> list[Trade]:
        """Get all trades ordered by timestamp"""
        with self._get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM trades 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            
            return [self._row_to_trade(row) for row in rows]
    
    def update_trade_status(self, trade_id: str, status: str, 
                           error_message: Optional[str] = None,
                           copied_timestamp: Optional[datetime] = None):
        """Update trade status"""
        with self._get_connection() as conn:
            if copied_timestamp:
                conn.execute("""
                    UPDATE trades 
                    SET status = ?, error_message = ?, copied_timestamp = ?
                    WHERE trade_id = ?
                """, (status, error_message, copied_timestamp.isoformat(), trade_id))
            else:
                conn.execute("""
                    UPDATE trades 
                    SET status = ?, error_message = ?
                    WHERE trade_id = ?
                """, (status, error_message, trade_id))
            conn.commit()
    
    def get_stats(self) -> dict:
        """Get trading statistics"""
        with self._get_connection() as conn:
            # Total trades
            total = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE is_target_trade = 0"
            ).fetchone()[0]
            
            # Executed trades
            executed = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE is_target_trade = 0 AND status = 'executed'"
            ).fetchone()[0]
            
            # Failed trades
            failed = conn.execute(
                "SELECT COUNT(*) FROM trades WHERE is_target_trade = 0 AND status = 'failed'"
            ).fetchone()[0]
            
            # Total volume
            volume = conn.execute(
                "SELECT COALESCE(SUM(copied_amount), 0) FROM trades WHERE is_target_trade = 0"
            ).fetchone()[0]
            
            # Average latency
            latency = conn.execute(
                "SELECT COALESCE(AVG(latency_seconds), 0) FROM trades WHERE is_target_trade = 0 AND latency_seconds > 0"
            ).fetchone()[0]
            
            # Total PnL
            pnl = conn.execute(
                "SELECT COALESCE(SUM(pnl), 0) FROM trades WHERE is_target_trade = 0"
            ).fetchone()[0]
            
            return {
                'total_trades': total,
                'executed': executed,
                'failed': failed,
                'total_volume_usdc': round(volume, 2),
                'avg_latency_seconds': round(latency, 2),
                'total_pnl': round(pnl, 2) if pnl else 0
            }
    
    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Convert database row to Trade object"""
        def parse_dt(dt_str):
            if dt_str:
                try:
                    return datetime.fromisoformat(dt_str)
                except:
                    return None
            return None
        
        return Trade(
            id=row['id'],
            trade_id=row['trade_id'],
            market_slug=row['market_slug'] or '',
            market_question=row['market_question'] or '',
            side=row['side'] or '',
            outcome=row['outcome'] or '',
            original_amount=row['original_amount'] or 0,
            copied_amount=row['copied_amount'] or 0,
            price=row['price'] or 0,
            timestamp=parse_dt(row['timestamp']),
            original_timestamp=parse_dt(row['original_timestamp']),
            copied_timestamp=parse_dt(row['copied_timestamp']),
            latency_seconds=row['latency_seconds'] or 0,
            status=row['status'] or 'pending',
            pnl=row['pnl'],
            error_message=row['error_message'],
            is_target_trade=bool(row['is_target_trade'])
        )
