"""
Database initialization and session management using SQLAlchemy
"""
import logging
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from scraper.models import Base, Trade, ScraperState, ScrapingLog

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database connections, sessions, and initialization.
    Uses SQLAlchemy ORM for all database operations.
    """
    
    def __init__(self, db_path: str = "database/trades.db"):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create engine with SQLite optimizations
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,  # Set to True for debugging SQL
            connect_args={
                "check_same_thread": False,  # Allow multi-threading
            },
            pool_pre_ping=True,  # Verify connections before using
            pool_recycle=300,  # Recycle connections after 5 minutes
        )
        
        # Enable foreign keys and WAL mode for better concurrency
        self._setup_sqlite_pragmas()
        
        # Create session factory
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
        
        # Initialize tables
        self.init_db()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def _setup_sqlite_pragmas(self):
        """Configure SQLite pragmas for better performance"""
        
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragmas(dbapi_conn, connection_record):
            """Set SQLite pragmas on each connection"""
            cursor = dbapi_conn.cursor()
            # Enable foreign key support
            cursor.execute("PRAGMA foreign_keys=ON")
            # Use WAL mode for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            # Synchronous mode NORMAL for performance/safety balance
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Cache size (negative value = KB)
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.close()
    
    def init_db(self):
        """Create all tables if they don't exist"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database tables created/verified")
        except SQLAlchemyError as e:
            logger.error(f"Failed to initialize database: {e}")
            raise
    
    @contextmanager
    def get_session(self) -> Session:
        """
        Context manager for database sessions.
        
        Usage:
            with db.get_session() as session:
                trade = session.query(Trade).first()
        
        Yields:
            SQLAlchemy Session object
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
    
    def get_session_factory(self) -> sessionmaker:
        """
        Get the session factory for manual session management.
        
        Returns:
            sessionmaker instance
        """
        return self.SessionLocal
    
    def get_engine(self):
        """Get the SQLAlchemy engine"""
        return self.engine
    
    def check_connection(self) -> bool:
        """
        Test database connection
        
        Returns:
            True if connection is working
        """
        try:
            with self.get_session() as session:
                session.execute("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def get_stats(self) -> dict:
        """
        Get database statistics
        
        Returns:
            Dictionary with trade statistics
        """
        with self.get_session() as session:
            total_trades = session.query(Trade).count()
            copied_trades = session.query(Trade).filter(Trade.copied == True).count()
            pending_trades = session.query(Trade).filter(
                Trade.copied == False
            ).count()
            
            # Get total volume
            from sqlalchemy import func
            total_volume = session.query(func.sum(Trade.amount_usdc)).scalar() or 0
            copied_volume = session.query(func.sum(Trade.amount_usdc)).filter(
                Trade.copied == True
            ).scalar() or 0
            
            return {
                'total_trades': total_trades,
                'copied_trades': copied_trades,
                'pending_trades': pending_trades,
                'total_volume_usdc': round(total_volume, 2),
                'copied_volume_usdc': round(copied_volume, 2),
            }
    
    def reset_database(self, confirm: bool = False):
        """
        DROP ALL TABLES - USE WITH CAUTION!
        
        Args:
            confirm: Must be True to actually drop tables
        """
        if not confirm:
            logger.warning("Database reset skipped - confirm=False")
            return
        
        logger.warning("Dropping all tables!")
        Base.metadata.drop_all(bind=self.engine)
        self.init_db()
        logger.info("Database reset complete")


# Global instance for convenience
db_manager = None


def init_db_manager(db_path: str = "database/trades.db") -> DatabaseManager:
    """
    Initialize the global database manager
    
    Args:
        db_path: Path to SQLite database
        
    Returns:
        DatabaseManager instance
    """
    global db_manager
    db_manager = DatabaseManager(db_path)
    return db_manager


def get_db() -> DatabaseManager:
    """
    Get the global database manager instance.
    Must call init_db_manager() first!
    
    Returns:
        DatabaseManager instance
    """
    if db_manager is None:
        raise RuntimeError("Database manager not initialized. Call init_db_manager() first.")
    return db_manager
