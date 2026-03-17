"""
Proxy Configuration for PM Bot
Supports HTTP/HTTPS proxies for external API calls
"""
import os

# Proxy Settings from environment
USE_PROXY = os.getenv('USE_PROXY', 'false').lower() == 'true'
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = os.getenv('PROXY_PORT', '')
PROXY_USER = os.getenv('PROXY_USERNAME', '')
PROXY_PASS = os.getenv('PROXY_PASSWORD', '')


def get_proxy_dict() -> dict:
    """
    Get proxy configuration as dict for requests library
    
    Returns:
        dict with 'http' and 'https' proxy URLs, or empty dict if proxy disabled
    """
    if not USE_PROXY or not PROXY_HOST or not PROXY_PORT:
        return {}
    
    # Build proxy URL with authentication if provided
    if PROXY_USER and PROXY_PASS:
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    else:
        proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
    
    return {
        'http': proxy_url,
        'https': proxy_url
    }


def get_proxy_url() -> str:
    """
    Get proxy URL as string
    
    Returns:
        Proxy URL string or empty string if proxy disabled
    """
    if not USE_PROXY or not PROXY_HOST or not PROXY_PORT:
        return ''
    
    if PROXY_USER and PROXY_PASS:
        return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
    else:
        return f"http://{PROXY_HOST}:{PROXY_PORT}"


def validate_proxy_config() -> list:
    """
    Validate proxy configuration
    
    Returns:
        List of error messages, empty if valid
    """
    errors = []
    
    if USE_PROXY:
        if not PROXY_HOST:
            errors.append("PROXY_HOST is required when USE_PROXY=true")
        if not PROXY_PORT:
            errors.append("PROXY_PORT is required when USE_PROXY=true")
        
        # Validate port is numeric
        if PROXY_PORT:
            try:
                int(PROXY_PORT)
            except ValueError:
                errors.append("PROXY_PORT must be a valid port number")
    
    return errors
