"""
Network Configuration for PM Bot
Supports separated Dashboard/Bot architecture with remote database
"""
import os

# Database Connection (supports remote PostgreSQL or local SQLite)
DB_TYPE = os.getenv('DB_TYPE', 'sqlite').lower()  # 'sqlite' or 'postgresql'
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5432')
DB_NAME = os.getenv('DB_NAME', 'pmbot')
DB_USER = os.getenv('DB_USER', 'pmbot')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_PATH = os.getenv('DATABASE_PATH', 'database/trades.db')  # For SQLite

# Dashboard Settings
DASHBOARD_HOST = os.getenv('DASHBOARD_HOST', '0.0.0.0')
DASHBOARD_PORT = int(os.getenv('DASHBOARD_PORT', '8080'))

# Bot Settings (for remote bot configuration)
BOT_HOST = os.getenv('BOT_HOST', '0.0.0.0')
BOT_API_PORT = int(os.getenv('BOT_API_PORT', '8081'))


def get_database_url() -> str:
    """
    Get database connection URL based on DB_TYPE
    
    Returns:
        SQLAlchemy compatible database URL
    """
    if DB_TYPE == 'postgresql':
        return f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    else:
        # SQLite - ensure path is absolute for Docker compatibility
        if not os.path.isabs(DB_PATH):
            # If relative path, make it relative to current working directory
            return f"sqlite:///{DB_PATH}"
        return f"sqlite:///{DB_PATH}"


def get_database_engine_options() -> dict:
    """
    Get SQLAlchemy engine options based on database type
    
    Returns:
        dict of engine options for create_engine()
    """
    if DB_TYPE == 'postgresql':
        return {
            'pool_pre_ping': True,
            'pool_recycle': 300,
            'pool_size': 10,
            'max_overflow': 20,
        }
    else:
        # SQLite options
        return {
            'connect_args': {
                "check_same_thread": False,
            },
            'pool_pre_ping': True,
            'pool_recycle': 300,
        }


def is_remote_database() -> bool:
    """
    Check if using a remote database (PostgreSQL)
    
    Returns:
        True if using PostgreSQL, False for SQLite
    """
    return DB_TYPE == 'postgresql'


def validate_network_config() -> list:
    """
    Validate network configuration
    
    Returns:
        List of error messages, empty if valid
    """
    errors = []
    
    if DB_TYPE == 'postgresql':
        if not DB_HOST:
            errors.append("DB_HOST is required when DB_TYPE=postgresql")
        if not DB_PORT:
            errors.append("DB_PORT is required when DB_TYPE=postgresql")
        if not DB_NAME:
            errors.append("DB_NAME is required when DB_TYPE=postgresql")
        if not DB_USER:
            errors.append("DB_USER is required when DB_TYPE=postgresql")
        if not DB_PASSWORD:
            errors.append("DB_PASSWORD is required when DB_TYPE=postgresql")
        
        # Validate port
        try:
            int(DB_PORT)
        except ValueError:
            errors.append("DB_PORT must be a valid port number")
    
    # Validate dashboard port
    try:
        int(DASHBOARD_PORT)
    except ValueError:
        errors.append("DASHBOARD_PORT must be a valid port number")
    
    return errors


def get_connection_info() -> dict:
    """
    Get human-readable connection info
    
    Returns:
        dict with connection details (safe for logging, no passwords)
    """
    if DB_TYPE == 'postgresql':
        return {
            'type': 'PostgreSQL',
            'host': DB_HOST,
            'port': DB_PORT,
            'database': DB_NAME,
            'user': DB_USER,
        }
    else:
        return {
            'type': 'SQLite',
            'path': DB_PATH,
        }
